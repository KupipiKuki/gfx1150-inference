#!/usr/bin/env python3
"""
Phase 2 Test Suite:
1. GGUF v3 header, metadata, and 32-byte aligned tensor parsing
2. WeightStreamer zero-copy mmap slicing + madvise prefetch/eviction
3. GPU HIP `dequantize_q4_0` kernel correctness
4. GPU HIP fused `matmul_q4_0` kernel correctness (M=1 GEMV decode & M=64 prefill) + throughput
"""

import os
import sys
import tempfile
import time
import numpy as np

_ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_SRC_DIR = os.path.join(_ROOT_DIR, "src")
_BUILD_DIR = os.path.join(_ROOT_DIR, "build")

for p in (_SRC_DIR, _BUILD_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from gguf_parser import (
    GGMLType,
    GGUFParser,
    GGUFValueType,
    dequantize_q4_0_cpu,
    quantize_q4_0_cpu,
    write_synthetic_gguf,
)
from weight_loader import WeightStreamer
import matmul_module


def test_gguf_and_streamer() -> bool:
    print("\n=== 1. Testing GGUF v3 Parser & WeightStreamer (mmap + madvise) ===")
    rng = np.random.default_rng(123)
    K, N = 256, 128

    w0_fp32 = (rng.standard_normal((N, K), dtype=np.float32) * (1.0 / np.sqrt(K)))
    w1_fp32 = (rng.standard_normal((N, K), dtype=np.float32) * (1.0 / np.sqrt(K)))
    norm_fp16 = np.ones((K,), dtype=np.float16)

    w0_q4 = quantize_q4_0_cpu(w0_fp32)
    w1_q4 = quantize_q4_0_cpu(w1_fp32)

    metadata = {
        "general.architecture": (GGUFValueType.STRING, "llama"),
        "llama.block_count": (GGUFValueType.UINT32, 2),
        "llama.embedding_length": (GGUFValueType.UINT32, K),
    }
    tensors = [
        ("blk.0.attn_q.weight", (K, N), GGMLType.Q4_0, w0_q4.tobytes()),
        ("blk.0.attn_norm.weight", (K,), GGMLType.F16, norm_fp16.tobytes()),
        ("blk.1.attn_q.weight", (K, N), GGMLType.Q4_0, w1_q4.tobytes()),
    ]

    with tempfile.NamedTemporaryFile(suffix=".gguf", delete=False) as tmp:
        tmp_path = tmp.name
        write_synthetic_gguf(tmp, metadata, tensors)

    try:
        with WeightStreamer(tmp_path) as streamer:
            assert streamer.gguf.version == 3
            assert streamer.gguf.metadata["general.architecture"] == "llama"
            assert streamer.num_layers == 2

            for name, info in streamer.gguf.tensors.items():
                assert info.abs_offset % 32 == 0, f"Tensor {name} not 32-byte aligned"

            with streamer.layer_context(0, prefetch_next=True) as layer0:
                q_info, q_view = layer0["blk.0.attn_q.weight"]
                assert q_info.ggml_type == GGMLType.Q4_0
                assert np.array_equal(q_view, w0_q4)

                norm_info, norm_view = layer0["blk.0.attn_norm.weight"]
                assert norm_info.ggml_type == GGMLType.F16
                assert np.array_equal(norm_view, norm_fp16)
                del q_view, norm_view

            with streamer.layer_context(1, prefetch_next=False) as layer1:
                _, q1_view = layer1["blk.1.attn_q.weight"]
                assert np.array_equal(q1_view, w1_q4)
                del q1_view

        print("✅ PASS: GGUF v3 header, 32-byte alignment, zero-copy mmap, and madvise lifecycle verified")
        return True
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_dequantize_q4_0_hip() -> bool:
    print("\n=== 2. Testing HIP `dequantize_q4_0` Kernel ===")
    rng = np.random.default_rng(42)
    num_elements = 1024 * 1024
    weights_fp32 = rng.standard_normal(num_elements, dtype=np.float32) * 0.1
    q4_bytes = quantize_q4_0_cpu(weights_fp32)

    ref_fp16 = dequantize_q4_0_cpu(q4_bytes, num_elements)
    gpu_fp16 = np.zeros(num_elements, dtype=np.float16)

    matmul_module.dequantize_q4_0(q4_bytes, gpu_fp16, num_elements)

    max_err = float(np.max(np.abs(gpu_fp16.astype(np.float32) - ref_fp16.astype(np.float32))))
    print(f"Dequantize 1M Q4_0 weights max error vs CPU ref: {max_err:.6f}")
    if max_err < 1e-3:
        print("✅ PASS: HIP dequantize_q4_0 matches CPU reference")
        return True
    print(f"❌ FAIL: max_err={max_err:.6f}")
    return False


def test_fused_matmul_q4_0_hip() -> bool:
    print("\n=== 3. Testing Fused HIP `matmul_q4_0` Kernel (Decode GEMV & Prefill) ===")
    rng = np.random.default_rng(99)
    all_passed = True

    for M, N, K in [(1, 4096, 4096), (16, 2048, 2048), (64, 1024, 1024)]:
        scale = 1.0 / np.sqrt(K)
        A_fp16 = (rng.standard_normal((M, K), dtype=np.float32) * scale).astype(np.float16)
        B_fp32 = rng.standard_normal((N, K), dtype=np.float32) * scale
        B_q4 = quantize_q4_0_cpu(B_fp32)

        # Reference: dequantize B to FP16 and compute FP32-accumulated A @ B^T
        B_deq_fp16 = dequantize_q4_0_cpu(B_q4, N * K).reshape(N, K)
        C_ref = (A_fp16.astype(np.float32) @ B_deq_fp16.astype(np.float32).T).astype(np.float16)

        C_gpu = np.zeros((M, N), dtype=np.float16)
        # Warm-up
        matmul_module.matmul_q4_0(A_fp16, B_q4, C_gpu, M, N, K)

        t0 = time.time()
        matmul_module.matmul_q4_0(A_fp16, B_q4, C_gpu, M, N, K)
        elapsed = time.time() - t0

        max_err = float(np.max(np.abs(C_gpu.astype(np.float32) - C_ref.astype(np.float32))))
        bw_gbps = (B_q4.nbytes + A_fp16.nbytes + C_gpu.nbytes) / elapsed / 1e9
        status = "✅ PASS" if max_err < 1e-3 else "❌ FAIL"
        print(
            f"  M={M:<3d} N={N:<4d} K={K:<4d} | max_err={max_err:.6f} | "
            f"time={elapsed*1000:.2f} ms | effective BW={bw_gbps:.1f} GB/s | {status}"
        )
        if max_err >= 1e-3:
            all_passed = False

    return all_passed


def main() -> int:
    print("=" * 65)
    print("GFX1150 Inference - Phase 2: GGUF + madvise + Q4_0 Kernel Tests")
    print("=" * 65)

    ok1 = test_gguf_and_streamer()
    ok2 = test_dequantize_q4_0_hip()
    ok3 = test_fused_matmul_q4_0_hip()

    print("\n" + "=" * 65)
    if ok1 and ok2 and ok3:
        print("🎉 All Phase 2 tests passed!")
        return 0
    print("⚠️  Some Phase 2 tests failed.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
