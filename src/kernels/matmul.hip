#ifndef MATMUL_HIP
#define MATMUL_HIP

#include <hip/hip_runtime.h>
#include <hip/hip_fp16.h>

// FP16 matrix multiplication kernel (M x K) * (K x N) = (M x N)
__global__ void matmul_kernel(
    const half* __restrict__ A,
    const half* __restrict__ B,
    half* __restrict__ C,
    const int M,
    const int N,
    const int K
) {
    const int row = blockIdx.y * blockDim.y + threadIdx.y;
    const int col = blockIdx.x * blockDim.x + threadIdx.x;
    
    if (row >= M || col >= N) return;
    
    half sum = __float2half(0.0f);
    for (int k = 0; k < K; ++k) {
        half a = A[row * K + k];
        half b = B[k * N + col];
        sum = __hadd(sum, __hmul(a, b));
    }
    C[row * N + col] = sum;
}

// Optimized version with shared memory tiling
__global__ void matmul_kernel_tiled(
    const half* __restrict__ A,
    const half* __restrict__ B,
    half* __restrict__ C,
    const int M,
    const int N,
    const int K
) {
    const int BLOCK_SIZE = 16;
    const int row = blockIdx.y * BLOCK_SIZE + threadIdx.y;
    const int col = blockIdx.x * BLOCK_SIZE + threadIdx.x;
    
    if (row >= M || col >= N) return;
    
    __shared__ half As[BLOCK_SIZE][BLOCK_SIZE];
    __shared__ half Bs[BLOCK_SIZE][BLOCK_SIZE];
    half sum = __float2half(0.0f);
    
    for (int t = 0; t < (K + BLOCK_SIZE - 1) / BLOCK_SIZE; ++t) {
        if (row < M && (threadIdx.x + t * BLOCK_SIZE) < K) {
            As[threadIdx.y][threadIdx.x] = A[row * K + (threadIdx.x + t * BLOCK_SIZE)];
        } else {
            As[threadIdx.y][threadIdx.x] = __float2half(0.0f);
        }
        
        if (col < N && (threadIdx.y + t * BLOCK_SIZE) < K) {
            Bs[threadIdx.y][threadIdx.x] = B[(threadIdx.y + t * BLOCK_SIZE) * N + col];
        } else {
            Bs[threadIdx.y][threadIdx.x] = __float2half(0.0f);
        }
        
        __syncthreads();
        
        for (int i = 0; i < BLOCK_SIZE; ++i) {
            sum = __hadd(sum, __hmul(As[threadIdx.y][i], Bs[i][threadIdx.x]));
        }
        
        __syncthreads();
    }
    
    if (row < M && col < N) {
        C[row * N + col] = sum;
    }
}

#endif // MATMUL_HIP