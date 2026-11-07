#ifndef MLP_H
#define MLP_H

// Identical to hip_runtime.h's typedef so this header stays includable from
// non-HIP C++ translation units. Redundant typedefs are legal C++.
typedef struct ihipStream_t* hipStream_t;

// Host-callable SwiGLU activation launcher:
// Computes out[i] = (gate[i] / (1.0f + expf(-gate[i]))) * up[i] in FP32, stored as FP16.
void launch_swiglu_fp16(
    const void* h_gate,
    const void* h_up,
    void* h_out,
    int num_elements
);

// Device-resident launcher (all pointers in GPU memory). `stream` is the
// compute stream the kernel launches on (7E; default 0 keeps the synchronous
// host wrapper unchanged).
void launch_swiglu_fp16_device(
    const void* d_gate,
    const void* d_up,
    void* d_out,
    int num_elements,
    hipStream_t stream = 0
);

#endif // MLP_H

