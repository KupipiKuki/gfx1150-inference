# B vs C — fork Strata vs a thin layer on llama.cpp v1.0.0

**Date:** 2026-11-15
**Sources:** `Strata/docs/HOW_IT_WORKS.md`, `Strata/AGENTS.md`, llama.cpp v1.0.0
release notes (2026-11-13), `docs/NEXT_PROJECT_SEED.md`, `docs/CAPABILITIES.md`.

## What Strata actually implements

From `HOW_IT_WORKS.md`:

- 24,576 experts; each token needs ~10. The GPU holds attention/DeltaNet mixers,
  gated-residual weights, routers, shared experts, the output head, the MTP draft
  layer, the KV cache (from 64K, the most-read part; the rest streams from RAM),
  and an **adaptive expert cache** that learns the hot set.
- RAM holds **all** experts, pinned. The CPU computes the experts the GPU does
  not hold **in place, concurrently with the GPU** (AVX-512/AVX2, ggml
  i-quants). Low-RAM mode keeps only what the GPU does not hold.
- SSD holds a 28.8 GB **n-gram table**, read a few rows per token through the OS
  cache.
- Speculation: the model's **MTP** layer drafts up to 3 tokens; one pass checks
  them; **prompt lookup** drafts up to 5 where measured acceptance pays. The
  draft is verified, so output is unchanged.
- Long context: prefill in up to **8,192-token** pieces; next-layer experts
  stream over PCIe while the current layer's attention runs.
- Same engine on **CUDA and HIP**; the engine is `src/`, `include/`, `metal/`,
  `sycl/`; the app is `apps/`, the server is `serve/`, the Terminal is
  `strata.py`/`strata_cli`/`strata_control/`. MIT; built with parts of
  llama.cpp/ggml (MIT).

## Comparison

| Dimension | B — fork/integrate Strata | C — thin layer on llama.cpp v1.0.0 |
|---|---|---|
| Hard parts | already implemented and measured: routing, expert cache, CPU fallback, MTP/prompt lookup, KV streaming | llama.cpp gives GGUF, backends, model coverage, speculation; the **expert cache and concurrent CPU expert compute must be written** |
| Time to a working MoE engine | days–weeks: install, run, verify the engine boundary, instrument | weeks–months: scheduler, placement, CPU kernels, tests |
| Abstraction fit | engine is a separate `src/`/`include/` from the app/server; can be forked without the product layers | the layer boundary is yours; llama.cpp's partial offload is per-layer, not per-expert |
| Hardware | HIP backend, documented RX 7700/7800/7900 and Strix Halo; AMD maturity still needs checking | ROCm via llama.cpp, mature; no expert-level placement |
| Maintenance | fork drift against 7k+ active commits; keep the engine surface, drop the app/server | track a very active upstream; own only the scheduler code |
| Evidence | "no claim without measurement" culture; easy to carry the current claims ledger/golden rig | same; the ledger/golden rig transfers either way |
| License | MIT + llama.cpp/ggml MIT; keep third_party notices | MIT |
| Differentiator | research/evidence + a specific policy on top of a working engine | a novel scheduler/engine you own end to end |
| Main risk | engine coupling or immature AMD path; model/license availability | rebuilding what Strata already has; performance ceiling |

## Recommendation

**B is the default.** The hard parts are real, measured and MIT-licensed; the
engine is separable from the app and server; the AMD path exists. Fork the
engine, keep the current evidence/claims substrate and golden rig, drop the
product layers you do not need, and add your policy/instrumentation. Verify two
things first: (1) the engine builds and runs from `src/`/`include/` without the
app/server, and (2) `docs/AMD_HIP.md` + community benchmarks support the gfx1100
target.

**C wins only if** the engine is too coupled to the app/server, the AMD path is
immature, or the owner's goal is specifically a novel scheduler and they accept
writing the expert cache, CPU fallback and speculation on llama.cpp's substrate.
llama.cpp v1.0.0 is the right substrate for that, but it is not the engine.

**D** remains the framing: B is the concrete path under D; C is the fallback.

## Cheap tests that settle it

1. **Engine boundary:** build Strata from `src/`/`include/` and run a model
   without `serve/` or `apps/`. Success: it serves or generates directly.
2. **AMD maturity:** read `docs/AMD_HIP.md` and run the documented AMD setup on
   the current Strix Halo APU. Success: a working run and a note on what was
   actually validated.
3. **llama.cpp baseline:** build v1.0.0 with ROCm on a gfx1100 host and run an
   MoE GGUF with partial offload. Success: VRAM/RAM split and tok/s baseline,
   and a list of what it does not do for expert placement.

## Was the v0.2 model unreliable, or did it take a shortcut?

Both, in a specific sense:

- It had **no browsing or tool access**, so it could not research Strata. The
  prompt was its only evidence.
- The prompt said "mark anything you are unsure about as UNKNOWN" and "each risk
  says what must be verified". The model instead asserted "the new scheduler
  fits seamlessly" and "MIT minimizes maintenance costs" — unsupported positive
  claims where the decisive facts were absent.
- That is a **calibration/instruction-following failure**, not a knowledge
  failure: it turned "unknown" into "fine". The scaling-ladder experiments are
  the same shortcut: a template-shaped answer instead of M0 decision
  experiments.

It is reliable for structure and fact extraction; it is not reliable as an
analyst when the decisive evidence is missing. Two cheap tests characterize it:

1. **Unknowns-only:** "List the five facts you do not have that are necessary to
   decide B vs C. Do not recommend." Success: modularity, AMD maturity, fork
   drift, model/license, hardware availability.
2. **Evidence update:** append the `HOW_IT_WORKS.md` facts and ask again.
   Success: the recommendation changes or explicitly cites the new facts;
   failure: it anchors on the earlier answer.

Run both at 300 tokens. If the model can list its unknowns and update on
evidence, the failure is prompting/priority; if not, it is a model limitation.
