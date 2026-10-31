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

#endif // MATMUL_H

