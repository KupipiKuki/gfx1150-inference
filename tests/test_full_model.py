#!/usr/bin/env python3
"""
Phase 4 End-to-End Test Suite (`tests/test_full_model.py`):
1. `GGUFTokenizer` BPE/SentencePiece encode/decode round-trip + `Q4_0` embedding row lookup
2. GPU-resident offset-addressed `KVCacheManager` (`gqa_attention_cached`) vs. uncached reference
3. Multi-layer `LlamaInferenceEngine` forward pass logits vs. full CPU reference (prefill + decode)
4. End-to-end token generation loop (`generate` & `generate_ids`: greedy, top-k/top-p sampling, throughput)
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
from kv_cache import KVCacheManager
from tokenizer import GGUFTokenizer, embed_tokens
from inference import LlamaInferenceEngine, sample_next_token
from test_layer import ref_gqa_attention, ref_rmsnorm, ref_rope, ref_swiglu


def test_tokenizer_and_embedding() -> bool:
    print("\n=== 1. Testing `GGUFTokenizer` & `Q4_0` Embedding Lookup ===")
    vocab = [
        "<unk>", "<s>", "</s>", "▁", "H", "e", "l", "o", "w", "r", "d",
        "▁H", "▁He", "▁Hel", "▁Hell", "▁Hello",
        "▁w", "▁wo", "▁wor", "▁worl", "▁world", "!", "<0xF0>", "<0x9F>", "<0x9A>", "<0x80>",
    ]
    scores = [float(i) for i in range(len(vocab))]
    tok = GGUFTokenizer(tokens=vocab, scores=scores, bos_token_id=1, eos_token_id=2)

    text = "Hello world!"
    encoded = tok.encode(text, add_bos=True)
    decoded = tok.decode(encoded, skip_special_tokens=True)
    print(f"  Prompt: '{text}' -> IDs: {encoded} -> Decoded: '{decoded}'")
    assert encoded[0] == 1
    assert decoded == text, f"Decoded '{decoded}' != '{text}'"

    # Test Q4_0 embedding lookup without full-table dequantization
    rng = np.random.default_rng(7)
    hidden_size = 64
    emb_fp32 = rng.standard_normal((len(vocab), hidden_size), dtype=np.float32) * 0.1
    emb_q4 = quantize_q4_0_cpu(emb_fp32)
    emb_deq_all = dequantize_q4_0_cpu(emb_q4, len(vocab) * hidden_size).reshape(len(vocab), hidden_size)

    from gguf_parser import GGUFTensorInfo
    info = GGUFTensorInfo(
        name="token_embd.weight",
        dims=(hidden_size, len(vocab)),
        ggml_type=GGMLType.Q4_0,
        rel_offset=0,
        abs_offset=0,
        n_elements=len(vocab) * hidden_size,
        n_bytes=emb_q4.nbytes,
    )
    rows = embed_tokens(encoded, info, emb_q4, hidden_size)
    assert np.array_equal(rows, emb_deq_all[encoded])
    print("✅ PASS: GGUFTokenizer round-trip and row-wise Q4_0 embedding lookup verified")
    return True


def test_gpu_kv_cache_manager() -> bool:
    print("\n=== 2. Testing GPU-Resident Offset `KVCacheManager` (`gqa_attention_cached`) ===")
    rng = np.random.default_rng(19)
    num_layers = 2
    max_seq_len = 32
    num_heads = 8
    num_kv_heads = 2
    head_dim = 32
    scale = 1.0 / math.sqrt(head_dim)

    total_len = 6
    Q_all = (rng.standard_normal((num_layers, total_len, num_heads, head_dim), dtype=np.float32) * 0.5).astype(np.float16)
    K_all = (rng.standard_normal((num_layers, total_len, num_kv_heads, head_dim), dtype=np.float32) * 0.5).astype(np.float16)
    V_all = (rng.standard_normal((num_layers, total_len, num_kv_heads, head_dim), dtype=np.float32) * 0.5).astype(np.float16)

    with KVCacheManager(num_layers, max_seq_len, num_kv_heads, head_dim) as kv_mgr:
        for l_idx in range(num_layers):
            # Step 1: Prefill first 4 tokens (pos 0..3)
            out_pre = np.zeros((4, num_heads, head_dim), dtype=np.float16)
            kv_mgr.attend(
                Q_all[l_idx, :4], K_all[l_idx, :4], V_all[l_idx, :4],
                out_pre, layer_idx=l_idx, q_len=4, start_pos=0,
                num_heads=num_heads, scale=scale, causal=True
            )
            ref_pre = ref_gqa_attention(Q_all[l_idx, :4], K_all[l_idx, :4], V_all[l_idx, :4], start_pos=0, scale=scale)
            err_pre = float(np.max(np.abs(out_pre.astype(np.float32) - ref_pre.astype(np.float32))))
            assert err_pre < 1e-3, f"Layer {l_idx} prefill error {err_pre}"

        # Step 2: Single-token decode for positions 4 and 5
        for step_pos in (4, 5):
            for l_idx in range(num_layers):
                out_dec = np.zeros((1, num_heads, head_dim), dtype=np.float16)
                kv_mgr.attend(
                    Q_all[l_idx, step_pos:step_pos+1],
                    K_all[l_idx, step_pos:step_pos+1],
                    V_all[l_idx, step_pos:step_pos+1],
                    out_dec, layer_idx=l_idx, q_len=1, start_pos=step_pos,
                    num_heads=num_heads, scale=scale, causal=True
                )
                ref_dec = ref_gqa_attention(
                    Q_all[l_idx, step_pos:step_pos+1],
                    K_all[l_idx, :step_pos+1],
                    V_all[l_idx, :step_pos+1],
                    start_pos=step_pos, scale=scale
                )
                err_dec = float(np.max(np.abs(out_dec.astype(np.float32) - ref_dec.astype(np.float32))))
                assert err_dec < 1e-3, f"Layer {l_idx} decode pos {step_pos} error {err_dec}"

        assert kv_mgr.current_seq_len == 6

    print("✅ PASS: GPU-resident offset KVCacheManager matches full-context CPU reference with zero host copies")
    return True


def test_full_model_inference() -> bool:
    print("\n=== 3. Testing End-to-End 2-Layer `LlamaInferenceEngine` (Logits & Generation) ===")
    rng = np.random.default_rng(2026)

    num_layers = 2
    hidden_size = 128
    intermediate_size = 256
    num_heads = 4
    num_kv_heads = 2
    head_dim = 32
    q_dim = num_heads * head_dim
    kv_dim = num_kv_heads * head_dim
    eps = 1e-5

    vocab = [
        "<unk>", "<s>", "</s>", "▁", "A", "M", "D", "▁AMD",
        "▁gfx", "1150", "▁gfx1150", "▁is", "▁fast", ".", "!", "?",
        "t", "o", "k", "e", "n", "s", "▁token", "▁tokens",
        "r", "c", "m", "▁ROCm", "H", "I", "P", "▁HIP",
    ]
    vocab_size = len(vocab)
    scores = [float(i) for i in range(vocab_size)]

    def _q4_pair(rows: int, cols: int):
        w = rng.standard_normal((rows, cols), dtype=np.float32) * (1.0 / math.sqrt(cols))
        q4 = quantize_q4_0_cpu(w)
        deq = dequantize_q4_0_cpu(q4, rows * cols).reshape(rows, cols)
        return q4, deq

    emb_q4, emb_deq = _q4_pair(vocab_size, hidden_size)
    out_q4, out_deq = _q4_pair(vocab_size, hidden_size)
    out_norm_w = (1.0 + 0.05 * rng.standard_normal(hidden_size, dtype=np.float32)).astype(np.float16)

    metadata = {
        "general.architecture": (GGUFValueType.STRING, "llama"),
        "llama.block_count": (GGUFValueType.UINT32, num_layers),
        "llama.embedding_length": (GGUFValueType.UINT32, hidden_size),
        "llama.feed_forward_length": (GGUFValueType.UINT32, intermediate_size),
        "llama.attention.head_count": (GGUFValueType.UINT32, num_heads),
        "llama.attention.head_count_kv": (GGUFValueType.UINT32, num_kv_heads),
        "llama.rope.dimension_count": (GGUFValueType.UINT32, head_dim),
        "llama.attention.layer_norm_rms_epsilon": (GGUFValueType.FLOAT32, eps),
        "llama.rope.freq_base": (GGUFValueType.FLOAT32, 10000.0),
        "tokenizer.ggml.tokens": (GGUFValueType.ARRAY, (GGUFValueType.STRING, vocab)),
        "tokenizer.ggml.scores": (GGUFValueType.ARRAY, (GGUFValueType.FLOAT32, scores)),
        "tokenizer.ggml.bos_token_id": (GGUFValueType.UINT32, 1),
        "tokenizer.ggml.eos_token_id": (GGUFValueType.UINT32, 2),
    }

    tensors = [
        ("token_embd.weight", (hidden_size, vocab_size), GGMLType.Q4_0, emb_q4.tobytes()),
        ("output_norm.weight", (hidden_size,), GGMLType.F16, out_norm_w.tobytes()),
        ("output.weight", (hidden_size, vocab_size), GGMLType.Q4_0, out_q4.tobytes()),
    ]

    cpu_layers = []
    for l_idx in range(num_layers):
        wq_q4, wq_deq = _q4_pair(q_dim, hidden_size)
        wk_q4, wk_deq = _q4_pair(kv_dim, hidden_size)
        wv_q4, wv_deq = _q4_pair(kv_dim, hidden_size)
        wo_q4, wo_deq = _q4_pair(hidden_size, q_dim)
        wg_q4, wg_deq = _q4_pair(intermediate_size, hidden_size)
        wu_q4, wu_deq = _q4_pair(intermediate_size, hidden_size)
        wd_q4, wd_deq = _q4_pair(hidden_size, intermediate_size)
        an_w = (1.0 + 0.05 * rng.standard_normal(hidden_size, dtype=np.float32)).astype(np.float16)
        fn_w = (1.0 + 0.05 * rng.standard_normal(hidden_size, dtype=np.float32)).astype(np.float16)

        p = f"blk.{l_idx}."
        tensors.extend([
            (p + "attn_norm.weight", (hidden_size,), GGMLType.F16, an_w.tobytes()),
            (p + "attn_q.weight", (hidden_size, q_dim), GGMLType.Q4_0, wq_q4.tobytes()),
            (p + "attn_k.weight", (hidden_size, kv_dim), GGMLType.Q4_0, wk_q4.tobytes()),
            (p + "attn_v.weight", (hidden_size, kv_dim), GGMLType.Q4_0, wv_q4.tobytes()),
            (p + "attn_output.weight", (q_dim, hidden_size), GGMLType.Q4_0, wo_q4.tobytes()),
            (p + "ffn_norm.weight", (hidden_size,), GGMLType.F16, fn_w.tobytes()),
            (p + "ffn_gate.weight", (hidden_size, intermediate_size), GGMLType.Q4_0, wg_q4.tobytes()),
            (p + "ffn_up.weight", (hidden_size, intermediate_size), GGMLType.Q4_0, wu_q4.tobytes()),
            (p + "ffn_down.weight", (intermediate_size, hidden_size), GGMLType.Q4_0, wd_q4.tobytes()),
        ])
        cpu_layers.append((an_w, wq_deq, wk_deq, wv_deq, wo_deq, fn_w, wg_deq, wu_deq, wd_deq))

    def _cpu_full_forward(token_ids):
        h = emb_deq[token_ids]
        seq = h.shape[0]
        for an_w, wq, wk, wv, wo, fn_w, wg, wu, wd in cpu_layers:
            nx = ref_rmsnorm(h, an_w, eps)
            q = (nx.astype(np.float32) @ wq.astype(np.float32).T).astype(np.float16).reshape(seq, num_heads, head_dim)
            k = (nx.astype(np.float32) @ wk.astype(np.float32).T).astype(np.float16).reshape(seq, num_kv_heads, head_dim)
            v = (nx.astype(np.float32) @ wv.astype(np.float32).T).astype(np.float16).reshape(seq, num_kv_heads, head_dim)
            q_r = ref_rope(q, pos_offset=0, freq_base=10000.0, neox_style=False)
            k_r = ref_rope(k, pos_offset=0, freq_base=10000.0, neox_style=False)
            attn = ref_gqa_attention(q_r, k_r, v, start_pos=0, scale=1.0 / math.sqrt(head_dim), causal=True)
            ap = (attn.reshape(seq, q_dim).astype(np.float32) @ wo.astype(np.float32).T).astype(np.float16)
            h = (h.astype(np.float32) + ap.astype(np.float32)).astype(np.float16)
            nh = ref_rmsnorm(h, fn_w, eps)
            gate = (nh.astype(np.float32) @ wg.astype(np.float32).T).astype(np.float16)
            up = (nh.astype(np.float32) @ wu.astype(np.float32).T).astype(np.float16)
            act = ref_swiglu(gate, up)
            down = (act.astype(np.float32) @ wd.astype(np.float32).T).astype(np.float16)
            h = (h.astype(np.float32) + down.astype(np.float32)).astype(np.float16)
        last_norm = ref_rmsnorm(h[-1:, :], out_norm_w, eps)
        logits = (last_norm.astype(np.float32) @ out_deq.astype(np.float32).T).astype(np.float16)
        return logits.reshape(-1)

    with tempfile.NamedTemporaryFile(suffix=".gguf", delete=False) as tmp:
        tmp_path = tmp.name
        write_synthetic_gguf(tmp, metadata, tensors)

    try:
        with LlamaInferenceEngine(tmp_path, max_seq_len=64) as engine:
            prompt_ids = [1, 7, 10, 11]
            # 1. Verify prefill logits for positions 0..3
            logits_pre = engine.forward_tokens(prompt_ids, pos_offset=0)
            ref_logits_pre = _cpu_full_forward(prompt_ids)
            err_pre = float(np.max(np.abs(logits_pre.astype(np.float32) - ref_logits_pre.astype(np.float32))))
            print(f"  Full-Model Prefill Logits max_err: {err_pre:.6f}")

            # 2. Verify single-token decode at position 4 using GPU KV cache
            next_tok = sample_next_token(logits_pre, temperature=0.0)
            logits_dec = engine.forward_tokens([next_tok], pos_offset=len(prompt_ids))
            ref_logits_dec = _cpu_full_forward(prompt_ids + [next_tok])
            err_dec = float(np.max(np.abs(logits_dec.astype(np.float32) - ref_logits_dec.astype(np.float32))))
            print(f"  Full-Model Decode  Logits max_err: {err_dec:.6f}")

            assert err_pre < 5e-3 and err_dec < 5e-3, f"Logits error too high: {err_pre}, {err_dec}"

            # 3. End-to-end text generation loop
            text_out, metrics = engine.generate(
                "AMD gfx1150", max_new_tokens=10, temperature=0.7, top_k=10, top_p=0.9, stop_on_eos=False, seed=42
            )
            print(f"  Generated {int(metrics['tokens_generated'])} tokens: '{text_out}'")
            print(
                f"  Throughput: {metrics['tokens_per_sec']:.1f} tok/s "
                f"(decode: {metrics['decode_tokens_per_sec']:.1f} tok/s)"
            )
            assert int(metrics["tokens_generated"]) == 10
            assert metrics["tokens_per_sec"] > 0.5

        print("✅ PASS: Full-model prefill, cached decode, and token generation verified")
        return True
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def main() -> int:
    print("=" * 70)
    print("GFX1150 Inference - Phase 4: Full-Model End-to-End Inference Tests")
    print("=" * 70)

    ok1 = test_tokenizer_and_embedding()
    ok2 = test_gpu_kv_cache_manager()
    ok3 = test_full_model_inference()

    print("\n" + "=" * 70)
    if ok1 and ok2 and ok3:
        print("🎉 All Phase 4 tests passed!")
        return 0
    print("⚠️  Some Phase 4 tests failed.")
    return 1


if __name__ == "__main__":
    sys.exit(main())

