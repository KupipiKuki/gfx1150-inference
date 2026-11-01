#include "attention.h"
#include "matmul.h"
#include "dequantize.h"
#include "rmsnorm.h"
#include "rope.h"
#include "mlp.h"
#include <hip/hip_runtime.h>
#include <hip/hip_fp16.h>
#include <algorithm>
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
constexpr int WAVES_PER_BLOCK = 8;
constexpr int BLOCK_THREADS = WAVE_SIZE * WAVES_PER_BLOCK; // 256 threads
constexpr int MAX_HEAD_DIM = 256;
constexpr int ELEMS_PER_LANE = MAX_HEAD_DIM / WAVE_SIZE; // up to 8 elements per lane

// Wave32-cooperative Online Softmax GQA Kernel for gfx1150.
// Each Wave32 (32 threads) processes one (query_pos m, query_head h) pair.
// Supports head_dim up to 256 (e.g. 64, 128, 256) with zero shared-memory overhead
// by keeping the query vector and running output accumulator in per-lane registers.
__global__ __launch_bounds__(BLOCK_THREADS) void gqa_online_softmax_kernel(
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

    const size_t qh_idx = static_cast<size_t>(blockIdx.x) * WAVES_PER_BLOCK + wave_id;
    const size_t total_qh = static_cast<size_t>(q_len) * num_heads;
    if (qh_idx >= total_qh) return;

    const int m = static_cast<int>(qh_idx / num_heads);
    const int h = static_cast<int>(qh_idx % num_heads);
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
            release();
            HIP_CHECK(hipMalloc(&d_K_pool, needed));
            hipError_t err = hipMalloc(&d_V_pool, needed);
            if (err != hipSuccess) {
                (void)hipFree(d_K_pool);
                d_K_pool = nullptr;
                HIP_CHECK(err);
            }
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

    const size_t total_qh = static_cast<size_t>(q_len) * num_heads;
    const size_t blocks = (total_qh + WAVES_PER_BLOCK - 1) / WAVES_PER_BLOCK;

    hipLaunchKernelGGL(
        gqa_online_softmax_kernel,
        dim3(static_cast<unsigned int>(blocks)),
        dim3(BLOCK_THREADS),
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

    const size_t total_qh = static_cast<size_t>(q_len) * num_heads;
    const size_t blocks = (total_qh + WAVES_PER_BLOCK - 1) / WAVES_PER_BLOCK;

    hipLaunchKernelGGL(
        gqa_online_softmax_kernel,
        dim3(static_cast<unsigned int>(blocks)),
        dim3(BLOCK_THREADS),
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

void launch_gqa_attention_cached_fp16_device(
    const void* d_Q,
    const void* d_K_new,
    const void* d_V_new,
    void* d_Out,
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

    // Device-to-Device (D2D) KV-cache write from on-GPU RoPE K / V projections
    HIP_CHECK(hipMemcpy(d_layer_K + write_offset, d_K_new, new_kv_bytes, hipMemcpyDeviceToDevice));
    HIP_CHECK(hipMemcpy(d_layer_V + write_offset, d_V_new, new_kv_bytes, hipMemcpyDeviceToDevice));

    const size_t total_qh = static_cast<size_t>(q_len) * num_heads;
    const size_t blocks = (total_qh + WAVES_PER_BLOCK - 1) / WAVES_PER_BLOCK;

    hipLaunchKernelGGL(
        gqa_online_softmax_kernel,
        dim3(static_cast<unsigned int>(blocks)),
        dim3(BLOCK_THREADS),
        0,
        0,
        static_cast<const half*>(d_Q),
        d_layer_K,
        d_layer_V,
        static_cast<half*>(d_Out),
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
}

namespace {

struct DeviceLayerWorkspace {
    half* d_x = nullptr;
    half* d_h = nullptr;
    half* d_normed = nullptr;
    half* d_norm_w = nullptr;
    half* d_q = nullptr;
    half* d_q_rot = nullptr;
    half* d_k = nullptr;
    half* d_k_rot = nullptr;
    half* d_v = nullptr;
    half* d_attn_out = nullptr;
    half* d_gate = nullptr;
    half* d_up = nullptr;
    half* d_swiglu = nullptr;
    void* d_w = nullptr;

    size_t cap_hidden = 0;
    size_t cap_norm_w = 0;
    size_t cap_q = 0;
    size_t cap_kv = 0;
    size_t cap_ffn = 0;
    size_t cap_w = 0;

    static void realloc_buf(half** ptr, size_t needed) {
        if (*ptr) HIP_CHECK(hipFree(*ptr));
        HIP_CHECK(hipMalloc(ptr, needed));
    }

    void ensure(
        size_t hidden_bytes,
        size_t norm_w_bytes,
        size_t q_bytes,
        size_t kv_bytes,
        size_t ffn_bytes
    ) {
        if (hidden_bytes > cap_hidden) {
            realloc_buf(&d_x, hidden_bytes);
            realloc_buf(&d_h, hidden_bytes);
            realloc_buf(&d_normed, hidden_bytes);
            cap_hidden = hidden_bytes;
        }
        if (norm_w_bytes > cap_norm_w) {
            realloc_buf(&d_norm_w, norm_w_bytes);
            cap_norm_w = norm_w_bytes;
        }
        if (q_bytes > cap_q) {
            realloc_buf(&d_q, q_bytes);
            realloc_buf(&d_q_rot, q_bytes);
            realloc_buf(&d_attn_out, q_bytes);
            cap_q = q_bytes;
        }
        if (kv_bytes > cap_kv) {
            realloc_buf(&d_k, kv_bytes);
            realloc_buf(&d_k_rot, kv_bytes);
            realloc_buf(&d_v, kv_bytes);
            cap_kv = kv_bytes;
        }
        if (ffn_bytes > cap_ffn) {
            realloc_buf(&d_gate, ffn_bytes);
            realloc_buf(&d_up, ffn_bytes);
            realloc_buf(&d_swiglu, ffn_bytes);
            cap_ffn = ffn_bytes;
        }
    }

    void ensure_weight(size_t w_bytes) {
        if (w_bytes > cap_w) {
            if (d_w) HIP_CHECK(hipFree(d_w));
            HIP_CHECK(hipMalloc(&d_w, w_bytes));
            cap_w = w_bytes;
        }
    }

    ~DeviceLayerWorkspace() {
        if (d_x) (void)hipFree(d_x);
        if (d_h) (void)hipFree(d_h);
        if (d_normed) (void)hipFree(d_normed);
        if (d_norm_w) (void)hipFree(d_norm_w);
        if (d_q) (void)hipFree(d_q);
        if (d_q_rot) (void)hipFree(d_q_rot);
        if (d_k) (void)hipFree(d_k);
        if (d_k_rot) (void)hipFree(d_k_rot);
        if (d_v) (void)hipFree(d_v);
        if (d_attn_out) (void)hipFree(d_attn_out);
        if (d_gate) (void)hipFree(d_gate);
        if (d_up) (void)hipFree(d_up);
        if (d_swiglu) (void)hipFree(d_swiglu);
        if (d_w) (void)hipFree(d_w);
    }
};

DeviceLayerWorkspace& get_layer_ws() {
    static DeviceLayerWorkspace ws;
    return ws;
}

size_t weight_bytes_for_type(int w_type, int N, int K) {
    if (w_type == 1) { // GGMLType.F16 (or converted F16)
        return static_cast<size_t>(N) * K * sizeof(half);
    } else if (w_type == 2) { // GGMLType.Q4_0
        if (K % QK4_0 != 0) throw std::invalid_argument("K must be divisible by 32 for Q4_0.");
        return static_cast<size_t>(N) * (K / QK4_0) * BLOCK_Q4_0_BYTES;
    } else if (w_type == 8) { // GGMLType.Q8_0
        if (K % QK8_0 != 0) throw std::invalid_argument("K must be divisible by 32 for Q8_0.");
        return static_cast<size_t>(N) * (K / QK8_0) * BLOCK_Q8_0_BYTES;
    } else if (w_type == 12) { // GGMLType.Q4_K
        if (K % QK_K != 0) throw std::invalid_argument("K must be divisible by 256 for Q4_K.");
        return static_cast<size_t>(N) * (K / QK_K) * BLOCK_Q4_K_BYTES;
    }
    throw std::invalid_argument("Unsupported ggml_type in device layer pipeline.");
}

void project_on_device(
    const half* d_in,
    const void* h_w,
    int w_type,
    half* d_out,
    int M,
    int N,
    int K,
    DeviceLayerWorkspace& ws
) {
    const size_t w_bytes = weight_bytes_for_type(w_type, N, K);
    ws.ensure_weight(w_bytes);
    HIP_CHECK(hipMemcpy(ws.d_w, h_w, w_bytes, hipMemcpyHostToDevice));

    if (w_type == 1) {
        launch_matmul_fp16_nt_device(d_in, ws.d_w, d_out, M, N, K);
    } else if (w_type == 2) {
        launch_matmul_q4_0_device(d_in, ws.d_w, d_out, M, N, K);
    } else if (w_type == 8) {
        launch_matmul_q8_0_device(d_in, ws.d_w, d_out, M, N, K);
    } else if (w_type == 12) {
        launch_matmul_q4_k_device(d_in, ws.d_w, d_out, M, N, K);
    }
}

} // namespace

void launch_forward_layer_cached_fp16(
    const void* h_x_in,
    void* h_x_out,
    const void* h_attn_norm_w,
    const void* h_wq, int wq_type,
    const void* h_wk, int wk_type,
    const void* h_wv, int wv_type,
    const void* h_wo, int wo_type,
    const void* h_ffn_norm_w,
    const void* h_wgate, int wgate_type,
    const void* h_wup, int wup_type,
    const void* h_wdown, int wdown_type,
    int layer_idx,
    int seq_len,
    int pos_offset,
    int hidden_size,
    int intermediate_size,
    int num_heads,
    int num_kv_heads,
    int head_dim,
    float rms_norm_eps,
    float rope_freq_base,
    bool rope_neox,
    float scale
) {
    const int q_dim = num_heads * head_dim;
    const int kv_dim = num_kv_heads * head_dim;

    const size_t hidden_bytes = static_cast<size_t>(seq_len) * hidden_size * sizeof(half);
    const size_t norm_w_bytes = static_cast<size_t>(hidden_size) * sizeof(half);
    const size_t q_bytes = static_cast<size_t>(seq_len) * q_dim * sizeof(half);
    const size_t kv_bytes = static_cast<size_t>(seq_len) * kv_dim * sizeof(half);
    const size_t ffn_bytes = static_cast<size_t>(seq_len) * intermediate_size * sizeof(half);

    auto& ws = get_layer_ws();
    ws.ensure(hidden_bytes, norm_w_bytes, q_bytes, kv_bytes, ffn_bytes);

    // 1. Single H2D copy of input hidden states for this layer
    HIP_CHECK(hipMemcpy(ws.d_x, h_x_in, hidden_bytes, hipMemcpyHostToDevice));

    // 2. Pre-Attention RMSNorm on device
    HIP_CHECK(hipMemcpy(ws.d_norm_w, h_attn_norm_w, norm_w_bytes, hipMemcpyHostToDevice));
    launch_rmsnorm_fp16_device(ws.d_x, ws.d_norm_w, ws.d_normed, seq_len, hidden_size, rms_norm_eps);

    // 3. Q, K, V projections on device
    project_on_device(ws.d_normed, h_wq, wq_type, ws.d_q, seq_len, q_dim, hidden_size, ws);
    project_on_device(ws.d_normed, h_wk, wk_type, ws.d_k, seq_len, kv_dim, hidden_size, ws);
    project_on_device(ws.d_normed, h_wv, wv_type, ws.d_v, seq_len, kv_dim, hidden_size, ws);

    // 4. RoPE on Q and K on device
    launch_rope_fp16_device(
        ws.d_q, ws.d_q_rot, seq_len, num_heads, head_dim, pos_offset, rope_freq_base, rope_neox
    );
    launch_rope_fp16_device(
        ws.d_k, ws.d_k_rot, seq_len, num_kv_heads, head_dim, pos_offset, rope_freq_base, rope_neox
    );

    // 5. D2D KV-cache update + GQA online-softmax attention on device
    launch_gqa_attention_cached_fp16_device(
        ws.d_q_rot, ws.d_k_rot, ws.d_v, ws.d_attn_out,
        layer_idx, seq_len, pos_offset,
        num_heads, num_kv_heads, head_dim,
        scale, true
    );

    // 6. Attention output projection on device (into ws.d_normed as scratch for attn_proj)
    project_on_device(ws.d_attn_out, h_wo, wo_type, ws.d_normed, seq_len, hidden_size, q_dim, ws);

    // 7. Fused First Residual + Pre-FFN RMSNorm on device:
    //    ws.d_h = half(float(ws.d_x) + float(ws.d_normed))
    //    ws.d_x = rmsnorm(ws.d_h, ffn_norm_w)
    HIP_CHECK(hipMemcpy(ws.d_norm_w, h_ffn_norm_w, norm_w_bytes, hipMemcpyHostToDevice));
    launch_rmsnorm_residual_fp16_device(
        ws.d_x, ws.d_normed, ws.d_norm_w, ws.d_h, ws.d_x, seq_len, hidden_size, rms_norm_eps
    );

    // 8. SwiGLU FFN on device
    project_on_device(ws.d_x, h_wgate, wgate_type, ws.d_gate, seq_len, intermediate_size, hidden_size, ws);
    project_on_device(ws.d_x, h_wup, wup_type, ws.d_up, seq_len, intermediate_size, hidden_size, ws);
    launch_swiglu_fp16_device(ws.d_gate, ws.d_up, ws.d_swiglu, seq_len * intermediate_size);
    project_on_device(ws.d_swiglu, h_wdown, wdown_type, ws.d_normed, seq_len, hidden_size, intermediate_size, ws);

    // 9. Second Residual on device: ws.d_x = half(float(ws.d_h) + float(ws.d_normed))
    launch_residual_add_fp16_device(ws.d_h, ws.d_normed, ws.d_x, seq_len * hidden_size);

    // 10. Single D2H copy of output hidden states for this layer
    HIP_CHECK(hipMemcpy(h_x_out, ws.d_x, hidden_bytes, hipMemcpyDeviceToHost));
}
