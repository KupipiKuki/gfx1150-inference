# 09 — Model strategy: test models vs end targets

**Date:** 2026-11-15
**Decision:** test a small MoE that shares architecture with an end target;
keep the large end targets for gfx1150/gfx1100.

## 1. Host roles

| Host | Memory | Role | End targets? |
|---|---|---|---|
| **gfx1150** (890M) | 91.94 GiB RAM / 45.92 GiB GTT | primary: large-MoE test and end-target host | **yes**, with expert streaming |
| **780M** (gfx1103) | **32 GB unified** | small-MoE test + dense continuation of `gfx-inference` | **no**: 32 GB cannot hold the end-target experts |
| gfx1100 (future) | 16–24 GB VRAM + RAM | Strata's design-center host | yes |
| MI25 (deferred) | 5×16 GB HBM2 | general-LLM experiment | no |

The 780M's 32 GB is a hard ceiling: Strata's design pins all experts in RAM.
A 32 GB host can run a **small** MoE with expert streaming/low-RAM mode, but it
cannot be the end-target host. That is not a failure; it is the test bed.

## 2. End targets

Strata's design center:

- **Qwen Next / Qwen3.8-Flash-Next**
- **DeepSeek v2** (V4 Flash would be an improvement)
- **Mistral 8x22B**

These are large MoE models (8x22B is ~141B total / ~39B active; DeepSeek v2 is
~236B total / ~21B active; Qwen Next is server-class). They need the gfx1150's
92 GB RAM (or gfx1100 + RAM/SSD) and the expert cache. Do **not** plan them for
the 780M.

## 3. Test models

Approximate Q4 sizes; verify from the GGUF metadata before downloading.

| Model | Total / active | Q4 approx | gfx1150 | 780M 32 GB | Why |
|---|---|---|---|---|---|
| **Mixtral 8x7B** | 46.7B / 12.9B | ~26 GB | comfortable | tight; low-RAM/SSD only | **same Mixtral family as 8x22B**; routing/expert-cache work transfers |
| **Qwen3-30B-A3B** | 30.5B / 3.3B | ~18 GB | comfortable | comfortable | modern Qwen MoE; sparse routing; verify Strata support |
| **Qwen1.5-MoE-A2.7B** | 14.3B / 2.7B | ~8 GB | very comfortable | very comfortable | cheapest 32 GB test; older arch; verify support |

## 4. Recommendation

- **gfx1150 Stage 1 spike:** **Mixtral 8x7B Q4_K_M** first. It is the closest
  small architecture to the 8x22B end target, so the routing/expert-cache work
  transfers. If Strata's Mixtral support needs a model-family change, fall back
  to **Qwen3-30B-A3B**.
- **780M:** **Qwen3-30B-A3B** (or Qwen1.5-MoE-A2.7B) because 32 GB cannot hold
  Mixtral 8x7B Q4 plus OS, KV and overhead. Use 8x7B only as a low-RAM/SSD
  stress test, and report it as such.
- **End targets:** gfx1150 and gfx1100 only. The 780M is the small-model lab.

## 5. First check before downloading tens of GB

1. `strata --families` / `docs/MODELS.md`: is the architecture supported by the
   pinned Strata commit?
2. The GGUF metadata: architecture, expert count, active experts, context,
   tokenizer/chat template, quant, license.
3. The model hash and pack layout; record them in the run note.

## 6. Honesty notes

- Sizes above are approximate. Verify from the model metadata; do not turn them
  into a capacity claim.
- The 780M is a small-MoE test and dense continuation, not an end-target host.
- Expert streaming on a model that does not fit natively is a different regime;
  do not compare its tok/s with a resident run.
- A model that Strata does not support is a **support task**, not a benchmark.

## 7. What this changes in the plan

- `08-roadmap-decision.md`: the gfx1150 spike model is Mixtral 8x7B, with
  Qwen3-30B-A3B as the fallback; the 780M model is Qwen3-30B-A3B/A2.7B.
- `01-hardware-matrix.md`: the 780M is marked 32 GB and "small-MoE test".
- `04-open-questions.md`: the model question becomes "which test model first",
  not "Qwen3.8 vs 8x22B"; the end targets are gfx1150/gfx1100.
