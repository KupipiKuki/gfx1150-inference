#include "rmsnorm.h"
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

constexpr int WAVE_SIZE = 32;
constexpr int BLOCK_THREADS = 256; // 8 Wave32 wavefronts (gfx1150 max workgroup size)
constexpr int NUM_WAVES = BLOCK_THREADS / WAVE_SIZE;

// One workgroup (256 threads) per row m in [0, M).
// Accumulates sum of squares in FP32 using Wave32 shuffle + LDS cross-wave reduction.
__global__ __launch_bounds__(BLOCK_THREADS) void rmsnorm_kernel(
    const half* __restrict__ x,
    const half* __restrict__ weight,
    half* __restrict__ out,
    const int M,
    const int K,
    const float eps
) {
    const int m = blockIdx.x;
    if (m >= M) return;

    const int tid = threadIdx.x;
    const int wave_id = tid / WAVE_SIZE;
    const int lane_id = tid % WAVE_SIZE;

    const half* x_row = x + static_cast<size_t>(m) * K;
    half* out_row = out + static_cast<size_t>(m) * K;

    float sum_sq = 0.0f;
    for (int k = tid; k < K; k += BLOCK_THREADS) {
        const float val = __half2float(x_row[k]);
        sum_sq += val * val;
    }

    // Intra-wavefront butterfly reduction across 32 lanes
    #pragma unroll
    for (int offset = WAVE_SIZE / 2; offset > 0; offset /= 2) {
        sum_sq += __shfl_down(sum_sq, offset, WAVE_SIZE);
    }

    __shared__ float wave_sums[NUM_WAVES];
    if (lane_id == 0) {
        wave_sums[wave_id] = sum_sq;
    }
    __syncthreads();

    // First wave reduces the 8 wavefront partial sums
    if (wave_id == 0) {
        float total_sq = (lane_id < NUM_WAVES) ? wave_sums[lane_id] : 0.0f;
        #pragma unroll
        for (int offset = NUM_WAVES / 2; offset > 0; offset /= 2) {
            total_sq += __shfl_down(total_sq, offset, WAVE_SIZE);
        }
        if (lane_id == 0) {
            wave_sums[0] = rsqrtf(total_sq / static_cast<float>(K) + eps);
        }
    }
    __syncthreads();

    const float rms_scale = wave_sums[0];

    for (int k = tid; k < K; k += BLOCK_THREADS) {
        const float v = __half2float(x_row[k]) * rms_scale * __half2float(weight[k]);
        out_row[k] = __float2half(v);
    }
}

namespace {

struct RMSNormWorkspace {
    half* d_x = nullptr;
    half* d_w = nullptr;
    half* d_out = nullptr;
    size_t cap_x = 0;
    size_t cap_w = 0;
    size_t cap_out = 0;

    void ensure(size_t sx, size_t sw, size_t sout) {
        if (sx > cap_x) {
            if (d_x) HIP_CHECK(hipFree(d_x));
            HIP_CHECK(hipMalloc(&d_x, sx));
            cap_x = sx;
        }
        if (sw > cap_w) {
            if (d_w) HIP_CHECK(hipFree(d_w));
            HIP_CHECK(hipMalloc(&d_w, sw));
            cap_w = sw;
        }
        if (sout > cap_out) {
            if (d_out) HIP_CHECK(hipFree(d_out));
            HIP_CHECK(hipMalloc(&d_out, sout));
            cap_out = sout;
        }
    }

    ~RMSNormWorkspace() {
        if (d_x) (void)hipFree(d_x);
        if (d_w) (void)hipFree(d_w);
        if (d_out) (void)hipFree(d_out);
    }
};

} // namespace

void launch_rmsnorm_fp16(
    const void* h_x,
    const void* h_weight,
    void* h_out,
    int M,
    int K,
    float eps
) {
    static RMSNormWorkspace ws;

    const size_t size_x = static_cast<size_t>(M) * K * sizeof(half);
    const size_t size_w = static_cast<size_t>(K) * sizeof(half);
    ws.ensure(size_x, size_w, size_x);

    HIP_CHECK(hipMemcpy(ws.d_x, h_x, size_x, hipMemcpyHostToDevice));
    HIP_CHECK(hipMemcpy(ws.d_w, h_weight, size_w, hipMemcpyHostToDevice));

    hipLaunchKernelGGL(
        rmsnorm_kernel,
        dim3(M),
        dim3(BLOCK_THREADS),
        0,
        0,
        ws.d_x,
        ws.d_w,
        ws.d_out,
        M,
        K,
        eps
    );
    HIP_CHECK(hipGetLastError());

    HIP_CHECK(hipMemcpy(h_out, ws.d_out, size_x, hipMemcpyDeviceToHost));
}

