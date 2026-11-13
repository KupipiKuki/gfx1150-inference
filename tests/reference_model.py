"""
Independent NumPy FP32 model-family reference for Phase 7C (test tree only).

Deliberately independent of the implementation under test: this module never
imports `layer`, `inference`, `model_spec`, or `matmul_module`. It resolves the
family hyperparameters straight from the GGUF metadata using the *pinned
llama.cpp semantics* (`149f5641b931aaf33697d70f9abc90c3e5300247`,
`src/models/phi3.cpp`, `src/models/gemma.cpp`, `src/llama-graph.cpp`), loads
tensor bytes directly from the synthetic GGUF, and computes the full forward
pass in FP32 NumPy:

- Phi-3: fused `attn_qkv` (+ optional fused or separate biases), NeoX RoPE,
  fused gate+up `ffn_up` (contiguous-half split, silu(first half) * second
  half), optional `ffn_up.bias` / `ffn_down.bias`.
- Gemma: `sqrt(hidden)` embedding scale, GeGLU (`gelu_tanh(gate) * up`,
  tanh-approximation GELU), NeoX RoPE, explicit `attention.key_length` /
  `attention.value_length` head dims, tied output, optional
  `{arch}.final_logit_softcapping` (`c * tanh(logits / c)`).

The only production code used is `src/gguf_parser.py`'s file-format layer
(GGUFParser for header access and the reference-block dequantizers to obtain
weight *values*); no engine graph code is involved.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Mapping

import numpy as np

import os
import sys

_SRC_DIR = os.path.join(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..")), "src"
)
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from gguf_parser import (  # noqa: E402
    GGMLType,
    GGUFParser,
    dequantize_q4_0_cpu,
    dequantize_q4_k_cpu,
    dequantize_q6_k_cpu,
    dequantize_q8_0_cpu,
)


def load_gguf_weights(path: str):
    """Parse a GGUF and return (metadata, {tensor name: FP32 row-major array})."""
    with open(path, "rb") as f:
        buf = f.read()
    gguf = GGUFParser(buf)
    metadata = dict(gguf.metadata)
    weights: Dict[str, np.ndarray] = {}
    for name, info in gguf.tensors.items():
        raw = np.frombuffer(
            buf, dtype=np.uint8, count=info.n_bytes, offset=info.abs_offset
        )
        shape = info.shape_row_major
        if info.ggml_type == GGMLType.F32:
            w = raw.view(np.float32).reshape(shape).astype(np.float32)
        elif info.ggml_type == GGMLType.F16:
            w = raw.view(np.float16).reshape(shape).astype(np.float32)
        elif info.ggml_type == GGMLType.Q4_0:
            w = dequantize_q4_0_cpu(raw, info.n_elements).reshape(shape).astype(np.float32)
        elif info.ggml_type == GGMLType.Q4_K:
            w = dequantize_q4_k_cpu(raw, info.n_elements).reshape(shape).astype(np.float32)
        elif info.ggml_type == GGMLType.Q6_K:
            w = dequantize_q6_k_cpu(raw, info.n_elements).reshape(shape).astype(np.float32)
        elif info.ggml_type == GGMLType.Q8_0:
            w = dequantize_q8_0_cpu(raw, info.n_elements).reshape(shape).astype(np.float32)
        else:
            raise ValueError(f"reference cannot load {name}: {info.ggml_type}")
        weights[name] = w
    return metadata, weights


def _meta(metadata: Mapping[str, Any], arch: str, key: str, default=None):
    akey = f"{arch}.{key}"
    if akey in metadata:
        return metadata[akey]
    lkey = f"llama.{key}"
    if lkey in metadata:
        return metadata[lkey]
    if default is not None:
        return default
    raise KeyError(akey)


def resolve_ref_params(metadata: Mapping[str, Any]) -> Dict[str, Any]:
    """Resolve family hparams from metadata by the pinned llama.cpp semantics."""
    arch = str(metadata.get("general.architecture", "llama")).lower()
    hidden = int(_meta(metadata, arch, "embedding_length"))
    inter = int(_meta(metadata, arch, "feed_forward_length"))
    heads = int(_meta(metadata, arch, "attention.head_count"))
    kv_heads = int(_meta(metadata, arch, "attention.head_count_kv", heads))
    rope_dims = int(_meta(metadata, arch, "rope.dimension_count", hidden // heads))
    key_dim = int(_meta(metadata, arch, "attention.key_length", rope_dims))
    value_dim = int(_meta(metadata, arch, "attention.value_length", key_dim))
    eps = float(_meta(metadata, arch, "attention.layer_norm_rms_epsilon", 1e-5))
    rope_base = float(_meta(metadata, arch, "rope.freq_base", 10000.0))
    layers = int(
        metadata.get(f"{arch}.block_count", metadata.get("llama.block_count", 0))
    )

    neox_key = f"{arch}.rope.neox"
    if neox_key in metadata:
        neox = bool(metadata[neox_key])
    elif "llama.rope.neox" in metadata:
        neox = bool(metadata["llama.rope.neox"])
    else:
        # llama.cpp rope_type: NEOX for phi3/gemma (and qwen2), NORM for llama.
        neox = arch in ("phi3", "gemma", "qwen2", "phi2", "gptneox")

    ffn_act = "geglu" if arch == "gemma" else "swiglu"
    embedding_scale = math.sqrt(hidden) if arch == "gemma" else 1.0
    softcap = metadata.get(f"{arch}.final_logit_softcapping")
    return {
        "arch": arch,
        "num_layers": layers,
        "hidden": hidden,
        "inter": inter,
        "heads": heads,
        "kv_heads": kv_heads,
        "key_dim": key_dim,
        "value_dim": value_dim,
        "eps": eps,
        "rope_base": rope_base,
        "neox": neox,
        "ffn_act": ffn_act,
        "embedding_scale": embedding_scale,
        "final_logit_softcapping": None if softcap is None else float(softcap),
    }


# --- FP32 primitive ops (own implementations; engine code not consulted) ---


def ref_rmsnorm(x: np.ndarray, weight: np.ndarray, eps: float) -> np.ndarray:
    ms = np.mean(x.astype(np.float32) ** 2, axis=-1, keepdims=True)
    normed = x.astype(np.float32) / np.sqrt(ms + eps)
    return normed * weight.astype(np.float32)


def ref_rope(
    x: np.ndarray, pos_offset: int, freq_base: float, neox_style: bool
) -> np.ndarray:
    """Rotate (seq, heads, head_dim) q/k vectors; NeoX pairs (i, i+half)."""
    seq_len, _heads, head_dim = x.shape
    half_dim = head_dim // 2
    x_f32 = x.astype(np.float32)
    out = np.empty_like(x_f32)

    pair_idx = np.arange(half_dim, dtype=np.float32)
    inv_freq = 1.0 / (freq_base ** (2.0 * pair_idx / head_dim))
    positions = np.arange(pos_offset, pos_offset + seq_len, dtype=np.float32)[:, None]
    angles = positions * inv_freq[None, :]
    cos = np.cos(angles)[:, None, :]
    sin = np.sin(angles)[:, None, :]

    if neox_style:
        v0 = x_f32[:, :, :half_dim]
        v1 = x_f32[:, :, half_dim:]
        out[:, :, :half_dim] = v0 * cos - v1 * sin
        out[:, :, half_dim:] = v0 * sin + v1 * cos
    else:
        v0 = x_f32[:, :, 0::2]
        v1 = x_f32[:, :, 1::2]
        out[:, :, 0::2] = v0 * cos - v1 * sin
        out[:, :, 1::2] = v0 * sin + v1 * cos
    return out


def ref_gqa_attention(
    q: np.ndarray, k: np.ndarray, v: np.ndarray, scale: float, causal: bool = True
) -> np.ndarray:
    """(seq, heads, head_dim) x (seq, kv_heads, head_dim) causal attention."""
    seq_len, num_heads, head_dim = q.shape
    _, num_kv_heads, v_head_dim = v.shape
    group = num_heads // num_kv_heads
    out = np.empty((seq_len, num_heads, head_dim), dtype=np.float32)
    for h in range(num_heads):
        kv_h = h // group
        for pos in range(seq_len):
            k_ctx = k[: pos + 1, kv_h, :]  # causal
            v_ctx = v[: pos + 1, kv_h, :]
            scores = (k_ctx @ q[pos, h, :].astype(np.float32)) * scale
            scores = scores - np.max(scores)
            p = np.exp(scores)
            p /= np.sum(p)
            out[pos, h, :] = p @ v_ctx
    return out


def ref_silu(x: np.ndarray) -> np.ndarray:
    x = x.astype(np.float32)
    return x / (1.0 + np.exp(-x))


def ref_swiglu(gate: np.ndarray, up: np.ndarray) -> np.ndarray:
    return (ref_silu(gate) * up.astype(np.float32)).astype(np.float16)


_GELU_COEF_A = 0.044715
_GELU_SQRT_2_OVER_PI = 0.7978845608028654


def ref_gelu_tanh(x: np.ndarray) -> np.ndarray:
    """ggml_gelu_f32: 0.5*x*(1 + tanh(sqrt(2/pi)*x*(1 + 0.044715*x^2)))."""
    x = x.astype(np.float32)
    return 0.5 * x * (
        1.0 + np.tanh(_GELU_SQRT_2_OVER_PI * x * (1.0 + _GELU_COEF_A * x * x))
    )


def ref_geglu(gate: np.ndarray, up: np.ndarray) -> np.ndarray:
    return (ref_gelu_tanh(gate) * up.astype(np.float32)).astype(np.float16)


# --- Full-model FP32 forward ---


def ref_forward(
    weights: Mapping[str, np.ndarray],
    params: Mapping[str, Any],
    token_ids,
) -> np.ndarray:
    """Compute next-token logits (vocab,) in FP32 for `token_ids`."""
    hidden = params["hidden"]
    inter = params["inter"]
    heads = params["heads"]
    kv_heads = params["kv_heads"]
    key_dim = params["key_dim"]
    value_dim = params["value_dim"]
    eps = params["eps"]
    rope_base = params["rope_base"]
    neox = params["neox"]
    q_dim = heads * key_dim
    kv_dim = kv_heads * value_dim
    scale = 1.0 / math.sqrt(value_dim)

    emb = weights["token_embd.weight"][token_ids].astype(np.float32)  # (seq, hidden)
    h = emb * params["embedding_scale"]
    seq_len = h.shape[0]

    for il in range(params["num_layers"]):
        p = f"blk.{il}."
        x = h
        nx = ref_rmsnorm(x, weights[p + "attn_norm.weight"], eps)

        if p + "attn_qkv.weight" in weights:
            qkv = nx @ weights[p + "attn_qkv.weight"].astype(np.float32).T
            if p + "attn_qkv.bias" in weights:
                qkv = qkv + weights[p + "attn_qkv.bias"].astype(np.float32)
            else:
                if p + "attn_q.bias" in weights:
                    qkv[:, :q_dim] += weights[p + "attn_q.bias"].astype(np.float32)
                if p + "attn_k.bias" in weights:
                    qkv[:, q_dim:q_dim + kv_dim] += weights[p + "attn_k.bias"].astype(np.float32)
                if p + "attn_v.bias" in weights:
                    qkv[:, q_dim + kv_dim:] += weights[p + "attn_v.bias"].astype(np.float32)
            q = qkv[:, :q_dim].reshape(seq_len, heads, key_dim)
            k = qkv[:, q_dim:q_dim + kv_dim].reshape(seq_len, kv_heads, key_dim)
            v = qkv[:, q_dim + kv_dim:].reshape(seq_len, kv_heads, value_dim)
        else:
            q = (nx @ weights[p + "attn_q.weight"].astype(np.float32).T).reshape(
                seq_len, heads, key_dim
            )
            k = (nx @ weights[p + "attn_k.weight"].astype(np.float32).T).reshape(
                seq_len, kv_heads, key_dim
            )
            v = (nx @ weights[p + "attn_v.weight"].astype(np.float32).T).reshape(
                seq_len, kv_heads, value_dim
            )
            if p + "attn_q.bias" in weights:
                q = q + weights[p + "attn_q.bias"].astype(np.float32).reshape(1, heads, key_dim)
            if p + "attn_k.bias" in weights:
                k = k + weights[p + "attn_k.bias"].astype(np.float32).reshape(1, kv_heads, key_dim)
            if p + "attn_v.bias" in weights:
                v = v + weights[p + "attn_v.bias"].astype(np.float32).reshape(1, kv_heads, value_dim)

        q = ref_rope(q, pos_offset=0, freq_base=rope_base, neox_style=neox)
        k = ref_rope(k, pos_offset=0, freq_base=rope_base, neox_style=neox)

        attn = ref_gqa_attention(
            q.astype(np.float32), k.astype(np.float32), v.astype(np.float32), scale
        )
        attn_flat = attn.reshape(seq_len, q_dim)
        sa = attn_flat @ weights[p + "attn_output.weight"].astype(np.float32).T
        if p + "attn_output.bias" in weights:
            sa = sa + weights[p + "attn_output.bias"].astype(np.float32)
        sa_out = x + sa

        fn = ref_rmsnorm(sa_out, weights[p + "ffn_norm.weight"], eps)
        if params["ffn_act"] == "geglu":
            gate = fn @ weights[p + "ffn_gate.weight"].astype(np.float32).T
            up = fn @ weights[p + "ffn_up.weight"].astype(np.float32).T
            act = ref_geglu(gate, up).astype(np.float32)
        elif p + "ffn_gate.weight" in weights:
            gate = fn @ weights[p + "ffn_gate.weight"].astype(np.float32).T
            up = fn @ weights[p + "ffn_up.weight"].astype(np.float32).T
            act = ref_swiglu(gate, up).astype(np.float32)
        else:
            # Phi-3 fused gate+up ffn_up: contiguous halves, silu(first) * second.
            up_fused = fn @ weights[p + "ffn_up.weight"].astype(np.float32).T
            if p + "ffn_up.bias" in weights:
                up_fused = up_fused + weights[p + "ffn_up.bias"].astype(np.float32)
            act = (
                ref_silu(up_fused[:, :inter]) * up_fused[:, inter:]
            ).astype(np.float32)

        ff = act @ weights[p + "ffn_down.weight"].astype(np.float32).T
        if p + "ffn_down.bias" in weights:
            ff = ff + weights[p + "ffn_down.bias"].astype(np.float32)
        h = sa_out + ff

    last = ref_rmsnorm(h[-1:, :], weights["output_norm.weight"], eps)
    head_name = "output.weight" if "output.weight" in weights else "token_embd.weight"
    logits = (last @ weights[head_name].astype(np.float32).T).reshape(-1)

    cap = params["final_logit_softcapping"]
    if cap is not None:
        logits = float(cap) * np.tanh(logits / float(cap))
    return logits.astype(np.float32)
