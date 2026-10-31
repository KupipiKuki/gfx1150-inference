#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <stdexcept>
#include "matmul.h"
#include "dequantize.h"

namespace py = pybind11;

void matmul(
    const py::array& A,
    const py::array& B,
    py::array& C,
    int M,
    int N,
    int K
) {
    if (A.itemsize() != 2 || B.itemsize() != 2 || C.itemsize() != 2) {
        throw std::invalid_argument("A, B, and C must be 2-byte FP16 (numpy.float16) arrays.");
    }
    if (!(A.flags() & py::array::c_style) ||
        !(B.flags() & py::array::c_style) ||
        !(C.flags() & py::array::c_style)) {
        throw std::invalid_argument("A, B, and C must be C-contiguous arrays.");
    }
    if (A.size() < static_cast<py::ssize_t>(M) * K ||
        B.size() < static_cast<py::ssize_t>(K) * N ||
        C.size() < static_cast<py::ssize_t>(M) * N) {
        throw std::invalid_argument("Array buffer sizes are smaller than specified M, N, K dimensions.");
    }

    const void* h_A = A.data();
    const void* h_B = B.data();
    void* h_C = C.mutable_data();

    py::gil_scoped_release release;
    launch_matmul_fp16(h_A, h_B, h_C, M, N, K);
}

void dequantize_q4_0(
    const py::buffer& q4_buf,
    py::array& out_fp16,
    int num_elements
) {
    if (num_elements <= 0 || num_elements % QK4_0 != 0) {
        throw std::invalid_argument("num_elements must be a positive multiple of 32.");
    }
    py::buffer_info q4_info = q4_buf.request();
    const size_t expected_bytes = static_cast<size_t>(num_elements / QK4_0) * BLOCK_Q4_0_BYTES;
    const size_t actual_bytes = static_cast<size_t>(q4_info.size) * q4_info.itemsize;
    if (actual_bytes < expected_bytes) {
        throw std::invalid_argument("Q4_0 buffer is smaller than required (num_elements / 32 * 18 bytes).");
    }
    if (out_fp16.itemsize() != 2 || !(out_fp16.flags() & py::array::c_style) ||
        out_fp16.size() < static_cast<py::ssize_t>(num_elements)) {
        throw std::invalid_argument("out_fp16 must be a C-contiguous numpy.float16 array with at least num_elements.");
    }

    const void* h_q4 = q4_info.ptr;
    void* h_out = out_fp16.mutable_data();

    py::gil_scoped_release release;
    launch_dequantize_q4_0(h_q4, h_out, num_elements);
}

void matmul_q4_0(
    const py::array& A,
    const py::buffer& B_q4,
    py::array& C,
    int M,
    int N,
    int K
) {
    if (K <= 0 || K % QK4_0 != 0) {
        throw std::invalid_argument("K must be a positive multiple of 32 for Q4_0 matmul.");
    }
    if (A.itemsize() != 2 || C.itemsize() != 2) {
        throw std::invalid_argument("A and C must be 2-byte FP16 (numpy.float16) arrays.");
    }
    if (!(A.flags() & py::array::c_style) || !(C.flags() & py::array::c_style)) {
        throw std::invalid_argument("A and C must be C-contiguous arrays.");
    }
    if (A.size() < static_cast<py::ssize_t>(M) * K ||
        C.size() < static_cast<py::ssize_t>(M) * N) {
        throw std::invalid_argument("A or C buffer size is smaller than M, N, K dimensions.");
    }

    py::buffer_info b_info = B_q4.request();
    const size_t expected_b_bytes = static_cast<size_t>(N) * (K / QK4_0) * BLOCK_Q4_0_BYTES;
    const size_t actual_b_bytes = static_cast<size_t>(b_info.size) * b_info.itemsize;
    if (actual_b_bytes < expected_b_bytes) {
        throw std::invalid_argument("B_q4 buffer is smaller than required N * (K / 32) * 18 bytes.");
    }

    const void* h_A = A.data();
    const void* h_B = b_info.ptr;
    void* h_C = C.mutable_data();

    py::gil_scoped_release release;
    launch_matmul_q4_0(h_A, h_B, h_C, M, N, K);
}

PYBIND11_MODULE(matmul_module, m) {
    m.doc() = "HIP FP16 & Q4_0 matrix multiplication and dequantization module for AMD gfx1150";
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
    m.def(
        "dequantize_q4_0",
        &dequantize_q4_0,
        "Dequantize GGUF Q4_0 blocks (18B per 32 weights) to FP16 on AMD GPU (gfx1150)",
        py::arg("q4_buf"),
        py::arg("out_fp16"),
        py::arg("num_elements")
    );
    m.def(
        "matmul_q4_0",
        &matmul_q4_0,
        "Fused FP16 x Q4_0 matrix multiplication C(M,N) = A(M,K) @ B(N,K)^T on AMD GPU (gfx1150)",
        py::arg("A"),
        py::arg("B_q4"),
        py::arg("C"),
        py::arg("M"),
        py::arg("N"),
        py::arg("K")
    );
}
