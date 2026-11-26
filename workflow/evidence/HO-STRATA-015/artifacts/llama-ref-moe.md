# DeepSeek-MoE-16B MoE block arithmetic — S4b reference

Source tree: llama.cpp `78e05298f0d68abff41d08d79fa7469264b2aff0` (same pin as HO-STRATA-014).
File:line citations are to that tree.

## Router (blocks 1–27)

```text
gate_inp  = ffn_gate_inp.weight  // shape [n_embd, n_expert]
logits    = gate_inp^T @ cur     // shape [n_expert, n_tokens]
probs     = softmax(logits)      // over all 64 experts
top6_idx  = argsort_top_k(probs, 6)        // [6, n_tokens]
top6_w    = probs[top6_idx]                // raw softmax probabilities, no re-normalisation
```

Reference locations:

- `logits = gate_inp @ cur` — `src/llama-graph.cpp:2327`.
- `probs = softmax(logits)` over all experts — `src/llama-graph.cpp:2344-2347`.
- `selected_experts = argsort_top_k(...)` — `src/llama-graph.cpp:2411-2412`.
- `weights = get_rows(probs, selected_experts)` — `src/llama-graph.cpp:2426`.
- `norm_w = false` is passed by DeepSeek, so the re-normalisation block at `src/llama-graph.cpp:2437-2458` is skipped — `src/models/deepseek.cpp:145`.

## Routed experts

For each token and each selected expert `e`:

```text
gate_e = ffn_gate_exps[:, :, e] @ cur   // [n_ff_exp, n_embd] @ [n_embd] -> [n_ff_exp]
up_e   = ffn_up_exps[:, :, e]   @ cur   // [n_ff_exp, n_embd] @ [n_embd] -> [n_ff_exp]
swiglu_e = silu(gate_e) * up_e
out_e    = ffn_down_exps[:, :, e] @ swiglu_e   // [n_embd, n_ff_exp] @ [n_ff_exp] -> [n_embd]
moe_out  = sum_e top6_w[e] * out_e
```

- Same SwiGLU FFN as the dense/shared path — `src/llama-graph.cpp:2499-2584`.
- Expert weight shape convention: `src/models/deepseek.cpp:47-65`.

## Shared experts

Two shared experts are always active and use the same SwiGLU shape as one routed expert:

```text
shexp_out = build_ffn(cur, ffn_gate_shexp, ffn_up_shexp, ffn_down_shexp, ...)
```

- Tensor declarations: `src/models/deepseek.cpp:63-65`.
- Invocation: `src/models/deepseek.cpp:153-160`.

## Placement in the residual

```text
moe_out  = build_moe_ffn(...)
shexp_out = build_ffn(...)
cur = moe_out + shexp_out            // inside the FFN branch
inpL = cur + ffn_inp                  // final residual add
```

- `cur = moe_out + shexp_out` — `src/models/deepseek.cpp:162`.
- `inpL = cur + ffn_inp` — `src/models/deepseek.cpp:166`.
- The shared expert is therefore added **inside** the FFN branch, before the residual add, and is not bypassed.

## Why the gate is teacher-forced (DEC-046)

The free-running trajectory first exceeds 5e-3 at **layer 19, position 1** (rel L2 2.668110e-02). The teacher-forced run for that same cell is **2.372101e-05** rel L2, proving the block arithmetic is correct. The free-running divergence is a router near-tie:

- Oracle top-6: `[25, 2, 3, 22, 5, 40]`
- Engine top-6: `[25, 2, 3, 22, 5, 33]`
- Exact-f32 6th-vs-7th probability margin: **3.36e-6**
- Exact-f32 corresponding logit margin: **7.95e-5**

Because the teacher-forced output matches the reference, the router formula, expert layout, shared-expert placement and FFN arithmetic are correct; the free-running gate was measuring accumulated drift crossing a sharp routing boundary. The gate therefore compares each block in isolation from the reference residual and K/V history, while the free-running profile is reported informationally.
