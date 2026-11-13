"""
Shared builder helpers for the Phase 7C spec tests (CPU) and family engine
tests (GPU). No test functions: this module exists so both lanes share one
source of truth for the synthetic metadata/tensor tables.

The metadata and tensor names/shapes mirror the recorded real-GGUF header
dumps in `audit/evidence/G3/7C/header-dumps/`.
"""

from __future__ import annotations

import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, ".."))
for _p in (os.path.join(_ROOT, "src"), _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from gguf_parser import GGMLType, GGUFTensorInfo  # noqa: E402


def info(name, dims, ggml_type=GGMLType.F32):
    """Minimal synthetic GGUFTensorInfo for spec validation tests."""
    dims = tuple(int(d) for d in dims)
    n_elements = int(np.prod(dims))
    block = {GGMLType.F32: (1, 4), GGMLType.F16: (1, 2)}[ggml_type]
    n_bytes = (n_elements // block[0]) * block[1]
    return GGUFTensorInfo(
        name=name, dims=dims, ggml_type=ggml_type,
        rel_offset=0, abs_offset=0, n_elements=n_elements, n_bytes=n_bytes,
    )


def phi3_metadata(num_layers=2, hidden=64, inter=128, heads=4, kv_heads=2,
                  head_dim=16):
    return {
        "general.architecture": "phi3",
        "phi3.block_count": num_layers,
        "phi3.embedding_length": hidden,
        "phi3.feed_forward_length": inter,
        "phi3.attention.head_count": heads,
        "phi3.attention.head_count_kv": kv_heads,
        "phi3.rope.dimension_count": head_dim,
        "phi3.attention.layer_norm_rms_epsilon": 1e-5,
        "phi3.rope.freq_base": 10000.0,
        "phi3.vocab_size": 50,
    }


def phi3_tensors(fused=True, hidden=64, inter=128, heads=4, kv_heads=2,
                 head_dim=16, num_layers=2):
    q_dim, kv_dim = heads * head_dim, kv_heads * head_dim
    tensors = {
        "token_embd.weight": info("token_embd.weight", (hidden, 50)),
        "output_norm.weight": info("output_norm.weight", (hidden,)),
    }
    for il in range(num_layers):
        p = f"blk.{il}."
        tensors[p + "attn_norm.weight"] = info(p + "attn_norm.weight", (hidden,))
        tensors[p + "ffn_norm.weight"] = info(p + "ffn_norm.weight", (hidden,))
        tensors[p + "attn_output.weight"] = info(p + "attn_output.weight", (q_dim, hidden))
        tensors[p + "ffn_down.weight"] = info(p + "ffn_down.weight", (inter, hidden))
        tensors[p + "ffn_up.weight"] = info(p + "ffn_up.weight", (hidden, 2 * inter))
        if fused:
            tensors[p + "attn_qkv.weight"] = info(
                p + "attn_qkv.weight", (hidden, q_dim + 2 * kv_dim)
            )
        else:
            tensors[p + "attn_q.weight"] = info(p + "attn_q.weight", (hidden, q_dim))
            tensors[p + "attn_k.weight"] = info(p + "attn_k.weight", (hidden, kv_dim))
            tensors[p + "attn_v.weight"] = info(p + "attn_v.weight", (hidden, kv_dim))
    return tensors


def gemma_metadata(num_layers=2, hidden=96, inter=192, heads=4, kv_heads=2,
                   key_dim=32, value_dim=32, eps=1e-6, softcap=None):
    meta = {
        "general.architecture": "gemma",
        "gemma.block_count": num_layers,
        "gemma.embedding_length": hidden,
        "gemma.feed_forward_length": inter,
        "gemma.attention.head_count": heads,
        "gemma.attention.head_count_kv": kv_heads,
        "gemma.attention.key_length": key_dim,
        "gemma.attention.value_length": value_dim,
        "gemma.attention.layer_norm_rms_epsilon": eps,
        "gemma.vocab_size": 50,
    }
    if softcap is not None:
        meta["gemma.final_logit_softcapping"] = softcap
    return meta


def gemma_tensors(hidden=96, inter=192, heads=4, kv_heads=2, key_dim=32,
                  value_dim=32, num_layers=2):
    q_dim, kv_dim = heads * key_dim, kv_heads * value_dim
    tensors = {
        "token_embd.weight": info("token_embd.weight", (hidden, 50)),
        "output_norm.weight": info("output_norm.weight", (hidden,)),
    }
    for il in range(num_layers):
        p = f"blk.{il}."
        tensors[p + "attn_norm.weight"] = info(p + "attn_norm.weight", (hidden,))
        tensors[p + "ffn_norm.weight"] = info(p + "ffn_norm.weight", (hidden,))
        tensors[p + "attn_q.weight"] = info(p + "attn_q.weight", (hidden, q_dim))
        tensors[p + "attn_k.weight"] = info(p + "attn_k.weight", (hidden, kv_dim))
        tensors[p + "attn_v.weight"] = info(p + "attn_v.weight", (hidden, kv_dim))
        tensors[p + "attn_output.weight"] = info(p + "attn_output.weight", (q_dim, hidden))
        tensors[p + "ffn_gate.weight"] = info(p + "ffn_gate.weight", (hidden, inter))
        tensors[p + "ffn_up.weight"] = info(p + "ffn_up.weight", (hidden, inter))
        tensors[p + "ffn_down.weight"] = info(p + "ffn_down.weight", (inter, hidden))
    return tensors


def qwen2_metadata_and_tensors(num_layers=1, hidden=64, inter=128, heads=4,
                               kv_heads=2):
    """qwen2 (llama-family layout alias) metadata + tensor table with one bias."""
    q_dim, kv_dim = heads * (hidden // heads), kv_heads * (hidden // heads)
    meta = {
        "general.architecture": "qwen2",
        "qwen2.block_count": num_layers,
        "qwen2.embedding_length": hidden,
        "qwen2.feed_forward_length": inter,
        "qwen2.attention.head_count": heads,
        "qwen2.attention.head_count_kv": kv_heads,
        "qwen2.vocab_size": 50,
        "qwen2.attention.layer_norm_rms_epsilon": 1e-6,
    }
    tensors = {
        "token_embd.weight": info("token_embd.weight", (hidden, 50)),
        "output_norm.weight": info("output_norm.weight", (hidden,)),
        "blk.0.attn_norm.weight": info("blk.0.attn_norm.weight", (hidden,)),
        "blk.0.attn_q.weight": info("blk.0.attn_q.weight", (hidden, q_dim)),
        "blk.0.attn_k.weight": info("blk.0.attn_k.weight", (hidden, kv_dim)),
        "blk.0.attn_v.weight": info("blk.0.attn_v.weight", (hidden, kv_dim)),
        "blk.0.attn_q.bias": info("blk.0.attn_q.bias", (q_dim,)),
        "blk.0.attn_output.weight": info("blk.0.attn_output.weight", (q_dim, hidden)),
        "blk.0.ffn_norm.weight": info("blk.0.ffn_norm.weight", (hidden,)),
        "blk.0.ffn_gate.weight": info("blk.0.ffn_gate.weight", (hidden, inter)),
        "blk.0.ffn_up.weight": info("blk.0.ffn_up.weight", (hidden, inter)),
        "blk.0.ffn_down.weight": info("blk.0.ffn_down.weight", (inter, hidden)),
    }
    return meta, tensors
