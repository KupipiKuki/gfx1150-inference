#!/usr/bin/env python3
"""7E overlap probe: builds a larger F16 synthetic llama model so projection
kernels are long enough to measure copy/compute overlap through the
GFX1150_STREAM_TRACE trace of launch_forward_layer_cached_fp16."""
import os
import sys

ROOT = "/home/kupipi/Documents/git/gfx1150-inference"
sys.path.insert(0, os.path.join(ROOT, "build"))
sys.path.insert(0, os.path.join(ROOT, "src"))

import tempfile
import numpy as np
import matmul_module  # noqa: F401
from gguf_parser import GGMLType, GGUFValueType, write_synthetic_gguf
import inference as inference_mod

H, I, HEADS, KVH, HD, LAYERS = 2048, 8192, 16, 4, 128, 1
SEQ = 256

def build(path):
    rng = np.random.default_rng(77)
    meta = {
        "general.architecture": (GGUFValueType.STRING, "llama"),
        "llama.block_count": (GGUFValueType.UINT32, LAYERS),
        "llama.embedding_length": (GGUFValueType.UINT32, H),
        "llama.feed_forward_length": (GGUFValueType.UINT32, I),
        "llama.attention.head_count": (GGUFValueType.UINT32, HEADS),
        "llama.attention.head_count_kv": (GGUFValueType.UINT32, KVH),
        "llama.rope.dimension_count": (GGUFValueType.UINT32, HD),
        "llama.attention.layer_norm_rms_epsilon": (GGUFValueType.FLOAT32, 1e-5),
    }
    vocab = 256
    meta["tokenizer.ggml.tokens"] = (GGUFValueType.ARRAY, (GGUFValueType.STRING, [f"t{i}" for i in range(vocab)]))
    meta["tokenizer.ggml.scores"] = (GGUFValueType.ARRAY, (GGUFValueType.FLOAT32, [0.0] * vocab))
    meta["tokenizer.ggml.eos_token_id"] = (GGUFValueType.UINT32, 2)
    tensors = []
    def f16(rows, cols):
        return (rng.standard_normal((rows, cols), dtype=np.float32) * 0.02).astype(np.float16).tobytes()
    tensors.append(("token_embd.weight", (H, vocab), GGMLType.F16, f16(H, vocab)))
    tensors.append(("output_norm.weight", (H,), GGMLType.F16, np.ones(H, dtype=np.float16).tobytes()))
    tensors.append(("output.weight", (H, vocab), GGMLType.F16, f16(2 * 1024 * 1024 // H // 2 * H, vocab)))  # small tied-ish head
    tol = 2 * 1024 * 1024  # 2 MiB per side cap for the LM head is not needed; use exact
    tensors[-1] = ("output.weight", (H, vocab), GGMLType.F16, f16(H, vocab))
    projs = [
        ("attn_norm.weight", (H,), H, None),
        ("attn_q.weight", (H, HEADS * HD), H, HEADS * HD),
        ("attn_k.weight", (H, KVH * HD), H, KVH * HD),
        ("attn_v.weight", (H, KVH * HD), H, KVH * HD),
        ("attn_output.weight", (HEADS * HD, H), HEADS * HD, H),
        ("ffn_norm.weight", (H,), H, None),
        ("ffn_gate.weight", (H, I), H, I),
        ("ffn_up.weight", (H, I), H, I),
        ("ffn_down.weight", (I, H), I, H),
    ]
    for name, dims, r, c in projs:
        payload = np.ones(r, dtype=np.float16).tobytes() if c is None else f16(r, c)
        tensors.append((f"blk.0.{name}", dims, GGMLType.F16, payload))
    with open(path, "wb") as fh:
        write_synthetic_gguf(fh, meta, tensors)

with tempfile.TemporaryDirectory() as tmpdir:
    model = os.path.join(tmpdir, "big_f16.gguf")
    build(model)
    print(f"model size: {os.path.getsize(model) / (1 << 20):.1f} MiB, seq={SEQ}")
    with inference_mod.LlamaInferenceEngine(model, max_seq_len=SEQ) as eng:
        _ = eng.forward_tokens(list(range(32)), pos_offset=0, compute_logits=False)
        for _ in range(2):  # warm page cache, then trace
            pass
        ids = list(range(SEQ))
        _ = eng.forward_tokens(ids, pos_offset=0, compute_logits=True)
    print("overlap probe done")
