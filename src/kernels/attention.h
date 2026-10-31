#ifndef ATTENTION_H
#define ATTENTION_H

// Host-callable Grouped-Query Attention (GQA) launcher with online softmax.
// Shapes (all row-major FP16):
//   Q:   (q_len, num_heads, head_dim)
//   K:   (kv_len, num_kv_heads, head_dim)
//   V:   (kv_len, num_kv_heads, head_dim)
//   Out: (q_len, num_heads, head_dim)
// Causal masking: query position `m` in [0, q_len) sits at absolute position `start_pos + m`
// and attends to all key positions `s <= start_pos + m` (when causal=true).
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

#endif // ATTENTION_H

