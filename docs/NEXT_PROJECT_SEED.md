# Next project — seed note: a Strata-class engine (MoE on consumer GPUs)

**Author:** DeepSeek V4.1 Flash (primary auditor)
**Date:** 2026-11-13
**Status:** proposal — the owner decides whether/when to start it. This note
records *what to carry over* from `gfx1150-inference` and *what not to*.
**Related:** [`docs/CAPABILITIES.md`](CAPABILITIES.md) (what the current engine
can do), [`PHASE7_7G_RESIDENCY_AND_FOLLOWUP_PLAN.md`](../PHASE7_7G_RESIDENCY_AND_FOLLOWUP_PLAN.md)
§0.1 (the drift analysis).

---

## 1. Thesis

*Run a model far larger than the card's VRAM by sharing the work across the
whole PC.* Strata's design (https://github.com/Niko1221/Strata) does this with
four mechanisms:

1. **MoE sparsity** — a 100B+ model with only ~3B *active* parameters per token,
   so only a slice of the weights is needed at any moment.
2. **Heterogeneous compute** — the **CPU** computes the experts the GPU does
   not hold, **concurrently** with the GPU, so RAM/SSD latency is hidden.
3. **Adaptive caching** — VRAM holds the *hottest* experts and re-learns that
   set while you chat; RAM holds everything else; SSD holds a large lookup
   table read a few rows per token.
4. **Speculation** — the model's own MTP layer drafts tokens (and n-gram
   "prompt lookup" drafts where measured acceptance pays), verified in one
   forward pass.

Target hardware: **discrete consumer GPUs** (gfx1100 RX 7700/7800/7900 with
8–16 GB VRAM + system RAM), where the three tiers are physically distinct.
That is the key difference from the current project, whose host is an
**unified-memory APU** where "RAM" and "VRAM" are the same pool.

## 2. Why a separate project rather than a mode in this one

| | Current engine | Strata-class engine |
|---|---|---|
| Model class | dense | **MoE** (routing, grouped GEMM, expert cache) |
| Device model | unified memory (RAM == VRAM pool) | **discrete VRAM + separate RAM + SSD** |
| Compute placement | GPU only | **GPU + CPU concurrently** |
| Weight residency | all-or-nothing (pin/stream) | **adaptive per-expert hot set** |
| Python↔device boundary | one sync **per layer** | needs a **multi-layer device-resident loop** |
| Speculation | none | MTP + n-gram |

The last two rows are the deepest ones: the current engine's Python-visible
per-layer boundary (the G2/7E "one sync per layer" contract) is fine for dense
inference but is the wrong abstraction for an expert-cache engine, and the
per-tensor H2D staging pattern is the wrong unit for experts that should stay
resident on the device. Retrofitting those into this codebase would import the
wrong abstractions into a codebase that is currently clean, verified, and
release-ready.

## 3. What to carry over (reuse, do not rewrite)

| Asset | Where | Why it transfers |
|---|---|---|
| Fail-closed GGUF parser (membership validation, 64-bit offsets, fail-fast arch/feature validation) | `src/gguf_parser.py`, `tests/test_gguf_and_q4.py` | MoE GGUFs add expert tensors; the parser's discipline is the point |
| Reference-faithful tokenizer + goldens + differential corpus | `src/tokenizer.py`, `tests/test_goldens_tokenizer.py`, `tests/fixtures/` | needs the same llama.cpp fidelity; the 7F-2 real-GGUF divergence is already caught by it |
| Model-spec validator (per-family shape/failure rules) | `src/model_spec.py`, `tests/test_model_families.py` | MoE needs new spec fields (expert counts, routing type) on this skeleton |
| llama.cpp-verified forward path + the comparison rig | `src/layer.py`, `scripts/qa/real_gguf_golden.py`, `audit/evidence/G6/7F/golden/` | the decisive-margin criterion and the "strict FAIL stays recorded" discipline is the reusable part |
| **Explicit-stream pipeline machinery** | `src/kernels/attention.hip`, `tests/test_stream_topology.py` | copy/compute streams, per-projection `hipEvent` timing, the armed layer guard, alloc-first growth — this *is* the overlap machinery a Strata-style engine needs (ours measures 0.000 ms of overlap today) |
| Residency/eviction policy + its measurement discipline | `src/memory_budget.py`, `src/weight_loader.py`, `audit/evidence/G4/7D/` | an expert cache is the same problem with a smarter policy |
| Telemetry schema | `src/inference.py` (`gfx1150-stats/1`), `docs/CAPABILITIES.md` | extend with expert hit-rate, CPU/GPU split time, cache hit ratio |
| Benchmark harness + regression gate | `scripts/bench/` | same warm-up/median/p95/15%-ratio discipline |
| Claims ledger, checker, canaries, strict gate | `audit/CLAIMS_LEDGER.md`, `scripts/qa/check_claims.py`, `scripts/qa/canary_claims.py` | the single most transferable asset: it is what keeps a "we run 100B models" project honest |
| Gate discipline (one work package per gate, evidence bundle, QAQC + independent audit) | `PHASE7_IMPLEMENTATION_HANDOFF.md`, `audit/*_SIGNOFF_*.md` | keep the ledger + strict gate; consider relaxing the ceremony to one gate per milestone |

## 4. What **not** to carry over

- Dense-only weight layout and **fp16 dequant per tensor** → replace with
  grouped GEMM over resident experts.
- The **GTT-intersected weight budget** → split host-RAM residency from
  device allocation (the bug measured in the current project: a 45.9 GiB device
  share throttles a 89.5 GiB host).
- **GPU-only** compute → the CPU fallback is the core trick, not an extra.
- All-or-nothing residency → adaptive per-expert hot set.
- The **per-layer Python↔device boundary** → the new engine needs a
  device-resident multi-layer loop (a much bigger change; plan it explicitly).
- Any assumption that "the model is small enough to be resident".

## 5. Milestones (each with its own gate)

| M | Milestone | Gate exit |
|---|---|---|
| **M0** | **ADR**: target hardware (a gfx1100 host with 8–16 GB VRAM + RAM) and model class (an MoE GGUF with a known-good reference implementation). No code before this. | ADR + a capacity report on the target host |
| **M1** | Port the substrate: parser, tokenizer, spec validator, golden rig, claims ledger, CI shape | the ported golden rig reproduces the current project's golden verdicts |
| **M2** | **MoE correctness spike** on the available APU: routing + grouped GEMM vs an independent NumPy reference. No speed claims. | synthetic-fixture correctness, the same way `phi3`/`gemma` were done here |
| **M3** | **Expert cache + adaptive residency**: VRAM hot set, RAM pool, SSD table; `mincore`-verified accounting (the deferred 7G-1 design) | measured cache hit ratio and a resident-bytes guarantee under the cap |
| **M4** | **CPU compute fallback** for cold experts (ggml i-quant kernels or an AVX2 path) running concurrently with the GPU | measured CPU/GPU overlap; a cold-expert token's latency is dominated by neither queue |
| **M5** | **Speculation**: n-gram / prompt-lookup drafting first (no model change), then MTP if the model has one | measured acceptance and a token/s gain, with output identical to greedy |
| **M6** | **Long-context KV**: reuse this project's offload/mmap work; fix the CPU/mmap KV budget to be host-RAM/disk-based rather than GTT-based | 32K+ context measured on the target host |
| **M7** | **Evidence & claims from day one**: ledger rows, strict gate, golden rig, bench gate, self-hosted GPU CI, an audit/QAQC pass per milestone | no claim without an artifact; the gate is machine-checked |

## 6. Open questions for the owner

1. **Hardware**: is a gfx1100-class host (8–16 GB VRAM + RAM) available for
   development *and* for CI, or must M0–M2 happen on the APU?
2. **Model**: which MoE GGUF (license, a reference implementation to compare
   against, an MTP head or not)? Without one, M2–M4 can only use synthetic
   fixtures.
3. **Process**: keep the full audit/QAQC ceremony per milestone, or keep only
   the ledger + strict gate + golden rig and relax the rest? Recommendation:
   keep the ledger, the strict gate and the golden rig; one gate per milestone.
4. **Licensing/provenance of the ported code**: this repo is MIT-licensed
   upstream work — confirm the attribution/notice requirements for the new
   repository.

---

*Nothing in this note is an authorization to start M1; M0 is the decision
point.*
