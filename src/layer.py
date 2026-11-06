"""
Model-spec driven Transformer Layer execution (`TransformerLayer`) for
gfx1150-inference.

Streams `blk.{layer_idx}.*` weights directly from SSD via `WeightStreamer`, executes
fused `Q4_0` projections, RMSNorm, RoPE, Grouped-Query Attention (GQA), and the
per-family FFN (SwiGLU for llama/qwen2/phi3, GeGLU for gemma; Phi-3 fused
`attn_qkv` / fused gate+up `ffn_up` layouts) on the AMD gfx1150 GPU, and evicts
completed layer pages via `MADV_DONTNEED`. The executed graph is selected by the
resolved `ModelSpec` (Phase 7C), never by hardcoded `llama.*` tensor names.
"""

from __future__ import annotations

import math
import os
import sys
from typing import Dict, Optional, Tuple, Union
import numpy as np

_SRC_DIR = os.path.dirname(os.path.abspath(__file__))
_BUILD_DIR = os.path.abspath(os.path.join(_SRC_DIR, "..", "build"))
if _SRC_DIR not in sys.path:
    sys.path.append(_SRC_DIR)

from gguf_parser import GGMLType, GGUFTensorInfo
from weight_loader import WeightStreamer
from kv_cache import KVCacheManager
from model_spec import ModelSpec, _NEOX_ROPE_ARCHS, get_arch_meta

try:
    import matmul_module
except ImportError:
    if _BUILD_DIR not in sys.path and os.path.isdir(_BUILD_DIR):
        sys.path.append(_BUILD_DIR)
    try:
        import matmul_module
    except ImportError as exc:
        raise ImportError(
            "Failed to import 'matmul_module' HIP extension. Build it first with:\n"
            "  cmake -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build -j\n"
            "or install the package via 'pip install -e . --no-build-isolation'."
        ) from exc


# Backward-compatible alias: the former `LlamaLayerConfig` is now the
# data-driven `ModelSpec` (same resolved values for the llama family plus the
# new per-family fields; `from_gguf_metadata` keeps its semantics).
LlamaLayerConfig = ModelSpec


# ggml-cpu reference GELU constants (tanh approximation, cf. ggml_gelu_f32):
# 0.5*x*(1 + tanh(sqrt(2/pi)*x*(1 + 0.044715*x^2)))
_GELU_TANH_COEF_A = 0.044715
_GELU_SQRT_2_OVER_PI = 0.7978845608028654


def geglu_host(gate_fp16: np.ndarray, up_fp16: np.ndarray) -> np.ndarray:
    """
    GeGLU (gemma FFN): `gelu_tanh(gate) * up` in FP32, cast back to FP16.

    Matches the reference layout `build_ffn(..., LLM_FFN_GELU, LLM_FFN_PAR)` /
    `ggml_vec_geglu_f32` (tanh-approximation GELU on the gate output) from the
    pinned llama.cpp (`src/models/gemma.cpp`).

    Limitation (documented in the README compatibility matrix): GeGLU runs on
    the host in NumPy FP32; the 7C package deliberately adds no new GPU kernel
    (a GeGLU/HIP kernel is future performance work, out of 7C scope).
    """
    g = gate_fp16.astype(np.float32)
    gelu = 0.5 * g * (1.0 + np.tanh(_GELU_SQRT_2_OVER_PI * g * (1.0 + _GELU_TANH_COEF_A * g * g)))
    return (gelu * up_fp16.astype(np.float32)).astype(np.float16)


def add_bias_fp32(x_fp16: np.ndarray, bias_fp16: np.ndarray) -> np.ndarray:
    """Apply a bias with the engine's FP32-add-then-FP16 accumulator behavior."""
    return (x_fp16.astype(np.float32) + bias_fp16.astype(np.float32)).astype(np.float16)


def _prepare_weight_for_device(
    weight_entry: Tuple[GGUFTensorInfo, np.ndarray],
    out_features: int,
    in_features: int,
) -> Tuple[np.ndarray, int]:
    """
    Prepare a GGUF weight buffer and its effective GGMLType int for device execution.
    F32 weights are converted to contiguous (N, K) FP16 without transposing.
    """
    info, w_view = weight_entry
    if info.ggml_type in (GGMLType.Q4_0, GGMLType.Q8_0, GGMLType.Q4_K, GGMLType.Q6_K):
        return w_view, int(info.ggml_type)
    if info.ggml_type == GGMLType.F16:
        w_nt = np.ascontiguousarray(w_view.view(np.float16).reshape(out_features, in_features))
        return w_nt, int(GGMLType.F16)
    if info.ggml_type == GGMLType.F32:
        w_nt = np.ascontiguousarray(
            w_view.view(np.float32).reshape(out_features, in_features).astype(np.float16)
        )
        return w_nt, int(GGMLType.F16)
    raise ValueError(f"Unsupported weight quantization type: {info.ggml_type}")


def linear_project(
    x_fp16: np.ndarray,
    weight_entry: Tuple[GGUFTensorInfo, np.ndarray],
    out_features: int,
) -> np.ndarray:
    """
    Compute `x_fp16 (M, K) @ W^T (N, K)` on GPU using fused quantized kernels
    (`matmul_q4_0`, `matmul_q8_0`, `matmul_q4_k`, `matmul_q6_k`) or native-layout
    FP16 `matmul_nt` (zero host transpose).
    """
    info, w_view = weight_entry
    M, K = x_fp16.shape
    N = out_features
    out = np.empty((M, N), dtype=np.float16)

    if info.ggml_type == GGMLType.Q4_0:
        matmul_module.matmul_q4_0(x_fp16, w_view, out, M, N, K)
    elif info.ggml_type == GGMLType.Q8_0:
        matmul_module.matmul_q8_0(x_fp16, w_view, out, M, N, K)
    elif info.ggml_type == GGMLType.Q4_K:
        matmul_module.matmul_q4_k(x_fp16, w_view, out, M, N, K)
    elif info.ggml_type == GGMLType.Q6_K:
        matmul_module.matmul_q6_k(x_fp16, w_view, out, M, N, K)
    elif info.ggml_type == GGMLType.F16:
        w_nt = np.ascontiguousarray(w_view.view(np.float16).reshape(N, K))
        matmul_module.matmul_nt(x_fp16, w_nt, out, M, N, K)
    elif info.ggml_type == GGMLType.F32:
        w_nt = np.ascontiguousarray(w_view.view(np.float32).reshape(N, K).astype(np.float16))
        matmul_module.matmul_nt(x_fp16, w_nt, out, M, N, K)
    else:
        raise ValueError(f"Unsupported weight quantization type: {info.ggml_type}")
    return out


def norm_weight_fp16(weight_entry: Tuple[GGUFTensorInfo, np.ndarray]) -> np.ndarray:
    info, w_view = weight_entry
    if info.ggml_type == GGMLType.F16:
        return np.ascontiguousarray(w_view.view(np.float16).reshape(-1))
    if info.ggml_type == GGMLType.F32:
        return np.ascontiguousarray(w_view.view(np.float32).reshape(-1).astype(np.float16))
    raise ValueError(f"Unsupported norm weight type: {info.ggml_type}")


KVCacheType = Union[KVCacheManager, Tuple[np.ndarray, np.ndarray]]


class TransformerLayer:
    """
    Executes a single Llama-architecture transformer block on AMD gfx1150 using
    SSD-streamed weights from `WeightStreamer`.
    """

    def __init__(self, config: ModelSpec):
        self.cfg = config
        self.scale = 1.0 / math.sqrt(config.head_dim)

    def forward_with_weights(
        self,
        hidden_states: np.ndarray,
        layer_weights: Dict[str, Tuple[GGUFTensorInfo, np.ndarray]],
        layer_idx: int,
        pos_offset: int = 0,
        kv_cache: Optional[KVCacheType] = None,
    ) -> Tuple[np.ndarray, Optional[Tuple[np.ndarray, np.ndarray]]]:
        """
        Run one transformer layer given already-mapped `layer_weights` dict for `layer_idx`.

        The executed graph is selected by the `ModelSpec` and the tensors
        actually present in the layer: fused `attn_qkv` (Phi-3/Gemma per header)
        or separate `attn_q/k/v` projections with optional biases, then RoPE,
        GQA attention with explicit key/value head dims, and the per-family
        FFN (SwiGLU on separate/fused gate+up, or GeGLU for gemma).

        Supports two KV cache modes:
        1. `KVCacheManager` (recommended for Phase 4+): GPU-resident offset-addressed KV cache;
           writes only the new `seq_len` K/V rows directly to device offset `pos_offset`
           with zero host slicing or copies.
        2. `Tuple[np.ndarray, np.ndarray]`: Host pre-allocated `(k_cache, v_cache)` arrays
           passed directly by pointer + `total_kv_len` without `ascontiguousarray` copy.
        """
        x = np.ascontiguousarray(hidden_states, dtype=np.float16)
        seq_len, hidden_size = x.shape
        cfg = self.cfg
        if hidden_size != cfg.hidden_size:
            raise ValueError(
                f"TransformerLayer hidden size mismatch: input has {hidden_size}, "
                f"spec '{cfg.arch}' expects {cfg.hidden_size}"
            )
        prefix = f"blk.{layer_idx}."

        q_dim = cfg.q_dim
        kv_dim = cfg.kv_dim
        head_dim = cfg.head_dim

        attn_norm_w = norm_weight_fp16(layer_weights[prefix + "attn_norm.weight"])
        ffn_norm_w = norm_weight_fp16(layer_weights[prefix + "ffn_norm.weight"])

        fused_qkv_weight = (prefix + "attn_qkv.weight") in layer_weights
        has_bias = any(
            (prefix + bname) in layer_weights
            for bname in (
                "attn_qkv.bias",
                "attn_q.bias",
                "attn_k.bias",
                "attn_v.bias",
                "attn_output.bias",
            )
        )

        # Fast C++-owned device-resident pipeline when using GPU-resident KVCacheManager.
        # Only valid for the llama-family layout: separate Q/K/V weights, no biases,
        # separate SwiGLU gate/up (no fused Phi-3 ffn_up); fused/gemma layouts use the
        # spec-driven path below.
        if (
            isinstance(kv_cache, KVCacheManager)
            and kv_cache.mode == "gpu"
            and not has_bias
            and not fused_qkv_weight
            and cfg.ffn_act == "swiglu"
            and not cfg.ffn_fused_gate_up
            and (prefix + "ffn_gate.weight") in layer_weights
        ):
            kv_cache.record_gpu_layer_step(layer_idx, seq_len, pos_offset)
            wq_buf, wq_type = _prepare_weight_for_device(
                layer_weights[prefix + "attn_q.weight"], q_dim, hidden_size
            )
            wk_buf, wk_type = _prepare_weight_for_device(
                layer_weights[prefix + "attn_k.weight"], kv_dim, hidden_size
            )
            wv_buf, wv_type = _prepare_weight_for_device(
                layer_weights[prefix + "attn_v.weight"], kv_dim, hidden_size
            )
            wo_buf, wo_type = _prepare_weight_for_device(
                layer_weights[prefix + "attn_output.weight"], hidden_size, q_dim
            )
            wgate_buf, wgate_type = _prepare_weight_for_device(
                layer_weights[prefix + "ffn_gate.weight"], cfg.intermediate_size, hidden_size
            )
            wup_buf, wup_type = _prepare_weight_for_device(
                layer_weights[prefix + "ffn_up.weight"], cfg.intermediate_size, hidden_size
            )
            wdown_buf, wdown_type = _prepare_weight_for_device(
                layer_weights[prefix + "ffn_down.weight"], hidden_size, cfg.intermediate_size
            )

            out_hidden = np.empty_like(x)
            matmul_module.forward_layer_cached(
                x, out_hidden,
                attn_norm_w,
                wq_buf, wq_type,
                wk_buf, wk_type,
                wv_buf, wv_type,
                wo_buf, wo_type,
                ffn_norm_w,
                wgate_buf, wgate_type,
                wup_buf, wup_type,
                wdown_buf, wdown_type,
                layer_idx, seq_len, pos_offset,
                hidden_size, cfg.intermediate_size,
                cfg.num_heads, cfg.num_kv_heads, cfg.head_dim,
                cfg.rms_norm_eps, cfg.rope_freq_base, cfg.rope_neox,
                self.scale
            )
            return out_hidden, None

        # 1. Pre-Attention RMSNorm
        normed_x = np.empty_like(x)
        matmul_module.rmsnorm(x, attn_norm_w, normed_x, seq_len, hidden_size, cfg.rms_norm_eps)

        # 2. Q, K, V projections.
        # Fused QKV (Phi-3/Gemma per header): one projection with N = q_dim+2*kv_dim
        # rows, then exact column slicing of the (M, q+2kv) output. This is valid for
        # quantized fused tensors too: the weight stays a single matmul operand and
        # is never reshaped as three separate tensors.
        if fused_qkv_weight:
            qkv_rows = q_dim + 2 * kv_dim
            qkv = linear_project(
                normed_x, layer_weights[prefix + "attn_qkv.weight"], qkv_rows
            )
            if (prefix + "attn_qkv.bias") in layer_weights:
                qkv = add_bias_fp32(qkv, norm_weight_fp16(layer_weights[prefix + "attn_qkv.bias"]))
            elif (prefix + "attn_q.bias") in layer_weights or (prefix + "attn_k.bias") in layer_weights or (prefix + "attn_v.bias") in layer_weights:
                # Fused weights may coexist with separate Q/K/V biases (legacy files).
                q_bias = (
                    norm_weight_fp16(layer_weights[prefix + "attn_q.bias"])
                    if (prefix + "attn_q.bias") in layer_weights
                    else np.zeros(q_dim, dtype=np.float16)
                )
                k_bias = (
                    norm_weight_fp16(layer_weights[prefix + "attn_k.bias"])
                    if (prefix + "attn_k.bias") in layer_weights
                    else np.zeros(kv_dim, dtype=np.float16)
                )
                v_bias = (
                    norm_weight_fp16(layer_weights[prefix + "attn_v.bias"])
                    if (prefix + "attn_v.bias") in layer_weights
                    else np.zeros(kv_dim, dtype=np.float16)
                )
                fused_bias = np.concatenate([q_bias, k_bias, v_bias]).astype(np.float16)
                qkv = add_bias_fp32(qkv, fused_bias)
            q_proj = np.ascontiguousarray(qkv[:, :q_dim])
            k_proj = np.ascontiguousarray(qkv[:, q_dim:q_dim + kv_dim])
            v_proj = np.ascontiguousarray(qkv[:, q_dim + kv_dim:])
        else:
            # Separate Q/K/V path (Fused Q4_0/Q8_0/Q4_K/Q6_K or FP16 NT) + optional
            # QKV biases (C-3).
            q_proj = linear_project(normed_x, layer_weights[prefix + "attn_q.weight"], q_dim)
            k_proj = linear_project(normed_x, layer_weights[prefix + "attn_k.weight"], kv_dim)
            v_proj = linear_project(normed_x, layer_weights[prefix + "attn_v.weight"], kv_dim)

            if (prefix + "attn_q.bias") in layer_weights:
                q_proj = add_bias_fp32(q_proj, norm_weight_fp16(layer_weights[prefix + "attn_q.bias"]))
            if (prefix + "attn_k.bias") in layer_weights:
                k_proj = add_bias_fp32(k_proj, norm_weight_fp16(layer_weights[prefix + "attn_k.bias"]))
            if (prefix + "attn_v.bias") in layer_weights:
                v_proj = add_bias_fp32(v_proj, norm_weight_fp16(layer_weights[prefix + "attn_v.bias"]))

        q_heads = q_proj.reshape(seq_len, cfg.num_heads, head_dim)
        k_heads = k_proj.reshape(seq_len, cfg.num_kv_heads, head_dim)
        v_heads = v_proj.reshape(seq_len, cfg.num_kv_heads, head_dim)

        # 3. Rotary Positional Embeddings (RoPE) on Q and K
        q_rot = np.empty_like(q_heads)
        k_rot = np.empty_like(k_heads)
        matmul_module.rope(
            q_heads, q_rot, seq_len, cfg.num_heads, head_dim,
            pos_offset, cfg.rope_freq_base, cfg.rope_neox
        )
        matmul_module.rope(
            k_heads, k_rot, seq_len, cfg.num_kv_heads, head_dim,
            pos_offset, cfg.rope_freq_base, cfg.rope_neox
        )

        # 4 & 5. Update KV cache and execute Grouped-Query Attention (GQA)
        total_kv_len = pos_offset + seq_len
        attn_out_heads = np.empty_like(q_rot)
        kv_present: Optional[Tuple[np.ndarray, np.ndarray]] = None

        if isinstance(kv_cache, KVCacheManager):
            kv_cache.attend(
                q_rot=q_rot,
                k_new=k_rot,
                v_new=v_heads,
                out=attn_out_heads,
                layer_idx=layer_idx,
                q_len=seq_len,
                start_pos=pos_offset,
                num_heads=cfg.num_heads,
                scale=self.scale,
                causal=True,
            )
        elif kv_cache is not None:
            # Zero-copy host buffer path: write in-place at pos_offset and pass full buffer
            # with `total_kv_len` (no slice copy or np.ascontiguousarray allocation).
            k_cache_arr, v_cache_arr = kv_cache
            k_cache_arr[pos_offset:total_kv_len] = k_rot
            v_cache_arr[pos_offset:total_kv_len] = v_heads
            matmul_module.gqa_attention(
                q_rot, k_cache_arr, v_cache_arr, attn_out_heads,
                seq_len, total_kv_len, cfg.num_heads, cfg.num_kv_heads, cfg.head_dim,
                pos_offset, self.scale, True
            )
            kv_present = (k_cache_arr[:total_kv_len], v_cache_arr[:total_kv_len])
        else:
            matmul_module.gqa_attention(
                q_rot, k_rot, v_heads, attn_out_heads,
                seq_len, total_kv_len, cfg.num_heads, cfg.num_kv_heads, cfg.head_dim,
                pos_offset, self.scale, True
            )
            kv_present = (k_rot, v_heads)

        attn_out_flat = attn_out_heads.reshape(seq_len, q_dim)

        # 6 & 7. Output Projection + Fused First Residual + Pre-FFN RMSNorm on GPU
        attn_proj = linear_project(
            attn_out_flat, layer_weights[prefix + "attn_output.weight"], hidden_size
        )
        if (prefix + "attn_output.bias") in layer_weights:
            out_bias = norm_weight_fp16(layer_weights[prefix + "attn_output.bias"])
            attn_proj = (attn_proj.astype(np.float32) + out_bias.astype(np.float32)).astype(np.float16)
        h = np.empty_like(x)
        normed_h = np.empty_like(x)
        matmul_module.rmsnorm_residual(
            x, attn_proj, ffn_norm_w, h, normed_h, seq_len, hidden_size, cfg.rms_norm_eps
        )

        # 8. Feed-Forward Network, selected by the family spec:
        # - gemma: GeGLU over separate gate/up (gelu_tanh(gate) * up; host FP32 path)
        # - phi3:  fused gate+up `ffn_up` (rows = 2*intermediate) -> SwiGLU on the
        #          split halves (same math as separate llama SwiGLU)
        # - llama/qwen2: separate gate/up -> SwiGLU (unchanged)
        if cfg.ffn_act == "geglu":
            gate = linear_project(
                normed_h, layer_weights[prefix + "ffn_gate.weight"], cfg.intermediate_size
            )
            up = linear_project(
                normed_h, layer_weights[prefix + "ffn_up.weight"], cfg.intermediate_size
            )
            ffn_act_out = geglu_host(gate, up)
        elif cfg.ffn_fused_gate_up:
            gate_up = linear_project(
                normed_h, layer_weights[prefix + "ffn_up.weight"], 2 * cfg.intermediate_size
            )
            if (prefix + "ffn_up.bias") in layer_weights:
                gate_up = add_bias_fp32(
                    gate_up, norm_weight_fp16(layer_weights[prefix + "ffn_up.bias"])
                )
            gate = np.ascontiguousarray(gate_up[:, : cfg.intermediate_size])
            up = np.ascontiguousarray(gate_up[:, cfg.intermediate_size :])
            ffn_act_out = np.empty_like(gate)
            matmul_module.swiglu(gate, up, ffn_act_out, seq_len * cfg.intermediate_size)
        else:
            gate = linear_project(
                normed_h, layer_weights[prefix + "ffn_gate.weight"], cfg.intermediate_size
            )
            up = linear_project(
                normed_h, layer_weights[prefix + "ffn_up.weight"], cfg.intermediate_size
            )
            ffn_act_out = np.empty_like(gate)
            matmul_module.swiglu(gate, up, ffn_act_out, seq_len * cfg.intermediate_size)

        down = linear_project(
            ffn_act_out, layer_weights[prefix + "ffn_down.weight"], hidden_size
        )
        if (prefix + "ffn_down.bias") in layer_weights:
            down = add_bias_fp32(
                down, norm_weight_fp16(layer_weights[prefix + "ffn_down.bias"])
            )

        # 9. Second Residual Connection on GPU
        out_hidden = np.empty_like(h)
        matmul_module.residual_add(h, down, out_hidden, seq_len * hidden_size)
        return out_hidden, kv_present

    def forward_streamed(
        self,
        hidden_states: np.ndarray,
        streamer: WeightStreamer,
        layer_idx: int,
        pos_offset: int = 0,
        kv_cache: Optional[KVCacheType] = None,
        prefetch_next: bool = True,
    ) -> Tuple[np.ndarray, Optional[Tuple[np.ndarray, np.ndarray]]]:
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
