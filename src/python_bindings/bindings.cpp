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

void matmul_nt(
    const py::array& A,
    const py::array& B_nt,
    py::array& C,
    int M,
    int N,
    int K
) {
    check_fp16_contiguous(A, "A", static_cast<py::ssize_t>(M) * K);
    check_fp16_contiguous(B_nt, "B_nt", static_cast<py::ssize_t>(N) * K);
    if (B_nt.ndim() == 2 && (B_nt.shape(0) != N || B_nt.shape(1) != K)) {
        throw std::invalid_argument("B_nt 2D shape must be (N, K) for matmul_nt.");
    }
    check_fp16_contiguous(C, "C", static_cast<py::ssize_t>(M) * N);

    const void* h_A = A.data();
    const void* h_B = B_nt.data();
    void* h_C = C.mutable_data();

    py::gil_scoped_release release;
    launch_matmul_fp16_nt(h_A, h_B, h_C, M, N, K);
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

void dequantize_q8_0(
    const py::buffer& q8_buf,
    py::array& out_fp16,
    int num_elements
) {
    if (num_elements <= 0 || num_elements % QK8_0 != 0) {
        throw std::invalid_argument("num_elements must be a positive multiple of 32.");
    }
    py::buffer_info q8_info = q8_buf.request();
    const size_t expected_bytes = static_cast<size_t>(num_elements / QK8_0) * BLOCK_Q8_0_BYTES;
    const size_t actual_bytes = static_cast<size_t>(q8_info.size) * q8_info.itemsize;
    if (actual_bytes < expected_bytes) {
        throw std::invalid_argument("Q8_0 buffer is smaller than required (num_elements / 32 * 34 bytes).");
    }
    check_fp16_contiguous(out_fp16, "out_fp16", num_elements);

    const void* h_q8 = q8_info.ptr;
    void* h_out = out_fp16.mutable_data();

    py::gil_scoped_release release;
    launch_dequantize_q8_0(h_q8, h_out, num_elements);
}

void matmul_q8_0(
    const py::array& A,
    const py::buffer& B_q8,
    py::array& C,
    int M,
    int N,
    int K
) {
    if (K <= 0 || K % QK8_0 != 0) {
        throw std::invalid_argument("K must be a positive multiple of 32 for Q8_0 matmul.");
    }
    check_fp16_contiguous(A, "A", static_cast<py::ssize_t>(M) * K);
    check_fp16_contiguous(C, "C", static_cast<py::ssize_t>(M) * N);

    py::buffer_info b_info = B_q8.request();
    const size_t expected_b_bytes = static_cast<size_t>(N) * (K / QK8_0) * BLOCK_Q8_0_BYTES;
    const size_t actual_b_bytes = static_cast<size_t>(b_info.size) * b_info.itemsize;
    if (actual_b_bytes < expected_b_bytes) {
        throw std::invalid_argument("B_q8 buffer is smaller than required N * (K / 32) * 34 bytes.");
    }

    const void* h_A = A.data();
    const void* h_B = b_info.ptr;
    void* h_C = C.mutable_data();

    py::gil_scoped_release release;
    launch_matmul_q8_0(h_A, h_B, h_C, M, N, K);
}

void dequantize_q4_k(
    const py::buffer& q4k_buf,
    py::array& out_fp16,
    int num_elements
) {
    if (num_elements <= 0 || num_elements % QK_K != 0) {
        throw std::invalid_argument("num_elements must be a positive multiple of 256.");
    }
    py::buffer_info q4k_info = q4k_buf.request();
    const size_t expected_bytes = static_cast<size_t>(num_elements / QK_K) * BLOCK_Q4_K_BYTES;
    const size_t actual_bytes = static_cast<size_t>(q4k_info.size) * q4k_info.itemsize;
    if (actual_bytes < expected_bytes) {
        throw std::invalid_argument("Q4_K buffer is smaller than required (num_elements / 256 * 144 bytes).");
    }
    check_fp16_contiguous(out_fp16, "out_fp16", num_elements);

    const void* h_q4k = q4k_info.ptr;
    void* h_out = out_fp16.mutable_data();

    py::gil_scoped_release release;
    launch_dequantize_q4_k(h_q4k, h_out, num_elements);
}

void matmul_q4_k(
    const py::array& A,
    const py::buffer& B_q4k,
    py::array& C,
    int M,
    int N,
    int K
) {
    if (K <= 0 || K % QK_K != 0) {
        throw std::invalid_argument("K must be a positive multiple of 256 for Q4_K matmul.");
    }
    check_fp16_contiguous(A, "A", static_cast<py::ssize_t>(M) * K);
    check_fp16_contiguous(C, "C", static_cast<py::ssize_t>(M) * N);

    py::buffer_info b_info = B_q4k.request();
    const size_t expected_b_bytes = static_cast<size_t>(N) * (K / QK_K) * BLOCK_Q4_K_BYTES;
    const size_t actual_b_bytes = static_cast<size_t>(b_info.size) * b_info.itemsize;
    if (actual_b_bytes < expected_b_bytes) {
        throw std::invalid_argument("B_q4k buffer is smaller than required N * (K / 256) * 144 bytes.");
    }

    const void* h_A = A.data();
    const void* h_B = b_info.ptr;
    void* h_C = C.mutable_data();

    py::gil_scoped_release release;
    launch_matmul_q4_k(h_A, h_B, h_C, M, N, K);
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

void rmsnorm_residual(
    const py::array& x,
    const py::array& residual,
    const py::array& weight,
    py::array& h_out,
    py::array& norm_out,
    int M,
    int K,
    float eps
) {
    const py::ssize_t total = static_cast<py::ssize_t>(M) * K;
    check_fp16_contiguous(x, "x", total);
    check_fp16_contiguous(residual, "residual", total);
    check_fp16_contiguous(weight, "weight", K);
    check_fp16_contiguous(h_out, "h_out", total);
    check_fp16_contiguous(norm_out, "norm_out", total);

    const void* ptr_x = x.data();
    const void* ptr_res = residual.data();
    const void* ptr_w = weight.data();
    void* ptr_h_out = h_out.mutable_data();
    void* ptr_norm_out = norm_out.mutable_data();

    py::gil_scoped_release release;
    launch_rmsnorm_residual_fp16(ptr_x, ptr_res, ptr_w, ptr_h_out, ptr_norm_out, M, K, eps);
}

void residual_add(
    const py::array& x,
    const py::array& residual,
    py::array& out,
    int num_elements
) {
    check_fp16_contiguous(x, "x", num_elements);
    check_fp16_contiguous(residual, "residual", num_elements);
    check_fp16_contiguous(out, "out", num_elements);

    const void* ptr_x = x.data();
    const void* ptr_res = residual.data();
    void* ptr_out = out.mutable_data();

    py::gil_scoped_release release;
    launch_residual_add_fp16(ptr_x, ptr_res, ptr_out, num_elements);
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

namespace {

const void* check_weight_buffer(
    const py::buffer& buf,
    int w_type,
    int N,
    int K,
    const char* name
) {
    py::buffer_info info = buf.request();
    const size_t actual_bytes = static_cast<size_t>(info.size) * info.itemsize;
    size_t expected_bytes = 0;
    if (w_type == 1) {
        expected_bytes = static_cast<size_t>(N) * K * 2;
    } else if (w_type == 2) {
        if (K <= 0 || K % QK4_0 != 0) {
            throw std::invalid_argument(std::string(name) + " K must be divisible by 32 for Q4_0.");
        }
        expected_bytes = static_cast<size_t>(N) * (K / QK4_0) * BLOCK_Q4_0_BYTES;
    } else if (w_type == 8) {
        if (K <= 0 || K % QK8_0 != 0) {
            throw std::invalid_argument(std::string(name) + " K must be divisible by 32 for Q8_0.");
        }
        expected_bytes = static_cast<size_t>(N) * (K / QK8_0) * BLOCK_Q8_0_BYTES;
    } else if (w_type == 12) {
        if (K <= 0 || K % QK_K != 0) {
            throw std::invalid_argument(std::string(name) + " K must be divisible by 256 for Q4_K.");
        }
        expected_bytes = static_cast<size_t>(N) * (K / QK_K) * BLOCK_Q4_K_BYTES;
    } else {
        throw std::invalid_argument(std::string(name) + " has unsupported ggml_type.");
    }
    if (actual_bytes < expected_bytes) {
        throw std::invalid_argument(std::string(name) + " weight buffer is smaller than required.");
    }
    return info.ptr;
}

} // namespace

void forward_layer_cached(
    const py::array& x_in,
    py::array& x_out,
    const py::array& attn_norm_w,
    const py::buffer& wq, int wq_type,
    const py::buffer& wk, int wk_type,
    const py::buffer& wv, int wv_type,
    const py::buffer& wo, int wo_type,
    const py::array& ffn_norm_w,
    const py::buffer& wgate, int wgate_type,
    const py::buffer& wup, int wup_type,
    const py::buffer& wdown, int wdown_type,
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
    const py::ssize_t hidden_elems = static_cast<py::ssize_t>(seq_len) * hidden_size;
    check_fp16_contiguous(x_in, "x_in", hidden_elems);
    check_fp16_contiguous(x_out, "x_out", hidden_elems);
    check_fp16_contiguous(attn_norm_w, "attn_norm_w", hidden_size);
    check_fp16_contiguous(ffn_norm_w, "ffn_norm_w", hidden_size);

    const int q_dim = num_heads * head_dim;
    const int kv_dim = num_kv_heads * head_dim;

    const void* h_x_in = x_in.data();
    void* h_x_out = x_out.mutable_data();
    const void* h_attn_norm_w = attn_norm_w.data();
    const void* h_ffn_norm_w = ffn_norm_w.data();

    const void* h_wq = check_weight_buffer(wq, wq_type, q_dim, hidden_size, "wq");
    const void* h_wk = check_weight_buffer(wk, wk_type, kv_dim, hidden_size, "wk");
    const void* h_wv = check_weight_buffer(wv, wv_type, kv_dim, hidden_size, "wv");
    const void* h_wo = check_weight_buffer(wo, wo_type, hidden_size, q_dim, "wo");
    const void* h_wgate = check_weight_buffer(wgate, wgate_type, intermediate_size, hidden_size, "wgate");
    const void* h_wup = check_weight_buffer(wup, wup_type, intermediate_size, hidden_size, "wup");
    const void* h_wdown = check_weight_buffer(wdown, wdown_type, hidden_size, intermediate_size, "wdown");

    py::gil_scoped_release release;
    launch_forward_layer_cached_fp16(
        h_x_in, h_x_out,
        h_attn_norm_w,
        h_wq, wq_type,
        h_wk, wk_type,
        h_wv, wv_type,
        h_wo, wo_type,
        h_ffn_norm_w,
        h_wgate, wgate_type,
        h_wup, wup_type,
        h_wdown, wdown_type,
        layer_idx, seq_len, pos_offset,
        hidden_size, intermediate_size,
        num_heads, num_kv_heads, head_dim,
        rms_norm_eps, rope_freq_base, rope_neox, scale
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
        "matmul_nt",
        &matmul_nt,
        "FP16 native-layout GGUF matrix multiplication C(M,N) = A(M,K) @ B_nt(N,K)^T on AMD GPU (gfx1150)",
        py::arg("A"),
        py::arg("B_nt"),
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
        "dequantize_q8_0",
        &dequantize_q8_0,
        "Dequantize GGUF Q8_0 blocks (34B per 32 weights) to FP16 on AMD GPU (gfx1150)",
        py::arg("q8_buf"),
        py::arg("out_fp16"),
        py::arg("num_elements")
    );
    m.def(
        "matmul_q8_0",
        &matmul_q8_0,
        "Fused FP16 x Q8_0 matrix multiplication C(M,N) = A(M,K) @ B(N,K)^T on AMD GPU (gfx1150)",
        py::arg("A"),
        py::arg("B_q8"),
        py::arg("C"),
        py::arg("M"),
        py::arg("N"),
        py::arg("K")
    );
    m.def(
        "dequantize_q4_k",
        &dequantize_q4_k,
        "Dequantize GGUF Q4_K super-blocks (144B per 256 weights) to FP16 on AMD GPU (gfx1150)",
        py::arg("q4k_buf"),
        py::arg("out_fp16"),
        py::arg("num_elements")
    );
    m.def(
        "matmul_q4_k",
        &matmul_q4_k,
        "Fused FP16 x Q4_K (Q4_K_M / Q4_K_S) matrix multiplication C(M,N) = A(M,K) @ B(N,K)^T on AMD GPU (gfx1150)",
        py::arg("A"),
        py::arg("B_q4k"),
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
        "rmsnorm_residual",
        &rmsnorm_residual,
        "Fused Residual Add + RMSNorm on AMD GPU (gfx1150)",
        py::arg("x"),
        py::arg("residual"),
        py::arg("weight"),
        py::arg("h_out"),
        py::arg("norm_out"),
        py::arg("M"),
        py::arg("K"),
        py::arg("eps") = 1e-5f
    );
    m.def(
        "residual_add",
        &residual_add,
        "FP32-accumulated FP16 residual addition on AMD GPU (gfx1150)",
        py::arg("x"),
        py::arg("residual"),
        py::arg("out"),
        py::arg("num_elements")
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
    m.def(
        "forward_layer_cached",
        &forward_layer_cached,
        "Execute a full transformer layer on-device with GPU-resident KV cache (1 H2D + 1 D2H)",
        py::arg("x_in"),
        py::arg("x_out"),
        py::arg("attn_norm_w"),
        py::arg("wq"), py::arg("wq_type"),
        py::arg("wk"), py::arg("wk_type"),
        py::arg("wv"), py::arg("wv_type"),
        py::arg("wo"), py::arg("wo_type"),
        py::arg("ffn_norm_w"),
        py::arg("wgate"), py::arg("wgate_type"),
        py::arg("wup"), py::arg("wup_type"),
        py::arg("wdown"), py::arg("wdown_type"),
        py::arg("layer_idx"),
        py::arg("seq_len"),
        py::arg("pos_offset"),
        py::arg("hidden_size"),
        py::arg("intermediate_size"),
        py::arg("num_heads"),
        py::arg("num_kv_heads"),
        py::arg("head_dim"),
        py::arg("rms_norm_eps"),
        py::arg("rope_freq_base"),
        py::arg("rope_neox"),
        py::arg("scale")
    );
}
