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

// Fused Residual Add + RMSNorm kernel:
// Computes h_out = half(float(x) + float(residual)) and norm_out = rmsnorm(h_out, weight)
// in a single workgroup launch per row.
__global__ __launch_bounds__(BLOCK_THREADS) void rmsnorm_residual_kernel(
    const half* __restrict__ x,
    const half* __restrict__ residual,
    const half* __restrict__ weight,
    half* __restrict__ h_out,
    half* __restrict__ norm_out,
    const int M,
    const int K,
    const float eps
) {
    const int m = blockIdx.x;
    if (m >= M) return;

    const int tid = threadIdx.x;
    const int wave_id = tid / WAVE_SIZE;
    const int lane_id = tid % WAVE_SIZE;

    const size_t row_offset = static_cast<size_t>(m) * K;
    const half* x_row = x + row_offset;
    const half* res_row = residual + row_offset;
    half* h_row = h_out + row_offset;
    half* norm_row = norm_out + row_offset;

    float sum_sq = 0.0f;
    for (int k = tid; k < K; k += BLOCK_THREADS) {
        const half h_val = __float2half(__half2float(x_row[k]) + __half2float(res_row[k]));
        h_row[k] = h_val;
        const float val = __half2float(h_val);
        sum_sq += val * val;
    }

    #pragma unroll
    for (int offset = WAVE_SIZE / 2; offset > 0; offset /= 2) {
        sum_sq += __shfl_down(sum_sq, offset, WAVE_SIZE);
    }

    __shared__ float wave_sums[NUM_WAVES];
    if (lane_id == 0) {
        wave_sums[wave_id] = sum_sq;
    }
    __syncthreads();

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
        const float v = __half2float(h_row[k]) * rms_scale * __half2float(weight[k]);
        norm_row[k] = __float2half(v);
    }
}

__global__ __launch_bounds__(BLOCK_THREADS) void residual_add_kernel(
    const half* __restrict__ x,
    const half* __restrict__ residual,
    half* __restrict__ out,
    const int num_elements
) {
    const int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= num_elements) return;
    out[idx] = __float2half(__half2float(x[idx]) + __half2float(residual[idx]));
}

namespace {

struct RMSNormWorkspace {
    half* d_x = nullptr;
    half* d_res = nullptr;
    half* d_w = nullptr;
    half* d_h_out = nullptr;
    half* d_out = nullptr;
    size_t cap_x = 0;
    size_t cap_res = 0;
    size_t cap_w = 0;
    size_t cap_h_out = 0;
    size_t cap_out = 0;

    void ensure(size_t sx, size_t sw, size_t sout, size_t sres = 0, size_t sh = 0) {
        if (sx > cap_x) {
            if (d_x) HIP_CHECK(hipFree(d_x));
            HIP_CHECK(hipMalloc(&d_x, sx));
            cap_x = sx;
        }
        if (sres > cap_res) {
            if (d_res) HIP_CHECK(hipFree(d_res));
            HIP_CHECK(hipMalloc(&d_res, sres));
            cap_res = sres;
        }
        if (sw > cap_w) {
            if (d_w) HIP_CHECK(hipFree(d_w));
            HIP_CHECK(hipMalloc(&d_w, sw));
            cap_w = sw;
        }
        if (sh > cap_h_out) {
            if (d_h_out) HIP_CHECK(hipFree(d_h_out));
            HIP_CHECK(hipMalloc(&d_h_out, sh));
            cap_h_out = sh;
        }
        if (sout > cap_out) {
            if (d_out) HIP_CHECK(hipFree(d_out));
            HIP_CHECK(hipMalloc(&d_out, sout));
            cap_out = sout;
        }
    }

    ~RMSNormWorkspace() {
        if (d_x) (void)hipFree(d_x);
        if (d_res) (void)hipFree(d_res);
        if (d_w) (void)hipFree(d_w);
        if (d_h_out) (void)hipFree(d_h_out);
        if (d_out) (void)hipFree(d_out);
    }
};

RMSNormWorkspace& get_rmsnorm_ws() {
    static RMSNormWorkspace ws;
    return ws;
}

} // namespace

void launch_rmsnorm_fp16_device(
    const void* d_x,
    const void* d_weight,
    void* d_out,
    int M,
    int K,
    float eps
) {
    hipLaunchKernelGGL(
        rmsnorm_kernel,
        dim3(M),
        dim3(BLOCK_THREADS),
        0,
        0,
        static_cast<const half*>(d_x),
        static_cast<const half*>(d_weight),
        static_cast<half*>(d_out),
        M,
        K,
        eps
    );
    HIP_CHECK(hipGetLastError());
}

void launch_rmsnorm_fp16(
    const void* h_x,
    const void* h_weight,
    void* h_out,
    int M,
    int K,
    float eps
) {
    auto& ws = get_rmsnorm_ws();

    const size_t size_x = static_cast<size_t>(M) * K * sizeof(half);
    const size_t size_w = static_cast<size_t>(K) * sizeof(half);
    ws.ensure(size_x, size_w, size_x);

    HIP_CHECK(hipMemcpy(ws.d_x, h_x, size_x, hipMemcpyHostToDevice));
    HIP_CHECK(hipMemcpy(ws.d_w, h_weight, size_w, hipMemcpyHostToDevice));

    launch_rmsnorm_fp16_device(ws.d_x, ws.d_w, ws.d_out, M, K, eps);

    HIP_CHECK(hipMemcpy(h_out, ws.d_out, size_x, hipMemcpyDeviceToHost));
}

void launch_rmsnorm_residual_fp16_device(
    const void* d_x,
    const void* d_residual,
    const void* d_weight,
    void* d_h_out,
    void* d_norm_out,
    int M,
    int K,
    float eps
) {
    hipLaunchKernelGGL(
        rmsnorm_residual_kernel,
        dim3(M),
        dim3(BLOCK_THREADS),
        0,
        0,
        static_cast<const half*>(d_x),
        static_cast<const half*>(d_residual),
        static_cast<const half*>(d_weight),
        static_cast<half*>(d_h_out),
        static_cast<half*>(d_norm_out),
        M,
        K,
        eps
    );
    HIP_CHECK(hipGetLastError());
}

void launch_rmsnorm_residual_fp16(
    const void* h_x,
    const void* h_residual,
    const void* h_weight,
    void* h_h_out,
    void* h_norm_out,
    int M,
    int K,
    float eps
) {
    auto& ws = get_rmsnorm_ws();

    const size_t size_x = static_cast<size_t>(M) * K * sizeof(half);
    const size_t size_w = static_cast<size_t>(K) * sizeof(half);
    ws.ensure(size_x, size_w, size_x, size_x, size_x);

    HIP_CHECK(hipMemcpy(ws.d_x, h_x, size_x, hipMemcpyHostToDevice));
    HIP_CHECK(hipMemcpy(ws.d_res, h_residual, size_x, hipMemcpyHostToDevice));
    HIP_CHECK(hipMemcpy(ws.d_w, h_weight, size_w, hipMemcpyHostToDevice));

    launch_rmsnorm_residual_fp16_device(ws.d_x, ws.d_res, ws.d_w, ws.d_h_out, ws.d_out, M, K, eps);

    HIP_CHECK(hipMemcpy(h_h_out, ws.d_h_out, size_x, hipMemcpyDeviceToHost));
    HIP_CHECK(hipMemcpy(h_norm_out, ws.d_out, size_x, hipMemcpyDeviceToHost));
}

void launch_residual_add_fp16_device(
    const void* d_x,
    const void* d_residual,
    void* d_out,
    int num_elements
) {
    const int grids = (num_elements + BLOCK_THREADS - 1) / BLOCK_THREADS;
    hipLaunchKernelGGL(
        residual_add_kernel,
        dim3(grids),
        dim3(BLOCK_THREADS),
        0,
        0,
        static_cast<const half*>(d_x),
        static_cast<const half*>(d_residual),
        static_cast<half*>(d_out),
        num_elements
    );
    HIP_CHECK(hipGetLastError());
}

void launch_residual_add_fp16(
    const void* h_x,
    const void* h_residual,
    void* h_out,
    int num_elements
) {
    auto& ws = get_rmsnorm_ws();

    const size_t size_x = static_cast<size_t>(num_elements) * sizeof(half);
    ws.ensure(size_x, 0, size_x, size_x, 0);

    HIP_CHECK(hipMemcpy(ws.d_x, h_x, size_x, hipMemcpyHostToDevice));
    HIP_CHECK(hipMemcpy(ws.d_res, h_residual, size_x, hipMemcpyHostToDevice));

    launch_residual_add_fp16_device(ws.d_x, ws.d_res, ws.d_out, num_elements);

    HIP_CHECK(hipMemcpy(h_out, ws.d_out, size_x, hipMemcpyDeviceToHost));
}

