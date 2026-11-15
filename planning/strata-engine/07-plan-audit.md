# 07 — Plan audit: roadmap review, route analysis, and lean APU plan (`gfx1150` + `gfx1103`)

**Date:** 2026-11-15  
**Scope:** Audit of `planning/strata-engine/` (`00`–`06`), `research/strata-memo/` (`auditor-memo.md`, `b-vs-c.md`), `docs/NEXT_PROJECT_SEED.md`, `docs/CAPABILITIES.md`, `docs/RELEASE_RECORD.md`, `docs/STATUS.md`, `PHASE7_7G_RESIDENCY_AND_FOLLOWUP_PLAN.md` (§0.1), and `IMPLEMENTATION_PLAN.md` (Phase 8).

---

## 1. Review of Current Planning Documents & Roadmap

### What Exists Today
1. **`gfx1150-inference` (Closed at G7-C)** — [`docs/STATUS.md`](../../docs/STATUS.md), [`docs/RELEASE_RECORD.md`](../../docs/RELEASE_RECORD.md), [`docs/CAPABILITIES.md`](../../docs/CAPABILITIES.md)
   - Verified dense-only `mmap` + `madvise` HIP inference engine on `gfx1150` (91.94 GiB RAM / 45.92 GiB GTT). Measured: TinyLlama-1.1B `16.35 tok/s`, Mistral-7B `2.63 tok/s` pinned / `0.42 tok/s` streamed (`0.000 ms` copy/compute overlap in stream mode), 32K `--offload-kv-cpu` at `0.86 tok/s`.
   - [`CMakeLists.txt`](../../CMakeLists.txt#L11) hardcodes `set(CMAKE_HIP_ARCHITECTURES "gfx1150")`. [`IMPLEMENTATION_PLAN.md` Phase 8](../../IMPLEMENTATION_PLAN.md#L276-L310) proposed `gfx1103` portability via `GFX_ARCH`, kernel audit, and dual-GPU validation, but it remained uncommitted/unstarted at project closure.
   - Its strongest assets are **evidence and correctness discipline**: fail-closed GGUF parser, llama.cpp-faithful tokenizer + 310-case differential corpus, memory budgeting (`GTT ∩ MemAvailable ∩ cgroup` for device, `MemAvailable` + disk for offloaded KV), telemetry (`gfx1150-stats/1`), bench gate, and `scripts/qa/check_claims.py --strict` + canaries.

2. **Research Memos** — [`research/strata-memo/auditor-memo.md`](../../research/strata-memo/auditor-memo.md), [`research/strata-memo/b-vs-c.md`](../../research/strata-memo/b-vs-c.md), [`docs/NEXT_PROJECT_SEED.md`](../../docs/NEXT_PROJECT_SEED.md)
   - Evaluated four routes: **A** (extend `gfx1150-inference`), **B** (fork Strata), **C** (thin layer on `llama.cpp v1.0.0`), **D** (hybrid: fork Strata engine, reuse `gfx1150-inference` evidence substrate).
   - Recommended **D with B as the concrete first path** and C as fallback, **explicitly gating M0 on running Strata on the existing APU and inspecting its engine boundary first** (`auditor-memo.md` lines 71–83).

3. **Strata-Engine Planning Pack** — [`planning/strata-engine/`](README.md) (`00`–`06`)
   - Expands into a **10-phase (`P0`–`P9`) + parallel `S0` roadmap** (`03-phased-plan.md`), anchored on **discrete `gfx1100` (RX 7900 XTX/XT/GRE)** as primary target, `gfx1103` as early-inclusion, `gfx1150` as current dev/validation host, and `gfx900` (5× MI25 over OCuLink) as a stretch track.
   - Demands an upfront **P2 capability abstraction** (`devices/*.json`, runtime `strata-device` probe, 7-row dispatch/fallback ladder, build matrix) *before* P3 engine substrate porting or P4+ MoE work.

### Key Diagnosis of the Current Roadmap
- **Scope explosion driven by unowned / incompatible hardware:** The heavy `P0`–`P9` architecture exists largely because the pack tries to unify **four fundamentally different hardware classes** before writing MoE code: discrete `gfx1100` (not yet on hand, where 3-tier VRAM/RAM/SSD residency is physically distinct), unified RDNA3/3.5 APUs (`gfx1103`/`gfx1150`), and legacy `gfx900` (wave64, no WMMA, no bf16, dropped from current ROCm).
- **Over-building what Strata already partially ships:** Per [`01-hardware-matrix.md`](01-hardware-matrix.md), Strata **already has**:
  - **`gfx1103`**: Linux opt-in path (`RADEON_780M.md`, `STRATA_EXPERIMENTAL_GFX1103=1`, `gfx1103-hipblaslt-100401.txt`, iGPU switches `STRATA_IGPU_PROMPT_SET`, `STRATA_PF_FUSED`, `STRATA_HIP_PROMPT_F16`; documented prompt 90→187 tok/s, 277 with WMMA opt-ins, ~16.6 decode).
  - **`gfx1150`**: Builds with `-DCMAKE_HIP_ARCHITECTURES=gfx1150` + `gfx1150-hipblaslt-100401.txt` (community report 15–19 tok/s decode, 125–130 prompt, 1.5–1.7× with table), though setup does not cleanly auto-install and the target is unvalidated.
- **Architectural affinity you can exploit:** `gfx1150` (890M, RDNA3.5) and `gfx1103` (780M, RDNA3) are both **Wave32, WMMA, fp32/fp16/bf16/int8, unified-memory LPDDR5 (~100 GB/s) iGPUs**. Unlike `gfx1100` or `gfx900`, tuning `gfx1150` and enabling `gfx1103` in Strata share almost the exact same execution and memory model.
- **Skipping Experiment #1:** `03-phased-plan.md` designs a custom fork + substrate port (`P2`–`P3`) before validating whether upstream Strata itself simply needs iGPU build/memory/tuning fixes.

---

## 2. Lean Plan: Fine-Tuning `gfx1150` & Adding/Promoting `gfx1103` in Strata

If the immediate goal is **working, fast, reliable MoE inference on `gfx1150` and `gfx1103`** (deferring `gfx1100` and keeping [`06-mi25-feasibility.md`](06-mi25-feasibility.md) completely separate), `P0`–`P9` collapses into a **4-stage, single-developer plan** (weeks, not months):

### Stage 1 — Clean Baseline & Gap Reproduction on `gfx1150` (Effort: S)
*Before writing code, replace community anecdotes with measured truth on the host you own.*
1. **Toolchain & build pin:** Record exact ROCm/HIP/TheRock stack, kernel, `linux-firmware`, and compiler versions on the `gfx1150` host (`rocminfo`, `hipcc --version`).
2. **Stock Strata build & smoke:** Build upstream Strata for `gfx1150` (`-DCMAKE_HIP_ARCHITECTURES=gfx1150`, verify whether `gfx1150-hipblaslt-100401.txt` loads cleanly or silently falls back). Document every setup/install friction point (since `01-hardware-matrix.md` notes setup does not auto-install for `gfx1150`).
3. **Baseline measurements:** Run a small + target MoE model (e.g., Qwen3.6-35B-A3B or Qwen3.8) with and without the tuning table and iGPU flags (`STRATA_IGPU_PROMPT_SET`, `STRATA_PF_FUSED`, `STRATA_HIP_PROMPT_F16`). Record prompt tok/s, decode tok/s, `MemAvailable`, GTT usage, `dmesg`, and whether the tuning table actually matches the local hipBLASLt version.
- **Gate 1:** Reproducible build + clean log + baseline benchmark table on `gfx1150` identifying exact bottlenecks and install failures.

### Stage 2 — Fine-Tune `gfx1150` in Strata (Effort: S–M)
*Fix what makes `gfx1150` "unvalidated" today.*
1. **Installer / CMake / runtime detection:** Make `gfx1150` a recognized installable target in Strata's setup/CMake scripts (matching `gfx1103`'s explicit target wiring rather than manual `-DCMAKE_HIP_ARCHITECTURES` workarounds), and verify hipBLASLt tuning table header/version matching so mismatches warn or fail instead of silently degrading.
2. **Unified-memory (APU) budget & residency tuning:** Apply the lesson from `gfx1150-inference` (7D / 7G-C): on unified memory, GTT share (~45.9 GiB) and `MemAvailable` (~89.5 GiB) behave differently from discrete VRAM. Tune Strata's arena pinning, GTT cap awareness, and CPU/GPU split defaults for Strix Point (`gfx1150`) so it neither over-pins into OOM/GTT exhaustion nor treats unified RAM as slow PCIe discrete copy.
3. **Kernel/switch tuning:** Profile and set sane defaults on `gfx1150` for prompt chunking, fused prefill (`STRATA_PF_FUSED`), FP16 prompt path, and WMMA/hipBLASLt row coverage in `gfx1150-hipblaslt-100401.txt` (re-tune missing shapes if profiling shows fallback to untuned GEMM).
- **Gate 2:** Clean install without manual hacks; verified correctness vs reference/CPU parity; measured improvement over Stage 1 baseline without OOM or silent fallback.

### Stage 3 — Add / Promote `gfx1103` (780M) Capability (Effort: S–M)
*Turn `gfx1103` from an experimental flag (`STRATA_EXPERIMENTAL_GFX1103=1`) into a clean, reproducible APU capability alongside `gfx1150`.*
1. **Shared APU capability profile (lightweight, not full P2):** Factor Strata's `RADEON_780M` / iGPU detection logic so "unified-memory RDNA3/3.5 iGPU" behaviors (shared-pool residency, `STRATA_IGPU_PROMPT_SET`, arena pin defaults) key off **detected unified memory (`integrated` flag) + Wave32/WMMA**, with arch-specific knobs (`cu_count`, tuning table filename) as small per-arch config rather than copy-pasting `if (gfx1103)` into `gfx1150`.
2. **ROCm 7.1+ vs override path:** Validate native `gfx1103` rocBLAS/hipBLASLt on ROCm 7.1+; make any `HSA_OVERRIDE_GFX_VERSION=11.0.0` fallback explicit/logged rather than silent, and verify multi-arch (`gfx1103;gfx1150`) or clean single-arch CMake/setup packaging.
3. **780M-specific tuning & firmware guardrails:**
   - Retune prompt chunk sizes / arena pin limits for smaller CU counts and tighter typical 780M system RAM budgets.
   - Address the documented `gc 11.0.1` MES firmware GPU-reset risk: document minimum `linux-firmware` check in preflight/diagnostics, test `STRATA_ARENA_PIN_GIB=none` vs pinned mode, and surface actionable errors on KFD/reset events.
   - Verify `gfx1103-hipblaslt-100401.txt` load and WMMA opt-in stability.
- **Gate 3:** Both `gfx1150` and `gfx1103` build from the same unified APU path; verified on real `gfx1103` hardware (no `dmesg` GPU resets across sustained runs, separate `gfx1103` measured baseline recorded).

### Stage 4 — Lightweight Evidence Verification & Packaging Decision (Effort: S)
*Preserve honesty without porting 100% of `gfx1150-inference`'s Phase 7 machinery upfront.*
1. **External verification harness:** Use `gfx1150-inference`'s existing benchmark statistics discipline (warm-up, medians/p95) and golden/ledger format as an external validation checklist to record per-card (`gfx1150` vs `gfx1103`) numbers separately.
2. **Upstream vs patchset maintenance:** Package Stages 2–3 as clean, minimal commits/PRs against a pinned Strata commit so upstream rebases take minutes rather than weeks.
- **Gate 4:** Clean patch series or merged upstream PRs; honest per-arch compatibility table (`ROCm version`, `firmware min`, `model`, `tok/s`, `known caveats`).

*(Note: Once `gfx1150` + `gfx1103` are solid in Strata, a future `gfx1100` card already works out of the box in Strata as a maintainer-tested target, and MI25/`gfx900` stays cleanly isolated in [`06-mi25-feasibility.md`](06-mi25-feasibility.md).)*

---

## 3. Comparative Analysis of the Three Routes

| Dimension | Route 1: Current Project (`gfx1150-inference`) Without Strata | Route 2: Modify Strata Directly (Upstream PRs / Thin Patch Overlay) | Route 3: New Fork Adding Functionality of Both (`P0`–`P9` / Hybrid D) |
|---|---|---|---|
| **Core Thesis Match** | **Poor for Strata-class goals.** Dense-only, GPU-only, no expert cache, no CPU compute, no speculation (`CAPABILITIES.md` §7). | **Strongest immediate match.** Strata already has MoE, adaptive expert cache, concurrent CPU compute, speculation, `gfx1103` opt-in, and `gfx1150` build. | **Strong theoretically, heavy in practice.** Gives MoE + evidence discipline, but bundles heavy re-architecture (`P2`–`P3`) before proving the core thesis. |
| **Effort for `gfx1150` + `gfx1103`** | Phase 8 (`gfx1103` portability) is **S–M** for *dense* models, but reaching Strata parity (S1–S5: MoE + grouped GEMM + CPU i-quants + expert cache + speculation + multi-layer C++ loop) is **XL (months)**. | **S–M (days to a few weeks).** Both cards are Wave32 RDNA3/3.5 unified-memory iGPUs that Strata already partially supports; work is build/setup fixes, GTT/memory tuning, and validation. | **L–XL.** Porting `gfx1150-inference`'s Python parser/tokenizer/golden rig/claims checker + building a P2 `devices/*.json` abstraction onto a 7k-commit C++/ggml repo is major integration work. |
| **Maintenance Burden (Solo Owner)** | **Low drift, huge feature debt.** You own 100% of the code, including every future model family, quant format, and MoE kernel. | **Lowest total burden** *if* upstream accepts PRs or patches remain localized to HIP/CMake/iGPU residency. Risk: upstream breaking changes if unpinned. | **Highest maintenance burden.** You carry fork drift against ~7,054 active commits *plus* glue code bridging two different codebases (Python/PyBind11 vs C++/ggml). |
| **Abstraction Fit** | Wrong base for MoE (`NEXT_PROJECT_SEED.md` §2): Python-visible per-layer sync (`0.000 ms` stream overlap in stream mode) and dense FP16 dequant layout must be rewritten. | Native C++/HIP multi-layer execution loop already built for expert caching and CPU/GPU overlap. | Right once complete, but designing `devices/*.json` + full dispatch ladder (`02-capability-abstraction.md`) for 2 nearly identical iGPUs is over-abstraction unless `gfx900`/`gfx1100` are active today. |
| **Evidence & Honesty Rigor** | **Best-in-class**, already proven and automated (`check_claims.py --strict`, 310-case tokenizer corpus, GTT/RAM/cgroup budget refusals). | Weakest natively unless you run an external QA harness / bench gate alongside your Strata branch. | High, *if* the porting cost in P3/P9 is paid without cutting corners. |

---

## 4. Verdict & Escalation Rule

1. **Why `gfx1150-inference` without Strata (Route 1) is NOT the best route — unless scope narrows to dense-only:**
   - As [`PHASE7_7G_RESIDENCY_AND_FOLLOWUP_PLAN.md` §0.1](../../PHASE7_7G_RESIDENCY_AND_FOLLOWUP_PLAN.md#L46-L108) and [`docs/NEXT_PROJECT_SEED.md` §2](../../docs/NEXT_PROJECT_SEED.md#L35-L53) concluded, `gfx1150-inference` is a verified **dense-model** engine. Adding `gfx1103` via Phase 8 yields dense 7B inference on 780M, not MoE, CPU/GPU concurrent compute, or speculation. Rebuilding Strata's mechanisms inside `gfx1150-inference` trades months of solo effort for parity with existing MIT code.
   - *Only choose Route 1 if* the goal is strictly **dense-model** SSD-offloaded research with maximum budget/claims auditability.

2. **Why modifying Strata directly (Route 2) is the best starting route:**
   - For fine-tuning `gfx1150` and solidifying `gfx1103` in Strata, **Route 2 dominates Route 3 on time-to-result and solo maintenance cost**:
     - No greenfield `P2` `devices/*.json` framework is required to unify two Wave32 RDNA3/3.5 unified-memory iGPUs (`gfx1103` and `gfx1150`).
     - No immediate fork-and-strip of `apps/`/`serve/` or Python GGUF/tokenizer re-porting is needed.
     - It directly executes [`auditor-memo.md` Experiment #1](../../research/strata-memo/auditor-memo.md#L69-L75) on real hardware first, while treating `gfx1150-inference` as a closed benchmark/QA methodology reference.

3. **When to escalate Route 2 → Route 3 (combined fork):**
   - Treat **Route 3 as an escalation path**, triggered only if:
     1. Upstream Strata's iGPU/APU memory handling is structurally rigid or upstream rejects/breaks `gfx1150`/`gfx1103` fixes;
     2. Incompatible hardware enters the active critical path (e.g., `gfx1100` discrete VRAM + `gfx900` wave64 MI25 passing [`06-mi25-feasibility.md`](06-mi25-feasibility.md)), making [`02-capability-abstraction.md`](02-capability-abstraction.md) necessary; or
     3. The deliverable becomes an independent, machine-gated research engine (`check_claims.py --strict`, telemetry/budget guarantees) rather than a tuned Strata deployment.

