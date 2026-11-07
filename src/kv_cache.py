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
   Files are allocated with `O_CREAT|O_EXCL|O_RDWR|O_NOFOLLOW` (symlinks rejected), sized
   only after a `statvfs` free-space check, and unlinked **immediately after** the mapping
   is established, so a crash before `close()` leaves no files behind (POSIX only;
   the mapping stays usable through its open file descriptor).

Allocation discipline (Phase 7D): before any allocation, the requested bytes are checked
against an effective budget — `min(max user cap, free GTT, MemAvailable, cgroup v2/v1
headroom) minus a safety margin` — and a request that cannot fit fails with a `ValueError`
naming the requested bytes, the effective budget, and the sources used. The manager never
attempts an allocation that can OOM.
"""

from __future__ import annotations

import mmap
import os
import sys
import threading
import warnings
from typing import Dict, List, Optional, Tuple
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

try:
    from . import memory_budget
except ImportError:
    _SRC_DIR = os.path.dirname(os.path.abspath(__file__))
    if _SRC_DIR not in sys.path:
        sys.path.append(_SRC_DIR)
    import memory_budget


DEFAULT_MAX_KV_BYTES = 32 * (1 << 30)  # 32 GiB user sanity cap against malformed GGUF headers

#: Safety margin held back from the effective KV budget: 10% of the cap.
#: Documented in README/PLAN and the G4 evidence bundle.
_KV_SAFETY_MARGIN_FRACTION = 10


def _effective_kv_budget(max_kv_bytes: int) -> Tuple[int, Dict[str, int]]:
    """Return `(effective_budget_bytes, sources)` for a KV allocation.

    The cap is `min(max_kv_bytes, free GTT, MemAvailable, cgroup headroom)`
    over every source readable on this host (unavailable sources are skipped
    and recorded), minus a 10% safety margin. `max_kv_bytes` is always a
    component so a test/user cap reproduces deterministically even when no
    host source is readable.
    """
    sources = memory_budget.read_budget_sources()
    cap = int(max_kv_bytes)
    used: Dict[str, int] = {"max_kv_bytes": cap}
    for name, value in sources.readings.items():
        used[name] = int(value)
        cap = min(cap, int(value))
    margin = max(0, cap // _KV_SAFETY_MARGIN_FRACTION)
    # A margin is only meaningful against the sources; the user cap is a hard
    # ceiling and deliberately not shrunk below the requested sanity limit
    # by more than the same 10% (deterministic for tests).
    return max(0, cap - margin), used


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
        self._mmap_files_unlinked = False

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

        # 7D-3: refuse requests that cannot fit the effective budget instead
        # of attempting an allocation that can OOM.
        self.kv_budget_bytes, self.kv_budget_sources = _effective_kv_budget(max_kv_bytes)
        if self.nbytes > self.kv_budget_bytes:
            sources_desc = ", ".join(
                f"{name}={value}" for name, value in self.kv_budget_sources.items()
            )
            raise ValueError(
                f"Requested KV cache size ({self.nbytes} bytes) exceeds the effective "
                f"KV budget ({self.kv_budget_bytes} bytes, "
                f"{_KV_SAFETY_MARGIN_FRACTION}% safety margin). "
                f"Budget sources used: {sources_desc}. Reduce max_seq_len/num_layers/heads, "
                f"or raise the max_kv_bytes user cap."
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

            # 7D-3: fail closed when the mmap directory does not have room for
            # the full K+V payload, before creating any file.
            required_bytes = 2 * per_buf_bytes
            self._check_mmap_disk_space(required_bytes)

            try:
                k_fd = os.open(k_path, open_flags, 0o600)
                self._created_mmap_files.append(k_path)
                try:
                    self._allocate_mmap_file(k_fd, per_buf_bytes)
                    self._k_mm = mmap.mmap(k_fd, per_buf_bytes, access=mmap.ACCESS_WRITE)
                finally:
                    os.close(k_fd)

                v_fd = os.open(v_path, open_flags, 0o600)
                self._created_mmap_files.append(v_path)
                try:
                    self._allocate_mmap_file(v_fd, per_buf_bytes)
                    self._v_mm = mmap.mmap(v_fd, per_buf_bytes, access=mmap.ACCESS_WRITE)
                finally:
                    os.close(v_fd)

                self._k_host = np.frombuffer(self._k_mm, dtype=np.float16).reshape(shape)
                self._v_host = np.frombuffer(self._v_mm, dtype=np.float16).reshape(shape)

                # 7D-3: unlink immediately after the mappings exist (POSIX):
                # a crash before close() leaves no files, the mapping stays
                # usable through its fd.
                self._unlink_mmap_files()
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

    # ------------------------------------------------------------------ #
    # mmap file helpers (7D-3)
    # ------------------------------------------------------------------ #

    def _check_mmap_disk_space(self, required_bytes: int) -> None:
        """Refuse cleanly when `mmap_dir` cannot hold `required_bytes` (7D-3).

        Uses `os.statvfs` free-bytes; raises `OSError` with the required and
        free byte counts instead of attempting the allocation.
        """
        required_bytes = int(required_bytes)
        try:
            st = os.statvfs(self.mmap_dir)
            free_bytes = st.f_bsize * st.f_bavail
        except OSError as exc:
            raise OSError(
                f"Cannot stat the KV mmap directory {self.mmap_dir!r} to check "
                f"free space: {exc}"
            ) from exc
        if free_bytes < required_bytes:
            raise OSError(
                f"Insufficient disk space for the mmap-backed KV cache: "
                f"requires {required_bytes} bytes, but {self.mmap_dir!r} has "
                f"{free_bytes} bytes free"
            )

    def _allocate_mmap_file(self, fd: int, length: int) -> None:
        """Size the KV mmap file: `posix_fallocate` when available, else ftruncate."""
        if hasattr(os, "posix_fallocate"):
            os.posix_fallocate(fd, 0, int(length))
        else:
            os.ftruncate(fd, int(length))

    def _unlink_mmap_files(self) -> None:
        """Unlink the created mmap files (best-effort, POSIX unlink-after-map)."""
        for p in self._created_mmap_files:
            try:
                os.unlink(p)
            except OSError as exc:
                warnings.warn(
                    f"KV mmap file {p!r} could not be unlinked after mapping "
                    f"({exc}); retaining the close()-time cleanup path.",
                    RuntimeWarning,
                    stacklevel=2,
                )
        self._mmap_files_unlinked = True

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
        """Paths of the disk-backed mmap files created by this instance.

        Under unlink-before-map (POSIX) the files no longer exist on disk
        while the mapping is live; the paths are recorded for provenance.
        """
        return list(self._created_mmap_files)

    def reset(self) -> None:
        """Reset logical sequence length to 0 without reallocating memory."""
        self.current_seq_len = 0

    def close(self) -> None:
        """Release pools, mappings, and files. Never raises: cleanup failures
        are warned (a `BufferError` from a mapping with live views must warn,
        not mask the original exception); the fds are already closed and every
        created file is removed or already unlinked-before-map."""
        if getattr(self, "_allocated", False):
            try:
                matmul_module.kv_cache_free()
            except Exception as exc:
                warnings.warn(
                    f"KVCacheManager.close(): kv_cache_free() failed during "
                    f"cleanup: {exc}",
                    RuntimeWarning,
                    stacklevel=2,
                )
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
                except BufferError as exc:
                    warnings.warn(
                        f"KVCacheManager.close(): the {attr} mapping still has "
                        f"live views and could not be released ({exc}); dropping "
                        f"the reference. The backing fd was already closed and "
                        f"the file was unlinked at allocation time.",
                        RuntimeWarning,
                        stacklevel=2,
                    )
                finally:
                    setattr(self, attr, None)
        if hasattr(self, "_created_mmap_files"):
            for p in self._created_mmap_files:
                try:
                    if os.path.exists(p):
                        os.remove(p)
                except OSError:
                    pass
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
