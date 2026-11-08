#ifndef MATMUL_H
#define MATMUL_H

#include <cstddef>

// Identical to hip_runtime.h's typedef so this header stays includable from
// non-HIP C++ translation units (python_bindings/bindings.cpp builds as CXX).
// Redundant typedefs of the same type are legal C++.
typedef struct ihipStream_t* hipStream_t;

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
// `stream` is the compute stream the kernel is launched on (7E explicit-stream
// topology; the default 0 keeps the synchronous host wrappers unchanged).
void launch_matmul_fp16_nt_device(
    const void* d_A,
    const void* d_B_nt,
    void* d_C,
    int M,
    int N,
    int K,
    hipStream_t stream = 0
);

#endif // MATMUL_H
