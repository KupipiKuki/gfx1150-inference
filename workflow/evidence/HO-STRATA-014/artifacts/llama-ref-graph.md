# DeepSeek-MoE-16B forward semantics — file:line citations

Source: llama.cpp `78e05298f0d68abff41d08d79fa7469264b2aff0` (tag `b12527`), the HO-010 oracle pin.
Architecture enum: `LLM_ARCH_DEEPSEEK` (`src/llama-arch.cpp:87`).
Model class: `llama_model_deepseek` (`src/models/models.h:1215`), graph builder in `src/models/deepseek.cpp`.

All references below are to that tree.

## 1. Geometry / hparams read from metadata

`src/models/deepseek.cpp:3-15` — `load_arch_hparams`:
- `attention.layer_norm_rms_epsilon` → RMSNorm eps (`hparams.f_norm_rms_eps`).
- `leading_dense_block_count` → number of dense FFN leading blocks (`hparams.n_layer_dense_lead`).
- `expert_feed_forward_length` array → expert FFN width (`hparams.n_ff_exp_arr`).
- `expert_shared_count` → shared expert count (`hparams.n_expert_shared`).
- `expert_weights_scale` → optional scalar applied to router weights (`hparams.expert_weights_scale`).

Generic loader (`src/llama-model.cpp:1529-1564`, `1596-1604`, `1614-1636`):
- `expert_count` → `n_expert` = 64.
- `expert_used_count` → `n_expert_used` = 6.
- `attention.head_count` → `n_head` = 16.
- `attention.head_count_kv` → `n_head_kv` = 16.
- `rope.freq_base` → `rope_freq_base_train`, default 10000.0.
- `rope.freq_scale` / scaling type → default no scaling (`rope_freq_scale_train` = 1.0).

## 2. Tensor layout

`src/models/deepseek.cpp:17-68` — `load_arch_tensors`.

Block 0 (dense leading block):
- `attn_norm.weight`, `attn_q.weight`, `attn_k.weight`, `attn_v.weight`, `attn_output.weight`.
- `ffn_norm.weight`.
- `ffn_gate.weight`, `ffn_up.weight`, `ffn_down.weight` (dense SwiGLU).

Blocks 1–27 (MoE blocks):
- Same attention tensors as block 0.
- `ffn_gate_inp.weight` — router, shape `[n_embd, n_expert]`.
- `ffn_gate_exps.weight`, `ffn_up_exps.weight`, `ffn_down_exps.weight` — routed experts, shape `[n_embd, n_ff_exp, n_expert]` / `[n_ff_exp, n_embd, n_expert]`.
- `ffn_gate_shexp.weight`, `ffn_up_shexp.weight`, `ffn_down_shexp.weight` — shared experts, shape `[n_embd, n_ff_exp * n_expert_shared]` / `[n_ff_exp * n_expert_shared, n_embd]`.

Global:
- `token_embd.weight`, `output_norm.weight`, `output.weight` (tied to token_embd if absent).

## 3. Block arithmetic — generic transformer, pre-norm residual

`src/models/deepseek.cpp:74-186` — `graph::graph`.

For every layer `il = 0 … 27`:

```text
inpSA = inpL
cur   = RMSNorm(inpL, attn_norm)          // src/models/deepseek.cpp:100
[Qcur, Kcur, Vcur] = QKV(cur)             // src/models/deepseek.cpp:106-107
cur   = RoPE(Qcur), RoPE(Kcur)            // src/models/deepseek.cpp:109-110
cur   = MHA(cur, Qcur, Kcur, Vcur, wo)    // src/models/deepseek.cpp:116-118
ffn_inp = cur + inpSA                     // src/models/deepseek.cpp:124 (attention residual)
cur   = RMSNorm(ffn_inp, ffn_norm)        // src/models/deepseek.cpp:127
if il < n_layer_dense_lead:
    cur = dense_FFN(cur)                  // src/models/deepseek.cpp:131-135
else:
    moe_out = MoE_FFN(cur)                // src/models/deepseek.cpp:139-150
    shexp_out = shared_FFN(cur)           // src/models/deepseek.cpp:153-160
    cur = moe_out + shexp_out             // src/models/deepseek.cpp:162
inpL = cur + ffn_inp                      // src/models/deepseek.cpp:166 (FFN residual)
```

Tail:
- `cur = RMSNorm(inpL, output_norm)` (`src/models/deepseek.cpp:176-178`).
- `logits = output @ cur` (`src/models/deepseek.cpp:182-184`).

## 4. RMSNorm

`src/llama-graph.cpp:1854-1886` — `build_norm`:
- Type `LLM_NORM_RMS` calls `ggml_rms_norm(ctx0, cur, hparams.f_norm_rms_eps)`.
- No learned bias; only a multiplicative weight if present.
- DeepSeek uses `LLM_NORM_RMS` at every norm site (`src/models/deepseek.cpp:100`, `:127`, `:176`).

## 5. MHA head layout (16/16, no GQA)

`src/models/deepseek.cpp:74-80` asserts `n_embd_head == n_rot` and uses the `n_head` / `n_head_kv` supplied by hparams.

`src/llama-graph.cpp:1890-2015` — `build_qkv`:
- Separate `wq`, `wk`, `wv` path (DeepSeek does not use fused QKV).
- `Qcur` shape: `[head_dim, n_head, n_tokens]`.
- `Kcur` shape: `[head_dim, n_head_kv, n_tokens]`.
- `Vcur` shape: `[head_dim, n_head_kv, n_tokens]`.
- For DeepSeek: `n_head = n_head_kv = 16`, `head_dim = 128`.

`src/llama-graph.cpp:3269-3330` / `:3401-3489` — `build_attn`:
- Stores K/V to KV cache, then calls `build_attn_mha`.
- `build_attn_mha` (`src/llama-graph.cpp:3092-3244`) performs standard MHA:
  - permute to `[head_dim, n_tokens, n_heads, streams]`
  - `KQ = K^T @ Q`
  - `softmax_ext(KQ, mask, kq_scale)`
  - `KQV = V @ KQ`
  - project with `wo`.
- No GQA broadcast because `n_head == n_head_kv`.

## 6. RoPE

`src/llama-graph.cpp:1711-1713` — `build_rope` calls `build_rope_impl`.

`src/llama-graph.cpp:1697-1709` — `build_rope_impl`:
- Calls `ggml_rope_ext(..., rp.freq_base, rp.freq_scale, ...)`.

`src/llama-model.cpp:2920-2948` — `get_rope_params` / `get_rope_freq_base` / `get_rope_freq_scale`:
- `freq_base  = cparams.rope_freq_base` (default from GGUF `rope.freq_base`, else 10000.0).
- `freq_scale = cparams.rope_freq_scale` (default 1.0).
- DeepSeek-MoE-16B has no custom `get_rope_params`, so it uses these defaults: base 1e4, no scaling.

## 7. SwiGLU gating (dense and shared-expert FFN)

`src/llama-graph.cpp:2019-2170` — `build_ffn`:
- DeepSeek calls with `type_op = LLM_FFN_SILU`, `type_gate = LLM_FFN_PAR` (`src/models/deepseek.cpp:135`, `:159`).
- `tmp = up @ cur`.
- `gate = gate @ cur`.
- With `LLM_FFN_SILU + LLM_FFN_PAR`: `ggml_swiglu_split(gate, up)` (`src/llama-graph.cpp:2128`).
- Then `down @ swiglu_out`.

Dense block: `ffn_up`, `ffn_gate`, `ffn_down` (`src/models/deepseek.cpp:44-46`).
Shared expert: `ffn_up_shexp`, `ffn_gate_shexp`, `ffn_down_shexp` (`src/models/deepseek.cpp:63-65`, used at `:153-159`).

## 8. MoE routing (blocks 1–27)

`src/models/deepseek.cpp:138-150` — MoE branch:
- `build_moe_ffn(cur, gate_inp, up_exps, gate_exps, down_exps, nullptr, n_expert=64, n_expert_used=6, LLM_FFN_SILU, norm_w=false, expert_weights_scale, LLAMA_EXPERT_GATING_FUNC_TYPE_SOFTMAX, il)`.

`src/llama-graph.cpp:2244-2584` — `build_moe_ffn`:
1. `logits = gate_inp @ cur` (`:2327`), shape `[n_expert, n_tokens]`.
2. `probs = softmax(logits)` over **all** experts (`:2344-2347`).
3. `selected_experts = argsort_top_k(selection_probs, n_expert_used)` (`:2411-2412`), shape `[6, n_tokens]`.
4. `weights = get_rows(probs, selected_experts)` (`:2426`), the raw softmax probabilities of the selected experts.
5. **No re-normalisation over the selected set**: DeepSeek passes `norm_w = false`, so the `if (norm_w)` block at `:2437-2458` is skipped.
6. Each selected expert runs the same SwiGLU FFN as the dense/shared path (`:2499-2584`), weighted by `weights` and summed.

The reference therefore uses top-6 **softmax-weighted** experts without a separate normalisation step over the selected six.

## 9. Shared-expert placement in the residual

`src/models/deepseek.cpp:152-166`:
- `moe_out = build_moe_ffn(...)` — routed experts.
- `shexp_out = build_ffn(...)` — shared experts (always active).
- `cur = moe_out + shexp_out` (`:162`).
- `cur = cur + ffn_inp` (`:166`) — residual add after FFN.

The shared expert is therefore added **inside the FFN branch**, before the residual add, and is **not** bypassed.

## 10. Output / norm tail

`src/models/deepseek.cpp:174-184`:
- After the layer loop, `cur = inpL` (final residual).
- `cur = build_norm(cur, output_norm, NULL, LLM_NORM_RMS, -1)` — output RMSNorm.
- `cur = build_lora_mm(model.output, cur, model.output_s)` — lm_head (tied to token_embd if `output` absent).

## 11. Summary of implementation-critical semantics

| Area | Semantic | Source |
|---|---|---|
| Block 0 | Dense SwiGLU FFN, width `feed_forward_length` | `src/models/deepseek.cpp:43-46`, `:130-136` |
| Blocks 1–27 | 64 routed experts, top-6, 2 shared experts, width 1408 | `src/models/deepseek.cpp:47-65`, `:138-164` |
| Router | Softmax over all 64 experts; top-6 by probability; **no re-normalisation over selected set** | `src/llama-graph.cpp:2344-2347`, `:2411-2412`, `:2426`, `norm_w=false` at `src/models/deepseek.cpp:145` |
| Shared experts | Always-active parallel SwiGLU, added to routed MoE output before residual | `src/models/deepseek.cpp:152-166` |
| Norm | RMSNorm pre-attention, pre-FFN, output; eps 1e-6 | `src/models/deepseek.cpp:4`, `:100`, `:127`, `:176`, `src/llama-graph.cpp:1862` |
| Attention | MHA 16 heads Q/K/V, head dim 128, no GQA | `src/models/deepseek.cpp:106-118`, `src/llama-graph.cpp:1890-2015` |
| RoPE | Base 1e4, no scaling | `src/llama-model.cpp:1614-1615`, `:2920-2948` |
| FFN activation | SwiGLU (SiLU gate × up, parallel) | `src/llama-graph.cpp:2128` |
| Output | RMSNorm then tied/un-tied lm_head | `src/models/deepseek.cpp:176-184` |
