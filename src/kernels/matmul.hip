#include "matmul.h"
#include <hip/hip_runtime.h>
#include <hip/hip_fp16.h>
#include <stdexcept>
#include <string>

#define HIP_CHECK(call)                                                        \
    do {                                                                       \
        hipError_t err = (call);                                               \
        if (err != hipSuccess) {                                               \
            throw std::runtime_error(                                          \
                std::string("HIP error at ") + __FILE__ + ":" +                \
                std::to_string(__LINE__) + " - " + hipGetErrorString(err));    \
        }                                                                      \
    } while (0)

constexpr int BLOCK_SIZE = 16;

// Naive FP16 matrix multiplication kernel (reference) with FP32 accumulation
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

    float sum = 0.0f;
    for (int k = 0; k < K; ++k) {
        sum += __half2float(A[row * K + k]) * __half2float(B[k * N + col]);
    }
    C[row * N + col] = __float2half(sum);
}

// 16x16 shared-memory tiled FP16 kernel for small/edge-case matrices
__global__ void matmul_kernel_tiled(
    const half* __restrict__ A,
    const half* __restrict__ B,
    half* __restrict__ C,
    const int M,
    const int N,
    const int K
) {
    const int tx = threadIdx.x;
    const int ty = threadIdx.y;
    const int row = blockIdx.y * BLOCK_SIZE + ty;
    const int col = blockIdx.x * BLOCK_SIZE + tx;

    // +1 padding avoids 32-bank LDS conflicts on RDNA3.5 (gfx1150)
    __shared__ float As[BLOCK_SIZE][BLOCK_SIZE + 1];
    __shared__ float Bs[BLOCK_SIZE][BLOCK_SIZE + 1];

    float sum = 0.0f;
    const int num_tiles = (K + BLOCK_SIZE - 1) / BLOCK_SIZE;

    for (int t = 0; t < num_tiles; ++t) {
        const int a_col = t * BLOCK_SIZE + tx;
        As[ty][tx] = (row < M && a_col < K) ? __half2float(A[row * K + a_col]) : 0.0f;

        const int b_row = t * BLOCK_SIZE + ty;
        Bs[ty][tx] = (b_row < K && col < N) ? __half2float(B[b_row * N + col]) : 0.0f;

        __syncthreads();

        #pragma unroll
        for (int i = 0; i < BLOCK_SIZE; ++i) {
            sum += As[ty][i] * Bs[i][tx];
        }

        __syncthreads();
    }

    if (row < M && col < N) {
        C[row * N + col] = __float2half(sum);
    }
}

// High-performance 2D register-blocked tiled kernel for gfx1150 (256 threads/workgroup)
// Workgroup: 16x16 threads (8 Wave32 wavefronts).
// Block tile: BM=64 x BN=64, BK=16. Each thread computes a TM=4 x TN=4 sub-tile in registers.
constexpr int BM = 64;
constexpr int BN = 64;
constexpr int BK = 16;
constexpr int TM = 4;
constexpr int TN = 4;

__global__ __launch_bounds__(256) void matmul_kernel_reg_tiled(
    const half* __restrict__ A,
    const half* __restrict__ B,
    half* __restrict__ C,
    const int M,
    const int N,
    const int K
) {
    const int tx = threadIdx.x; // 0..15
    const int ty = threadIdx.y; // 0..15
    const int tid = ty * 16 + tx; // 0..255

    const int block_row = blockIdx.y * BM;
    const int block_col = blockIdx.x * BN;

    __shared__ float As[BM][BK + 1];
    __shared__ float Bs[BK][BN + 1];

    float acc[TM][TN] = {{0.0f}};

    // 256 threads load 64x16 = 1024 elements of A (4 elements per thread)
    // and 16x64 = 1024 elements of B (4 elements per thread)
    const int a_tile_row = tid / 4;       // 0..63
    const int a_tile_col = (tid % 4) * 4; // 0, 4, 8, 12

    const int b_tile_row = tid / 16;       // 0..15
    const int b_tile_col = (tid % 16) * 4; // 0, 4, ..., 60

    const int num_tiles = (K + BK - 1) / BK;

    for (int t = 0; t < num_tiles; ++t) {
        const int k_base = t * BK;
        const int g_a_row = block_row + a_tile_row;
        const int g_b_row = k_base + b_tile_row;

        #pragma unroll
        for (int i = 0; i < 4; ++i) {
            const int g_a_col = k_base + a_tile_col + i;
            As[a_tile_row][a_tile_col + i] =
                (g_a_row < M && g_a_col < K) ? __half2float(A[g_a_row * K + g_a_col]) : 0.0f;

            const int g_b_col = block_col + b_tile_col + i;
            Bs[b_tile_row][b_tile_col + i] =
                (g_b_row < K && g_b_col < N) ? __half2float(B[g_b_row * N + g_b_col]) : 0.0f;
        }

        __syncthreads();

        #pragma unroll
        for (int k = 0; k < BK; ++k) {
            float a_reg[TM];
            float b_reg[TN];
            #pragma unroll
            for (int m = 0; m < TM; ++m) {
                a_reg[m] = As[ty * TM + m][k];
            }
            #pragma unroll
            for (int n = 0; n < TN; ++n) {
                b_reg[n] = Bs[k][tx * TN + n];
            }
            #pragma unroll
            for (int m = 0; m < TM; ++m) {
                #pragma unroll
                for (int n = 0; n < TN; ++n) {
                    acc[m][n] += a_reg[m] * b_reg[n];
                }
            }
        }

        __syncthreads();
    }

    #pragma unroll
    for (int m = 0; m < TM; ++m) {
        const int row = block_row + ty * TM + m;
        if (row < M) {
            #pragma unroll
            for (int n = 0; n < TN; ++n) {
                const int col = block_col + tx * TN + n;
                if (col < N) {
                    C[row * N + col] = __float2half(acc[m][n]);
                }
            }
        }
    }
}

namespace {

// Grow-only device buffer cache to avoid per-call hipMalloc/hipFree overhead
struct DeviceWorkspace {
    half* d_A = nullptr;
    half* d_B = nullptr;
    half* d_C = nullptr;
    size_t cap_A = 0;
    size_t cap_B = 0;
    size_t cap_C = 0;

    void ensure(size_t size_A, size_t size_B, size_t size_C) {
        if (size_A > cap_A) {
            if (d_A) HIP_CHECK(hipFree(d_A));
            HIP_CHECK(hipMalloc(&d_A, size_A));
            cap_A = size_A;
        }
        if (size_B > cap_B) {
            if (d_B) HIP_CHECK(hipFree(d_B));
            HIP_CHECK(hipMalloc(&d_B, size_B));
            cap_B = size_B;
        }
        if (size_C > cap_C) {
            if (d_C) HIP_CHECK(hipFree(d_C));
            HIP_CHECK(hipMalloc(&d_C, size_C));
            cap_C = size_C;
        }
    }

    ~DeviceWorkspace() {
        if (d_A) (void)hipFree(d_A);
        if (d_B) (void)hipFree(d_B);
        if (d_C) (void)hipFree(d_C);
    }
};

} // namespace

void launch_matmul_fp16(
    const void* h_A,
    const void* h_B,
    void* h_C,
    int M,
    int N,
    int K
) {
    static DeviceWorkspace ws;

    const size_t size_A = static_cast<size_t>(M) * K * sizeof(half);
    const size_t size_B = static_cast<size_t>(K) * N * sizeof(half);
    const size_t size_C = static_cast<size_t>(M) * N * sizeof(half);

    ws.ensure(size_A, size_B, size_C);

    HIP_CHECK(hipMemcpy(ws.d_A, h_A, size_A, hipMemcpyHostToDevice));
    HIP_CHECK(hipMemcpy(ws.d_B, h_B, size_B, hipMemcpyHostToDevice));

    dim3 blockDim(BLOCK_SIZE, BLOCK_SIZE);

    if (M >= 64 && N >= 64) {
        dim3 gridDim((N + BN - 1) / BN, (M + BM - 1) / BM);
        hipLaunchKernelGGL(
            matmul_kernel_reg_tiled,
            gridDim,
            blockDim,
            0,
            0,
            ws.d_A,
            ws.d_B,
            ws.d_C,
            M,
            N,
            K
        );
    } else {
        dim3 gridDim((N + BLOCK_SIZE - 1) / BLOCK_SIZE, (M + BLOCK_SIZE - 1) / BLOCK_SIZE);
        hipLaunchKernelGGL(
            matmul_kernel_tiled,
            gridDim,
            blockDim,
            0,
            0,
            ws.d_A,
            ws.d_B,
            ws.d_C,
            M,
            N,
            K
        );
    }
    HIP_CHECK(hipGetLastError());

    // hipMemcpy DeviceToHost implicitly synchronizes the default stream
    HIP_CHECK(hipMemcpy(h_C, ws.d_C, size_C, hipMemcpyDeviceToHost));
}
