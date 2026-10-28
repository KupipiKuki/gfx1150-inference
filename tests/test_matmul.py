#!/usr/bin/env python3
"""
Test script for HIP matrix multiplication kernel.
Validates correctness against PyTorch and measures performance.
"""

import torch
import numpy as np
import time

try:
    import matmul_module
    HIP_AVAILABLE = True
except ImportError:
    HIP_AVAILABLE = False
    print("WARNING: matmul_module not found. Run 'cmake --build .' first.")

def test_matmul_correctness(M=1024, N=1024, K=1024, tolerance=1e-3):
    if not HIP_AVAILABLE:
        print("SKIP: HIP module not available")
        return False
    
    print(f"\n=== Testing {M}x{K} @ {K}x{N} (FP16) ===")
    
    torch.manual_seed(42)
    A_np = torch.randn(M, K, dtype=torch.float16, device="cpu").numpy()
    B_np = torch.randn(K, N, dtype=torch.float16, device="cpu").numpy()
    C_np = np.zeros((M, N), dtype=np.float16)
    
    A_torch = torch.from_numpy(A_np)
    B_torch = torch.from_numpy(B_np)
    C_torch = torch.matmul(A_torch, B_torch)
    
    start_time = time.time()
    matmul_module.matmul(A_np, B_np, C_np, M, N, K)
    hip_time = time.time() - start_time
    
    C_hip = torch.from_numpy(C_np)
    max_error = (C_hip - C_torch).abs().max().item()
    mean_error = (C_hip - C_torch).abs().mean().item()
    
    print(f"Max error:   {max_error:.6f}")
    print(f"Mean error:  {mean_error:.6f}")
    print(f"HIP time:    {hip_time:.4f} seconds")
    print(f"Throughput:  {2 * M * N * K / hip_time / 1e12:.2f} TFLOPS")
    
    if max_error < tolerance:
        print("✅ PASS: Results match PyTorch within tolerance")
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
    
    for M, N, K in test_cases:
        print(f"\nTesting {M}x{K} @ {K}x{N}...", end=" ")
        A_np = torch.randn(M, K, dtype=torch.float16, device="cpu").numpy()
        B_np = torch.randn(K, N, dtype=torch.float16, device="cpu").numpy()
        C_np = np.zeros((M, N), dtype=np.float16)
        
        C_torch = torch.matmul(
            torch.from_numpy(A_np),
            torch.from_numpy(B_np)
        )
        
        matmul_module.matmul(A_np, B_np, C_np, M, N, K)
        C_hip = torch.from_numpy(C_np)
        max_error = (C_hip - C_torch).abs().max().item()
        
        if max_error < 1e-2:
            print("✅ PASS")
        else:
            print(f"❌ FAIL (max_error={max_error:.6f})")
            all_passed = False
    
    return all_passed

def main():
    print("=" * 60)
    print("GFX1150 Inference - Phase 1: HIP Matmul Tests")
    print("=" * 60)
    
    try:
        import subprocess
        result = subprocess.run(
            ["rocminfo"],
            capture_output=True,
            text=True
        )
        if "gfx1150" in result.stdout:
            print("✅ GPU: gfx1150 detected")
        else:
            print("⚠️  WARNING: gfx1150 not detected in rocminfo")
    except FileNotFoundError:
        print("❌ ERROR: rocminfo not found. Install ROCm first.")
        return
    
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
    exit(main())