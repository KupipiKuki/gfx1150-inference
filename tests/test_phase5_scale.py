"""
Phase 5 Validation & 70B-Scale Test Suite (`tests/test_phase5_scale.py`):
1. `Q8_0` dequantization & fused `matmul_q8_0` HIP kernel verification.
2. `Q4_K` (`Q4_K_M` / `Q4_K_S` 256-element super-block) dequantization & fused `matmul_q4_k`
   HIP kernel verification, including 70B hidden dimension (`K = 8192`) benchmark.
3. Mixed-precision `Q4_K_M` (`Q4_K` + `Q8_0`) multi-layer GGUF end-to-end inference.
4. Chunked prompt prefill (`prefill_chunk_size`) equivalence & multi-prompt batch generation (`generate_batch`).
5. CPU RAM (`offload_kv_to_cpu=True`) and NVMe `mmap` (`kv_mmap_dir=...`) KV-cache offload equivalence.
6. CLI entry point (`inference.main`) verification.

Phase 7A-1: converted to a pytest module.

- The module-scope ``import matmul_module`` and ``from inference import ...`` moved
  into the test bodies: ``src/inference.py`` imports ``matmul_module`` at module
  scope, so importing it at module level raised a collection error on a
  CPU-only host (audit AUD-2).
- The module is marked ``gpu``; ``python3 tests/test_phase5_scale.py`` still works
  as a standalone script.
"""

from __future__ import annotations

import os
import sys
import inspect
import tempfile
import time
from typing import Dict, List, Tuple
import numpy as np
import pytest

_ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for _p in (os.path.join(_ROOT_DIR, "build"), os.path.join(_ROOT_DIR, "src")):
    if _p not in sys.path and os.path.isdir(_p):
        sys.path.insert(0, _p)

from gguf_parser import (
    GGMLType,
    GGUFValueType,
    quantize_q4_0_cpu,
    quantize_q8_0_cpu,
    dequantize_q8_0_cpu,
    quantize_q4_k_cpu,
    dequantize_q4_k_cpu,
    quantize_q6_k_cpu,
    dequantize_q6_k_cpu,
    write_synthetic_gguf,
)

# Every test in this module belongs to the hardware lane.
pytestmark = pytest.mark.gpu


def test_q8_0_kernels(matmul_module) -> None:
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


def test_q4_k_superblock_kernels_and_70b_scale(matmul_module) -> None:
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


def test_q4km_chunked_batch_and_kv_offload(matmul_module) -> None:
    # Imported here (not at module scope): src/inference.py imports matmul_module
    # at module scope and would break collection on a CPU-only host.
    from inference import LlamaInferenceEngine, main as cli_main

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

            # Verify singleton GPU KV pool guard prevents accidental concurrent GPU pool overwrite (O-3)
            caught_singleton = False
            try:
                _ = LlamaInferenceEngine(gguf_path, max_seq_len=64, offload_kv_to_cpu=False)
            except RuntimeError:
                caught_singleton = True
            assert caught_singleton, "Expected RuntimeError when creating second active GPU KVCacheManager"
            print("  [Singleton Guard] Second active GPU KVCacheManager properly rejected")

        # Verify failed KVCacheManager.__init__ rolls back _active_gpu_instance cleanly
        from kv_cache import KVCacheManager
        caught_init_err = False
        try:
            _ = KVCacheManager(num_layers=0, max_seq_len=64, num_kv_heads=4, head_dim=32)
        except ValueError:
            caught_init_err = True
        assert caught_init_err and not KVCacheManager._active_gpu_instance, (
            "_active_gpu_instance was not rolled back after kv_cache_init exception"
        )

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
            created_mmaps = engine_mmap.kv_cache.mmap_files
            assert len(created_mmaps) == 2 and all(os.path.exists(p) for p in created_mmaps)
            ids_mmap, _ = engine_mmap.generate_ids(
                prompt_ids, max_new_tokens=6, temperature=0.0, stop_on_eos=False
            )
            print(f"  [mmap KV Offload] device_bytes=0, ids={ids_mmap}")
            assert ids_mmap == ids_full, f"mmap KV offload mismatch: {ids_mmap} != {ids_full}"

        # Confirm mmap files were cleaned up on close()
        assert all(not os.path.exists(p) for p in created_mmaps)

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


def test_v060_prefill_tile_and_fused_residual_kernels(matmul_module) -> None:
    """
    Verify v0.6.0 Stage 6C kernel additions:
    1. Multi-row prefill kernels (`TILE_M = 4`, `M >= 4`) for `Q4_0`, `Q8_0`, and `Q4_K`
       match single-row (`M = 1`) wave kernel output bit-close on identical random weights
       (including non-multiple-of-4 `M = 7`).
    2. Fused `rmsnorm_residual` and `residual_add` match FP32-accumulated reference.
    """
    print("--- Testing v0.6.0 Prefill TILE_M=4 Equivalence & Fused Residual Kernels ---")
    rng = np.random.default_rng(601)
    N, K = 128, 256
    w_fp32 = rng.standard_normal((N, K), dtype=np.float32) * 0.2
    w_q4_0 = quantize_q4_0_cpu(w_fp32)
    w_q8_0 = quantize_q8_0_cpu(w_fp32)
    w_q4_k = quantize_q4_k_cpu(w_fp32)

    for M in (4, 7, 16):
        A = (rng.standard_normal((M, K), dtype=np.float32) * 0.2).astype(np.float16)
        for q_name, w_buf, fn in (
            ("Q4_0", w_q4_0, matmul_module.matmul_q4_0),
            ("Q8_0", w_q8_0, matmul_module.matmul_q8_0),
            ("Q4_K", w_q4_k, matmul_module.matmul_q4_k),
        ):
            c_prefill = np.empty((M, N), dtype=np.float16)
            fn(A, w_buf, c_prefill, M, N, K)

            # Compute row-by-row using the M=1 single-row wave kernel path
            c_single = np.empty((M, N), dtype=np.float16)
            for m in range(M):
                row_in = np.ascontiguousarray(A[m : m + 1])
                row_out = np.empty((1, N), dtype=np.float16)
                fn(row_in, w_buf, row_out, 1, N, K)
                c_single[m] = row_out[0]

            diff = float(np.max(np.abs(c_prefill.astype(np.float32) - c_single.astype(np.float32))))
            assert diff == 0.0, f"{q_name} prefill M={M} vs M=1 wave mismatch: max_diff={diff}"
    print("  [Prefill TILE_M=4 vs M=1 Wave] Q4_0, Q8_0, Q4_K bit-identical across M=4, 7, 16")

    # Test fused rmsnorm_residual and residual_add
    M_res, K_res = 9, 256
    eps = 1e-5
    x = (rng.standard_normal((M_res, K_res), dtype=np.float32) * 0.5).astype(np.float16)
    res = (rng.standard_normal((M_res, K_res), dtype=np.float32) * 0.5).astype(np.float16)
    weight = (rng.standard_normal(K_res, dtype=np.float32) * 0.2 + 1.0).astype(np.float16)

    h_gpu = np.empty_like(x)
    norm_gpu = np.empty_like(x)
    matmul_module.rmsnorm_residual(x, res, weight, h_gpu, norm_gpu, M_res, K_res, eps)

    h_ref = (x.astype(np.float32) + res.astype(np.float32)).astype(np.float16)
    norm_ref = np.empty_like(x)
    matmul_module.rmsnorm(h_ref, weight, norm_ref, M_res, K_res, eps)

    assert np.array_equal(h_gpu, h_ref), "rmsnorm_residual h_out mismatch"
    assert np.array_equal(norm_gpu, norm_ref), "rmsnorm_residual norm_out mismatch"

    add_gpu = np.empty_like(x)
    matmul_module.residual_add(x, res, add_gpu, M_res * K_res)
    assert np.array_equal(add_gpu, h_ref), "residual_add mismatch"
    print("  [rmsnorm_residual & residual_add] Bit-identical to unfused reference")


def test_v061_q6_k_kernels_and_qwen2_mixed_q4km_and_guards(matmul_module) -> None:
    """
    Verify v0.6.1 additions on GPU:
    1. C-1: `dequantize_q6_k` and `matmul_q6_k` (single-row wave and `TILE_M=4` prefill wave).
    2. C-1 / C-2 / C-3 / C-7: End-to-end mixed `Q4_K` + `Q6_K` (`Q4_K_M`) inference with
       `qwen2.*` metadata keys, GPT-2 `Ġ` BPE tokenizer, optional QKV biases, `cache_weights=True`,
       and `max_new_tokens=0` / `max_seq_len` overflow guards.
    3. S-2 / N-4: PyBind11 `int16`, read-only output, strided quantized buffer, and `matmul_nt` shape guards.
    """
    # Imported here (not at module scope): src/inference.py imports matmul_module
    # at module scope and would break collection on a CPU-only host.
    from inference import LlamaInferenceEngine

    print("--- Testing v0.6.1 Q6_K Kernels, Qwen2/GPT-2 BPE Mixed Q4_K_M & Bindings Guards ---")
    rng = np.random.default_rng(611)
    num_elements = 512 * 256
    w_fp32 = rng.standard_normal(num_elements, dtype=np.float32) * 0.3
    q6k_bytes = quantize_q6_k_cpu(w_fp32)

    ref_fp16 = dequantize_q6_k_cpu(q6k_bytes, num_elements)
    gpu_fp16 = np.empty(num_elements, dtype=np.float16)
    matmul_module.dequantize_q6_k(q6k_bytes, gpu_fp16, num_elements)
    deq_diff = float(np.max(np.abs(gpu_fp16.astype(np.float32) - ref_fp16.astype(np.float32))))
    print(f"  [dequantize_q6_k] max_abs_diff={deq_diff:.6e}")
    assert deq_diff < 1e-3, f"dequantize_q6_k mismatch: {deq_diff}"

    N, K = 64, 512
    w_mat_fp32 = rng.standard_normal((N, K), dtype=np.float32) * 0.2
    w_mat_q6k = quantize_q6_k_cpu(w_mat_fp32)
    w_mat_deq = dequantize_q6_k_cpu(w_mat_q6k, N * K).reshape(N, K).astype(np.float32)

    for M in (1, 4, 7):
        A = (rng.standard_normal((M, K), dtype=np.float32) * 0.2).astype(np.float16)
        C_gpu = np.empty((M, N), dtype=np.float16)
        matmul_module.matmul_q6_k(A, w_mat_q6k, C_gpu, M, N, K)
        C_ref = A.astype(np.float32) @ w_mat_deq.T
        mm_diff = float(np.max(np.abs(C_gpu.astype(np.float32) - C_ref)))
        assert mm_diff < 5e-2, f"matmul_q6_k M={M} mismatch: {mm_diff}"

        if M >= 4:
            C_single = np.empty((M, N), dtype=np.float16)
            for m in range(M):
                row_in = np.ascontiguousarray(A[m : m + 1])
                row_out = np.empty((1, N), dtype=np.float16)
                matmul_module.matmul_q6_k(row_in, w_mat_q6k, row_out, 1, N, K)
                C_single[m] = row_out[0]
            wave_diff = float(np.max(np.abs(C_gpu.astype(np.float32) - C_single.astype(np.float32))))
            assert wave_diff == 0.0, f"Q6_K prefill M={M} vs M=1 wave mismatch: {wave_diff}"
    print("  [matmul_q6_k] M=1, 4, 7 verified (TILE_M=4 bit-identical to M=1 wave)")

    # S-2 / N-4: Bindings validation guards
    a_ok = np.zeros((2, 32), dtype=np.float16)
    b_ok = np.zeros((4, 32), dtype=np.float16)
    c_ok = np.zeros((2, 4), dtype=np.float16)

    # 1. int16 array rejected as FP16
    a_int16 = np.zeros((2, 32), dtype=np.int16)
    try:
        matmul_module.matmul_nt(a_int16, b_ok, c_ok, 2, 4, 32)
        raise AssertionError("Expected ValueError for int16 input array")
    except ValueError:
        pass

    # 2. Read-only output array rejected
    c_ro = np.zeros((2, 4), dtype=np.float16)
    c_ro.setflags(write=False)
    try:
        matmul_module.matmul_nt(a_ok, b_ok, c_ro, 2, 4, 32)
        raise AssertionError("Expected ValueError for read-only output array")
    except ValueError:
        pass

    # 3. Strided quantized weight buffer rejected
    q4_strided = np.zeros((4, 36), dtype=np.uint8)[:, ::2]
    try:
        matmul_module.matmul_q4_0(a_ok, q4_strided, c_ok, 2, 4, 32)
        raise AssertionError("Expected ValueError for non-contiguous quantized buffer")
    except ValueError:
        pass

    # 4. 1D B_nt rejected by matmul_nt
    try:
        matmul_module.matmul_nt(a_ok, b_ok.reshape(-1), c_ok, 2, 4, 32)
        raise AssertionError("Expected ValueError for 1D B_nt in matmul_nt")
    except ValueError:
        pass
    print("  [S-2 / N-4 Bindings Guards] int16, read-only output, strided quant buffer, and 1D B_nt rejected")

    # End-to-end mixed Q4_K + Q6_K ('Q4_K_M') model with qwen2.* metadata, GPT-2 'Ġ' BPE, and QKV biases
    hidden = 256
    inter = 512
    n_heads = 4
    n_kv = 2
    head_dim = 64
    q_dim = n_heads * head_dim
    kv_dim = n_kv * head_dim

    gpt2_tokens = [
        "<pad>", "<s>", "</s>",
        "H", "e", "l", "o", "\u0120", "w", "r", "d",
        "He", "ll", "llo", "Hello",
        "\u0120w", "or", "orl", "orld", "\u0120world",
    ]
    gpt2_merges = [
        "H e", "l l", "ll o", "He llo",
        "\u0120 w", "o r", "or l", "orl d", "\u0120w orld",
    ]
    vocab_size = len(gpt2_tokens)

    def _q4k(rows: int, cols: int) -> Tuple[Tuple[int, int], GGMLType, bytes]:
        arr = (rng.standard_normal((rows, cols), dtype=np.float32) * 0.05).astype(np.float32)
        return (cols, rows), GGMLType.Q4_K, quantize_q4_k_cpu(arr).tobytes()

    def _q6k(rows: int, cols: int) -> Tuple[Tuple[int, int], GGMLType, bytes]:
        arr = (rng.standard_normal((rows, cols), dtype=np.float32) * 0.05).astype(np.float32)
        return (cols, rows), GGMLType.Q6_K, quantize_q6_k_cpu(arr).tobytes()

    norm_ones = np.ones(hidden, dtype=np.float32).tobytes()
    q_bias = np.zeros(q_dim, dtype=np.float32).tobytes()
    k_bias = np.zeros(kv_dim, dtype=np.float32).tobytes()
    v_bias = np.zeros(kv_dim, dtype=np.float32).tobytes()

    tensors = [
        ("token_embd.weight", *_q6k(vocab_size, hidden)),
        ("output_norm.weight", (hidden,), GGMLType.F32, norm_ones),
        ("output.weight", *_q6k(vocab_size, hidden)),
        ("blk.0.attn_norm.weight", (hidden,), GGMLType.F32, norm_ones),
        ("blk.0.attn_q.weight", *_q4k(q_dim, hidden)),
        ("blk.0.attn_q.bias", (q_dim,), GGMLType.F32, q_bias),
        ("blk.0.attn_k.weight", *_q4k(kv_dim, hidden)),
        ("blk.0.attn_k.bias", (kv_dim,), GGMLType.F32, k_bias),
        ("blk.0.attn_v.weight", *_q6k(kv_dim, hidden)),
        ("blk.0.attn_v.bias", (kv_dim,), GGMLType.F32, v_bias),
        ("blk.0.attn_output.weight", *_q4k(hidden, q_dim)),
        ("blk.0.ffn_norm.weight", (hidden,), GGMLType.F32, norm_ones),
        ("blk.0.ffn_gate.weight", *_q4k(inter, hidden)),
        ("blk.0.ffn_up.weight", *_q4k(inter, hidden)),
        ("blk.0.ffn_down.weight", *_q6k(hidden, inter)),
    ]
    metadata = {
        "general.architecture": (GGUFValueType.STRING, "qwen2"),
        "qwen2.block_count": (GGUFValueType.UINT32, 1),
        "qwen2.embedding_length": (GGUFValueType.UINT32, hidden),
        "qwen2.feed_forward_length": (GGUFValueType.UINT32, inter),
        "qwen2.attention.head_count": (GGUFValueType.UINT32, n_heads),
        "qwen2.attention.head_count_kv": (GGUFValueType.UINT32, n_kv),
        "qwen2.rope.dimension_count": (GGUFValueType.UINT32, head_dim),
        "tokenizer.ggml.model": (GGUFValueType.STRING, "gpt2"),
        "tokenizer.ggml.tokens": (GGUFValueType.ARRAY, (GGUFValueType.STRING, gpt2_tokens)),
        "tokenizer.ggml.merges": (GGUFValueType.ARRAY, (GGUFValueType.STRING, gpt2_merges)),
        "tokenizer.ggml.bos_token_id": (GGUFValueType.UINT32, 1),
        "tokenizer.ggml.eos_token_id": (GGUFValueType.UINT32, 2),
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        qwen_gguf = os.path.join(tmpdir, "qwen2_q4km_q6k.gguf")
        with open(qwen_gguf, "wb") as f:
            write_synthetic_gguf(f, metadata, tensors)

        with LlamaInferenceEngine(qwen_gguf, max_seq_len=16, cache_weights=True) as eng:
            # C-7: max_new_tokens=0 returns empty list without running decode
            zero_ids, zero_m = eng.generate_ids([1, 14, 19], max_new_tokens=0)
            assert zero_ids == [] and zero_m["tokens_generated"] == 0.0

            # C-7: Prompt + max_new_tokens > max_seq_len raises ValueError upfront
            try:
                eng.generate_ids([1, 14, 19], max_new_tokens=20)
                raise AssertionError("Expected ValueError when prompt + max_new_tokens > max_seq_len")
            except ValueError:
                pass

            out_text, metrics = eng.generate("Hello world", max_new_tokens=3, stop_on_eos=False)
            assert metrics["tokens_generated"] == 3.0
            print(f"  [Qwen2 + Q6_K/Q4_K_M + QKV Bias + GPT-2 BPE] generated {int(metrics['tokens_generated'])} tokens ({out_text!r})")


if __name__ == "__main__":
    print("=== Phase 5 & v0.6.1: K-Quants (Q4_K/Q6_K), 70B Scale, Prefill & KV Offload Test Suite ===")
    try:
        import matmul_module
    except ImportError as exc:
        print(f"ERROR: matmul_module not available ({exc}). Run 'cmake --build build' first.")
        sys.exit(1)

    _checks = [
        ("Q8_0 kernels", test_q8_0_kernels),
        ("Q4_K superblock kernels & 70B scale", test_q4_k_superblock_kernels_and_70b_scale),
        ("Q4_K_M chunked prefill, batching & KV offload", test_q4km_chunked_batch_and_kv_offload),
        ("v0.6.0 prefill TILE_M=4 & fused residual", test_v060_prefill_tile_and_fused_residual_kernels),
        ("v0.6.1 Q6_K kernels, Qwen2 mixed Q4_K_M & guards", test_v061_q6_k_kernels_and_qwen2_mixed_q4km_and_guards),
    ]

    _failures = []
    for _label, _check in _checks:
        try:
            # Only the extension-dependent checks need the module passed in.
            if "matmul_module" in inspect.signature(_check).parameters:
                _check(matmul_module)
            else:
                _check()
        except AssertionError as exc:
            print(f"FAIL: {_label}: {exc}")
            _failures.append(_label)

    if _failures:
        print(f"\n=== {len(_failures)} Phase 5 test(s) failed: {', '.join(_failures)} ===")
        sys.exit(1)
    print("=== All Phase 5 & v0.6.1 Tests Passed! ===")
    sys.exit(0)

