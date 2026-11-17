# 10 — Project split: Strata (gfx1150) vs gfx-inference continuation (780M)

**Date:** 2026-11-15
**Decision:** two separate projects with separate plans, branches and evidence
trails. The 780M leaves the Strata plan until it is logical to add it back.

> **Update 2026-11-15:** the split is the **current execution boundary**, not a
> permanent architecture. The large-model investigation
> (`12-large-model-support-investigation.md`) evaluates a **hybrid** that may
> join the gfx-inference evidence/dense substrate with the Strata MoE engine.
> No branch merge before HO-007 and an owner decision; the 780M dense
> continuation remains separate for now.

## 1. Strata project

- **Host:** gfx1150 (current APU); gfx1100 future; MI25 deferred.
- **Goal:** MoE inference on the APU, Route 2 (modify Strata directly, pinned
  patch overlay).
- **Test beds (gfx1150, one per family):**
  - **Mistral:** Mixtral 8x7B Q4_K_M (architecture-adjacent to 8x22B).
  - **Qwen:** Qwen3-30B-A3B Q4_K_M (or Qwen1.5-MoE-A2.7B).
  - **DeepSeek:** DeepSeek-V2-Lite (v2-adjacent) or DeepSeek-MoE-16B (safe
    general MoE).
- **End targets:** Qwen Next, DeepSeek v2/V4, Mistral 8x22B — gfx1150 now,
  gfx1100 later.
- **Not in scope:** the 780M (moved), the MI25 (deferred), the P0–P9
  capability framework (escalation annex).

## 2. gfx-inference continuation

- **Host:** 780M (gfx1103, **32 GB unified**), plus the current gfx1150 for
  dense work.
- **Goal:** continue the dense engine. Phase 8 already proposes the `GFX_ARCH`
  build target, kernel portability audit, 780M validation and a separate
  performance baseline.
- **Not in scope:** Strata/MoE; add it only if a small MoE fits and it becomes
  logical.
- **The 32 GB ceiling:** enough for dense 7B and a small MoE test, not for the
  Strata end-target experts. Do not promise end-target MoE on the 780M.

## 3. Why split

1. **Different memory ceilings:** the 780M's 32 GB cannot hold the end-target
   experts; gfx1150 has 92 GB.
2. **Different abstractions:** the dense engine's Python-visible per-layer
   boundary is the wrong base for Strata's C++ MoE/expert-cache loop.
3. **Different evidence:** dense and MoE claims must not share a ledger row
   without a profile tag; separate trails avoid accidental cross-claims.
4. **Different schedules:** the 780M dense port is a small, bounded task; the
   Strata work is a longer research effort.

## 4. Boundary rules

- No shared branch: `research/strata-memo` stays Strata; the dense 780M work
  belongs to the `gfx-inference` repository/plan.
- No shared claims row: every row names `capability_profile` and
  `model_family`; a dense 780M result never stands in for a MoE result.
- The 780M may later become a **consumer** of a small Strata test model; it is
  not a target now.
- The audit's Stage 3 (`gfx1103` promote) is **moved** to the gfx-inference
  continuation; it is not part of Strata's first plan.

## 5. First actions after the split

- **Strata:** gfx1150 Stage 1 spike; run the three test beds one at a time
  (Mixtral first, then Qwen, then DeepSeek), recording a baseline for each.
- **gfx-inference:** the 780M dense port (Phase 8) on its own schedule; it
  does not block the Strata spike.

## 6. What the Strata pack should stop doing

- Stop treating gfx1103 as a Strata critical-path or escalation target.
- Stop planning 32 GB end-target runs; the 780M is a separate small-model lab.
- Keep `06-mi25-feasibility.md` deferred; it is not part of either first
  action.
