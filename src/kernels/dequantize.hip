#include "dequantize.h"
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

// Packed 18-byte GGML Q4_0 block structure
#pragma pack(push, 1)
struct block_q4_0 {
    half d;                 // 2-byte FP16 delta (scale)
    uint8_t qs[QK4_0 / 2];  // 16 bytes of packed 4-bit unsigned nibbles (offset by -8)
};
#pragma pack(pop)

static_assert(sizeof(block_q4_0) == BLOCK_Q4_0_BYTES, "block_q4_0 must be 18 bytes");

// 1 thread per Q4_0 block (32 weights)
__global__ void dequantize_q4_0_kernel(
    const block_q4_0* __restrict__ x,
    half* __restrict__ y,
    const int num_blocks
) {
    const int ib = blockIdx.x * blockDim.x + threadIdx.x;
    if (ib >= num_blocks) return;

    const float d = __half2float(x[ib].d);
    const uint8_t* qs = x[ib].qs;
    half* out = y + ib * QK4_0;

    #pragma unroll
    for (int j = 0; j < QK4_0 / 2; ++j) {
        const uint8_t packed = qs[j];
        const int x0 = static_cast<int>(packed & 0x0F) - 8;
        const int x1 = static_cast<int>(packed >> 4) - 8;
        out[j]              = __float2half(d * static_cast<float>(x0));
        out[j + QK4_0 / 2]  = __float2half(d * static_cast<float>(x1));
    }
}

// Wave32-optimized fused Q4_0 GEMV/Matmul kernel for M=1..4 (decode & small batch)
// Each wavefront (32 threads on gfx1150) cooperatively computes 1 output element C[m, n]
// by streaming blocks along K in parallel and reducing across the 32 lanes.
constexpr int WAVE_SIZE = 32;
constexpr int WAVES_PER_BLOCK = 8; // 256 threads per workgroup

__global__ __launch_bounds__(256) void matmul_q4_0_wave_kernel(
    const half* __restrict__ A,
    const block_q4_0* __restrict__ B,
    half* __restrict__ C,
    const int M,
    const int N,
    const int K,
    const int blocks_per_row
) {
    const int tid = threadIdx.x; // 0..255
    const int wave_id = tid / WAVE_SIZE; // 0..7
    const int lane_id = tid % WAVE_SIZE; // 0..31

    const int n = blockIdx.x * WAVES_PER_BLOCK + wave_id;
    const int m = blockIdx.y;

    if (m >= M || n >= N) return;

    const half* a_row = A + static_cast<size_t>(m) * K;
    const block_q4_0* b_row = B + static_cast<size_t>(n) * blocks_per_row;

    float sum = 0.0f;

    // Each lane processes one Q4_0 block (32 elements) per step
    for (int ib = lane_id; ib < blocks_per_row; ib += WAVE_SIZE) {
        const float d = __half2float(b_row[ib].d);
        const uint8_t* qs = b_row[ib].qs;
        const half* a_blk = a_row + ib * QK4_0;

        float block_sum = 0.0f;
        #pragma unroll
        for (int j = 0; j < QK4_0 / 2; ++j) {
            const uint8_t packed = qs[j];
            const float w0 = static_cast<float>(static_cast<int>(packed & 0x0F) - 8);
            const float w1 = static_cast<float>(static_cast<int>(packed >> 4) - 8);
            const float a0 = __half2float(a_blk[j]);
            const float a1 = __half2float(a_blk[j + QK4_0 / 2]);
            block_sum += a0 * w0 + a1 * w1;
        }
        sum += d * block_sum;
    }

    // Intra-wavefront butterfly reduction across 32 lanes
    #pragma unroll
    for (int offset = WAVE_SIZE / 2; offset > 0; offset /= 2) {
        sum += __shfl_down(sum, offset, WAVE_SIZE);
    }

    if (lane_id == 0) {
        C[static_cast<size_t>(m) * N + n] = __float2half(sum);
    }
}

namespace {

struct Q4Workspace {
    void* d_buf0 = nullptr;
    void* d_buf1 = nullptr;
    void* d_buf2 = nullptr;
    size_t cap0 = 0;
    size_t cap1 = 0;
    size_t cap2 = 0;

    void ensure(size_t s0, size_t s1, size_t s2) {
        if (s0 > cap0) {
            if (d_buf0) HIP_CHECK(hipFree(d_buf0));
            HIP_CHECK(hipMalloc(&d_buf0, s0));
            cap0 = s0;
        }
        if (s1 > cap1) {
            if (d_buf1) HIP_CHECK(hipFree(d_buf1));
            HIP_CHECK(hipMalloc(&d_buf1, s1));
            cap1 = s1;
        }
        if (s2 > cap2) {
            if (d_buf2) HIP_CHECK(hipFree(d_buf2));
            HIP_CHECK(hipMalloc(&d_buf2, s2));
            cap2 = s2;
        }
    }

    ~Q4Workspace() {
        if (d_buf0) (void)hipFree(d_buf0);
        if (d_buf1) (void)hipFree(d_buf1);
        if (d_buf2) (void)hipFree(d_buf2);
    }
};

Q4Workspace& get_q4_workspace() {
    static Q4Workspace ws;
    return ws;
}

} // namespace

void launch_dequantize_q4_0(
    const void* h_q4,
    void* h_fp16_out,
    int num_elements
) {
    if (num_elements % QK4_0 != 0) {
        throw std::invalid_argument("num_elements must be a multiple of 32 for Q4_0 dequantization.");
    }
    const int num_blocks = num_elements / QK4_0;
    const size_t size_in = static_cast<size_t>(num_blocks) * sizeof(block_q4_0);
    const size_t size_out = static_cast<size_t>(num_elements) * sizeof(half);

    auto& ws = get_q4_workspace();
    ws.ensure(size_in, size_out, 0);

    HIP_CHECK(hipMemcpy(ws.d_buf0, h_q4, size_in, hipMemcpyHostToDevice));

    const int threads = 256;
    const int grids = (num_blocks + threads - 1) / threads;

    hipLaunchKernelGGL(
        dequantize_q4_0_kernel,
        dim3(grids),
        dim3(threads),
        0,
        0,
        static_cast<const block_q4_0*>(ws.d_buf0),
        static_cast<half*>(ws.d_buf1),
        num_blocks
    );
    HIP_CHECK(hipGetLastError());

    HIP_CHECK(hipMemcpy(h_fp16_out, ws.d_buf1, size_out, hipMemcpyDeviceToHost));
}

void launch_matmul_q4_0(
    const void* h_A_fp16,
    const void* h_B_q4,
    void* h_C_fp16,
    int M,
    int N,
    int K
) {
    if (K % QK4_0 != 0) {
        throw std::invalid_argument("K dimension must be a multiple of 32 for Q4_0 matmul.");
    }
    const int blocks_per_row = K / QK4_0;
    const size_t size_A = static_cast<size_t>(M) * K * sizeof(half);
    const size_t size_B = static_cast<size_t>(N) * blocks_per_row * sizeof(block_q4_0);
    const size_t size_C = static_cast<size_t>(M) * N * sizeof(half);

    auto& ws = get_q4_workspace();
    ws.ensure(size_A, size_B, size_C);

    HIP_CHECK(hipMemcpy(ws.d_buf0, h_A_fp16, size_A, hipMemcpyHostToDevice));
    HIP_CHECK(hipMemcpy(ws.d_buf1, h_B_q4, size_B, hipMemcpyHostToDevice));

    dim3 blockDim(WAVE_SIZE * WAVES_PER_BLOCK); // 256 threads
    dim3 gridDim(
        (N + WAVES_PER_BLOCK - 1) / WAVES_PER_BLOCK,
        M
    );

    hipLaunchKernelGGL(
        matmul_q4_0_wave_kernel,
        gridDim,
        blockDim,
        0,
        0,
        static_cast<const half*>(ws.d_buf0),
        static_cast<const block_q4_0*>(ws.d_buf1),
        static_cast<half*>(ws.d_buf2),
        M,
        N,
        K,
        blocks_per_row
    );
    HIP_CHECK(hipGetLastError());

    HIP_CHECK(hipMemcpy(h_C_fp16, ws.d_buf2, size_C, hipMemcpyDeviceToHost));
}

