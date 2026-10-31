#ifndef MLP_H
#define MLP_H

// Host-callable SwiGLU activation launcher:
// Computes out[i] = (gate[i] / (1.0f + expf(-gate[i]))) * up[i] in FP32, stored as FP16.
void launch_swiglu_fp16(
    const void* h_gate,
    const void* h_up,
    void* h_out,
    int num_elements
);

#endif // MLP_H

