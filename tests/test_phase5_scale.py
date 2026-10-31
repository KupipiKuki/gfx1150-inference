"""
Phase 5 Validation & 70B-Scale Test Suite (`tests/test_phase5_scale.py`):
1. `Q8_0` dequantization & fused `matmul_q8_0` HIP kernel verification.
2. `Q4_K` (`Q4_K_M` / `Q4_K_S` 256-element super-block) dequantization & fused `matmul_q4_k`
   HIP kernel verification, including 70B hidden dimension (`K = 8192`) benchmark.
3. Mixed-precision `Q4_K_M` (`Q4_K` + `Q8_0`) multi-layer GGUF end-to-end inference.
4. Chunked prompt prefill (`prefill_chunk_size`) equivalence & multi-prompt batch generation (`generate_batch`).
5. CPU RAM (`offload_kv_to_cpu=True`) and NVMe `mmap` (`kv_mmap_dir=...`) KV-cache offload equivalence.
6. CLI entry point (`inference.main`) verification.
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from typing import Dict, List, Tuple
import numpy as np

_ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for _p in (os.path.join(_ROOT_DIR, "build"), os.path.join(_ROOT_DIR, "src")):
    if _p not in sys.path and os.path.isdir(_p):
        sys.path.insert(0, _p)

import matmul_module
from gguf_parser import (
    GGMLType,
    GGUFValueType,
    quantize_q8_0_cpu,
    dequantize_q8_0_cpu,
    quantize_q4_k_cpu,
    dequantize_q4_k_cpu,
    write_synthetic_gguf,
)
from inference import LlamaInferenceEngine, main as cli_main


def test_q8_0_kernels() -> None:
    print("--- Testing Q8_0 Dequantize & Fused Matmul HIP Kernels ---")
    rng = np.random.default_rng(501)
    num_elements = 4096 * 32
    w_fp32 = rng.standard_normal(num_elements, dtype=np.float32) * 0.5
    q8_bytes = quantize_q8_0_cpu(w_fp32)

    ref_fp16 = dequantize_q8_0_cpu(q8_bytes, num_elements)
    gpu_fp16 = np.empty(num_elements, dtype=np.float16)
    matmul_module.dequantize_q8_0(q8_bytes, gpu_fp16, num_elements)

    deq_err = float(np.max(np.abs(gpu_fp16.astype(np.float32) - ref_fp16.astype(np.float32))))
    print(f"  [dequantize_q8_0] elements={num_elements}: max_error={deq_err:.6f}")
    assert deq_err < 1e-3, f"dequantize_q8_0 error {deq_err} >= 1e-3"

    for M, N, K in [(1, 512, 1024), (8, 256, 512)]:
        A = (rng.standard_normal((M, K), dtype=np.float32) * 0.2).astype(np.float16)
        B_fp32 = rng.standard_normal((N, K), dtype=np.float32) * 0.2
        B_q8 = quantize_q8_0_cpu(B_fp32)
        B_deq = dequantize_q8_0_cpu(B_q8, N * K).reshape(N, K)

        C_gpu = np.empty((M, N), dtype=np.float16)
        matmul_module.matmul_q8_0(A, B_q8, C_gpu, M, N, K)

        C_ref = (A.astype(np.float32) @ B_deq.astype(np.float32).T).astype(np.float16)
        err = float(np.max(np.abs(C_gpu.astype(np.float32) - C_ref.astype(np.float32))))
        print(f"  [matmul_q8_0] ({M}x{N}x{K}): max_error={err:.6f}")
        assert err < 1e-2, f"matmul_q8_0 error {err} >= 1e-2"


def test_q4_k_superblock_kernels_and_70b_scale() -> None:
    print("--- Testing Q4_K (256-Elem Super-Block) Kernels & 70B Dimension (K=8192) ---")
    rng = np.random.default_rng(502)
    num_elements = 256 * 256  # 256 super-blocks
    w_fp32 = rng.standard_normal(num_elements, dtype=np.float32) * 0.4
    q4k_bytes = quantize_q4_k_cpu(w_fp32)

    ref_fp16 = dequantize_q4_k_cpu(q4k_bytes, num_elements)
    gpu_fp16 = np.empty(num_elements, dtype=np.float16)
    matmul_module.dequantize_q4_k(q4k_bytes, gpu_fp16, num_elements)

    deq_err = float(np.max(np.abs(gpu_fp16.astype(np.float32) - ref_fp16.astype(np.float32))))
    print(f"  [dequantize_q4_k] elements={num_elements}: max_error={deq_err:.6f}")
    assert deq_err < 1e-3, f"dequantize_q4_k error {deq_err} >= 1e-3"

    # Test decode (M=1), prefill (M=8), and 70B Llama-3 hidden_size (K=8192)
    for M, N, K in [(1, 256, 512), (8, 256, 512), (1, 1024, 8192)]:
        A = (rng.standard_normal((M, K), dtype=np.float32) * 0.1).astype(np.float16)
        B_fp32 = rng.standard_normal((N, K), dtype=np.float32) * 0.1
        B_q4k = quantize_q4_k_cpu(B_fp32)
        B_deq = dequantize_q4_k_cpu(B_q4k, N * K).reshape(N, K)

        C_gpu = np.empty((M, N), dtype=np.float16)
        t0 = time.time()
        matmul_module.matmul_q4_k(A, B_q4k, C_gpu, M, N, K)
        elapsed_ms = (time.time() - t0) * 1000.0

        C_ref = (A.astype(np.float32) @ B_deq.astype(np.float32).T).astype(np.float16)
        err = float(np.max(np.abs(C_gpu.astype(np.float32) - C_ref.astype(np.float32))))
        print(f"  [matmul_q4_k] ({M}x{N}x{K}): max_error={err:.6f} ({elapsed_ms:.2f} ms)")
        assert err < 2e-2, f"matmul_q4_k error {err} >= 2e-2"


def _build_synthetic_q4km_model(path: str, num_layers: int = 2) -> None:
    """
    Create a synthetic multi-layer GGUF model using mixed `Q4_K` + `Q8_0` (`Q4_K_M`)
    quantization (`hidden_size = 256`, `intermediate_size = 512`).
    """
    rng = np.random.default_rng(503)
    hidden_size = 256
    intermediate_size = 512
    num_heads = 8
    num_kv_heads = 4
    head_dim = 32
    q_dim = num_heads * head_dim
    kv_dim = num_kv_heads * head_dim

    tokens = [
        "<unk>", "<s>", "</s>",
        "\u2581", "h", "e", "l", "o", "w", "r", "d",
        "\u2581h", "\u2581he", "\u2581hel", "\u2581hell", "\u2581hello",
        "\u2581w", "\u2581wo", "\u2581wor", "\u2581worl", "\u2581world",
        "\u2581gfx", "1150", "\u2581gfx1150",
        "a", "b", "c", "i", "n", "f", "s", "t",
    ]
    vocab_size = len(tokens)
    scores = [float(i) for i in range(vocab_size)]

    metadata: Dict[str, Tuple[GGUFValueType, object]] = {
        "general.architecture": (GGUFValueType.STRING, "llama"),
        "llama.block_count": (GGUFValueType.UINT32, num_layers),
        "llama.embedding_length": (GGUFValueType.UINT32, hidden_size),
        "llama.feed_forward_length": (GGUFValueType.UINT32, intermediate_size),
        "llama.attention.head_count": (GGUFValueType.UINT32, num_heads),
        "llama.attention.head_count_kv": (GGUFValueType.UINT32, num_kv_heads),
        "llama.rope.dimension_count": (GGUFValueType.UINT32, head_dim),
        "llama.attention.layer_norm_rms_epsilon": (GGUFValueType.FLOAT32, 1e-5),
        "llama.rope.freq_base": (GGUFValueType.FLOAT32, 10000.0),
        "tokenizer.ggml.tokens": (GGUFValueType.ARRAY, (GGUFValueType.STRING, tokens)),
        "tokenizer.ggml.scores": (GGUFValueType.ARRAY, (GGUFValueType.FLOAT32, scores)),
        "tokenizer.ggml.bos_token_id": (GGUFValueType.UINT32, 1),
        "tokenizer.ggml.eos_token_id": (GGUFValueType.UINT32, 2),
    }

    tensors: List[Tuple[str, Tuple[int, ...], GGMLType, bytes]] = []

    # Token embeddings in Q4_K (vocab_size x 256)
    emb_fp32 = rng.standard_normal((vocab_size, hidden_size), dtype=np.float32) * 0.08
    tensors.append(
        ("token_embd.weight", (hidden_size, vocab_size), GGMLType.Q4_K, quantize_q4_k_cpu(emb_fp32).tobytes())
    )

    for l_idx in range(num_layers):
        p = f"blk.{l_idx}."
        tensors.append(
            (p + "attn_norm.weight", (hidden_size,), GGMLType.F16, np.ones(hidden_size, dtype=np.float16).tobytes())
        )
        tensors.append(
            (p + "ffn_norm.weight", (hidden_size,), GGMLType.F16, np.ones(hidden_size, dtype=np.float16).tobytes())
        )
        # Q4_K projections + Q8_0 attn_v (matching real Q4_K_M mixed quantization!)
        for name, out_dim, in_dim, qtype in [
            ("attn_q.weight", q_dim, hidden_size, GGMLType.Q4_K),
            ("attn_k.weight", kv_dim, hidden_size, GGMLType.Q4_K),
            ("attn_v.weight", kv_dim, hidden_size, GGMLType.Q8_0),
            ("attn_output.weight", hidden_size, q_dim, GGMLType.Q4_K),
            ("ffn_gate.weight", intermediate_size, hidden_size, GGMLType.Q4_K),
            ("ffn_up.weight", intermediate_size, hidden_size, GGMLType.Q4_K),
            ("ffn_down.weight", hidden_size, intermediate_size, GGMLType.Q8_0),
        ]:
            w = rng.standard_normal((out_dim, in_dim), dtype=np.float32) * 0.06
            raw = quantize_q4_k_cpu(w).tobytes() if qtype == GGMLType.Q4_K else quantize_q8_0_cpu(w).tobytes()
            tensors.append((p + name, (in_dim, out_dim), qtype, raw))

    tensors.append(
        ("output_norm.weight", (hidden_size,), GGMLType.F16, np.ones(hidden_size, dtype=np.float16).tobytes())
    )
    out_w = rng.standard_normal((vocab_size, hidden_size), dtype=np.float32) * 0.08
    tensors.append(
        ("output.weight", (hidden_size, vocab_size), GGMLType.Q8_0, quantize_q8_0_cpu(out_w).tobytes())
    )

    with open(path, "wb") as f:
        write_synthetic_gguf(f, metadata, tensors)


def test_q4km_chunked_batch_and_kv_offload() -> None:
    print("--- Testing Q4_K_M End-to-End, Chunked Prefill, Batching, CPU/mmap KV Offload & CLI ---")
    with tempfile.TemporaryDirectory() as tmpdir:
        gguf_path = os.path.join(tmpdir, "synthetic_q4km.gguf")
        mmap_kv_dir = os.path.join(tmpdir, "kv_mmap")
        _build_synthetic_q4km_model(gguf_path, num_layers=2)

        prompt_ids = [1, 15, 20, 23, 4, 5]  # 6 tokens

        # 1. Standard GPU-resident KV cache + full prefill vs chunked prefill
        with LlamaInferenceEngine(gguf_path, max_seq_len=128) as engine_gpu:
            assert engine_gpu.kv_cache.device_bytes > 0
            ids_full, metrics_full = engine_gpu.generate_ids(
                prompt_ids, max_new_tokens=6, temperature=0.0, stop_on_eos=False
            )
            ids_chunked, _ = engine_gpu.generate_ids(
                prompt_ids, max_new_tokens=6, temperature=0.0, stop_on_eos=False, prefill_chunk_size=2
            )
            print(f"  [Full vs Chunked Prefill] full={ids_full}, chunked(2)={ids_chunked}")
            assert ids_full == ids_chunked, f"Chunked prefill mismatch: {ids_full} != {ids_chunked}"

            # Multi-prompt batch processing
            batch_texts, batch_metrics = engine_gpu.generate_batch(
                ["hello world", "gfx1150"], max_new_tokens=4, temperature=0.0, stop_on_eos=False
            )
            print(
                f"  [Batch Inference] batch_size={int(batch_metrics['batch_size'])}, "
                f"tok/s={batch_metrics['tokens_per_sec']:.2f}, outputs={batch_texts}"
            )
            assert len(batch_texts) == 2

        # 2. CPU-offloaded KV cache equivalence
        with LlamaInferenceEngine(gguf_path, max_seq_len=128, offload_kv_to_cpu=True) as engine_cpu:
            assert engine_cpu.kv_cache.device_bytes == 0
            ids_cpu, _ = engine_cpu.generate_ids(
                prompt_ids, max_new_tokens=6, temperature=0.0, stop_on_eos=False
            )
            print(f"  [CPU KV Offload] device_bytes=0, ids={ids_cpu}")
            assert ids_cpu == ids_full, f"CPU KV offload mismatch: {ids_cpu} != {ids_full}"

        # 3. NVMe mmap-backed KV cache equivalence
        with LlamaInferenceEngine(gguf_path, max_seq_len=128, kv_mmap_dir=mmap_kv_dir) as engine_mmap:
            assert engine_mmap.kv_cache.device_bytes == 0
            assert os.path.exists(os.path.join(mmap_kv_dir, "kv_cache_k.mmap"))
            ids_mmap, _ = engine_mmap.generate_ids(
                prompt_ids, max_new_tokens=6, temperature=0.0, stop_on_eos=False
            )
            print(f"  [mmap KV Offload] device_bytes=0, ids={ids_mmap}")
            assert ids_mmap == ids_full, f"mmap KV offload mismatch: {ids_mmap} != {ids_full}"

        # Confirm mmap files were cleaned up on close()
        assert not os.path.exists(os.path.join(mmap_kv_dir, "kv_cache_k.mmap"))

        # 4. CLI entry point verification
        rc = cli_main([
            "--model", gguf_path,
            "--prompt", "hello world",
            "--max-new-tokens", "4",
            "--prefill-chunk-size", "2",
            "--offload-kv-cpu",
        ])
        assert rc == 0, f"CLI returned non-zero exit code: {rc}"
        print("  [CLI Entry Point] gfx1150-infer exited with code 0")


if __name__ == "__main__":
    print("=== Phase 5: K-Quants (Q4_K_M / Q8_0), 70B Scale & KV Offload Test Suite ===")
    test_q8_0_kernels()
    test_q4_k_superblock_kernels_and_70b_scale()
    test_q4km_chunked_batch_and_kv_offload()
    print("=== All Phase 5 Tests Passed! ===")

