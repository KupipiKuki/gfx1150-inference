#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <cmath>
#include <stdexcept>
#include "matmul.h"
#include "dequantize.h"
#include "rmsnorm.h"
#include "rope.h"
#include "attention.h"
#include "mlp.h"

namespace py = pybind11;

namespace {

void check_fp16_contiguous(const py::array& arr, const char* name, py::ssize_t min_elems) {
    if (arr.itemsize() != 2) {
        throw std::invalid_argument(std::string(name) + " must be a 2-byte FP16 (numpy.float16) array.");
    }
    if (!(arr.flags() & py::array::c_style)) {
        throw std::invalid_argument(std::string(name) + " must be a C-contiguous array.");
    }
    if (arr.size() < min_elems) {
        throw std::invalid_argument(std::string(name) + " buffer is smaller than expected dimensions.");
    }
}

} // namespace

void matmul(
    const py::array& A,
    const py::array& B,
    py::array& C,
    int M,
    int N,
    int K
) {
    check_fp16_contiguous(A, "A", static_cast<py::ssize_t>(M) * K);
    check_fp16_contiguous(B, "B", static_cast<py::ssize_t>(K) * N);
    check_fp16_contiguous(C, "C", static_cast<py::ssize_t>(M) * N);

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
    check_fp16_contiguous(out_fp16, "out_fp16", num_elements);

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
    check_fp16_contiguous(A, "A", static_cast<py::ssize_t>(M) * K);
    check_fp16_contiguous(C, "C", static_cast<py::ssize_t>(M) * N);

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

void rmsnorm(
    const py::array& x,
    const py::array& weight,
    py::array& out,
    int M,
    int K,
    float eps
) {
    check_fp16_contiguous(x, "x", static_cast<py::ssize_t>(M) * K);
    check_fp16_contiguous(weight, "weight", K);
    check_fp16_contiguous(out, "out", static_cast<py::ssize_t>(M) * K);

    const void* h_x = x.data();
    const void* h_w = weight.data();
    void* h_out = out.mutable_data();

    py::gil_scoped_release release;
    launch_rmsnorm_fp16(h_x, h_w, h_out, M, K, eps);
}

void rope(
    const py::array& x_in,
    py::array& x_out,
    int seq_len,
    int num_heads,
    int head_dim,
    int pos_offset,
    float freq_base,
    bool neox_style
) {
    const py::ssize_t total = static_cast<py::ssize_t>(seq_len) * num_heads * head_dim;
    check_fp16_contiguous(x_in, "x_in", total);
    check_fp16_contiguous(x_out, "x_out", total);

    const void* h_in = x_in.data();
    void* h_out = x_out.mutable_data();

    py::gil_scoped_release release;
    launch_rope_fp16(h_in, h_out, seq_len, num_heads, head_dim, pos_offset, freq_base, neox_style);
}

void gqa_attention(
    const py::array& Q,
    const py::array& K,
    const py::array& V,
    py::array& Out,
    int q_len,
    int kv_len,
    int num_heads,
    int num_kv_heads,
    int head_dim,
    int start_pos,
    float scale,
    bool causal
) {
    const py::ssize_t q_elems = static_cast<py::ssize_t>(q_len) * num_heads * head_dim;
    const py::ssize_t kv_elems = static_cast<py::ssize_t>(kv_len) * num_kv_heads * head_dim;
    check_fp16_contiguous(Q, "Q", q_elems);
    check_fp16_contiguous(K, "K", kv_elems);
    check_fp16_contiguous(V, "V", kv_elems);
    check_fp16_contiguous(Out, "Out", q_elems);

    const void* h_Q = Q.data();
    const void* h_K = K.data();
    const void* h_V = V.data();
    void* h_Out = Out.mutable_data();

    py::gil_scoped_release release;
    launch_gqa_attention_fp16(
        h_Q, h_K, h_V, h_Out,
        q_len, kv_len, num_heads, num_kv_heads, head_dim,
        start_pos, scale, causal
    );
}

void swiglu(
    const py::array& gate,
    const py::array& up,
    py::array& out,
    int num_elements
) {
    check_fp16_contiguous(gate, "gate", num_elements);
    check_fp16_contiguous(up, "up", num_elements);
    check_fp16_contiguous(out, "out", num_elements);

    const void* h_gate = gate.data();
    const void* h_up = up.data();
    void* h_out = out.mutable_data();

    py::gil_scoped_release release;
    launch_swiglu_fp16(h_gate, h_up, h_out, num_elements);
}

void kv_cache_init(int num_layers, int max_seq_len, int num_kv_heads, int head_dim) {
    py::gil_scoped_release release;
    init_device_kv_cache_fp16(num_layers, max_seq_len, num_kv_heads, head_dim);
}

void kv_cache_free() {
    py::gil_scoped_release release;
    free_device_kv_cache_fp16();
}

void gqa_attention_cached(
    const py::array& Q,
    const py::array& K_new,
    const py::array& V_new,
    py::array& Out,
    int layer_idx,
    int q_len,
    int start_pos,
    int num_heads,
    int num_kv_heads,
    int head_dim,
    float scale,
    bool causal
) {
    const py::ssize_t q_elems = static_cast<py::ssize_t>(q_len) * num_heads * head_dim;
    const py::ssize_t kv_new_elems = static_cast<py::ssize_t>(q_len) * num_kv_heads * head_dim;
    check_fp16_contiguous(Q, "Q", q_elems);
    check_fp16_contiguous(K_new, "K_new", kv_new_elems);
    check_fp16_contiguous(V_new, "V_new", kv_new_elems);
    check_fp16_contiguous(Out, "Out", q_elems);

    const void* h_Q = Q.data();
    const void* h_K_new = K_new.data();
    const void* h_V_new = V_new.data();
    void* h_Out = Out.mutable_data();

    py::gil_scoped_release release;
    launch_gqa_attention_cached_fp16(
        h_Q, h_K_new, h_V_new, h_Out,
        layer_idx, q_len, start_pos,
        num_heads, num_kv_heads, head_dim,
        scale, causal
    );
}

PYBIND11_MODULE(matmul_module, m) {
    m.doc() = "HIP FP16 & Q4_0 Transformer Kernels for AMD gfx1150";
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
    m.def(
        "rmsnorm",
        &rmsnorm,
        "Root Mean Square Layer Normalization on AMD GPU (gfx1150)",
        py::arg("x"),
        py::arg("weight"),
        py::arg("out"),
        py::arg("M"),
        py::arg("K"),
        py::arg("eps") = 1e-5f
    );
    m.def(
        "rope",
        &rope,
        "Rotary Positional Embeddings (RoPE) on AMD GPU (gfx1150)",
        py::arg("x_in"),
        py::arg("x_out"),
        py::arg("seq_len"),
        py::arg("num_heads"),
        py::arg("head_dim"),
        py::arg("pos_offset") = 0,
        py::arg("freq_base") = 10000.0f,
        py::arg("neox_style") = false
    );
    m.def(
        "gqa_attention",
        &gqa_attention,
        "Grouped-Query Attention (GQA) with online softmax on AMD GPU (gfx1150)",
        py::arg("Q"),
        py::arg("K"),
        py::arg("V"),
        py::arg("Out"),
        py::arg("q_len"),
        py::arg("kv_len"),
        py::arg("num_heads"),
        py::arg("num_kv_heads"),
        py::arg("head_dim"),
        py::arg("start_pos") = 0,
        py::arg("scale") = 0.0f,
        py::arg("causal") = true
    );
    m.def(
        "swiglu",
        &swiglu,
        "Fused SwiGLU activation out = SiLU(gate) * up on AMD GPU (gfx1150)",
        py::arg("gate"),
        py::arg("up"),
        py::arg("out"),
        py::arg("num_elements")
    );
    m.def(
        "kv_cache_init",
        &kv_cache_init,
        "Allocate GPU-resident GQA KV cache pool for all transformer layers",
        py::arg("num_layers"),
        py::arg("max_seq_len"),
        py::arg("num_kv_heads"),
        py::arg("head_dim")
    );
    m.def(
        "kv_cache_free",
        &kv_cache_free,
        "Free GPU-resident GQA KV cache pool"
    );
    m.def(
        "gqa_attention_cached",
        &gqa_attention_cached,
        "Update GPU-resident KV cache at start_pos and run GQA online-softmax attention",
        py::arg("Q"),
        py::arg("K_new"),
        py::arg("V_new"),
        py::arg("Out"),
        py::arg("layer_idx"),
        py::arg("q_len"),
        py::arg("start_pos"),
        py::arg("num_heads"),
        py::arg("num_kv_heads"),
        py::arg("head_dim"),
        py::arg("scale") = 0.0f,
        py::arg("causal") = true
    );
}
