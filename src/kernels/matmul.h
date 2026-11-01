#ifndef MATMUL_H
#define MATMUL_H

// Host-callable FP16 matrix multiplication launcher compiled by amdclang++ in matmul.hip.
// Computes C (M x N) = A (M x K) * B (K x N), where h_A, h_B, h_C point to host FP16 buffers.
void launch_matmul_fp16(
    const void* h_A,
    const void* h_B,
    void* h_C,
    int M,
    int N,
    int K
);

// Native-layout GGUF FP16 matrix multiplication without host transpose:
// Computes C (M x N) = A (M x K) * B_nt^T, where B_nt is (N x K) row-major in FP16.
void launch_matmul_fp16_nt(
    const void* h_A,
    const void* h_B_nt,
    void* h_C,
    int M,
    int N,
    int K
);

// Device-resident variant of launch_matmul_fp16_nt (all pointers in GPU memory).
void launch_matmul_fp16_nt_device(
    const void* d_A,
    const void* d_B_nt,
    void* d_C,
    int M,
    int N,
    int K
);

#endif // MATMUL_H
