#!/usr/bin/env python3
"""
QAQC probe (7C): llama-family fixed-prompt logits/generation regression.

Self-contained on purpose: it uses only the stable public surface
(`write_synthetic_gguf` + `LlamaInferenceEngine`) so the *same script* runs on
the parent commit 8426ec6 and on the 7C candidate; identical output proves the
llama-family path is unchanged by the model-spec refactor.

Usage: python probe_llama_regression.py  (prints a deterministic report; the
evidence log captures both parent and candidate runs for a byte comparison).
"""

from __future__ import annotations

import hashlib
import math
import os
import sys
import tempfile

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", "..", "..", ".."))
_SRC = os.path.join(_ROOT, "src")
_BUILD = os.path.join(_ROOT, "build")
for _p in (_SRC, _BUILD):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

from gguf_parser import GGMLType, GGUFValueType, quantize_q4_0_cpu, write_synthetic_gguf  # noqa: E402


VOCAB = [
    "<unk>", "<s>", "</s>", "▁", "A", "M", "D", "▁AMD",
    "▁gfx", "1150", "▁gfx1150", "▁is", "▁fast", ".", "!", "?",
]

PROMPT_IDS = [1, 7, 10, 11]      # fixed prompt
SEED = 42                         # fixed seed
LOGITS_DIGITS = 8                 # stable fp16 printing


def main() -> int:
    rng = np.random.default_rng(20261107)

    num_layers = 2
    hidden = 128
    inter = 256
    num_heads = 4
    num_kv_heads = 2
    head_dim = 32
    q_dim = num_heads * head_dim
    kv_dim = num_kv_heads * head_dim
    vocab_size = len(VOCAB)
    eps = 1e-5

    def q4(rows, cols):
        w = rng.standard_normal((rows, cols), dtype=np.float32) * (1.0 / math.sqrt(cols))
        return quantize_q4_0_cpu(w)

    metadata = {
        "general.architecture": (GGUFValueType.STRING, "llama"),
        "llama.block_count": (GGUFValueType.UINT32, num_layers),
        "llama.embedding_length": (GGUFValueType.UINT32, hidden),
        "llama.feed_forward_length": (GGUFValueType.UINT32, inter),
        "llama.attention.head_count": (GGUFValueType.UINT32, num_heads),
        "llama.attention.head_count_kv": (GGUFValueType.UINT32, num_kv_heads),
        "llama.rope.dimension_count": (GGUFValueType.UINT32, head_dim),
        "llama.attention.layer_norm_rms_epsilon": (GGUFValueType.FLOAT32, eps),
        "llama.rope.freq_base": (GGUFValueType.FLOAT32, 10000.0),
        "tokenizer.ggml.tokens": (GGUFValueType.ARRAY, (GGUFValueType.STRING, VOCAB)),
        "tokenizer.ggml.scores": (
            GGUFValueType.ARRAY, (GGUFValueType.FLOAT32, [float(-i) for i in range(vocab_size)])
        ),
        "tokenizer.ggml.bos_token_id": (GGUFValueType.UINT32, 1),
        "tokenizer.ggml.eos_token_id": (GGUFValueType.UINT32, 2),
        "tokenizer.ggml.add_bos_token": (GGUFValueType.BOOL, False),
    }

    tensors = [
        ("token_embd.weight", (hidden, vocab_size), GGMLType.Q4_0, q4(vocab_size, hidden).tobytes()),
        ("output_norm.weight", (hidden,), GGMLType.F16,
         (1.0 + 0.05 * rng.standard_normal(hidden, dtype=np.float32)).astype(np.float16).tobytes()),
        ("output.weight", (hidden, vocab_size), GGMLType.Q4_0, q4(vocab_size, hidden).tobytes()),
    ]
    for il in range(num_layers):
        p = f"blk.{il}."
        tensors.extend([
            (p + "attn_norm.weight", (hidden,), GGMLType.F16,
             (1.0 + 0.05 * rng.standard_normal(hidden, dtype=np.float32)).astype(np.float16).tobytes()),
            (p + "attn_q.weight", (hidden, q_dim), GGMLType.Q4_0, q4(q_dim, hidden).tobytes()),
            (p + "attn_k.weight", (hidden, kv_dim), GGMLType.Q4_0, q4(kv_dim, hidden).tobytes()),
            (p + "attn_v.weight", (hidden, kv_dim), GGMLType.Q4_0, q4(kv_dim, hidden).tobytes()),
            (p + "attn_output.weight", (q_dim, hidden), GGMLType.Q4_0, q4(hidden, q_dim).tobytes()),
            (p + "ffn_norm.weight", (hidden,), GGMLType.F16,
             (1.0 + 0.05 * rng.standard_normal(hidden, dtype=np.float32)).astype(np.float16).tobytes()),
            (p + "ffn_gate.weight", (hidden, inter), GGMLType.Q4_0, q4(inter, hidden).tobytes()),
            (p + "ffn_up.weight", (hidden, inter), GGMLType.Q4_0, q4(inter, hidden).tobytes()),
            (p + "ffn_down.weight", (inter, hidden), GGMLType.Q4_0, q4(hidden, inter).tobytes()),
        ])

    with tempfile.NamedTemporaryFile(suffix=".gguf", delete=False) as tmp:
        write_synthetic_gguf(tmp, metadata, tensors)
        gguf_path = tmp.name

    try:
        from inference import LlamaInferenceEngine, sample_next_token

        with LlamaInferenceEngine(gguf_path, max_seq_len=64) as engine:
            logits = engine.forward_tokens(PROMPT_IDS, pos_offset=0)
            logits_hex = hashlib.sha256(
                np.ascontiguousarray(logits.astype(np.float32)).tobytes()
            ).hexdigest()
            greedy_ids = []
            next_id = sample_next_token(logits, temperature=0.0)
            greedy_ids.append(next_id)
            all_ids = list(PROMPT_IDS) + [next_id]
            for _ in range(7):
                step = engine.forward_tokens([next_id], pos_offset=len(all_ids) - 1)
                next_id = sample_next_token(step, temperature=0.0)
                greedy_ids.append(next_id)
                all_ids.append(next_id)

            new_ids, _ = engine.generate_ids(
                PROMPT_IDS, max_new_tokens=8, temperature=0.0, seed=SEED
            )

        print("=== llama fixed-prompt regression probe ===")
        print(f"prompt_ids = {PROMPT_IDS}")
        print(f"logits_sha256 (fp32 bytes of unordered fp16 logits) = {logits_hex}")
        print("logits_head = " + ", ".join(
            f"{v:.{LOGITS_DIGITS}f}" for v in logits.astype(np.float32)[:6]
        ))
        print(f"greedy_ids = {greedy_ids}")
        print(f"generate_ids = {new_ids}")
        print("VERDICT: see parent/candidate comparison")
        return 0
    finally:
        if os.path.exists(gguf_path):
            os.remove(gguf_path)


if __name__ == "__main__":
    sys.exit(main())
