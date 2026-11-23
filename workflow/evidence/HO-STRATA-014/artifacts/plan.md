# HO-STRATA-014 AC-10 plan: DeepSeek-MoE-16B forward path

## Shape chosen: (B) dedicated path in the `src/qwen35` mould

The generic engine (`src/core/layer.cpp`, `src/core/session.cpp`) is built around GDN/QSA layers: every attention layer it knows is `qsa_layer`, which requires indexer tensors (`indexer.k_proj.weight`, `indexer.q_proj.weight`, `attn_q_norm.weight`, `attn_k_norm.weight`, etc.) that do not exist in DeepSeek-MoE-16B (`include/strata/core/family_layout.hpp:196-220`). There is no standard MHA/RoPE/dense-FFN path in the generic engine. Extending the generic engine to run DeepSeek would therefore be a **structural engine change** (DEC-021 T1) and would touch the same code path that `qwen4exp` depends on, with high regression risk.

A dedicated `src/deepseek/` engine mirrors the proven `src/qwen35/` precedent: it adds a self-contained GPU engine that `src/program/generate.cpp` switches to for `deepseek`, exactly as `strata` already switches to `strata::qwen35::run` for `qwen35moe`. This isolates the qwen4exp/qwen35moe paths and implements the llama.cpp graph (`artifacts/llama-ref-graph.md`) verbatim.

Because a dedicated engine is thousands of lines and several new files, this shape crosses DEC-021 T2. A deviation request (`DR-HO-STRATA-014-1.md`) is therefore raised before any code is written.

## Files to be touched (Strata checkout)

| Path | Current lines | Role | Estimated inserted lines |
|---|---|---|---|
| `src/deepseek/ds_engine.cu` | new | Main HIP/CUDA engine: session alloc, weight upload, layer loop (MHA + RoPE + dense/MoE FFN + shared experts), KV cache, dump writer | 3,500–4,500 |
| `src/deepseek/ds_kernels.cuh` | new | Decode-kernel declarations / small inline kernels (norm, rope apply, attention, moe combine) | 350–500 |
| `src/deepseek/ds_main.cpp` | new | Stand-alone `strata-deepseek` entry point (mirrors `src/qwen35/q36_main.cpp`, 5 lines) | 5–20 |
| `src/deepseek/dsref.cu` | new | CPU reference executable `strata-deepseek-ref` for parity harness / debugging | 700–900 |
| `include/strata/deepseek/engine.hpp` | new | Public header: `strata::deepseek::run(argc, argv)` declaration | 10–20 |
| `include/strata/deepseek/context_fit.hpp` | new | One-session context-fit check (header-only, mirrors qwen35) | 50–100 |
| `cmake/strata_gpu_engine.cmake` | 817 | Add `strata_deepseek` static lib, `strata-deepseek` executable, `target_link_libraries(strata PRIVATE strata_deepseek)`, `STRATA_HAVE_DEEPSEEK` define | 30–50 |
| `src/program/generate.cpp` | 23,155 | `--parity-run` CLI parsing/gating; family switch to `strata::deepseek::run` when `STRATA_HAVE_DEEPSEEK` is defined; refusal bypass only with `--dump-layers` | 60–100 |
| `tests/core/model_family_test.cpp` | 349 | Unit test: block 0 has no `*_exps` tensors, block 1 does; `--parity-run` without `--dump-layers` is refused | 60–100 |
| `include/strata/core/family_layout.hpp` | 392 | Minor: enforce dense-first-block tensor expectations if needed (likely no-op after S1–S3) | 0–20 |

**Total inserted-line estimate (Strata): 4,765–6,210 lines.**
**New files: 6–7.**

Workflow-repo files (not counted against T2):

| Path | Role |
|---|---|
| `workflow/evidence/HO-STRATA-014/scripts/compare_layers.py` | Stand-alone oracle-vs-engine dump comparator |
| `workflow/evidence/HO-STRATA-014/artifacts/*` | Run artifacts, hashes, patch, manifest |

## Cumulative T2 impact against `baf16363`

Current overlay (S1–S3, HO-STRATA-012): **6 files / +234 / −31** (`git diff --stat baf16363..bac859ef9`).

With shape B S4:
- Modified existing files: `src/program/generate.cpp`, `tests/core/model_family_test.cpp`, `cmake/strata_gpu_engine.cmake`, possibly `include/strata/core/family_layout.hpp` → **3–4 modified files**.
- New files: `src/deepseek/ds_engine.cu`, `ds_kernels.cuh`, `ds_main.cpp`, `dsref.cu`, plus 2–3 `include/strata/deepseek/*.hpp` → **6–7 new files**.
- Cumulative files touched: **9–11** (>5).
- Cumulative insertions: **~234 + 4,800–6,200 ≈ 5,000–6,400** (>300).
- Deletions: negligible.

**Conclusion:** both T2 clauses (files >5, insertions >300) are crossed, and shape A would additionally trigger T1 (structural change to the generic engine). A deviation is required.

## `--parity-run` gating implementation

In `src/program/generate.cpp`:

1. Add `bool parity_run = false` to the options struct; parse `--parity-run` in the CLI loop (near `--dump-layers` at `:3731`).
2. When `--native` is supplied and the family is `DeepseekMoe`:
   - If `!parity_run` → keep the existing named refusal from `model_family_not_supported` (`:4812-4816`).
   - If `parity_run && o.dump_layers.empty()` → usage error: `stderr` message, exit ≠ 0.
   - If `parity_run && !o.dump_layers.empty()` → allow the run to proceed to the family switch.
3. Before the first token, print exactly one stderr line:
   ```text
   strata generate: parity run: architecture 'deepseek' is not supported; this path exists for HO-STRATA-014/015 parity only
   ```
4. `--parity-run` never bypasses `ModelFamily::Unknown`; unknown families still get the existing refusal.
5. `model_family_runs()` (`include/strata/artifact/model_family.hpp:60`) is **not** changed; normal runs without `--parity-run` continue to refuse.

## `--dump-layers` path for a 4-token prompt

The dedicated engine will write the same binary layout the generic engine uses (`generate.cpp:9969-9985`, `src/core/session.cpp:662-666`, `:758-766`):

- Shape per record: `[n_layers + 1][hc][n_embd]` f32.
- For DeepSeek: `hc = 1`, `n_layers = 28`, `n_embd = 2048` → 29 slots × 2048 floats per record.
- Slot 0 = input residual (post-embedding), slot `l+1` = after block `l`.
- CLI: `--parity-run --native <pack> --dump-layers /tmp/opencode/s4-dump.bin --tokens 549,6077,280,7239 --max-new 1 --greedy`
  - 4 prompt positions + 1 generated position = 5 records (`k = 5`).
  - File size: `5 × 29 × 2048 × 4 = 1,187,840` bytes.
  - `compare_layers.py` compares only the first 4 records against the oracle `[4][28][2048]`.

The dedicated engine's layer loop will enqueue a `cudaMemcpyAsync` of `s.R` (or equivalent residual buffer) into a pinned host staging buffer after every block, matching the ordering proven by `src/core/session.cpp:758-766`.

## Risks found

1. **No standard attention path in the generic engine.** `qsa_layer` expects indexer/q_norm/k_norm tensors absent in DeepSeek. Adding MHA to the generic engine is T1.
2. **Dense-first block.** Block 0 has a full-width dense FFN (`n_ff_dense = 10944`) while blocks 1–27 are MoE (`n_ff = 1408`). The engine must branch per layer.
3. **Shared experts always active.** Two shared experts run in parallel with the top-6 routed experts and are added before the residual.
4. **Router normalisation.** The reference does **not** re-normalise weights over the selected top-6 set (`norm_w = false`); it uses the raw softmax probabilities of the selected experts.
5. **RoPE defaults.** Base 1e4, no scaling; the engine must not apply Flash-Next's default scaling.
6. **SwiGLU gating.** Both dense and MoE/shared FFN use parallel SiLU gating (`LLM_FFN_SILU + LLM_FFN_PAR`).
7. **KV cache layout.** MHA 16/16 with head dim 128; no GQA broadcast.
8. **Dedicated-engine size.** Shape B is large and crosses T2, but it is the only Route-2 option that avoids T1 and keeps qwen4exp/qwen35moe isolated.
