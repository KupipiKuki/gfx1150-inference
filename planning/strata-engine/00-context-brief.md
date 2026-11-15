# 00 — Context brief: Strata-class engine on mixed AMD hardware

**Status:** planning resource — not an authorization to code. M0 is the decision point.
**Owner:** the project owner. **Planning model:** DeepSeek API (this pack is the context).
**Date:** 2026-11-15.

## 1. Goal

Build a Strata-class engine that runs a large MoE model on consumer AMD
hardware by sharing work across GPU, CPU, RAM and SSD, with an honest evidence
trail. The priority is:

- **gfx1150** — Radeon 890M (current APU host): **primary**; it is the machine
  we run on and what matters.
- **gfx1100** — RX 7900 XTX/XT/GRE: **future**; no card yet; Strata already
  supports it as a maintainer-tested target.
- **gfx900** — Instinct MI25 (Vega 10, 16 GB HBM2): **deferred**; the OCuLink
  adapters and a hardware build are not ready. `06-mi25-feasibility.md` is the
  plan for when they are.
- **gfx1103** — Radeon 780M: **separate project**; full `gfx-inference`
  continuation (dense), not Strata. See `10-project-split.md`.

The starting route is the audit's **Route 2** (modify Strata directly, pinned
patch overlay) for **gfx1150**; the 780M is a separate dense project. The
P0–P9 capability framework is the escalation annex for the day gfx1100/gfx900
enters the critical path. See `07-plan-audit.md`, `08-roadmap-decision.md` and
`10-project-split.md`.

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
- The starting route is **Route 2** (modify Strata directly, pinned patch
  overlay) per `07-plan-audit.md`; a fork or a thin llama.cpp layer is the
  escalation path, not the default.
- The 780M is a separate dense project; the MI25 is deferred. Neither is a
  Strata critical-path target. Support is an **engineering claim**, not a
  marketing claim, until measured.
- The current gfx1150 host has 91.94 GiB RAM and a 45.92 GiB GTT share; it can
  validate the engine before a discrete card exists.

## 4. Success criteria (M0–M2)

1. A device-capability descriptor and runtime probe that report arch, memory
   model (unified/discrete), wave size, dtypes, matrix-core support, ROCm
   version, and supported model families for **gfx1150 now**; gfx1100/gfx900
   are later entries. gfx1103 is out of scope (separate project).
2. A build matrix that compiles the engine for **gfx1150**, with a documented
   ROCm version and driver. gfx1100 is future; gfx900 is deferred; gfx1103 is
   a separate project.
3. A synthetic MoE correctness fixture that runs on the gfx1150 host and
   selects the expected kernel path per capability, with a NumPy reference.
4. No recoding required to add a card: adding a target is a descriptor entry +
   a build target + a validation run, not a new kernel branch.

## 5. Documents in this pack

| File | Purpose |
|---|---|
| `01-hardware-matrix.md` | per-card facts, ROCm/build status, Strata support, risks |
| `02-capability-abstraction.md` | the early-inclusion design: descriptor, probe, dispatch, build matrix, tests |
| `03-phased-plan.md` | P0–P9 (escalation annex), work packages, gates, deliverables, dependencies |
| `04-open-questions.md` | owner decisions the plan cannot make |
| `05-deepseek-prompt.md` | the prompt to turn this pack into the detailed plan |
| `06-mi25-feasibility.md` | the separate 5× MI25 / OCuLink general-LLM test (deferred) |
| `07-plan-audit.md` | the independent audit: Route 2 first, P0–P9 escalation |
| `08-roadmap-decision.md` | the adopted priority and the gfx1150 first action |
| `09-model-strategy.md` | the three gfx1150 test beds and the end targets |
| `10-project-split.md` | Strata (gfx1150) vs the 780M dense continuation |
