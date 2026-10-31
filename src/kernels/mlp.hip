#include "mlp.h"
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

__global__ void swiglu_kernel(
    const half* __restrict__ gate,
    const half* __restrict__ up,
    half* __restrict__ out,
    const int num_elements
) {
    const int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= num_elements) return;

    const float g = __half2float(gate[idx]);
    const float u = __half2float(up[idx]);
    const float silu_g = g / (1.0f + expf(-g));
    out[idx] = __float2half(silu_g * u);
}

namespace {

struct SwiGLUWorkspace {
    half* d_gate = nullptr;
    half* d_up = nullptr;
    half* d_out = nullptr;
    size_t cap = 0;

    void ensure(size_t bytes) {
        if (bytes > cap) {
            if (d_gate) HIP_CHECK(hipFree(d_gate));
            if (d_up) HIP_CHECK(hipFree(d_up));
            if (d_out) HIP_CHECK(hipFree(d_out));
            HIP_CHECK(hipMalloc(&d_gate, bytes));
            HIP_CHECK(hipMalloc(&d_up, bytes));
            HIP_CHECK(hipMalloc(&d_out, bytes));
            cap = bytes;
        }
    }

    ~SwiGLUWorkspace() {
        if (d_gate) (void)hipFree(d_gate);
        if (d_up) (void)hipFree(d_up);
        if (d_out) (void)hipFree(d_out);
    }
};

} // namespace

void launch_swiglu_fp16(
    const void* h_gate,
    const void* h_up,
    void* h_out,
    int num_elements
) {
    static SwiGLUWorkspace ws;
    const size_t bytes = static_cast<size_t>(num_elements) * sizeof(half);
    ws.ensure(bytes);

    HIP_CHECK(hipMemcpy(ws.d_gate, h_gate, bytes, hipMemcpyHostToDevice));
    HIP_CHECK(hipMemcpy(ws.d_up, h_up, bytes, hipMemcpyHostToDevice));

    const int threads = 256;
    const int blocks = (num_elements + threads - 1) / threads;

    hipLaunchKernelGGL(
        swiglu_kernel,
        dim3(blocks),
        dim3(threads),
        0,
        0,
        ws.d_gate,
        ws.d_up,
        ws.d_out,
        num_elements
    );
    HIP_CHECK(hipGetLastError());

    HIP_CHECK(hipMemcpy(h_out, ws.d_out, bytes, hipMemcpyDeviceToHost));
}

