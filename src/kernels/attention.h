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

#endif // ATTENTION_H
