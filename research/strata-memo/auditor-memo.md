# Auditor memo — build vs fork for a Strata-class engine

**Date:** 2026-11-15
**Question:** build on the current dense-APU substrate (A), fork Strata (B),
build a thin layer on llama.cpp v1.0.0 (C), or hybrid (D)?
**Recommendation:** **D — hybrid, with B as the concrete first path and C as
the fallback if Strata's engine is not separable.**

## Why

1. **The hard parts already exist in someone else's code.** MoE routing,
   grouped GEMM, expert caching, CPU fallback and speculation are the actual
   cost. Strata is a shipping MIT project with those mechanisms and explicit
   support for RX 7700/7800/7900 (gfx1100) and Ryzen AI Max / Strix Halo. A
   solo owner building all of that from scratch (A) is paying the highest cost
   for the least differentiation.
2. **llama.cpp v1.0.0 is the stable substrate, not the scheduler.** It gives
   `libllama`/`libggml` API/ABI stability, dynamic backends, 150+ model
   architectures, all mainstream speculative decoding and ROCm. It does not
   advertise a first-class per-expert adaptive hot-set cache with concurrent
   CPU/GPU expert compute. That gap is where the owner's work belongs.
3. **The current project's real asset is evidence discipline.** The fail-closed
   GGUF parser, tokenizer goldens, model-spec validator, bench gate, claims
   ledger/checker/canaries and CI shape are what make a "we run 100B models"
   project honest. They transfer; the dense compute path does not.

## Criteria

| Criterion | A (current substrate) | B (fork Strata) | C (thin layer on llama.cpp) | D (hybrid) |
|---|---|---|---|---|
| MoE / expert cache / CPU fallback | absent; must build all | present as a product; verify internals | llama.cpp has MoE + layer offload, not expert-level cache | fork the scheduler, reuse the rest |
| Abstraction fit (device-resident loop, no per-layer Python sync) | wrong: dense, per-layer boundary | likely right; verify `include/strata`/`src` | right if the layer is a C/C++ scheduler | right |
| gfx1100 / ROCm fit | current host is APU only | documented RX 7700/7800/7900 | llama.cpp ROCm backend | same |
| License / maintenance | self-owned, but all work | MIT, 7k commits, active; fork drift is a cost | MIT, very active upstream | MIT + own small layer |
| Evidence/testability | strongest (ledger/goldens) | can carry the ledger over | can carry the ledger over | strongest |
| Time to first result | months | days to weeks | weeks | days to weeks |

## Reuse / rewrite

- **Reuse from the current project:** GGUF parser, tokenizer, model-spec
  validator, golden rig, claims ledger/checker/canaries, bench gate, CI shape.
- **Take from llama.cpp:** ggml backends, GGUF/quantization, model coverage,
  speculation, stable C API.
- **Take from Strata (if B/D):** expert cache, CPU/GPU placement, localhost
  API/app layer if useful.
- **Write new:** the evidence integration for the new engine, the gfx1100
  capacity report, the M0 ADR, and — only if differentiating — the scheduler
  policy itself.

## Risks / unknowns

- **Strata modularity:** is the engine separable from the desktop/terminal app
  and the OpenAI/Anthropic API, or is the fork a full-product fork? Verify in
  `docs/HOW_IT_WORKS.md`, `AGENTS.md`, `include/strata`, `src`.
- **Marketing vs implementation:** does Strata actually implement adaptive
  per-expert VRAM/RAM/SSD caching, or is it layer offload with a model catalog?
  The `research/`, `bench/` and `src` trees must be read.
- **AMD maturity:** the docs claim RX 7700/7800/7900 and Strix Halo; community
  benchmarks and `docs/AMD_HIP.md` must be checked, not assumed.
- **Model choice:** Qwen3.6-35B-A3B (MoE, ~3B active) is the natural target;
  confirm license, GGUF availability and a known-good reference.
- **Hardware:** a gfx1100 host for development **and** CI; otherwise M0-M2
  happen on the APU.
- **Fork drift:** 7k commits and active development mean either track upstream
  or accept divergence; a thin C layer on llama.cpp avoids most of this.
- **Licensing:** Strata and llama.cpp are MIT; keep the third_party notices and
  attribution.

## First three experiments (M0 inputs)

1. **Run Strata on the current Strix Halo APU.** Install the terminal app, run
   the documented MoE model, record memory tiers and what the monitor reports.
   Success: a working run plus a note separating what Strata actually does from
   what the README implies. This is cheap and tests the Strix Halo claim on
   hardware you already have.
2. **Build llama.cpp v1.0.0 with the ROCm backend on a gfx1100 host.** Run a
   MoE GGUF with partial GPU offload; record VRAM/RAM split and tokens/s.
   Success: a baseline and a clear list of what llama.cpp does and does not do
   for expert placement.
3. **Read the Strata engine boundary.** `docs/HOW_IT_WORKS.md`, `AGENTS.md`,
   `include/strata`, `src`, `research/`; answer whether the scheduler/expert
   cache is separable and whether the app/API can be dropped. Success: a
   one-page architecture note with a fork-vs-thin-layer verdict.

## What would flip the recommendation

- **To C** if Strata's engine is tightly coupled to the app/API or its
  scheduler cannot be isolated; a thin layer on llama.cpp is then cleaner.
- **To B-only** if Strata's scheduler is separable, its AMD path is mature, and
  the owner's goal is measurement/research rather than a novel policy.
- **To A** only if the owner's differentiator is a scheduler that cannot be
  expressed on either substrate and the MoE/offload kernels are cheaper to
  write than to integrate. That case is not supported by the facts here.
- **If the gfx1100 host is unavailable:** Strata's Strix Halo support makes B
  more attractive for M0-M2 on the APU.
