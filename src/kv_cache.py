"""
Grouped-Query Attention (GQA) KV Cache Manager (`KVCacheManager`) for gfx1150-inference.

Eliminates per-step host KV slicing and O(context_len) host-to-device memory copies
by maintaining a pre-allocated GPU/GTT-resident KV cache pool (`kv_cache_init` /
`gqa_attention_cached`) addressed directly by `(layer_idx, start_pos)` offset.
"""

from __future__ import annotations

import os
import sys
import numpy as np

_SRC_DIR = os.path.dirname(os.path.abspath(__file__))
_BUILD_DIR = os.path.abspath(os.path.join(_SRC_DIR, "..", "build"))
for _p in (_SRC_DIR, _BUILD_DIR):
    if _p not in sys.path and os.path.isdir(_p):
        sys.path.insert(0, _p)

import matmul_module


class KVCacheManager:
    """
    Manages the GPU-resident GQA KV cache across all transformer layers.

    Only the newly computed `q_len` Key/Value slices at step `start_pos` are transferred
    to device offset `(layer_idx, start_pos)`, avoiding any host-side array slicing,
    concatenation, or full-context re-uploads.
    """

    def __init__(
        self,
        num_layers: int,
        max_seq_len: int,
        num_kv_heads: int,
        head_dim: int,
    ):
        self.num_layers = int(num_layers)
        self.max_seq_len = int(max_seq_len)
        self.num_kv_heads = int(num_kv_heads)
        self.head_dim = int(head_dim)
        self.current_seq_len = 0
        self._allocated = False

        matmul_module.kv_cache_init(
            self.num_layers,
            self.max_seq_len,
            self.num_kv_heads,
            self.head_dim,
        )
        self._allocated = True

    @property
    def nbytes(self) -> int:
        """Total bytes allocated in GPU/GTT memory across K and V pools."""
        return 2 * self.num_layers * self.max_seq_len * self.num_kv_heads * self.head_dim * 2

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
        Write `k_new` and `v_new` (`q_len` tokens) into the GPU KV cache at
        `(layer_idx, start_pos)` and compute GQA online-softmax attention over
        `[0 .. start_pos + q_len)` directly in device memory.
        """
        if start_pos + q_len > self.max_seq_len:
            raise ValueError(
                f"Sequence length {start_pos + q_len} exceeds max_seq_len {self.max_seq_len}"
            )
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
            self.current_seq_len = start_pos + q_len

    def reset(self) -> None:
        """Reset logical sequence length to 0 without reallocating GPU memory."""
        self.current_seq_len = 0

    def close(self) -> None:
        if self._allocated:
            matmul_module.kv_cache_free()
            self._allocated = False

    def __enter__(self) -> "KVCacheManager":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

