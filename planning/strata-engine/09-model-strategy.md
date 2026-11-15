# 09 — Model strategy: three test beds on gfx1150

**Date:** 2026-11-15
**Scope:** Strata project, gfx1150 only. The 780M is a separate dense project
(`10-project-split.md`).

## 1. Why three test beds

Strata's design center is Qwen, Mistral and DeepSeek. Testing one small MoE
from each family exercises the model-family code paths and the expert cache
before the large end targets. All three fit the gfx1150's 92 GB RAM at Q4.

## 2. Test matrix

Approximate Q4 sizes; verify from the GGUF metadata before downloading.

| Family | Test model | Total / active | Q4 approx | Notes |
|---|---|---|---|---|
| **Mistral** | **Mixtral 8x7B** | 46.7B / 12.9B | ~26 GB | **architecture-adjacent to the 8x22B end target**; 8-expert top-2 routing; best first test |
| **Qwen** | **Qwen3-30B-A3B** | 30.5B / 3.3B | ~18 GB | modern Qwen MoE; sparse routing; verify Strata support |
| **Qwen (fallback)** | Qwen1.5-MoE-A2.7B | 14.3B / 2.7B | ~8 GB | cheapest Qwen test; older arch; verify support |
| **DeepSeek** | **DeepSeek-V2-Lite** | 15.7B / 2.4B | ~10 GB | **v2-adjacent (MLA + DeepSeek MoE)**; llama.cpp/MLA support must be verified |
| **DeepSeek (fallback)** | **DeepSeek-MoE-16B** | 16.4B / 2.8B | ~10 GB | safe general DeepSeek MoE; older architecture, not v2-adjacent |

## 3. End targets

- **Qwen Next / Qwen3.8-Flash-Next**
- **DeepSeek v2** (V4 Flash as an improvement)
- **Mistral 8x22B**

These are large MoE models; gfx1150 now (92 GB, expert streaming), gfx1100
later. The 780M 32 GB is not an end-target host.

## 4. Recommended order

1. **Mixtral 8x7B Q4_K_M** — first, because it is the closest small
   architecture to 8x22B and Strata's Mistral support is a design center.
2. **Qwen3-30B-A3B Q4_K_M** — second, to exercise the Qwen path at a smaller
   size. Fall back to Qwen1.5-MoE-A2.7B if support is missing.
3. **DeepSeek-V2-Lite** — third, if `strata --families` / the model family
   supports the v2 architecture. Otherwise use **DeepSeek-MoE-16B** as the
   general DeepSeek MoE test.

The order can change if a support check says a model is not loadable; the rule
is **verify support before downloading tens of GB**.

## 5. First check before each download

1. `strata --families` / `docs/MODELS.md`: is the architecture supported by the
   pinned Strata commit?
2. GGUF metadata: architecture, expert count, active experts, context,
   tokenizer/chat template, quant, license.
3. Model hash and pack layout; record them in the run note.

## 6. Honesty notes

- Sizes are approximate. Verify from the model metadata; do not turn them into
  a capacity claim.
- A model that Strata does not support is a **support task**, not a benchmark.
- Expert streaming on a model that does not fit natively is a different regime;
  do not compare its tok/s with a resident run.
- Record one baseline per `(capability_profile, model_family, workload)`; no
  cross-family claim.
- The 780M 32 GB is a separate dense project; do not fold its results into the
  Strata ledger.
