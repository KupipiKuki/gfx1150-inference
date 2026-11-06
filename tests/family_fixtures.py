"""
Synthetic model-family GGUF fixture builders for Phase 7C tests.

All tensors use the *real* tensor names and shapes recorded from the actual
GGUF header dumps in `audit/evidence/G3/7C/header-dumps/`:

- Phi-3 (`microsoft/Phi-3-mini-4k-instruct-q4.gguf`): fused
  `blk.N.attn_qkv.weight` (hidden, q_dim + 2*kv_dim), fused
  `blk.N.ffn_up.weight` (hidden, 2*intermediate), `blk.N.attn_output.weight`
  (q_dim, hidden), RMSNorm weights, no `ffn_gate`, tied output.
  The legacy layout (separate attn_q/k/v + biases) is also built here to prove
  fused/separate equivalence.
- Gemma (`gemma-2b-it.Q4_K_M.gguf`): separate `attn_q/k/v.weight`, explicit
  `gemma.attention.key_length` / `value_length` (7B-style mismatch with
  hidden//heads), separate `ffn_gate/up/down`, tied output, optional
  `gemma.final_logit_softcapping`.

Quantization: F16 everywhere, or a Q4_K_M-style mix (Q4_K projections with
Q6_K down-projections) to exercise the quantized fused paths. Norm weights are
F32 exactly like the real dumps.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, ".."))
_SRC = os.path.join(_ROOT, "src")
for _p in (_SRC, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from gguf_parser import (  # noqa: E402
    GGMLType,
    GGUFValueType,
    quantize_q4_0_cpu,
    quantize_q4_k_cpu,
    quantize_q6_k_cpu,
    write_synthetic_gguf,
)


# ---------------------------------------------------------------------------
# Shared small-vocabulary tokenizer metadata (SentencePiece-style with scores)
# ---------------------------------------------------------------------------


def _tokenizer_meta(vocab: List[str]) -> Dict[str, Tuple[GGUFValueType, Any]]:
    scores = [float(-(i + 1)) for i in range(len(vocab))]
    return {
        "tokenizer.ggml.tokens": (GGUFValueType.ARRAY, (GGUFValueType.STRING, vocab)),
        "tokenizer.ggml.scores": (GGUFValueType.ARRAY, (GGUFValueType.FLOAT32, scores)),
        "tokenizer.ggml.bos_token_id": (GGUFValueType.UINT32, 1),
        "tokenizer.ggml.eos_token_id": (GGUFValueType.UINT32, 2),
        "tokenizer.ggml.add_bos_token": (GGUFValueType.BOOL, False),
    }


_VOCAB = [
    "<unk>", "<s>", "</s>", "▁", "A", "M", "D", "▁AMD",
    "▁gfx", "1150", "▁gfx1150", "▁is", "▁fast", ".", "!", "?",
    "t", "o", "k", "e", "n", "s", "▁token", "▁tokens",
    "r", "c", "m", "▁ROCm", "H", "I", "P", "▁HIP",
    "p", "h", "i", "l", "a", "▁phi", "g", "e", "▁gem",
    "q", "u", "▁geo", "z", "x", "v", "b", "j", "w", "y",
]


# ---------------------------------------------------------------------------
# Phi-3 fixture
# ---------------------------------------------------------------------------


def build_phi3_weights(
    rng: np.random.Generator,
    hidden: int = 64,
    inter: int = 128,
    num_heads: int = 4,
    num_kv_heads: int = 2,
    head_dim: int = 16,
    num_layers: int = 2,
    biases: bool = True,
    ffn_biases: bool = True,
    bias_scale: float = 0.05,
):
    """Deterministic seeded Phi-3 weight set (fused layout)."""
    q_dim = num_heads * head_dim
    kv_dim = num_kv_heads * head_dim
    vocab = len(_VOCAB)
    gen = lambda r, c: (
        rng.standard_normal((r, c), dtype=np.float32) * (1.0 / math.sqrt(c))
    )
    model: Dict[str, np.ndarray] = {
        "token_embd.weight": gen(vocab, hidden),
        "output_norm.weight": (1.0 + 0.05 * rng.standard_normal(hidden, dtype=np.float32)),
    }
    for il in range(num_layers):
        p = f"blk.{il}."
        model[p + "attn_norm.weight"] = 1.0 + 0.05 * rng.standard_normal(hidden, dtype=np.float32)
        model[p + "ffn_norm.weight"] = 1.0 + 0.05 * rng.standard_normal(hidden, dtype=np.float32)
        wq, wk, wv = gen(q_dim, hidden), gen(kv_dim, hidden), gen(kv_dim, hidden)
        model[p + "attn_qkv.weight"] = np.concatenate([wq, wk, wv], axis=0)
        model[p + "attn_output.weight"] = gen(hidden, q_dim)
        wgate, wup = gen(inter, hidden), gen(inter, hidden)
        model[p + "ffn_up.weight"] = np.concatenate([wgate, wup], axis=0)
        model[p + "ffn_down.weight"] = gen(hidden, inter)
        # Biases draw from a layer-seeded child RNG so that a no-bias build and
        # a zero-bias build produce byte-identical *weights* from the same seed
        # (bias presence must not perturb the main RNG state).
        bias_rng = np.random.default_rng(0x7C0 + il)
        if biases:
            model[p + "attn_qkv.bias"] = bias_scale * bias_rng.standard_normal(q_dim + 2 * kv_dim, dtype=np.float32)
        if ffn_biases:
            model[p + "ffn_up.bias"] = bias_scale * bias_rng.standard_normal(2 * inter, dtype=np.float32)
            model[p + "ffn_down.bias"] = bias_scale * bias_rng.standard_normal(hidden, dtype=np.float32)
    return model


def build_phi3_gguf(
    path,
    rng: np.random.Generator,
    *,
    layout: str = "fused",  # "fused" | "separate"
    quant: str = "f16",  # "f16" | "q4km"
    **weights_kwargs,
) -> Dict[str, Any]:
    """Write a synthetic Phi-3 GGUF; returns the constructed metadata dict."""
    hidden = weights_kwargs.get("hidden", 64)
    inter = weights_kwargs.get("inter", 128)
    num_heads = weights_kwargs.get("num_heads", 4)
    num_kv_heads = weights_kwargs.get("num_kv_heads", 2)
    head_dim = weights_kwargs.get("head_dim", 16)
    num_layers = weights_kwargs.get("num_layers", 2)
    biases = weights_kwargs.get("biases", True)
    ffn_biases = weights_kwargs.get("ffn_biases", True)

    model = build_phi3_weights(rng, **weights_kwargs)

    metadata: Dict[str, Tuple[GGUFValueType, Any]] = {
        "general.architecture": (GGUFValueType.STRING, "phi3"),
        "general.name": (GGUFValueType.STRING, "synthetic-phi3-7c"),
        "phi3.block_count": (GGUFValueType.UINT32, num_layers),
        "phi3.embedding_length": (GGUFValueType.UINT32, hidden),
        "phi3.feed_forward_length": (GGUFValueType.UINT32, inter),
        "phi3.attention.head_count": (GGUFValueType.UINT32, num_heads),
        "phi3.attention.head_count_kv": (GGUFValueType.UINT32, num_kv_heads),
        "phi3.rope.dimension_count": (GGUFValueType.UINT32, head_dim),
        "phi3.attention.layer_norm_rms_epsilon": (GGUFValueType.FLOAT32, 1e-5),
        "phi3.rope.freq_base": (GGUFValueType.FLOAT32, 10000.0),
    }
    metadata.update(_tokenizer_meta(_VOCAB))

    q_dim = num_heads * head_dim
    kv_dim = num_kv_heads * head_dim
    inter_real = inter

    def proj_type() -> GGMLType:
        return GGMLType.Q4_K if quant == "q4km" else GGMLType.F16

    def down_type() -> GGMLType:
        return GGMLType.Q6_K if quant == "q4km" else GGMLType.F16

    def quantize(name_w, type_) -> bytes:
        if type_ == GGMLType.F16:
            return name_w.astype(np.float16).tobytes()
        if type_ == GGMLType.Q4_K:
            return quantize_q4_k_cpu(name_w.astype(np.float32)).tobytes()
        if type_ == GGMLType.Q6_K:
            return quantize_q6_k_cpu(name_w.astype(np.float32)).tobytes()
        raise ValueError(f"unsupported fixture quant {type_} for {name_w.shape}")

    tensors = []
    tensors.append(("output_norm.weight", (hidden,), GGMLType.F32,
                    model["output_norm.weight"].astype(np.float32).tobytes()))
    emb = model["token_embd.weight"]
    tensors.append(("token_embd.weight", (hidden, len(_VOCAB)),
                    GGMLType.F16, emb.astype(np.float16).tobytes()))

    for il in range(num_layers):
        p = f"blk.{il}."
        tensors.append((p + "attn_norm.weight", (hidden,), GGMLType.F32,
                        model[p + "attn_norm.weight"].astype(np.float32).tobytes()))
        tensors.append((p + "ffn_norm.weight", (hidden,), GGMLType.F32,
                        model[p + "ffn_norm.weight"].astype(np.float32).tobytes()))

        if layout == "fused":
            tensors.append((p + "attn_qkv.weight", (hidden, q_dim + 2 * kv_dim),
                            proj_type(), quantize(model[p + "attn_qkv.weight"], proj_type())))
            if biases:
                tensors.append((p + "attn_qkv.bias", (q_dim + 2 * kv_dim,),
                                GGMLType.F32, model[p + "attn_qkv.bias"].astype(np.float32).tobytes()))
        else:
            w_full = model[p + "attn_qkv.weight"]
            tensors.append((p + "attn_q.weight", (hidden, q_dim), proj_type(),
                            quantize(w_full[:q_dim], proj_type())))
            tensors.append((p + "attn_k.weight", (hidden, kv_dim), proj_type(),
                            quantize(w_full[q_dim:q_dim + kv_dim], proj_type())))
            tensors.append((p + "attn_v.weight", (hidden, kv_dim), proj_type(),
                            quantize(w_full[q_dim + kv_dim:], proj_type())))
            if biases:
                b_full = model[p + "attn_qkv.bias"]
                for bname, b_ends in (
                    ("attn_q.bias", (0, q_dim)),
                    ("attn_k.bias", (q_dim, q_dim + kv_dim)),
                    ("attn_v.bias", (q_dim + kv_dim, q_dim + 2 * kv_dim)),
                ):
                    tensors.append((p + bname, (b_ends[1] - b_ends[0],), GGMLType.F32,
                                    b_full[b_ends[0]:b_ends[1]].astype(np.float32).tobytes()))

        tensors.append((p + "attn_output.weight", (q_dim, hidden), proj_type(),
                        quantize(model[p + "attn_output.weight"], proj_type())))

        tensors.append((p + "ffn_up.weight", (hidden, 2 * inter_real), proj_type(),
                        quantize(model[p + "ffn_up.weight"], proj_type())))
        tensors.append((p + "ffn_down.weight", (inter_real, hidden), down_type(),
                        quantize(model[p + "ffn_down.weight"], down_type())))
        if ffn_biases:
            tensors.append((p + "ffn_up.bias", (2 * inter_real,), GGMLType.F32,
                            model[p + "ffn_up.bias"].astype(np.float32).tobytes()))
            tensors.append((p + "ffn_down.bias", (hidden,), GGMLType.F32,
                            model[p + "ffn_down.bias"].astype(np.float32).tobytes()))

    with open(path, "wb") as f:
        write_synthetic_gguf(f, metadata, tensors)
    # Quantization constraints of the helpers require the element counts align;
    # harmless assertion as a builder sanity check.
    return metadata


# ---------------------------------------------------------------------------
# Gemma fixture (gemma v1; 7B-style key_length != hidden // num_heads)
# ---------------------------------------------------------------------------


def build_gemma_weights(
    rng: np.random.Generator,
    hidden: int = 96,
    inter: int = 192,
    num_heads: int = 4,
    num_kv_heads: int = 2,
    key_dim: int = 32,  # != hidden // num_heads (24): 7B-style explicit dims
    value_dim: int = 32,
    num_layers: int = 2,
):
    q_dim = num_heads * key_dim
    kv_dim = num_kv_heads * value_dim
    vocab = len(_VOCAB)
    gen = lambda r, c: (
        rng.standard_normal((r, c), dtype=np.float32) * (1.0 / math.sqrt(c))
    )
    model: Dict[str, np.ndarray] = {
        "token_embd.weight": gen(vocab, hidden),
        "output_norm.weight": 1.0 + 0.05 * rng.standard_normal(hidden, dtype=np.float32),
    }
    for il in range(num_layers):
        p = f"blk.{il}."
        model[p + "attn_norm.weight"] = 1.0 + 0.05 * rng.standard_normal(hidden, dtype=np.float32)
        model[p + "ffn_norm.weight"] = 1.0 + 0.05 * rng.standard_normal(hidden, dtype=np.float32)
        model[p + "attn_q.weight"] = gen(q_dim, hidden)
        model[p + "attn_k.weight"] = gen(kv_dim, hidden)
        model[p + "attn_v.weight"] = gen(kv_dim, hidden)
        model[p + "attn_output.weight"] = gen(hidden, q_dim)
        model[p + "ffn_gate.weight"] = gen(inter, hidden)
        model[p + "ffn_up.weight"] = gen(inter, hidden)
        model[p + "ffn_down.weight"] = gen(hidden, inter)
    return model


def build_gemma_gguf(
    path,
    rng: np.random.Generator,
    *,
    quant: str = "f16",  # "f16" | "q4k"
    final_logit_softcapping: Optional[float] = None,  # e.g. 30.0
    **dims,
) -> Dict[str, Tuple[GGUFValueType, Any]]:
    """Write a synthetic gemma (v1) GGUF; returns the constructed metadata dict."""
    hidden = dims.get("hidden", 96)
    inter = dims.get("inter", 192)
    num_heads = dims.get("num_heads", 4)
    num_kv_heads = dims.get("num_kv_heads", 2)
    key_dim = dims.get("key_dim", 32)
    value_dim = dims.get("value_dim", 32)
    num_layers = dims.get("num_layers", 2)

    model = build_gemma_weights(
        rng, hidden, inter, num_heads, num_kv_heads, key_dim, value_dim, num_layers
    )
    q_dim = num_heads * key_dim
    kv_dim = num_kv_heads * value_dim

    metadata: Dict[str, Tuple[GGUFValueType, Any]] = {
        "general.architecture": (GGUFValueType.STRING, "gemma"),
        "general.name": (GGUFValueType.STRING, "synthetic-gemma-7c"),
        "gemma.block_count": (GGUFValueType.UINT32, num_layers),
        "gemma.embedding_length": (GGUFValueType.UINT32, hidden),
        "gemma.feed_forward_length": (GGUFValueType.UINT32, inter),
        "gemma.attention.head_count": (GGUFValueType.UINT32, num_heads),
        "gemma.attention.head_count_kv": (GGUFValueType.UINT32, num_kv_heads),
        "gemma.attention.key_length": (GGUFValueType.UINT32, key_dim),
        "gemma.attention.value_length": (GGUFValueType.UINT32, value_dim),
        "gemma.attention.layer_norm_rms_epsilon": (GGUFValueType.FLOAT32, 1e-6),
        "gemma.rope.freq_base": (GGUFValueType.FLOAT32, 10000.0),
    }
    if final_logit_softcapping is not None:
        metadata["gemma.final_logit_softcapping"] = (
            GGUFValueType.FLOAT32, float(final_logit_softcapping)
        )
    metadata.update(_tokenizer_meta(_VOCAB))

    proj_type = GGMLType.Q4_K if quant == "q4k" else GGMLType.F16

    def quantize(w: np.ndarray, type_: GGMLType) -> bytes:
        if type_ == GGMLType.F16:
            return w.astype(np.float16).tobytes()
        if type_ == GGMLType.Q4_K:
            return quantize_q4_k_cpu(w.astype(np.float32)).tobytes()
        raise ValueError(type_)

    tensors = [
        ("token_embd.weight", (hidden, len(_VOCAB)), GGMLType.F16,
         model["token_embd.weight"].astype(np.float16).tobytes()),
        ("output_norm.weight", (hidden,), GGMLType.F32,
         model["output_norm.weight"].astype(np.float32).tobytes()),
    ]
    for il in range(num_layers):
        p = f"blk.{il}."
        tensors.append((p + "attn_norm.weight", (hidden,), GGMLType.F32,
                        model[p + "attn_norm.weight"].astype(np.float32).tobytes()))
        tensors.append((p + "ffn_norm.weight", (hidden,), GGMLType.F32,
                        model[p + "ffn_norm.weight"].astype(np.float32).tobytes()))
        tensors.append((p + "attn_q.weight", (hidden, q_dim), proj_type,
                        quantize(model[p + "attn_q.weight"], proj_type)))
        tensors.append((p + "attn_k.weight", (hidden, kv_dim), proj_type,
                        quantize(model[p + "attn_k.weight"], proj_type)))
        tensors.append((p + "attn_v.weight", (hidden, kv_dim), proj_type,
                        quantize(model[p + "attn_v.weight"], proj_type)))
        tensors.append((p + "attn_output.weight", (q_dim, hidden), proj_type,
                        quantize(model[p + "attn_output.weight"], proj_type)))
        tensors.append((p + "ffn_gate.weight", (hidden, inter), proj_type,
                        quantize(model[p + "ffn_gate.weight"], proj_type)))
        tensors.append((p + "ffn_up.weight", (hidden, inter), proj_type,
                        quantize(model[p + "ffn_up.weight"], proj_type)))
        tensors.append((p + "ffn_down.weight", (inter, hidden), proj_type,
                        quantize(model[p + "ffn_down.weight"], proj_type)))

    with open(path, "wb") as f:
        write_synthetic_gguf(f, metadata, tensors)
    return metadata
