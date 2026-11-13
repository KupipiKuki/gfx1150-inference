#!/usr/bin/env python3
"""
Test script for HIP matrix multiplication kernel.
Validates correctness against PyTorch (or NumPy FP32 reference) and measures performance.

Phase 7A-1: converted to a pytest module.

- Every ``test_*`` function asserts and returns ``None``. The previous version
  returned ``True``/``False``, which pytest ignores: such a test could never fail
  (audit AUD-2).
- The module is marked ``gpu``; the ``matmul_module`` fixture skips the tests
  when the compiled HIP extension is unavailable, so the module imports cleanly
  on a CPU-only host.
- ``python3 tests/test_matmul.py`` still works as a standalone script.
"""

import os
import sys
import inspect
import shutil
import subprocess
import time
import numpy as np
import pytest

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

# Automatically include project build/ directory in module search path
_BUILD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "build"))
if os.path.isdir(_BUILD_DIR) and _BUILD_DIR not in sys.path:
    sys.path.insert(0, _BUILD_DIR)

# Every test in this module exercises the HIP extension.
pytestmark = pytest.mark.gpu


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


@pytest.mark.slow
def test_matmul_correctness(matmul_module, M=1024, N=1024, K=1024, tolerance=1e-3) -> None:
    """FP16 matmul must match the FP32-accumulated NumPy/PyTorch reference."""
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

    assert max_error < tolerance, (
        f"Max error {max_error:.6f} exceeds tolerance {tolerance} "
        f"({ref_name} reference, {M}x{K} @ {K}x{N})"
    )
    print(f"✅ PASS: Results match {ref_name} within tolerance")


def test_edge_cases(matmul_module) -> None:
    """Degenerate and non-power-of-two shapes must match the reference."""
    print("\n=== Testing Edge Cases ===")

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

        assert max_error < 1e-2, (
            f"matmul {M}x{K} @ {K}x{N} max_error={max_error:.6f} exceeds 1e-2"
        )
        print(f"✅ PASS (max_error={max_error:.6f})")

        # Also test matmul_nt (native GGUF N x K layout without host transpose)
        B_nt = np.ascontiguousarray(B_np.T)
        C_nt = np.zeros((M, N), dtype=np.float16)
        matmul_module.matmul_nt(A_np, B_nt, C_nt, M, N, K)
        nt_err = float(np.abs(C_nt.astype(np.float32) - C_ref.astype(np.float32)).max())
        assert nt_err < 1e-2, (
            f"matmul_nt {M}x{K} @ {K}x{N} max_error={nt_err:.6f} exceeds 1e-2"
        )

    # Validate matmul_nt rejects swapped 2D B_nt shape (K, N) when K != N
    A_rect = _make_random_fp16(8, 64, seed=201)
    B_wrong = _make_random_fp16(64, 32, seed=202)  # (K=64, N=32) instead of (N=32, K=64)
    C_rect = np.zeros((8, 32), dtype=np.float16)
    try:
        matmul_module.matmul_nt(A_rect, B_wrong, C_rect, 8, 32, 64)
    except ValueError:
        print("\n✅ PASS: matmul_nt rejected swapped (K, N) B_nt shape")
    else:
        raise AssertionError(
            "matmul_nt did not reject swapped (K, N) B_nt shape "
            "(expected ValueError for K=64, N=32)"
        )


def main() -> int:
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

    try:
        import matmul_module
    except ImportError as exc:
        print(f"❌ ERROR: matmul_module not available ({exc}). "
              "Run 'cmake --build build' first.")
        return 1

    checks = [
        ("Correctness test", test_matmul_correctness),
        ("Edge cases test", test_edge_cases),
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

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for label, _ in checks:
        print(f"{label}: {'❌ FAIL' if label in failures else '✅ PASS'}")

    if failures:
        print("\n⚠️  Some tests failed. Check implementation.")
        return 1
    print("\n🎉 All tests passed! Phase 1 complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
