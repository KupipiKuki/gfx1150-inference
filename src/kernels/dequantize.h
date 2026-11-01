#ifndef DEQUANTIZE_H
#define DEQUANTIZE_H

#include <cstdint>

// Standard GGML Q4_0 block size: 32 weights per 18-byte block (2B FP16 scale + 16B nibbles)
constexpr int QK4_0 = 32;
constexpr int BLOCK_Q4_0_BYTES = 18;

// Standard GGML Q8_0 block size: 32 weights per 34-byte block (2B FP16 scale + 32B int8)
constexpr int QK8_0 = 32;
constexpr int BLOCK_Q8_0_BYTES = 34;

// Standard GGML Q4_K super-block size: 256 weights per 144-byte block
// (2B FP16 d + 2B FP16 dmin + 12B packed 6-bit scales/mins + 128B nibbles)
constexpr int QK_K = 256;
constexpr int K_SCALE_SIZE = 12;
constexpr int BLOCK_Q4_K_BYTES = 144;

// Standard GGML Q6_K super-block size: 256 weights per 210-byte block
// (128B ql low 4-bits + 64B qh high 2-bits + 16B int8 scales + 2B FP16 d)
constexpr int BLOCK_Q6_K_BYTES = 210;

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

// Dequantize `num_elements` (must be a multiple of 32) from Q8_0 bytes into FP16 (half) output
void launch_dequantize_q8_0(
    const void* h_q8,
    void* h_fp16_out,
    int num_elements
);

// Fused FP16 x Q8_0 matrix multiplication:
// Computes C (M x N, FP16) = A (M x K, FP16) * B^T (N x K, Q8_0 quantized along K)
void launch_matmul_q8_0(
    const void* h_A_fp16,
    const void* h_B_q8,
    void* h_C_fp16,
    int M,
    int N,
    int K
);

// Dequantize `num_elements` (must be a multiple of 256) from Q4_K super-blocks into FP16 output
void launch_dequantize_q4_k(
    const void* h_q4k,
    void* h_fp16_out,
    int num_elements
);

// Fused FP16 x Q4_K (Q4_K_M / Q4_K_S) matrix multiplication:
// Computes C (M x N, FP16) = A (M x K, FP16) * B^T (N x K, Q4_K quantized along K)
void launch_matmul_q4_k(
    const void* h_A_fp16,
    const void* h_B_q4k,
    void* h_C_fp16,
    int M,
    int N,
    int K
);

// Dequantize `num_elements` (must be a multiple of 256) from Q6_K super-blocks into FP16 output
void launch_dequantize_q6_k(
    const void* h_q6k,
    void* h_fp16_out,
    int num_elements
);

// Fused FP16 x Q6_K matrix multiplication:
// Computes C (M x N, FP16) = A (M x K, FP16) * B^T (N x K, Q6_K quantized along K)
void launch_matmul_q6_k(
    const void* h_A_fp16,
    const void* h_B_q6k,
    void* h_C_fp16,
    int M,
    int N,
    int K
);

// Device-resident fused quantized matmul launchers (all pointers in GPU memory)
void launch_matmul_q4_0_device(
    const void* d_A_fp16,
    const void* d_B_q4,
    void* d_C_fp16,
    int M,
    int N,
    int K
);

void launch_matmul_q8_0_device(
    const void* d_A_fp16,
    const void* d_B_q8,
    void* d_C_fp16,
    int M,
    int N,
    int K
);

void launch_matmul_q4_k_device(
    const void* d_A_fp16,
    const void* d_B_q4k,
    void* d_C_fp16,
    int M,
    int N,
    int K
);

void launch_matmul_q6_k_device(
    const void* d_A_fp16,
    const void* d_B_q6k,
    void* d_C_fp16,
    int M,
    int N,
    int K
);

#endif // DEQUANTIZE_H

