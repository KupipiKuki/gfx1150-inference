"""
Grouped-Query Attention (GQA) KV Cache Manager (`KVCacheManager`) for gfx1150-inference.

Supports three storage backends for 7B–70B models:
1. **GPU-resident pool (default)**: Pre-allocated device/GTT memory (`kv_cache_init` /
   `gqa_attention_cached`) addressed by `(layer_idx, start_pos)` with zero host copies.
2. **CPU-offloaded pool (`offload_to_cpu=True`)**: Pre-allocated host `np.float16` buffers
   updated in-place without slice allocations, keeping GPU pool memory at 0 bytes.
3. **SSD `mmap`-offloaded pool (`mmap_dir=...`)**: Disk-backed `np.memmap` KV cache for
   ultra-long context research runs on 70B models where even host RAM is constrained.
"""

from __future__ import annotations

import os
import sys
from typing import Optional
import numpy as np

_SRC_DIR = os.path.dirname(os.path.abspath(__file__))
_BUILD_DIR = os.path.abspath(os.path.join(_SRC_DIR, "..", "build"))
for _p in (_SRC_DIR, _BUILD_DIR):
    if _p not in sys.path and os.path.isdir(_p):
        sys.path.insert(0, _p)

import matmul_module


class KVCacheManager:
    """
    Manages the GQA KV cache across all transformer layers with GPU-resident,
    CPU-offloaded, or NVMe `mmap`-backed storage.
    """

    def __init__(
        self,
        num_layers: int,
        max_seq_len: int,
        num_kv_heads: int,
        head_dim: int,
        offload_to_cpu: bool = False,
        mmap_dir: Optional[str] = None,
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
        self._mmap_files: list[str] = []

        shape = (self.num_layers, self.max_seq_len, self.num_kv_heads, self.head_dim)

        if self.mmap_dir is not None:
            os.makedirs(self.mmap_dir, exist_ok=True)
            k_path = os.path.join(self.mmap_dir, "kv_cache_k.mmap")
            v_path = os.path.join(self.mmap_dir, "kv_cache_v.mmap")
            self._mmap_files = [k_path, v_path]
            self._k_host = np.memmap(k_path, dtype=np.float16, mode="w+", shape=shape)
            self._v_host = np.memmap(v_path, dtype=np.float16, mode="w+", shape=shape)
        elif self.offload_to_cpu:
            self._k_host = np.empty(shape, dtype=np.float16)
            self._v_host = np.empty(shape, dtype=np.float16)
        else:
            matmul_module.kv_cache_init(
                self.num_layers,
                self.max_seq_len,
                self.num_kv_heads,
                self.head_dim,
            )
            self._allocated = True

    @property
    def nbytes(self) -> int:
        """Total logical bytes across K and V pools."""
        return 2 * self.num_layers * self.max_seq_len * self.num_kv_heads * self.head_dim * 2

    @property
    def device_bytes(self) -> int:
        """Bytes allocated in persistent GPU KV pool (0 when offloaded to CPU/mmap)."""
        return 0 if self.offload_to_cpu else self.nbytes

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
            assert self._k_host is not None and self._v_host is not None
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

    def reset(self) -> None:
        """Reset logical sequence length to 0 without reallocating memory."""
        self.current_seq_len = 0

    def close(self) -> None:
        if self._allocated:
            matmul_module.kv_cache_free()
            self._allocated = False
        self._k_host = None
        self._v_host = None
        for p in self._mmap_files:
            try:
                if os.path.exists(p):
                    os.remove(p)
            except OSError:
                pass
        self._mmap_files.clear()

    def __enter__(self) -> "KVCacheManager":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
