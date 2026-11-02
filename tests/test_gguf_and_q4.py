#!/usr/bin/env python3
"""
Phase 2 Test Suite:
1. GGUF v3 header, metadata, and 32-byte aligned tensor parsing
2. WeightStreamer zero-copy mmap slicing + madvise prefetch/eviction
3. GPU HIP `dequantize_q4_0` kernel correctness
4. GPU HIP fused `matmul_q4_0` kernel correctness (M=1 GEMV decode & M=64 prefill) + throughput

Phase 7A-1: converted to a pytest module.

- Every ``test_*`` function asserts and returns ``None``. The previous version
  returned ``True``/``False``, which pytest ignores: such a test could never fail
  (audit AUD-2).
- ``import matmul_module`` moved out of module scope into the ``matmul_module``
  fixture, so this module imports cleanly on a CPU-only host instead of raising
  a collection error (audit AUD-2).
- The module is marked ``gpu``; ``python3 tests/test_gguf_and_q4.py`` still works
  as a standalone script.
"""

import os
import sys
import inspect
import tempfile
import time
import numpy as np
import pytest

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

# Every test in this module belongs to the hardware lane.
pytestmark = pytest.mark.gpu


def test_gguf_and_streamer() -> None:
    """GGUF v3 parsing, 32-byte alignment, zero-copy mmap and madvise lifecycle."""
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
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_dequantize_q4_0_hip(matmul_module) -> None:
    """HIP ``dequantize_q4_0`` must match the CPU reference exactly."""
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
    assert max_err < 1e-3, f"dequantize_q4_0 max_err={max_err:.6f} exceeds 1e-3"
    print("✅ PASS: HIP dequantize_q4_0 matches CPU reference")


@pytest.mark.slow
def test_fused_matmul_q4_0_hip(matmul_module) -> None:
    """Fused HIP ``matmul_q4_0`` must match a dequantize-then-matmul reference."""
    print("\n=== 3. Testing Fused HIP `matmul_q4_0` Kernel (Decode GEMV & Prefill) ===")
    rng = np.random.default_rng(99)

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
        assert max_err < 1e-3, (
            f"matmul_q4_0 M={M} N={N} K={K} max_err={max_err:.6f} exceeds 1e-3"
        )


def main() -> int:
    print("=" * 65)
    print("GFX1150 Inference - Phase 2: GGUF + madvise + Q4_0 Kernel Tests")
    print("=" * 65)

    try:
        import matmul_module
    except ImportError as exc:
        print(f"❌ ERROR: matmul_module not available ({exc}). "
              "Run 'cmake --build build' first.")
        return 1

    checks = [
        ("GGUF parser & WeightStreamer", test_gguf_and_streamer),
        ("HIP dequantize_q4_0", test_dequantize_q4_0_hip),
        ("HIP fused matmul_q4_0", test_fused_matmul_q4_0_hip),
    ]

    failures = []
    for label, check in checks:
        try:
            # Only the extension-dependent checks need the module passed in.
            if "matmul_module" in inspect.signature(check).parameters:
                check(matmul_module)
            else:
                check()
        except AssertionError as exc:
            print(f"❌ FAIL: {label}: {exc}")
            failures.append(label)

    print("\n" + "=" * 65)
    if failures:
        print(f"⚠️  {len(failures)} Phase 2 test(s) failed: {', '.join(failures)}")
        return 1
    print("🎉 All Phase 2 tests passed!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
