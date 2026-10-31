"""
Single Llama Transformer Layer execution pipeline (`TransformerLayer`) for gfx1150-inference.

Streams `blk.{layer_idx}.*` weights directly from SSD via `WeightStreamer`, executes
fused `Q4_0` projections, RMSNorm, RoPE, Grouped-Query Attention (GQA), and SwiGLU MLP
on the AMD gfx1150 GPU, and evicts completed layer pages via `MADV_DONTNEED`.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import os
import sys
from typing import Dict, Optional, Tuple
import numpy as np

_SRC_DIR = os.path.dirname(os.path.abspath(__file__))
_BUILD_DIR = os.path.abspath(os.path.join(_SRC_DIR, "..", "build"))
for _p in (_SRC_DIR, _BUILD_DIR):
    if _p not in sys.path and os.path.isdir(_p):
        sys.path.insert(0, _p)

from gguf_parser import GGMLType, GGUFTensorInfo
from weight_loader import WeightStreamer
import matmul_module


@dataclass(frozen=True)
class LlamaLayerConfig:
    hidden_size: int
    intermediate_size: int
    num_heads: int
    num_kv_heads: int
    head_dim: int
    rms_norm_eps: float = 1e-5
    rope_freq_base: float = 10000.0
    rope_neox: bool = False

    @classmethod
    def from_gguf_metadata(cls, metadata: Dict[str, object]) -> "LlamaLayerConfig":
        hidden_size = int(metadata["llama.embedding_length"])
        intermediate_size = int(metadata["llama.feed_forward_length"])
        num_heads = int(metadata["llama.attention.head_count"])
        num_kv_heads = int(metadata.get("llama.attention.head_count_kv", num_heads))
        head_dim = int(metadata.get("llama.rope.dimension_count", hidden_size // num_heads))
        rms_norm_eps = float(metadata.get("llama.attention.layer_norm_rms_epsilon", 1e-5))
        rope_freq_base = float(metadata.get("llama.rope.freq_base", 10000.0))
        return cls(
            hidden_size=hidden_size,
            intermediate_size=intermediate_size,
            num_heads=num_heads,
            num_kv_heads=num_kv_heads,
            head_dim=head_dim,
            rms_norm_eps=rms_norm_eps,
            rope_freq_base=rope_freq_base,
            rope_neox=False,
        )


def _linear_project(
    x_fp16: np.ndarray,
    weight_entry: Tuple[GGUFTensorInfo, np.ndarray],
    out_features: int,
) -> np.ndarray:
    """
    Compute `x_fp16 (M, K) @ W^T (N, K)` on GPU using fused `matmul_q4_0` for Q4_0 weights
    or FP16 `matmul` for F16 weights.
    """
    info, w_view = weight_entry
    M, K = x_fp16.shape
    N = out_features
    out = np.empty((M, N), dtype=np.float16)

    if info.ggml_type == GGMLType.Q4_0:
        matmul_module.matmul_q4_0(x_fp16, w_view, out, M, N, K)
    elif info.ggml_type == GGMLType.F16:
        # w_view has row-major shape (N, K); transpose to C-contiguous (K, N) for matmul
        w_t = np.ascontiguousarray(w_view.reshape(N, K).T)
        matmul_module.matmul(x_fp16, w_t, out, M, N, K)
    elif info.ggml_type == GGMLType.F32:
        w_t = np.ascontiguousarray(w_view.reshape(N, K).astype(np.float16).T)
        matmul_module.matmul(x_fp16, w_t, out, M, N, K)
    else:
        raise ValueError(f"Unsupported weight quantization type: {info.ggml_type}")
    return out


def _norm_weight_fp16(weight_entry: Tuple[GGUFTensorInfo, np.ndarray]) -> np.ndarray:
    info, w_view = weight_entry
    if info.ggml_type == GGMLType.F16:
        return np.ascontiguousarray(w_view.view(np.float16).reshape(-1))
    if info.ggml_type == GGMLType.F32:
        return np.ascontiguousarray(w_view.view(np.float32).reshape(-1).astype(np.float16))
    raise ValueError(f"Unsupported norm weight type: {info.ggml_type}")


class TransformerLayer:
    """
    Executes a single Llama-architecture transformer block on AMD gfx1150 using
    SSD-streamed weights from `WeightStreamer`.
    """

    def __init__(self, config: LlamaLayerConfig):
        self.cfg = config
        self.scale = 1.0 / math.sqrt(config.head_dim)

    def forward_with_weights(
        self,
        hidden_states: np.ndarray,
        layer_weights: Dict[str, Tuple[GGUFTensorInfo, np.ndarray]],
        layer_idx: int,
        pos_offset: int = 0,
        kv_cache: Optional[Tuple[np.ndarray, np.ndarray]] = None,
    ) -> Tuple[np.ndarray, Tuple[np.ndarray, np.ndarray]]:
        """
        Run one transformer layer given already-mapped `layer_weights` dict for `layer_idx`.

        Args:
            hidden_states: Input activations `(seq_len, hidden_size)` in `np.float16`.
            layer_weights: Mapping of `blk.{layer_idx}.*` tensor names to `(info, view)`.
            layer_idx: Layer index `0 .. num_layers - 1`.
            pos_offset: Starting token position index (`0` for initial prompt prefill).
            kv_cache: Optional tuple `(k_cache, v_cache)` where each array has shape
                      `(max_seq_len, num_kv_heads, head_dim)` in `np.float16`.

        Returns:
            `(next_hidden_states, (k_present, v_present))`
        """
        x = np.ascontiguousarray(hidden_states, dtype=np.float16)
        seq_len, hidden_size = x.shape
        cfg = self.cfg
        prefix = f"blk.{layer_idx}."

        q_dim = cfg.num_heads * cfg.head_dim
        kv_dim = cfg.num_kv_heads * cfg.head_dim

        # 1. Pre-Attention RMSNorm
        attn_norm_w = _norm_weight_fp16(layer_weights[prefix + "attn_norm.weight"])
        normed_x = np.empty_like(x)
        matmul_module.rmsnorm(x, attn_norm_w, normed_x, seq_len, hidden_size, cfg.rms_norm_eps)

        # 2. Q, K, V Projections (Fused Q4_0 or FP16)
        q_proj = _linear_project(normed_x, layer_weights[prefix + "attn_q.weight"], q_dim)
        k_proj = _linear_project(normed_x, layer_weights[prefix + "attn_k.weight"], kv_dim)
        v_proj = _linear_project(normed_x, layer_weights[prefix + "attn_v.weight"], kv_dim)

        q_heads = q_proj.reshape(seq_len, cfg.num_heads, cfg.head_dim)
        k_heads = k_proj.reshape(seq_len, cfg.num_kv_heads, cfg.head_dim)
        v_heads = v_proj.reshape(seq_len, cfg.num_kv_heads, cfg.head_dim)

        # 3. Rotary Positional Embeddings (RoPE) on Q and K
        q_rot = np.empty_like(q_heads)
        k_rot = np.empty_like(k_heads)
        matmul_module.rope(
            q_heads, q_rot, seq_len, cfg.num_heads, cfg.head_dim,
            pos_offset, cfg.rope_freq_base, cfg.rope_neox
        )
        matmul_module.rope(
            k_heads, k_rot, seq_len, cfg.num_kv_heads, cfg.head_dim,
            pos_offset, cfg.rope_freq_base, cfg.rope_neox
        )

        # 4. Update or construct KV cache up to `total_kv_len = pos_offset + seq_len`
        total_kv_len = pos_offset + seq_len
        if kv_cache is not None:
            k_cache, v_cache = kv_cache
            k_cache[pos_offset:total_kv_len] = k_rot
            v_cache[pos_offset:total_kv_len] = v_heads
            k_present = np.ascontiguousarray(k_cache[:total_kv_len])
            v_present = np.ascontiguousarray(v_cache[:total_kv_len])
        else:
            k_present = k_rot
            v_present = v_heads

        # 5. Grouped-Query Attention (GQA) with Online Softmax
        attn_out_heads = np.empty_like(q_rot)
        matmul_module.gqa_attention(
            q_rot, k_present, v_present, attn_out_heads,
            seq_len, total_kv_len, cfg.num_heads, cfg.num_kv_heads, cfg.head_dim,
            pos_offset, self.scale, True
        )
        attn_out_flat = attn_out_heads.reshape(seq_len, q_dim)

        # 6. Output Projection + First Residual Connection
        attn_proj = _linear_project(
            attn_out_flat, layer_weights[prefix + "attn_output.weight"], hidden_size
        )
        h = (x.astype(np.float32) + attn_proj.astype(np.float32)).astype(np.float16)

        # 7. Pre-FFN RMSNorm
        ffn_norm_w = _norm_weight_fp16(layer_weights[prefix + "ffn_norm.weight"])
        normed_h = np.empty_like(h)
        matmul_module.rmsnorm(h, ffn_norm_w, normed_h, seq_len, hidden_size, cfg.rms_norm_eps)

        # 8. SwiGLU Feed-Forward Network (gate_proj, up_proj -> SwiGLU -> down_proj)
        gate = _linear_project(
            normed_h, layer_weights[prefix + "ffn_gate.weight"], cfg.intermediate_size
        )
        up = _linear_project(
            normed_h, layer_weights[prefix + "ffn_up.weight"], cfg.intermediate_size
        )
        swiglu_out = np.empty_like(gate)
        matmul_module.swiglu(gate, up, swiglu_out, seq_len * cfg.intermediate_size)

        down = _linear_project(
            swiglu_out, layer_weights[prefix + "ffn_down.weight"], hidden_size
        )

        # 9. Second Residual Connection
        out_hidden = (h.astype(np.float32) + down.astype(np.float32)).astype(np.float16)
        return out_hidden, (k_present, v_present)

    def forward_streamed(
        self,
        hidden_states: np.ndarray,
        streamer: WeightStreamer,
        layer_idx: int,
        pos_offset: int = 0,
        kv_cache: Optional[Tuple[np.ndarray, np.ndarray]] = None,
        prefetch_next: bool = True,
    ) -> Tuple[np.ndarray, Tuple[np.ndarray, np.ndarray]]:
        """
        Stream weights for `layer_idx` from SSD via `streamer.layer_context`, run the
        layer forward pass on GPU, prefetch `layer_idx + 1`, and evict `layer_idx` pages.
        """
        with streamer.layer_context(layer_idx, prefetch_next=prefetch_next) as layer_weights:
            return self.forward_with_weights(
                hidden_states=hidden_states,
                layer_weights=layer_weights,
                layer_idx=layer_idx,
                pos_offset=pos_offset,
                kv_cache=kv_cache,
            )

