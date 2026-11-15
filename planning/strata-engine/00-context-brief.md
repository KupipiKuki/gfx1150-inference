# 00 — Context brief: Strata-class engine on mixed AMD hardware

**Status:** planning resource — not an authorization to code. M0 is the decision point.
**Owner:** the project owner. **Planning model:** DeepSeek API (this pack is the context).
**Date:** 2026-11-15.

## 1. Goal

Build a Strata-class engine that runs a large MoE model on consumer AMD
hardware by sharing work across GPU, CPU, RAM and SSD, with an honest evidence
trail. The engine must support, from the first architecture decision:

- **gfx1100** — RX 7900 XTX/XT/GRE (24/20/16 GB), the primary discrete target.
- **gfx1103** — Radeon 780M (Phoenix/Hawk Point iGPU, shared memory), an
  early-inclusion target with a special ROCm/build path.
- **gfx900** — Instinct MI25 (Vega 10, 16 GB HBM2), an early-inclusion
  research target that needs a legacy/custom ROCm and a wave64 compat path.
- **gfx1150** — Radeon 890M (current APU host), the development/validation
  host until a gfx1100 machine exists.

The point of early inclusion is to avoid recoding later. The capability layer,
the build matrix, the dispatch/fallback ladder and the evidence hooks must be
designed for all four targets in P1–P2, not bolted on after the gfx1100 path
works.

## 2. Non-goals

- No performance claim without a measured artifact.
- No "runs 100B models" claim; the claim set is per-card, per-model, per-run.
- No Windows support for the 780M or MI25 in the first plan; Linux first.
- No product/app work (desktop app, web UI, installers) in the engine plan.
- No training, fine-tuning, or model conversion beyond what the model packs
  need.

## 3. Constraints

- The owner is one person; maintenance cost is a first-class criterion.
- Evidence discipline: claims ledger, golden rig, bench gate, strict claims
  checker, one gate per milestone.
- The engine is expected to be **Strata-derived** (fork) or a **thin layer on
  llama.cpp v1.0.0**; M0 decides. The capability layer must not assume either.
- The 780M and MI25 are experimental; their support is an **engineering
  claim**, not a marketing claim, until measured.
- The current gfx1150 host has 91.94 GiB RAM and a 45.92 GiB GTT share; it can
  validate the engine before a discrete card exists.

## 4. Success criteria (M0–M2)

1. A device-capability descriptor and runtime probe that report arch, memory
   model (unified/discrete), wave size, dtypes, matrix-core support, ROCm
   version, and supported model families for every target.
2. A build matrix that compiles the engine for gfx1100, gfx1103, gfx900 and
   gfx1150 (the last two via their compat paths), with a documented ROCm
   version and driver per target.
3. A synthetic MoE correctness fixture that runs on the gfx1150 host and
   selects the expected kernel path per capability, with a NumPy reference.
4. No recoding required to add a card: adding a target is a descriptor entry +
   a build target + a validation run, not a new kernel branch.

## 5. Documents in this pack

| File | Purpose |
|---|---|
| `01-hardware-matrix.md` | per-card facts, ROCm/build status, Strata support, risks |
| `02-capability-abstraction.md` | the early-inclusion design: descriptor, probe, dispatch, build matrix, tests |
| `03-phased-plan.md` | P0–P8, work packages, gates, deliverables, dependencies |
| `04-open-questions.md` | owner decisions the plan cannot make |
| `05-deepseek-prompt.md` | the prompt to turn this pack into the detailed plan |
