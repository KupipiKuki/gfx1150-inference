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

// Packed 34-byte GGML Q8_0 block structure
struct block_q8_0 {
    half d;                 // 2-byte FP16 delta (scale)
    int8_t qs[QK8_0];       // 32 bytes of signed 8-bit quantized weights
};

// Packed 144-byte GGML Q4_K super-block structure (256 weights)
struct block_q4_k {
    half d;                         // 2B FP16 super-block scale for quantized sub-block scales
    half dmin;                      // 2B FP16 super-block scale for quantized sub-block mins
    uint8_t scales[K_SCALE_SIZE];   // 12B packed 6-bit scales (8) and 6-bit mins (8)
    uint8_t qs[QK_K / 2];           // 128B packed 4-bit unsigned weights (256 nibbles)
};
#pragma pack(pop)

static_assert(sizeof(block_q4_0) == BLOCK_Q4_0_BYTES, "block_q4_0 must be 18 bytes");
static_assert(sizeof(block_q8_0) == BLOCK_Q8_0_BYTES, "block_q8_0 must be 34 bytes");
static_assert(sizeof(block_q4_k) == BLOCK_Q4_K_BYTES, "block_q4_k must be 144 bytes");

__device__ __forceinline__ void get_scale_min_k4(
    int j,
    const uint8_t* __restrict__ q,
    uint8_t& sc,
    uint8_t& m
) {
    if (j < 4) {
        sc = q[j] & 63;
        m  = q[j + 4] & 63;
    } else {
        sc = (q[j + 4] & 0x0F) | ((q[j - 4] >> 6) << 4);
        m  = (q[j + 4] >> 4)   | ((q[j]     >> 6) << 4);
    }
}

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

// 1 thread per Q8_0 block (32 weights)
__global__ void dequantize_q8_0_kernel(
    const block_q8_0* __restrict__ x,
    half* __restrict__ y,
    const int num_blocks
) {
    const int ib = blockIdx.x * blockDim.x + threadIdx.x;
    if (ib >= num_blocks) return;

    const float d = __half2float(x[ib].d);
    const int8_t* qs = x[ib].qs;
    half* out = y + ib * QK8_0;

    #pragma unroll
    for (int j = 0; j < QK8_0; ++j) {
        out[j] = __float2half(d * static_cast<float>(qs[j]));
    }
}

// Wave32-optimized fused Q8_0 GEMV/Matmul kernel
__global__ __launch_bounds__(256) void matmul_q8_0_wave_kernel(
    const half* __restrict__ A,
    const block_q8_0* __restrict__ B,
    half* __restrict__ C,
    const int M,
    const int N,
    const int K,
    const int blocks_per_row
) {
    const int tid = threadIdx.x;
    const int wave_id = tid / WAVE_SIZE;
    const int lane_id = tid % WAVE_SIZE;

    const int n = blockIdx.x * WAVES_PER_BLOCK + wave_id;
    const int m = blockIdx.y;

    if (m >= M || n >= N) return;

    const half* a_row = A + static_cast<size_t>(m) * K;
    const block_q8_0* b_row = B + static_cast<size_t>(n) * blocks_per_row;

    float sum = 0.0f;

    for (int ib = lane_id; ib < blocks_per_row; ib += WAVE_SIZE) {
        const float d = __half2float(b_row[ib].d);
        const int8_t* qs = b_row[ib].qs;
        const half* a_blk = a_row + ib * QK8_0;

        float block_sum = 0.0f;
        #pragma unroll
        for (int j = 0; j < QK8_0; ++j) {
            block_sum += __half2float(a_blk[j]) * static_cast<float>(qs[j]);
        }
        sum += d * block_sum;
    }

    #pragma unroll
    for (int offset = WAVE_SIZE / 2; offset > 0; offset /= 2) {
        sum += __shfl_down(sum, offset, WAVE_SIZE);
    }

    if (lane_id == 0) {
        C[static_cast<size_t>(m) * N + n] = __float2half(sum);
    }
}

// 1 Wave32 wavefront per Q4_K super-block (256 weights) for coalesced dequantization
__global__ __launch_bounds__(256) void dequantize_q4_k_kernel(
    const block_q4_k* __restrict__ x,
    half* __restrict__ y,
    const int num_super_blocks
) {
    const int tid = threadIdx.x;
    const int wave_id = tid / WAVE_SIZE;
    const int lane_id = tid % WAVE_SIZE; // 0..31

    const int ib = blockIdx.x * WAVES_PER_BLOCK + wave_id;
    if (ib >= num_super_blocks) return;

    const float d = __half2float(x[ib].d);
    const float min_val = __half2float(x[ib].dmin);
    const uint8_t* scales = x[ib].scales;
    const uint8_t* qs = x[ib].qs;
    half* out = y + static_cast<size_t>(ib) * QK_K;

    #pragma unroll
    for (int chunk = 0; chunk < 4; ++chunk) {
        uint8_t sc0, m0, sc1, m1;
        get_scale_min_k4(2 * chunk,     scales, sc0, m0);
        get_scale_min_k4(2 * chunk + 1, scales, sc1, m1);

        const float d0 = d * static_cast<float>(sc0);
        const float dm0 = min_val * static_cast<float>(m0);
        const float d1 = d * static_cast<float>(sc1);
        const float dm1 = min_val * static_cast<float>(m1);

        const uint8_t q_byte = qs[chunk * 32 + lane_id];
        const float q0 = static_cast<float>(q_byte & 0x0F);
        const float q1 = static_cast<float>(q_byte >> 4);

        out[chunk * 64 + lane_id]      = __float2half(d0 * q0 - dm0);
        out[chunk * 64 + 32 + lane_id] = __float2half(d1 * q1 - dm1);
    }
}

// Wave32-cooperative fused Q4_K (Q4_K_M / Q4_K_S) Matmul/GEMV kernel:
// All 32 lanes in a wavefront process index `l = lane_id` (0..31) across the 4 chunks
// of each 256-element super-block, ensuring 100% wave utilization even for small K
// and coalesced 32-byte/64-byte global memory reads.
__global__ __launch_bounds__(256) void matmul_q4_k_wave_kernel(
    const half* __restrict__ A,
    const block_q4_k* __restrict__ B,
    half* __restrict__ C,
    const int M,
    const int N,
    const int K,
    const int super_blocks_per_row
) {
    const int tid = threadIdx.x;
    const int wave_id = tid / WAVE_SIZE;
    const int lane_id = tid % WAVE_SIZE; // 0..31

    const int n = blockIdx.x * WAVES_PER_BLOCK + wave_id;
    const int m = blockIdx.y;

    if (m >= M || n >= N) return;

    const half* a_row = A + static_cast<size_t>(m) * K;
    const block_q4_k* b_row = B + static_cast<size_t>(n) * super_blocks_per_row;

    float sum = 0.0f;

    for (int ib = 0; ib < super_blocks_per_row; ++ib) {
        const float d = __half2float(b_row[ib].d);
        const float min_val = __half2float(b_row[ib].dmin);
        const uint8_t* scales = b_row[ib].scales;
        const uint8_t* qs = b_row[ib].qs;
        const half* a_blk = a_row + static_cast<size_t>(ib) * QK_K;

        #pragma unroll
        for (int chunk = 0; chunk < 4; ++chunk) {
            uint8_t sc0, m0, sc1, m1;
            get_scale_min_k4(2 * chunk,     scales, sc0, m0);
            get_scale_min_k4(2 * chunk + 1, scales, sc1, m1);

            const float d0 = d * static_cast<float>(sc0);
            const float dm0 = min_val * static_cast<float>(m0);
            const float d1 = d * static_cast<float>(sc1);
            const float dm1 = min_val * static_cast<float>(m1);

            const uint8_t q_byte = qs[chunk * 32 + lane_id];
            const float w0 = d0 * static_cast<float>(q_byte & 0x0F) - dm0;
            const float w1 = d1 * static_cast<float>(q_byte >> 4)   - dm1;

            const float a0 = __half2float(a_blk[chunk * 64 + lane_id]);
            const float a1 = __half2float(a_blk[chunk * 64 + 32 + lane_id]);

            sum += a0 * w0 + a1 * w1;
        }
    }

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

void launch_dequantize_q8_0(
    const void* h_q8,
    void* h_fp16_out,
    int num_elements
) {
    if (num_elements % QK8_0 != 0) {
        throw std::invalid_argument("num_elements must be a multiple of 32 for Q8_0 dequantization.");
    }
    const int num_blocks = num_elements / QK8_0;
    const size_t size_in = static_cast<size_t>(num_blocks) * sizeof(block_q8_0);
    const size_t size_out = static_cast<size_t>(num_elements) * sizeof(half);

    auto& ws = get_q4_workspace();
    ws.ensure(size_in, size_out, 0);

    HIP_CHECK(hipMemcpy(ws.d_buf0, h_q8, size_in, hipMemcpyHostToDevice));

    const int threads = 256;
    const int grids = (num_blocks + threads - 1) / threads;

    hipLaunchKernelGGL(
        dequantize_q8_0_kernel,
        dim3(grids),
        dim3(threads),
        0,
        0,
        static_cast<const block_q8_0*>(ws.d_buf0),
        static_cast<half*>(ws.d_buf1),
        num_blocks
    );
    HIP_CHECK(hipGetLastError());

    HIP_CHECK(hipMemcpy(h_fp16_out, ws.d_buf1, size_out, hipMemcpyDeviceToHost));
}

void launch_matmul_q8_0(
    const void* h_A_fp16,
    const void* h_B_q8,
    void* h_C_fp16,
    int M,
    int N,
    int K
) {
    if (K % QK8_0 != 0) {
        throw std::invalid_argument("K dimension must be a multiple of 32 for Q8_0 matmul.");
    }
    const int blocks_per_row = K / QK8_0;
    const size_t size_A = static_cast<size_t>(M) * K * sizeof(half);
    const size_t size_B = static_cast<size_t>(N) * blocks_per_row * sizeof(block_q8_0);
    const size_t size_C = static_cast<size_t>(M) * N * sizeof(half);

    auto& ws = get_q4_workspace();
    ws.ensure(size_A, size_B, size_C);

    HIP_CHECK(hipMemcpy(ws.d_buf0, h_A_fp16, size_A, hipMemcpyHostToDevice));
    HIP_CHECK(hipMemcpy(ws.d_buf1, h_B_q8, size_B, hipMemcpyHostToDevice));

    dim3 blockDim(WAVE_SIZE * WAVES_PER_BLOCK); // 256 threads
    dim3 gridDim(
        (N + WAVES_PER_BLOCK - 1) / WAVES_PER_BLOCK,
        M
    );

    hipLaunchKernelGGL(
        matmul_q8_0_wave_kernel,
        gridDim,
        blockDim,
        0,
        0,
        static_cast<const half*>(ws.d_buf0),
        static_cast<const block_q8_0*>(ws.d_buf1),
        static_cast<half*>(ws.d_buf2),
        M,
        N,
        K,
        blocks_per_row
    );
    HIP_CHECK(hipGetLastError());

    HIP_CHECK(hipMemcpy(h_C_fp16, ws.d_buf2, size_C, hipMemcpyDeviceToHost));
}

void launch_dequantize_q4_k(
    const void* h_q4k,
    void* h_fp16_out,
    int num_elements
) {
    if (num_elements % QK_K != 0) {
        throw std::invalid_argument("num_elements must be a multiple of 256 for Q4_K dequantization.");
    }
    const int num_super_blocks = num_elements / QK_K;
    const size_t size_in = static_cast<size_t>(num_super_blocks) * sizeof(block_q4_k);
    const size_t size_out = static_cast<size_t>(num_elements) * sizeof(half);

    auto& ws = get_q4_workspace();
    ws.ensure(size_in, size_out, 0);

    HIP_CHECK(hipMemcpy(ws.d_buf0, h_q4k, size_in, hipMemcpyHostToDevice));

    dim3 blockDim(WAVE_SIZE * WAVES_PER_BLOCK); // 256 threads (8 waves per block)
    dim3 gridDim((num_super_blocks + WAVES_PER_BLOCK - 1) / WAVES_PER_BLOCK);

    hipLaunchKernelGGL(
        dequantize_q4_k_kernel,
        gridDim,
        blockDim,
        0,
        0,
        static_cast<const block_q4_k*>(ws.d_buf0),
        static_cast<half*>(ws.d_buf1),
        num_super_blocks
    );
    HIP_CHECK(hipGetLastError());

    HIP_CHECK(hipMemcpy(h_fp16_out, ws.d_buf1, size_out, hipMemcpyDeviceToHost));
}

void launch_matmul_q4_k(
    const void* h_A_fp16,
    const void* h_B_q4k,
    void* h_C_fp16,
    int M,
    int N,
    int K
) {
    if (K % QK_K != 0) {
        throw std::invalid_argument("K dimension must be a multiple of 256 for Q4_K matmul.");
    }
    const int super_blocks_per_row = K / QK_K;
    const size_t size_A = static_cast<size_t>(M) * K * sizeof(half);
    const size_t size_B = static_cast<size_t>(N) * super_blocks_per_row * sizeof(block_q4_k);
    const size_t size_C = static_cast<size_t>(M) * N * sizeof(half);

    auto& ws = get_q4_workspace();
    ws.ensure(size_A, size_B, size_C);

    HIP_CHECK(hipMemcpy(ws.d_buf0, h_A_fp16, size_A, hipMemcpyHostToDevice));
    HIP_CHECK(hipMemcpy(ws.d_buf1, h_B_q4k, size_B, hipMemcpyHostToDevice));

    dim3 blockDim(WAVE_SIZE * WAVES_PER_BLOCK); // 256 threads
    dim3 gridDim(
        (N + WAVES_PER_BLOCK - 1) / WAVES_PER_BLOCK,
        M
    );

    hipLaunchKernelGGL(
        matmul_q4_k_wave_kernel,
        gridDim,
        blockDim,
        0,
        0,
        static_cast<const half*>(ws.d_buf0),
        static_cast<const block_q4_k*>(ws.d_buf1),
        static_cast<half*>(ws.d_buf2),
        M,
        N,
        K,
        super_blocks_per_row
    );
    HIP_CHECK(hipGetLastError());

    HIP_CHECK(hipMemcpy(h_C_fp16, ws.d_buf2, size_C, hipMemcpyDeviceToHost));
}

