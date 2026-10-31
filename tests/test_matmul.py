#!/usr/bin/env python3
"""
Test script for HIP matrix multiplication kernel.
Validates correctness against PyTorch (or NumPy FP32 reference) and measures performance.
"""

import os
import sys
import shutil
import subprocess
import time
import numpy as np

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

# Automatically include project build/ directory in module search path
_BUILD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "build"))
if os.path.isdir(_BUILD_DIR) and _BUILD_DIR not in sys.path:
    sys.path.insert(0, _BUILD_DIR)

try:
    import matmul_module
    HIP_AVAILABLE = True
except ImportError as e:
    HIP_AVAILABLE = False
    print(f"WARNING: matmul_module not found ({e}). Run 'cmake --build build' first.")


def _make_random_fp16(M, K, seed=None, scale=None):
    if scale is None:
        # Scale by 1/sqrt(K) (standard Xavier/attention scaling) so dot products
        # remain O(1) and FP16 ULP spacing stays <= 1e-3
        scale = 1.0 / np.sqrt(max(K, 1))
    if TORCH_AVAILABLE:
        if seed is not None:
            torch.manual_seed(seed)
        return (torch.randn(M, K, dtype=torch.float32, device="cpu") * scale).to(torch.float16).numpy()
    rng = np.random.default_rng(seed)
    return (rng.standard_normal((M, K), dtype=np.float32) * scale).astype(np.float16)


def _reference_matmul_fp16(A_np, B_np):
    if TORCH_AVAILABLE:
        return torch.matmul(torch.from_numpy(A_np), torch.from_numpy(B_np)).numpy()
    return (A_np.astype(np.float32) @ B_np.astype(np.float32)).astype(np.float16)


def test_matmul_correctness(M=1024, N=1024, K=1024, tolerance=1e-3):
    if not HIP_AVAILABLE:
        print("SKIP: HIP module not available")
        return False

    ref_name = "PyTorch" if TORCH_AVAILABLE else "NumPy (FP32 accum)"
    print(f"\n=== Testing {M}x{K} @ {K}x{N} (FP16 vs {ref_name}) ===")

    A_np = _make_random_fp16(M, K, seed=42)
    B_np = _make_random_fp16(K, N, seed=43)
    C_np = np.zeros((M, N), dtype=np.float16)

    C_ref = _reference_matmul_fp16(A_np, B_np)

    # Warm-up run to initialize HIP context and allocate workspace buffers
    matmul_module.matmul(A_np, B_np, C_np, M, N, K)

    start_time = time.time()
    matmul_module.matmul(A_np, B_np, C_np, M, N, K)
    hip_time = time.time() - start_time

    diff = np.abs(C_np.astype(np.float32) - C_ref.astype(np.float32))
    max_error = float(diff.max())
    mean_error = float(diff.mean())

    print(f"Max error:   {max_error:.6f}")
    print(f"Mean error:  {mean_error:.6f}")
    print(f"HIP time:    {hip_time:.4f} seconds")
    print(f"Throughput:  {2 * M * N * K / hip_time / 1e12:.2f} TFLOPS")

    if max_error < tolerance:
        print(f"✅ PASS: Results match {ref_name} within tolerance")
        return True
    else:
        print(f"❌ FAIL: Max error {max_error:.6f} exceeds tolerance {tolerance}")
        return False


def test_edge_cases():
    if not HIP_AVAILABLE:
        print("SKIP: HIP module not available")
        return False

    print("\n=== Testing Edge Cases ===")
    all_passed = True

    test_cases = [
        (1, 1024, 1024),    # Single row
        (1024, 1, 1024),    # Single column
        (1, 1, 1),          # Scalar
        (1023, 1023, 1023), # Non-power-of-2
        (16, 16, 16),       # Small matrices
        (1024, 512, 256),   # Rectangular
    ]

    for idx, (M, N, K) in enumerate(test_cases):
        print(f"\nTesting {M}x{K} @ {K}x{N}...", end=" ")
        A_np = _make_random_fp16(M, K, seed=100 + idx * 2)
        B_np = _make_random_fp16(K, N, seed=101 + idx * 2)
        C_np = np.zeros((M, N), dtype=np.float16)

        C_ref = _reference_matmul_fp16(A_np, B_np)

        matmul_module.matmul(A_np, B_np, C_np, M, N, K)
        max_error = float(np.abs(C_np.astype(np.float32) - C_ref.astype(np.float32)).max())

        if max_error < 1e-2:
            print(f"✅ PASS (max_error={max_error:.6f})")
        else:
            print(f"❌ FAIL (max_error={max_error:.6f})")
            all_passed = False

    return all_passed


def main():
    print("=" * 60)
    print("GFX1150 Inference - Phase 1: HIP Matmul Tests")
    print("=" * 60)

    rocminfo_bin = shutil.which("rocminfo") or "/opt/rocm/bin/rocminfo"
    try:
        result = subprocess.run(
            [rocminfo_bin],
            capture_output=True,
            text=True
        )
        if "gfx1150" in result.stdout:
            print("✅ GPU: gfx1150 detected")
        else:
            print("⚠️  WARNING: gfx1150 not detected in rocminfo")
    except FileNotFoundError:
        print("❌ ERROR: rocminfo not found. Install ROCm first.")
        return 1

    correctness_pass = test_matmul_correctness()
    edge_cases_pass = test_edge_cases()

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Correctness test: {'✅ PASS' if correctness_pass else '❌ FAIL'}")
    print(f"Edge cases test:   {'✅ PASS' if edge_cases_pass else '❌ FAIL'}")

    if correctness_pass and edge_cases_pass:
        print("\n🎉 All tests passed! Phase 1 complete.")
        return 0
    else:
        print("\n⚠️  Some tests failed. Check implementation.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
