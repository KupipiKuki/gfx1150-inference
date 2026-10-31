#!/usr/bin/env python3
"""
Phase 3 Test Suite:
1. HIP `rmsnorm` kernel accuracy vs FP32 reference
2. HIP `rope` (Rotary Positional Embeddings) kernel accuracy (adjacent & NeoX styles, prefill & offset decode)
3. HIP `gqa_attention` (Grouped-Query Attention with online softmax) accuracy (causal prefill & KV-cached decode)
4. HIP `swiglu` activation kernel accuracy
5. End-to-end `TransformerLayer` forward pass streamed from a GGUF v3 file (`Q4_0` weights + `madvise` eviction)
"""

import math
import os
import sys
import tempfile
import numpy as np

_ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_SRC_DIR = os.path.join(_ROOT_DIR, "src")
_BUILD_DIR = os.path.join(_ROOT_DIR, "build")

for _p in (_SRC_DIR, _BUILD_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from gguf_parser import (
    GGMLType,
    GGUFValueType,
    dequantize_q4_0_cpu,
    quantize_q4_0_cpu,
    write_synthetic_gguf,
)
from weight_loader import WeightStreamer
from layer import LlamaLayerConfig, TransformerLayer
import matmul_module


def ref_rmsnorm(x: np.ndarray, weight: np.ndarray, eps: float = 1e-5) -> np.ndarray:
    x_f32 = x.astype(np.float32)
    w_f32 = weight.astype(np.float32)
    rms = np.sqrt(np.mean(x_f32 * x_f32, axis=-1, keepdims=True) + eps)
    return ((x_f32 / rms) * w_f32).astype(np.float16)


def ref_rope(
    x: np.ndarray,
    pos_offset: int = 0,
    freq_base: float = 10000.0,
    neox_style: bool = False,
) -> np.ndarray:
    seq_len, num_heads, head_dim = x.shape
    half_dim = head_dim // 2
    x_f32 = x.astype(np.float32)
    out = np.empty_like(x_f32)

    pair_idx = np.arange(half_dim, dtype=np.float32)
    inv_freq = 1.0 / (freq_base ** (2.0 * pair_idx / head_dim))
    positions = np.arange(pos_offset, pos_offset + seq_len, dtype=np.float32)[:, None]
    angles = positions * inv_freq[None, :]  # (seq_len, half_dim)
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

    return out.astype(np.float16)


def ref_gqa_attention(
    Q: np.ndarray,
    K: np.ndarray,
    V: np.ndarray,
    start_pos: int = 0,
    scale: float = 0.0,
    causal: bool = True,
) -> np.ndarray:
    q_len, num_heads, head_dim = Q.shape
    kv_len, num_kv_heads, _ = K.shape
    group_size = num_heads // num_kv_heads
    if scale == 0.0:
        scale = 1.0 / math.sqrt(head_dim)

    q_f32 = Q.astype(np.float32)
    k_f32 = K.astype(np.float32)
    v_f32 = V.astype(np.float32)
    out = np.zeros_like(q_f32)

    for m in range(q_len):
        max_kv = min(kv_len, start_pos + m + 1) if causal else kv_len
        for h in range(num_heads):
            kv_h = h // group_size
            scores = (k_f32[:max_kv, kv_h, :] @ q_f32[m, h, :]) * scale
            scores -= np.max(scores)
            probs = np.exp(scores)
            probs /= np.sum(probs)
            out[m, h, :] = probs @ v_f32[:max_kv, kv_h, :]

    return out.astype(np.float16)


def ref_swiglu(gate: np.ndarray, up: np.ndarray) -> np.ndarray:
    g = gate.astype(np.float32)
    u = up.astype(np.float32)
    silu = g / (1.0 + np.exp(-g))
    return (silu * u).astype(np.float16)


def test_rmsnorm_kernel() -> bool:
    print("\n=== 1. Testing HIP `rmsnorm` Kernel ===")
    rng = np.random.default_rng(10)
    for M, K in [(1, 4096), (16, 2048), (7, 1024)]:
        x = rng.standard_normal((M, K), dtype=np.float32).astype(np.float16)
        w = (1.0 + 0.1 * rng.standard_normal((K,), dtype=np.float32)).astype(np.float16)
        out_gpu = np.zeros_like(x)
        out_ref = ref_rmsnorm(x, w, 1e-5)

        matmul_module.rmsnorm(x, w, out_gpu, M, K, 1e-5)
        max_err = float(np.max(np.abs(out_gpu.astype(np.float32) - out_ref.astype(np.float32))))
        print(f"  rmsnorm ({M}x{K}): max_err={max_err:.6f}")
        if max_err >= 2e-3:
            print("❌ FAIL")
            return False
    print("✅ PASS: HIP rmsnorm matches CPU FP32 reference")
    return True


def test_rope_kernel() -> bool:
    print("\n=== 2. Testing HIP `rope` Kernel ===")
    rng = np.random.default_rng(20)
    for neox in (False, True):
        for seq_len, pos_offset in [(8, 0), (1, 17)]:
            num_heads, head_dim = 16, 64
            x = rng.standard_normal((seq_len, num_heads, head_dim), dtype=np.float32).astype(np.float16)
            out_gpu = np.zeros_like(x)
            out_ref = ref_rope(x, pos_offset=pos_offset, freq_base=10000.0, neox_style=neox)

            matmul_module.rope(x, out_gpu, seq_len, num_heads, head_dim, pos_offset, 10000.0, neox)
            max_err = float(np.max(np.abs(out_gpu.astype(np.float32) - out_ref.astype(np.float32))))
            style_name = "NeoX" if neox else "GGUF-Llama"
            print(f"  rope ({style_name}, seq={seq_len}, offset={pos_offset}): max_err={max_err:.6f}")
            if max_err >= 2e-3:
                print("❌ FAIL")
                return False
    print("✅ PASS: HIP rope matches CPU FP32 reference")
    return True


def test_gqa_attention_kernel() -> bool:
    print("\n=== 3. Testing HIP `gqa_attention` Kernel (GQA 4:1, Prefill & Decode) ===")
    rng = np.random.default_rng(30)
    num_heads, num_kv_heads, head_dim = 16, 4, 64
    scale = 1.0 / math.sqrt(head_dim)

    # Case A: Causal prompt prefill (q_len=12, kv_len=12, start_pos=0)
    # Case B: Single-token KV-cache decode (q_len=1, kv_len=25, start_pos=24)
    for q_len, kv_len, start_pos in [(12, 12, 0), (1, 25, 24)]:
        Q = (rng.standard_normal((q_len, num_heads, head_dim), dtype=np.float32) * 0.5).astype(np.float16)
        K = (rng.standard_normal((kv_len, num_kv_heads, head_dim), dtype=np.float32) * 0.5).astype(np.float16)
        V = (rng.standard_normal((kv_len, num_kv_heads, head_dim), dtype=np.float32) * 0.5).astype(np.float16)

        out_gpu = np.zeros_like(Q)
        out_ref = ref_gqa_attention(Q, K, V, start_pos=start_pos, scale=scale, causal=True)

        matmul_module.gqa_attention(
            Q, K, V, out_gpu,
            q_len, kv_len, num_heads, num_kv_heads, head_dim,
            start_pos, scale, True
        )
        max_err = float(np.max(np.abs(out_gpu.astype(np.float32) - out_ref.astype(np.float32))))
        mode = "Prefill" if q_len > 1 else "KV-Decode"
        print(f"  gqa_attention ({mode}, q={q_len}, kv={kv_len}): max_err={max_err:.6f}")
        if max_err >= 2e-3:
            print("❌ FAIL")
            return False

    print("✅ PASS: HIP gqa_attention matches CPU online softmax reference")
    return True


def test_swiglu_kernel() -> bool:
    print("\n=== 4. Testing HIP `swiglu` Kernel ===")
    rng = np.random.default_rng(40)
    n = 16 * 1024
    gate = rng.standard_normal(n, dtype=np.float32).astype(np.float16)
    up = rng.standard_normal(n, dtype=np.float32).astype(np.float16)
    out_gpu = np.zeros_like(gate)
    out_ref = ref_swiglu(gate, up)

    matmul_module.swiglu(gate, up, out_gpu, n)
    max_err = float(np.max(np.abs(out_gpu.astype(np.float32) - out_ref.astype(np.float32))))
    print(f"  swiglu ({n} elements): max_err={max_err:.6f}")
    if max_err < 2e-3:
        print("✅ PASS: HIP swiglu matches CPU reference")
        return True
    print("❌ FAIL")
    return False


def test_end_to_end_transformer_layer() -> bool:
    print("\n=== 5. Testing End-to-End Streamed `TransformerLayer` (Prefill + KV Decode) ===")
    rng = np.random.default_rng(50)

    hidden_size = 256
    intermediate_size = 512
    num_heads = 8
    num_kv_heads = 2  # 4:1 GQA
    head_dim = 32
    q_dim = num_heads * head_dim
    kv_dim = num_kv_heads * head_dim
    eps = 1e-5

    def _rand_q4_weight(out_dim: int, in_dim: int):
        w_f32 = rng.standard_normal((out_dim, in_dim), dtype=np.float32) * (1.0 / math.sqrt(in_dim))
        q4 = quantize_q4_0_cpu(w_f32)
        deq = dequantize_q4_0_cpu(q4, out_dim * in_dim).reshape(out_dim, in_dim)
        return q4, deq

    wq_q4, wq_deq = _rand_q4_weight(q_dim, hidden_size)
    wk_q4, wk_deq = _rand_q4_weight(kv_dim, hidden_size)
    wv_q4, wv_deq = _rand_q4_weight(kv_dim, hidden_size)
    wo_q4, wo_deq = _rand_q4_weight(hidden_size, q_dim)

    wgate_q4, wgate_deq = _rand_q4_weight(intermediate_size, hidden_size)
    wup_q4, wup_deq = _rand_q4_weight(intermediate_size, hidden_size)
    wdown_q4, wdown_deq = _rand_q4_weight(hidden_size, intermediate_size)

    attn_norm_w = (1.0 + 0.05 * rng.standard_normal(hidden_size, dtype=np.float32)).astype(np.float16)
    ffn_norm_w = (1.0 + 0.05 * rng.standard_normal(hidden_size, dtype=np.float32)).astype(np.float16)

    metadata = {
        "general.architecture": (GGUFValueType.STRING, "llama"),
        "llama.block_count": (GGUFValueType.UINT32, 1),
        "llama.embedding_length": (GGUFValueType.UINT32, hidden_size),
        "llama.feed_forward_length": (GGUFValueType.UINT32, intermediate_size),
        "llama.attention.head_count": (GGUFValueType.UINT32, num_heads),
        "llama.attention.head_count_kv": (GGUFValueType.UINT32, num_kv_heads),
        "llama.rope.dimension_count": (GGUFValueType.UINT32, head_dim),
        "llama.attention.layer_norm_rms_epsilon": (GGUFValueType.FLOAT32, eps),
        "llama.rope.freq_base": (GGUFValueType.FLOAT32, 10000.0),
    }

    tensors = [
        ("blk.0.attn_norm.weight", (hidden_size,), GGMLType.F16, attn_norm_w.tobytes()),
        ("blk.0.attn_q.weight", (hidden_size, q_dim), GGMLType.Q4_0, wq_q4.tobytes()),
        ("blk.0.attn_k.weight", (hidden_size, kv_dim), GGMLType.Q4_0, wk_q4.tobytes()),
        ("blk.0.attn_v.weight", (hidden_size, kv_dim), GGMLType.Q4_0, wv_q4.tobytes()),
        ("blk.0.attn_output.weight", (q_dim, hidden_size), GGMLType.Q4_0, wo_q4.tobytes()),
        ("blk.0.ffn_norm.weight", (hidden_size,), GGMLType.F16, ffn_norm_w.tobytes()),
        ("blk.0.ffn_gate.weight", (hidden_size, intermediate_size), GGMLType.Q4_0, wgate_q4.tobytes()),
        ("blk.0.ffn_up.weight", (hidden_size, intermediate_size), GGMLType.Q4_0, wup_q4.tobytes()),
        ("blk.0.ffn_down.weight", (intermediate_size, hidden_size), GGMLType.Q4_0, wdown_q4.tobytes()),
    ]

    with tempfile.NamedTemporaryFile(suffix=".gguf", delete=False) as tmp:
        tmp_path = tmp.name
        write_synthetic_gguf(tmp, metadata, tensors)

    def _cpu_layer_ref(x_seq: np.ndarray) -> np.ndarray:
        seq = x_seq.shape[0]
        nx = ref_rmsnorm(x_seq, attn_norm_w, eps)
        q = (nx.astype(np.float32) @ wq_deq.astype(np.float32).T).astype(np.float16).reshape(seq, num_heads, head_dim)
        k = (nx.astype(np.float32) @ wk_deq.astype(np.float32).T).astype(np.float16).reshape(seq, num_kv_heads, head_dim)
        v = (nx.astype(np.float32) @ wv_deq.astype(np.float32).T).astype(np.float16).reshape(seq, num_kv_heads, head_dim)

        q_r = ref_rope(q, pos_offset=0, freq_base=10000.0, neox_style=False)
        k_r = ref_rope(k, pos_offset=0, freq_base=10000.0, neox_style=False)

        attn = ref_gqa_attention(q_r, k_r, v, start_pos=0, scale=1.0 / math.sqrt(head_dim), causal=True)
        attn_proj = (attn.reshape(seq, q_dim).astype(np.float32) @ wo_deq.astype(np.float32).T).astype(np.float16)
        h = (x_seq.astype(np.float32) + attn_proj.astype(np.float32)).astype(np.float16)

        nh = ref_rmsnorm(h, ffn_norm_w, eps)
        gate = (nh.astype(np.float32) @ wgate_deq.astype(np.float32).T).astype(np.float16)
        up = (nh.astype(np.float32) @ wup_deq.astype(np.float32).T).astype(np.float16)
        act = ref_swiglu(gate, up)
        down = (act.astype(np.float32) @ wdown_deq.astype(np.float32).T).astype(np.float16)
        return (h.astype(np.float32) + down.astype(np.float32)).astype(np.float16)

    try:
        total_seq = 5
        x_all = (rng.standard_normal((total_seq, hidden_size), dtype=np.float32) * 0.5).astype(np.float16)
        ref_all = _cpu_layer_ref(x_all)

        with WeightStreamer(tmp_path) as streamer:
            cfg = LlamaLayerConfig.from_gguf_metadata(streamer.gguf.metadata)
            layer = TransformerLayer(cfg)

            k_cache = np.zeros((16, num_kv_heads, head_dim), dtype=np.float16)
            v_cache = np.zeros((16, num_kv_heads, head_dim), dtype=np.float16)

            # 1. Prefill first 4 tokens (positions 0..3)
            out_prefill, _ = layer.forward_streamed(
                x_all[:4], streamer, layer_idx=0, pos_offset=0, kv_cache=(k_cache, v_cache)
            )
            # 2. Decode 5th token (position 4) using KV cache from prefill
            out_decode, _ = layer.forward_streamed(
                x_all[4:5], streamer, layer_idx=0, pos_offset=4, kv_cache=(k_cache, v_cache)
            )

        err_prefill = float(np.max(np.abs(out_prefill.astype(np.float32) - ref_all[:4].astype(np.float32))))
        err_decode = float(np.max(np.abs(out_decode.astype(np.float32) - ref_all[4:5].astype(np.float32))))
        print(f"  Streamed Layer Prefill (4 tokens) max_err: {err_prefill:.6f}")
        print(f"  Streamed Layer Decode  (1 token)  max_err: {err_decode:.6f}")

        if err_prefill < 5e-3 and err_decode < 5e-3:
            print("✅ PASS: End-to-end streamed TransformerLayer matches CPU reference for both prefill and decode")
            return True
        print("❌ FAIL")
        return False
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def main() -> int:
    print("=" * 68)
    print("GFX1150 Inference - Phase 3: Llama Transformer Layer Kernel Tests")
    print("=" * 68)

    ok1 = test_rmsnorm_kernel()
    ok2 = test_rope_kernel()
    ok3 = test_gqa_attention_kernel()
    ok4 = test_swiglu_kernel()
    ok5 = test_end_to_end_transformer_layer()

    print("\n" + "=" * 68)
    if ok1 and ok2 and ok3 and ok4 and ok5:
        print("🎉 All Phase 3 tests passed!")
        return 0
    print("⚠️  Some Phase 3 tests failed.")
    return 1


if __name__ == "__main__":
    sys.exit(main())

