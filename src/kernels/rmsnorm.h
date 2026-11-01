#ifndef RMSNORM_H
#define RMSNORM_H

// Host-callable RMSNorm launcher compiled by amdclang++ in rmsnorm.hip.
// Computes: out[m, k] = (x[m, k] / sqrt(mean(x[m, :]^2) + eps)) * weight[k]
// All input/output arrays are FP16 (half) of shape:
//   x:      (M, K)
//   weight: (K,)
//   out:    (M, K)
void launch_rmsnorm_fp16(
    const void* h_x,
    const void* h_weight,
    void* h_out,
    int M,
    int K,
    float eps
);

// Fused Residual Add + RMSNorm launcher:
// Computes in a single kernel pass:
//   h_out[m, k]    = half(float(x[m, k]) + float(residual[m, k]))
//   norm_out[m, k] = (h_out[m, k] / sqrt(mean(h_out[m, :]^2) + eps)) * weight[k]
void launch_rmsnorm_residual_fp16(
    const void* h_x,
    const void* h_residual,
    const void* h_weight,
    void* h_h_out,
    void* h_norm_out,
    int M,
    int K,
    float eps
);

// GPU FP32-accumulated residual addition:
//   out[i] = half(float(x[i]) + float(residual[i]))
void launch_residual_add_fp16(
    const void* h_x,
    const void* h_residual,
    void* h_out,
    int num_elements
);

// Device-resident launchers (all pointers in GPU memory)
void launch_rmsnorm_fp16_device(
    const void* d_x,
    const void* d_weight,
    void* d_out,
    int M,
    int K,
    float eps
);

void launch_rmsnorm_residual_fp16_device(
    const void* d_x,
    const void* d_residual,
    const void* d_weight,
    void* d_h_out,
    void* d_norm_out,
    int M,
    int K,
    float eps
);

void launch_residual_add_fp16_device(
    const void* d_x,
    const void* d_residual,
    void* d_out,
    int num_elements
);

#endif // RMSNORM_H

