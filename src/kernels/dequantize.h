#ifndef DEQUANTIZE_H
#define DEQUANTIZE_H

#include <cstdint>

// Standard GGML Q4_0 block size: 32 weights per 18-byte block (2B FP16 scale + 16B nibbles)
constexpr int QK4_0 = 32;
constexpr int BLOCK_Q4_0_BYTES = 18;

// Dequantize `num_elements` (must be a multiple of 32) from Q4_0 bytes into FP16 (half) output
void launch_dequantize_q4_0(
    const void* h_q4,
    void* h_fp16_out,
    int num_elements
);

// Fused FP16 x Q4_0 matrix multiplication:
// Computes C (M x N, FP16) = A (M x K, FP16) * B^T (N x K, Q4_0 quantized along K)
// Avoids 4x memory expansion by dequantizing Q4_0 blocks directly in GPU registers.
void launch_matmul_q4_0(
    const void* h_A_fp16,
    const void* h_B_q4,
    void* h_C_fp16,
    int M,
    int N,
    int K
);

#endif // DEQUANTIZE_H

