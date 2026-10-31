#include "rope.h"
#include <hip/hip_runtime.h>
#include <hip/hip_fp16.h>
#include <cmath>
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

// Each thread handles one complex rotation pair (i0, i1) for one (seq_idx, head_idx)
__global__ void rope_kernel(
    const half* __restrict__ x_in,
    half* __restrict__ x_out,
    const int seq_len,
    const int num_heads,
    const int head_dim,
    const int pos_offset,
    const float freq_base,
    const bool neox_style
) {
    const int half_dim = head_dim / 2;
    const int total_pairs = seq_len * num_heads * half_dim;
    const int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= total_pairs) return;

    const int pair_idx = idx % half_dim;
    const int temp = idx / half_dim;
    const int head_idx = temp % num_heads;
    const int seq_idx = temp / num_heads;

    const int pos = pos_offset + seq_idx;
    const float exponent = static_cast<float>(2 * pair_idx) / static_cast<float>(head_dim);
    const float inv_freq = 1.0f / powf(freq_base, exponent);
    const float angle = static_cast<float>(pos) * inv_freq;
    const float cos_val = cosf(angle);
    const float sin_val = sinf(angle);

    const size_t base = (static_cast<size_t>(seq_idx) * num_heads + head_idx) * head_dim;
    const int idx0 = neox_style ? pair_idx : (2 * pair_idx);
    const int idx1 = neox_style ? (pair_idx + half_dim) : (2 * pair_idx + 1);

    const float v0 = __half2float(x_in[base + idx0]);
    const float v1 = __half2float(x_in[base + idx1]);

    x_out[base + idx0] = __float2half(v0 * cos_val - v1 * sin_val);
    x_out[base + idx1] = __float2half(v0 * sin_val + v1 * cos_val);
}

namespace {

struct RoPEWorkspace {
    half* d_in = nullptr;
    half* d_out = nullptr;
    size_t cap = 0;

    void ensure(size_t bytes) {
        if (bytes > cap) {
            if (d_in) HIP_CHECK(hipFree(d_in));
            if (d_out) HIP_CHECK(hipFree(d_out));
            HIP_CHECK(hipMalloc(&d_in, bytes));
            HIP_CHECK(hipMalloc(&d_out, bytes));
            cap = bytes;
        }
    }

    ~RoPEWorkspace() {
        if (d_in) (void)hipFree(d_in);
        if (d_out) (void)hipFree(d_out);
    }
};

} // namespace

void launch_rope_fp16(
    const void* h_in,
    void* h_out,
    int seq_len,
    int num_heads,
    int head_dim,
    int pos_offset,
    float freq_base,
    bool neox_style
) {
    if (head_dim <= 0 || head_dim % 2 != 0) {
        throw std::invalid_argument("head_dim must be a positive even integer for RoPE.");
    }
    static RoPEWorkspace ws;
    const size_t bytes = static_cast<size_t>(seq_len) * num_heads * head_dim * sizeof(half);
    ws.ensure(bytes);

    HIP_CHECK(hipMemcpy(ws.d_in, h_in, bytes, hipMemcpyHostToDevice));

    const int total_pairs = seq_len * num_heads * (head_dim / 2);
    const int threads = 256;
    const int blocks = (total_pairs + threads - 1) / threads;

    hipLaunchKernelGGL(
        rope_kernel,
        dim3(blocks),
        dim3(threads),
        0,
        0,
        ws.d_in,
        ws.d_out,
        seq_len,
        num_heads,
        head_dim,
        pos_offset,
        freq_base,
        neox_style
    );
    HIP_CHECK(hipGetLastError());

    HIP_CHECK(hipMemcpy(h_out, ws.d_out, bytes, hipMemcpyDeviceToHost));
}

