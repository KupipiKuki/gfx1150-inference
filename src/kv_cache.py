"""
Grouped-Query Attention (GQA) KV Cache Manager (`KVCacheManager`) for gfx1150-inference.

Supports three storage backends for 7B–70B models:
1. **GPU-resident pool (default)**: Pre-allocated device/GTT memory (`kv_cache_init` /
   `gqa_attention_cached`) addressed by `(layer_idx, start_pos)` with zero host copies.
   Note: The device KV pool is a process-wide singleton (single active GPU-resident
   `KVCacheManager` at a time, single-threaded execution).
2. **CPU-offloaded pool (`offload_to_cpu=True`)**: Pre-allocated host `np.float16` buffers
   updated in-place without slice allocations, keeping persistent GPU pool memory at 0 bytes
   (trades per-step H2D KV bandwidth for reduced GPU memory footprint on long contexts).
3. **SSD `mmap`-offloaded pool (`mmap_dir=...`)**: Disk-backed `np.memmap` KV cache for
   ultra-long context research runs on 70B models where both GPU and host RAM are constrained.
"""

from __future__ import annotations

import mmap
import os
import sys
import threading
import warnings
from typing import List, Optional
import numpy as np

try:
    import matmul_module
except ImportError:
    _SRC_DIR = os.path.dirname(os.path.abspath(__file__))
    _BUILD_DIR = os.path.abspath(os.path.join(_SRC_DIR, "..", "build"))
    if os.path.isdir(_BUILD_DIR) and _BUILD_DIR not in sys.path:
        sys.path.append(_BUILD_DIR)
    try:
        import matmul_module
    except ImportError as exc:
        raise ImportError(
            "Failed to import 'matmul_module' HIP extension. Build it first with:\n"
            "  cmake -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build -j\n"
            "or install the package via 'pip install -e . --no-build-isolation'."
        ) from exc


DEFAULT_MAX_KV_BYTES = 32 * (1 << 30)  # 32 GiB sanity cap against malformed GGUF headers


class KVCacheManager:
    """
    Manages the GQA KV cache across all transformer layers with GPU-resident,
    CPU-offloaded, or NVMe `mmap`-backed storage.
    """

    _active_gpu_instance: bool = False
    _gpu_lock: threading.Lock = threading.Lock()

    def __init__(
        self,
        num_layers: int,
        max_seq_len: int,
        num_kv_heads: int,
        head_dim: int,
        offload_to_cpu: bool = False,
        mmap_dir: Optional[str] = None,
        max_kv_bytes: int = DEFAULT_MAX_KV_BYTES,
    ):
        self.num_layers = int(num_layers)
        self.max_seq_len = int(max_seq_len)
        self.num_kv_heads = int(num_kv_heads)
        self.head_dim = int(head_dim)
        self.offload_to_cpu = bool(offload_to_cpu or mmap_dir is not None)
        self.mmap_dir = mmap_dir
        self.current_seq_len = 0
        self._allocated = False
        self._k_host: Optional[np.ndarray] = None
        self._v_host: Optional[np.ndarray] = None
        self._k_mm: Optional[mmap.mmap] = None
        self._v_mm: Optional[mmap.mmap] = None
        self._created_mmap_files: List[str] = []

        if (
            self.num_layers <= 0
            or self.max_seq_len <= 0
            or self.num_kv_heads <= 0
            or self.head_dim <= 0
        ):
            raise ValueError(
                f"KV cache dimensions must all be positive "
                f"(got layers={self.num_layers}, max_seq_len={self.max_seq_len}, "
                f"kv_heads={self.num_kv_heads}, head_dim={self.head_dim})"
            )

        if self.nbytes > max_kv_bytes:
            raise ValueError(
                f"Requested KV cache size ({self.nbytes} bytes) exceeds max_kv_bytes "
                f"sanity limit ({max_kv_bytes} bytes)."
            )

        shape = (self.num_layers, self.max_seq_len, self.num_kv_heads, self.head_dim)
        per_buf_bytes = self.nbytes // 2

        if self.mmap_dir is not None:
            os.makedirs(self.mmap_dir, exist_ok=True)
            uid = f"{os.getpid()}_{id(self):x}"
            k_path = os.path.join(self.mmap_dir, f"kv_cache_k_{uid}.mmap")
            v_path = os.path.join(self.mmap_dir, f"kv_cache_v_{uid}.mmap")
            open_flags = (
                os.O_CREAT
                | os.O_EXCL
                | os.O_RDWR
                | getattr(os, "O_NOFOLLOW", 0)
            )
            try:
                k_fd = os.open(k_path, open_flags, 0o600)
                self._created_mmap_files.append(k_path)
                try:
                    os.ftruncate(k_fd, per_buf_bytes)
                    self._k_mm = mmap.mmap(k_fd, per_buf_bytes, access=mmap.ACCESS_WRITE)
                finally:
                    os.close(k_fd)

                v_fd = os.open(v_path, open_flags, 0o600)
                self._created_mmap_files.append(v_path)
                try:
                    os.ftruncate(v_fd, per_buf_bytes)
                    self._v_mm = mmap.mmap(v_fd, per_buf_bytes, access=mmap.ACCESS_WRITE)
                finally:
                    os.close(v_fd)

                self._k_host = np.frombuffer(self._k_mm, dtype=np.float16).reshape(shape)
                self._v_host = np.frombuffer(self._v_mm, dtype=np.float16).reshape(shape)
            except BaseException:
                self.close()
                raise
        elif self.offload_to_cpu:
            self._k_host = np.empty(shape, dtype=np.float16)
            self._v_host = np.empty(shape, dtype=np.float16)
        else:
            with KVCacheManager._gpu_lock:
                if KVCacheManager._active_gpu_instance:
                    raise RuntimeError(
                        "A GPU-resident KVCacheManager is already active in this process "
                        "(DeviceKVCachePool is a singleton). Close the existing instance first "
                        "or pass offload_to_cpu=True."
                    )
                KVCacheManager._active_gpu_instance = True
            try:
                matmul_module.kv_cache_init(
                    self.num_layers,
                    self.max_seq_len,
                    self.num_kv_heads,
                    self.head_dim,
                )
                self._allocated = True
            except BaseException:
                with KVCacheManager._gpu_lock:
                    KVCacheManager._active_gpu_instance = False
                self._allocated = False
                try:
                    matmul_module.kv_cache_free()
                except Exception:
                    pass
                raise

    @property
    def nbytes(self) -> int:
        """Total logical bytes across K and V pools."""
        return 2 * self.num_layers * self.max_seq_len * self.num_kv_heads * self.head_dim * 2

    @property
    def mode(self) -> str:
        """Active KV cache storage backend ('gpu', 'cpu', or 'mmap')."""
        if self.mmap_dir is not None:
            return "mmap"
        return "cpu" if self.offload_to_cpu else "gpu"

    @property
    def device_bytes(self) -> int:
        """Bytes allocated in persistent GPU KV pool (0 when offloaded to CPU/mmap)."""
        return 0 if self.offload_to_cpu else self.nbytes

    def record_gpu_layer_step(self, layer_idx: int, q_len: int, start_pos: int) -> None:
        """
        Validate bounds and update `current_seq_len` when the C++-owned device-resident
        layer pipeline (`forward_layer_cached`) writes directly to the GPU KV cache pool.
        """
        total_kv_len = start_pos + q_len
        if total_kv_len > self.max_seq_len:
            raise ValueError(
                f"Sequence length {total_kv_len} exceeds max_seq_len {self.max_seq_len}"
            )
        if not self._allocated:
            raise RuntimeError("GPU KV cache pool is not allocated or has been closed.")
        if layer_idx == self.num_layers - 1:
            self.current_seq_len = total_kv_len

    def attend(
        self,
        q_rot: np.ndarray,
        k_new: np.ndarray,
        v_new: np.ndarray,
        out: np.ndarray,
        layer_idx: int,
        q_len: int,
        start_pos: int,
        num_heads: int,
        scale: float,
        causal: bool = True,
    ) -> None:
        """
        Write `k_new` and `v_new` (`q_len` tokens) into the KV cache at
        `(layer_idx, start_pos)` and compute GQA online-softmax attention over
        `[0 .. start_pos + q_len)`.
        """
        total_kv_len = start_pos + q_len
        if total_kv_len > self.max_seq_len:
            raise ValueError(
                f"Sequence length {total_kv_len} exceeds max_seq_len {self.max_seq_len}"
            )

        if self.offload_to_cpu:
            if self._k_host is None or self._v_host is None:
                raise RuntimeError("CPU/mmap KV cache buffers are not allocated or have been closed.")
            k_layer = self._k_host[layer_idx]
            v_layer = self._v_host[layer_idx]
            k_layer[start_pos:total_kv_len] = k_new
            v_layer[start_pos:total_kv_len] = v_new
            matmul_module.gqa_attention(
                q_rot,
                k_layer,
                v_layer,
                out,
                q_len,
                total_kv_len,
                num_heads,
                self.num_kv_heads,
                self.head_dim,
                start_pos,
                scale,
                causal,
            )
        else:
            if not self._allocated:
                raise RuntimeError("GPU KV cache pool is not allocated or has been closed.")
            matmul_module.gqa_attention_cached(
                q_rot,
                k_new,
                v_new,
                out,
                layer_idx,
                q_len,
                start_pos,
                num_heads,
                self.num_kv_heads,
                self.head_dim,
                scale,
                causal,
            )

        if layer_idx == self.num_layers - 1:
            self.current_seq_len = total_kv_len

    @property
    def mmap_files(self) -> List[str]:
        """Paths of disk-backed mmap files created by this instance."""
        return list(self._created_mmap_files)

    def reset(self) -> None:
        """Reset logical sequence length to 0 without reallocating memory."""
        self.current_seq_len = 0

    def close(self) -> None:
        if getattr(self, "_allocated", False):
            try:
                matmul_module.kv_cache_free()
            finally:
                self._allocated = False
                with KVCacheManager._gpu_lock:
                    KVCacheManager._active_gpu_instance = False
        self._k_host = None
        self._v_host = None
        for attr in ("_k_mm", "_v_mm"):
            mm = getattr(self, attr, None)
            if mm is not None:
                try:
                    mm.close()
                finally:
                    setattr(self, attr, None)
        for p in getattr(self, "_created_mmap_files", []):
            try:
                if os.path.exists(p):
                    os.remove(p)
            except OSError:
                pass
        if hasattr(self, "_created_mmap_files"):
            self._created_mmap_files.clear()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception as exc:
            try:
                warnings.warn(
                    f"KVCacheManager.close() raised during finalization: {exc}",
                    RuntimeWarning,
                    stacklevel=2,
                )
            except Exception:
                pass

    def __enter__(self) -> "KVCacheManager":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
