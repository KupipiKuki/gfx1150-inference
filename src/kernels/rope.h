#ifndef ROPE_H
#define ROPE_H

// Identical to hip_runtime.h's typedef so this header stays includable from
// non-HIP C++ translation units. Redundant typedefs are legal C++.
typedef struct ihipStream_t* hipStream_t;

// Host-callable Rotary Positional Embedding (RoPE) launcher compiled by amdclang++.
// Applies RoPE rotation to tensor `x` of shape (seq_len, num_heads, head_dim) in FP16.
// - pos_offset: starting token position index (0 for prefill, >0 for KV-cached decode)
// - freq_base: RoPE theta base (e.g. 10000.0f for Llama-2, 500000.0f for Llama-3)
// - neox_style: if false (GGUF Llama default), pairs adjacent (2*i, 2*i+1);
//               if true (HuggingFace/NeoX style), pairs (i, i + head_dim/2).
void launch_rope_fp16(
    const void* h_in,
    void* h_out,
    int seq_len,
    int num_heads,
    int head_dim,
    int pos_offset,
    float freq_base,
    bool neox_style
);

void launch_rope_fp16_device(
    const void* d_in,
    void* d_out,
    int seq_len,
    int num_heads,
    int head_dim,
    int pos_offset,
    float freq_base,
    bool neox_style,
    hipStream_t stream = 0
);

#endif // ROPE_H

