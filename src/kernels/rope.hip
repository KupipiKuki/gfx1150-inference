#include "rope.h"
#include <hip/hip_runtime.h>
#include <hip/hip_fp16.h>
#include <cmath>
#include <stdexcept>
#include <string>
#include <vector>

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
// using the host-precomputed inv_freq table (eliminating device powf calls).
__global__ void rope_kernel(
    const half* __restrict__ x_in,
    const float* __restrict__ inv_freq_table,
    half* __restrict__ x_out,
    const int seq_len,
    const int num_heads,
    const int head_dim,
    const int pos_offset,
    const bool neox_style
) {
    const int half_dim = head_dim / 2;
    const size_t total_pairs = static_cast<size_t>(seq_len) * num_heads * half_dim;
    const size_t idx = static_cast<size_t>(blockIdx.x) * blockDim.x + threadIdx.x;
    if (idx >= total_pairs) return;

    const int pair_idx = static_cast<int>(idx % half_dim);
    const size_t temp = idx / half_dim;
    const int head_idx = static_cast<int>(temp % num_heads);
    const int seq_idx = static_cast<int>(temp / num_heads);

    const int pos = pos_offset + seq_idx;
    const float inv_freq = inv_freq_table[pair_idx];
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
    float* d_inv_freq = nullptr;
    size_t cap = 0;
    size_t cap_freq_bytes = 0;
    int cached_head_dim = -1;
    float cached_freq_base = -1.0f;

    void ensure_freq(int head_dim, float freq_base) {
        const int half_dim = head_dim / 2;
        const size_t freq_bytes = static_cast<size_t>(half_dim) * sizeof(float);
        if (freq_bytes > cap_freq_bytes) {
            if (d_inv_freq) HIP_CHECK(hipFree(d_inv_freq));
            HIP_CHECK(hipMalloc(&d_inv_freq, freq_bytes));
            cap_freq_bytes = freq_bytes;
            cached_head_dim = -1;
        }
        if (head_dim != cached_head_dim || freq_base != cached_freq_base) {
            std::vector<float> h_freq(half_dim);
            for (int i = 0; i < half_dim; ++i) {
                const float exponent = static_cast<float>(2 * i) / static_cast<float>(head_dim);
                h_freq[i] = 1.0f / std::pow(freq_base, exponent);
            }
            HIP_CHECK(hipMemcpy(d_inv_freq, h_freq.data(), freq_bytes, hipMemcpyHostToDevice));
            cached_head_dim = head_dim;
            cached_freq_base = freq_base;
        }
    }

    void ensure(size_t bytes, int head_dim, float freq_base) {
        if (bytes > cap) {
            if (d_in) HIP_CHECK(hipFree(d_in));
            if (d_out) HIP_CHECK(hipFree(d_out));
            HIP_CHECK(hipMalloc(&d_in, bytes));
            HIP_CHECK(hipMalloc(&d_out, bytes));
            cap = bytes;
        }
        ensure_freq(head_dim, freq_base);
    }

    ~RoPEWorkspace() {
        if (d_in) (void)hipFree(d_in);
        if (d_out) (void)hipFree(d_out);
        if (d_inv_freq) (void)hipFree(d_inv_freq);
    }
};

RoPEWorkspace& get_rope_ws() {
    static RoPEWorkspace ws;
    return ws;
}

} // namespace

void launch_rope_fp16_device(
    const void* d_in,
    void* d_out,
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
    auto& ws = get_rope_ws();
    ws.ensure_freq(head_dim, freq_base);

    const size_t total_pairs = static_cast<size_t>(seq_len) * num_heads * (head_dim / 2);
    const size_t threads = 256;
    const size_t blocks = (total_pairs + threads - 1) / threads;

    hipLaunchKernelGGL(
        rope_kernel,
        dim3(static_cast<unsigned int>(blocks)),
        dim3(static_cast<unsigned int>(threads)),
        0,
        0,
        static_cast<const half*>(d_in),
        ws.d_inv_freq,
        static_cast<half*>(d_out),
        seq_len,
        num_heads,
        head_dim,
        pos_offset,
        neox_style
    );
    HIP_CHECK(hipGetLastError());
}

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
    auto& ws = get_rope_ws();
    const size_t bytes = static_cast<size_t>(seq_len) * num_heads * head_dim * sizeof(half);
    ws.ensure(bytes, head_dim, freq_base);

    HIP_CHECK(hipMemcpy(ws.d_in, h_in, bytes, hipMemcpyHostToDevice));

    launch_rope_fp16_device(
        ws.d_in, ws.d_out, seq_len, num_heads, head_dim, pos_offset, freq_base, neox_style
    );

    HIP_CHECK(hipMemcpy(h_out, ws.d_out, bytes, hipMemcpyDeviceToHost));
}
