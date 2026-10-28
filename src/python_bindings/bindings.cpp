#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <hip/hip_runtime.h>
#include "matmul.hip"

namespace py = pybind11;

void matmul(
    const py::array_t<half>& A,
    const py::array_t<half>& B,
    py::array_t<half>& C,
    int M,
    int N,
    int K
) {
    half *d_A, *d_B, *d_C;
    size_t size_A = M * K * sizeof(half);
    size_t size_B = K * N * sizeof(half);
    size_t size_C = M * N * sizeof(half);
    
    hipMalloc(&d_A, size_A);
    hipMalloc(&d_B, size_B);
    hipMalloc(&d_C, size_C);
    
    hipMemcpy(d_A, A.data(), size_A, hipMemcpyHostToDevice);
    hipMemcpy(d_B, B.data(), size_B, hipMemcpyHostToDevice);
    
    dim3 blockDim(16, 16);
    dim3 gridDim(
        (N + blockDim.x - 1) / blockDim.x,
        (M + blockDim.y - 1) / blockDim.y
    );
    
    hipLaunchKernelGGL(
        matmul_kernel_tiled,
        gridDim,
        blockDim,
        0,
        0,
        d_A,
        d_B,
        d_C,
        M,
        N,
        K
    );
    
    hipMemcpy(C.mutable_data(), d_C, size_C, hipMemcpyDeviceToHost);
    
    hipFree(d_A);
    hipFree(d_B);
    hipFree(d_C);
    
    hipDeviceSynchronize();
}

PYBIND11_MODULE(matmul_module, m) {
    m.def(
        "matmul",
        &matmul,
        "FP16 matrix multiplication on AMD GPU (gfx1150)",
        py::arg("A"),
        py::arg("B"),
        py::arg("C"),
        py::arg("M"),
        py::arg("N"),
        py::arg("K")
    );
}