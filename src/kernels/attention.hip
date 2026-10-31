#include "attention.h"
#include <hip/hip_runtime.h>
#include <hip/hip_fp16.h>
#include <cmath>
#include <cfloat>
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
constexpr int MAX_HEAD_DIM = 256;
constexpr int ELEMS_PER_LANE = MAX_HEAD_DIM / WAVE_SIZE; // up to 8 elements per lane

// Wave32-cooperative Online Softmax GQA Kernel for gfx1150.
// Each Wave32 (32 threads) processes one (query_pos m, query_head h) pair.
// Supports head_dim up to 256 (e.g. 64, 128, 256) with zero shared-memory overhead
// by keeping the query vector and running output accumulator in per-lane registers.
__global__ __launch_bounds__(256) void gqa_online_softmax_kernel(
    const half* __restrict__ Q,
    const half* __restrict__ K,
    const half* __restrict__ V,
    half* __restrict__ Out,
    const int q_len,
    const int kv_len,
    const int num_heads,
    const int num_kv_heads,
    const int head_dim,
    const int start_pos,
    const float scale,
    const bool causal
) {
    const int tid = threadIdx.x;
    const int wave_id = tid / WAVE_SIZE; // 0..7
    const int lane_id = tid % WAVE_SIZE; // 0..31

    const int qh_idx = blockIdx.x * 8 + wave_id;
    const int total_qh = q_len * num_heads;
    if (qh_idx >= total_qh) return;

    const int m = qh_idx / num_heads;
    const int h = qh_idx % num_heads;
    const int group_size = num_heads / num_kv_heads;
    const int kv_h = h / group_size;

    const half* q_ptr = Q + (static_cast<size_t>(m) * num_heads + h) * head_dim;
    half* out_ptr = Out + (static_cast<size_t>(m) * num_heads + h) * head_dim;

    float q_reg[ELEMS_PER_LANE];
    float out_acc[ELEMS_PER_LANE];

    #pragma unroll
    for (int i = 0; i < ELEMS_PER_LANE; ++i) {
        const int d = lane_id + i * WAVE_SIZE;
        q_reg[i] = (d < head_dim) ? __half2float(q_ptr[d]) : 0.0f;
        out_acc[i] = 0.0f;
    }

    const int max_kv = causal ? min(kv_len, start_pos + m + 1) : kv_len;

    float m_prev = -FLT_MAX;
    float l_prev = 0.0f;

    for (int s = 0; s < max_kv; ++s) {
        const half* k_ptr = K + (static_cast<size_t>(s) * num_kv_heads + kv_h) * head_dim;
        const half* v_ptr = V + (static_cast<size_t>(s) * num_kv_heads + kv_h) * head_dim;

        float dot = 0.0f;
        #pragma unroll
        for (int i = 0; i < ELEMS_PER_LANE; ++i) {
            const int d = lane_id + i * WAVE_SIZE;
            if (d < head_dim) {
                dot += q_reg[i] * __half2float(k_ptr[d]);
            }
        }

        // Wave32 all-reduce for Q·K dot product
        #pragma unroll
        for (int offset = WAVE_SIZE / 2; offset > 0; offset /= 2) {
            dot += __shfl_xor(dot, offset, WAVE_SIZE);
        }

        const float score = dot * scale;
        const float m_new = fmaxf(m_prev, score);
        const float exp_prev = expf(m_prev - m_new);
        const float exp_curr = expf(score - m_new);
        l_prev = l_prev * exp_prev + exp_curr;

        #pragma unroll
        for (int i = 0; i < ELEMS_PER_LANE; ++i) {
            const int d = lane_id + i * WAVE_SIZE;
            if (d < head_dim) {
                out_acc[i] = out_acc[i] * exp_prev + exp_curr * __half2float(v_ptr[d]);
            }
        }
        m_prev = m_new;
    }

    const float inv_l = (l_prev > 0.0f) ? (1.0f / l_prev) : 0.0f;
    #pragma unroll
    for (int i = 0; i < ELEMS_PER_LANE; ++i) {
        const int d = lane_id + i * WAVE_SIZE;
        if (d < head_dim) {
            out_ptr[d] = __float2half(out_acc[i] * inv_l);
        }
    }
}

namespace {

struct AttentionWorkspace {
    half* d_Q = nullptr;
    half* d_K = nullptr;
    half* d_V = nullptr;
    half* d_Out = nullptr;
    size_t cap_Q = 0;
    size_t cap_K = 0;
    size_t cap_V = 0;
    size_t cap_Out = 0;

    void ensure(size_t sq, size_t sk, size_t sv, size_t sout) {
        if (sq > cap_Q) {
            if (d_Q) HIP_CHECK(hipFree(d_Q));
            HIP_CHECK(hipMalloc(&d_Q, sq));
            cap_Q = sq;
        }
        if (sk > cap_K) {
            if (d_K) HIP_CHECK(hipFree(d_K));
            HIP_CHECK(hipMalloc(&d_K, sk));
            cap_K = sk;
        }
        if (sv > cap_V) {
            if (d_V) HIP_CHECK(hipFree(d_V));
            HIP_CHECK(hipMalloc(&d_V, sv));
            cap_V = sv;
        }
        if (sout > cap_Out) {
            if (d_Out) HIP_CHECK(hipFree(d_Out));
            HIP_CHECK(hipMalloc(&d_Out, sout));
            cap_Out = sout;
        }
    }

    ~AttentionWorkspace() {
        if (d_Q) (void)hipFree(d_Q);
        if (d_K) (void)hipFree(d_K);
        if (d_V) (void)hipFree(d_V);
        if (d_Out) (void)hipFree(d_Out);
    }
};

struct DeviceKVCachePool {
    half* d_K_pool = nullptr;
    half* d_V_pool = nullptr;
    int num_layers = 0;
    int max_seq_len = 0;
    int num_kv_heads = 0;
    int head_dim = 0;
    size_t cap_bytes = 0;

    void init(int layers, int max_seq, int kv_heads, int dim) {
        const size_t needed =
            static_cast<size_t>(layers) * max_seq * kv_heads * dim * sizeof(half);
        if (needed > cap_bytes) {
            if (d_K_pool) HIP_CHECK(hipFree(d_K_pool));
            if (d_V_pool) HIP_CHECK(hipFree(d_V_pool));
            HIP_CHECK(hipMalloc(&d_K_pool, needed));
            HIP_CHECK(hipMalloc(&d_V_pool, needed));
            cap_bytes = needed;
        }
        num_layers = layers;
        max_seq_len = max_seq;
        num_kv_heads = kv_heads;
        head_dim = dim;
    }

    void release() {
        if (d_K_pool) {
            (void)hipFree(d_K_pool);
            d_K_pool = nullptr;
        }
        if (d_V_pool) {
            (void)hipFree(d_V_pool);
            d_V_pool = nullptr;
        }
        cap_bytes = 0;
        num_layers = 0;
        max_seq_len = 0;
    }

    ~DeviceKVCachePool() {
        release();
    }
};

AttentionWorkspace& get_attn_ws() {
    static AttentionWorkspace ws;
    return ws;
}

DeviceKVCachePool& get_kv_pool() {
    static DeviceKVCachePool pool;
    return pool;
}

} // namespace

void launch_gqa_attention_fp16(
    const void* h_Q,
    const void* h_K,
    const void* h_V,
    void* h_Out,
    int q_len,
    int kv_len,
    int num_heads,
    int num_kv_heads,
    int head_dim,
    int start_pos,
    float scale,
    bool causal
) {
    if (head_dim <= 0 || head_dim > MAX_HEAD_DIM) {
        throw std::invalid_argument("head_dim must be in (0, 256] for gqa_attention.");
    }
    if (num_kv_heads <= 0 || num_heads % num_kv_heads != 0) {
        throw std::invalid_argument("num_heads must be divisible by num_kv_heads.");
    }

    auto& ws = get_attn_ws();
    const size_t size_Q = static_cast<size_t>(q_len) * num_heads * head_dim * sizeof(half);
    const size_t size_KV = static_cast<size_t>(kv_len) * num_kv_heads * head_dim * sizeof(half);

    ws.ensure(size_Q, size_KV, size_KV, size_Q);

    HIP_CHECK(hipMemcpy(ws.d_Q, h_Q, size_Q, hipMemcpyHostToDevice));
    HIP_CHECK(hipMemcpy(ws.d_K, h_K, size_KV, hipMemcpyHostToDevice));
    HIP_CHECK(hipMemcpy(ws.d_V, h_V, size_KV, hipMemcpyHostToDevice));

    const int total_qh = q_len * num_heads;
    const int waves_per_block = 8; // 256 threads
    const int blocks = (total_qh + waves_per_block - 1) / waves_per_block;

    hipLaunchKernelGGL(
        gqa_online_softmax_kernel,
        dim3(blocks),
        dim3(waves_per_block * WAVE_SIZE),
        0,
        0,
        ws.d_Q,
        ws.d_K,
        ws.d_V,
        ws.d_Out,
        q_len,
        kv_len,
        num_heads,
        num_kv_heads,
        head_dim,
        start_pos,
        scale,
        causal
    );
    HIP_CHECK(hipGetLastError());

    HIP_CHECK(hipMemcpy(h_Out, ws.d_Out, size_Q, hipMemcpyDeviceToHost));
}

void init_device_kv_cache_fp16(
    int num_layers,
    int max_seq_len,
    int num_kv_heads,
    int head_dim
) {
    if (num_layers <= 0 || max_seq_len <= 0 || num_kv_heads <= 0 || head_dim <= 0) {
        throw std::invalid_argument("KV cache dimensions must all be positive.");
    }
    get_kv_pool().init(num_layers, max_seq_len, num_kv_heads, head_dim);
}

void free_device_kv_cache_fp16() {
    get_kv_pool().release();
}

void launch_gqa_attention_cached_fp16(
    const void* h_Q,
    const void* h_K_new,
    const void* h_V_new,
    void* h_Out,
    int layer_idx,
    int q_len,
    int start_pos,
    int num_heads,
    int num_kv_heads,
    int head_dim,
    float scale,
    bool causal
) {
    auto& pool = get_kv_pool();
    if (!pool.d_K_pool || !pool.d_V_pool) {
        throw std::runtime_error("Device KV cache not initialized. Call kv_cache_init first.");
    }
    if (layer_idx < 0 || layer_idx >= pool.num_layers) {
        throw std::out_of_range("layer_idx out of range for DeviceKVCachePool.");
    }
    const int kv_len = start_pos + q_len;
    if (start_pos < 0 || kv_len > pool.max_seq_len) {
        throw std::out_of_range("start_pos + q_len exceeds max_seq_len in DeviceKVCachePool.");
    }
    if (num_kv_heads != pool.num_kv_heads || head_dim != pool.head_dim) {
        throw std::invalid_argument("num_kv_heads or head_dim mismatch with DeviceKVCachePool.");
    }

    const size_t row_elems = static_cast<size_t>(num_kv_heads) * head_dim;
    const size_t layer_stride = static_cast<size_t>(pool.max_seq_len) * row_elems;
    half* d_layer_K = pool.d_K_pool + static_cast<size_t>(layer_idx) * layer_stride;
    half* d_layer_V = pool.d_V_pool + static_cast<size_t>(layer_idx) * layer_stride;

    const size_t new_kv_bytes = static_cast<size_t>(q_len) * row_elems * sizeof(half);
    const size_t write_offset = static_cast<size_t>(start_pos) * row_elems;

    // Copy only the newly generated K and V slices directly to their offset in GPU memory
    HIP_CHECK(hipMemcpy(d_layer_K + write_offset, h_K_new, new_kv_bytes, hipMemcpyHostToDevice));
    HIP_CHECK(hipMemcpy(d_layer_V + write_offset, h_V_new, new_kv_bytes, hipMemcpyHostToDevice));

    auto& ws = get_attn_ws();
    const size_t size_Q = static_cast<size_t>(q_len) * num_heads * head_dim * sizeof(half);
    ws.ensure(size_Q, 0, 0, size_Q);

    HIP_CHECK(hipMemcpy(ws.d_Q, h_Q, size_Q, hipMemcpyHostToDevice));

    const int total_qh = q_len * num_heads;
    const int waves_per_block = 8;
    const int blocks = (total_qh + waves_per_block - 1) / waves_per_block;

    hipLaunchKernelGGL(
        gqa_online_softmax_kernel,
        dim3(blocks),
        dim3(waves_per_block * WAVE_SIZE),
        0,
        0,
        ws.d_Q,
        d_layer_K,
        d_layer_V,
        ws.d_Out,
        q_len,
        kv_len,
        num_heads,
        num_kv_heads,
        head_dim,
        start_pos,
        scale,
        causal
    );
    HIP_CHECK(hipGetLastError());

    HIP_CHECK(hipMemcpy(h_Out, ws.d_Out, size_Q, hipMemcpyDeviceToHost));
}
