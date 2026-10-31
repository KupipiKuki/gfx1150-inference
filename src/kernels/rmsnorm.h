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

#endif // RMSNORM_H

