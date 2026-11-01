#ifndef ATTENTION_H
#define ATTENTION_H

// Host-callable Grouped-Query Attention (GQA) launcher with online softmax.
// Shapes (all row-major FP16):
//   Q:   (q_len, num_heads, head_dim)
//   K:   (kv_len, num_kv_heads, head_dim)
//   V:   (kv_len, num_kv_heads, head_dim)
//   Out: (q_len, num_heads, head_dim)
void launch_gqa_attention_fp16(
    const void* h_Q,
    const void* h_K,
    const void* h_V,
    void* h_Out,
    int q_len,
    int kv_len,
    int num_heads,
    int num_kv_heads,
    int head_dim,
    int start_pos,
    float scale,
    bool causal
);

// Allocate/resize GPU-resident GQA KV cache for all layers:
// Shape per K and V buffer: (num_layers, max_seq_len, num_kv_heads, head_dim) in FP16.
void init_device_kv_cache_fp16(
    int num_layers,
    int max_seq_len,
    int num_kv_heads,
    int head_dim
);

// Free GPU-resident KV cache buffers.
void free_device_kv_cache_fp16();

// Offset-based GPU-resident KV cache update + GQA attention:
// Copies only the new `q_len` K/V rows (`h_K_new`, `h_V_new`) directly into device KV cache
// for `layer_idx` at token offset `start_pos`, then attends over `[0 .. start_pos + q_len)`.
// Eliminates host-side KV cache slicing/copying and O(context_len) H2D transfers per step.
void launch_gqa_attention_cached_fp16(
    const void* h_Q,
    const void* h_K_new,
    const void* h_V_new,
    void* h_Out,
    int layer_idx,
    int q_len,
    int start_pos,
    int num_heads,
    int num_kv_heads,
    int head_dim,
    float scale,
    bool causal
);

// Device-resident variant: copies `d_K_new` and `d_V_new` via D2D (`hipMemcpyDeviceToDevice`)
// into the GPU-resident KV cache pool at `(layer_idx, start_pos)`, then runs GQA attention
// from `d_Q` into `d_Out` without any host-device activation transfers.
void launch_gqa_attention_cached_fp16_device(
    const void* d_Q,
    const void* d_K_new,
    const void* d_V_new,
    void* d_Out,
    int layer_idx,
    int q_len,
    int start_pos,
    int num_heads,
    int num_kv_heads,
    int head_dim,
    float scale,
    bool causal
);

// C++-owned device-resident transformer layer pipeline (Stage 6C-ii / P-1):
// Performs 1 H2D activation copy at layer entry, keeps all intermediate activations
// on-device across RMSNorm, QKV projections, RoPE, D2D KV-cache update, GQA attention,
// output projection, fused residual+RMSNorm, SwiGLU FFN, and final residual add,
// and performs 1 D2H activation copy at layer exit.
void launch_forward_layer_cached_fp16(
    const void* h_x_in,
    void* h_x_out,
    const void* h_attn_norm_w,
    const void* h_wq, int wq_type,
    const void* h_wk, int wk_type,
    const void* h_wv, int wv_type,
    const void* h_wo, int wo_type,
    const void* h_ffn_norm_w,
    const void* h_wgate, int wgate_type,
    const void* h_wup, int wup_type,
    const void* h_wdown, int wdown_type,
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
);

#endif // ATTENTION_H
