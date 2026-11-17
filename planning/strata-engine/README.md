# Strata-engine planning pack

Resources for turning the Strata-class decision into a detailed, phased
implementation plan. Written to be uploaded to the DeepSeek API; the prompt is
in `05-deepseek-prompt.md`.

## Priority (2026-11-15)

1. **gfx1150** — primary; the machine we run on, and what matters.
2. **gfx1100** — future; no card yet.
3. **gfx900 (5× MI25)** — **deferred**; adapters and a hardware build are not
   ready. `06-mi25-feasibility.md` is the plan for when they are.
4. **780M (gfx1103)** — **separate project**; full `gfx-inference` continuation
   (dense), not Strata. See `10-project-split.md`.

The starting route is **Route 2** — modify Strata directly, pinned patch
overlay — per `07-plan-audit.md` and `08-roadmap-decision.md`. P0–P9 is the
escalation annex, not the starting plan.

## Read in this order

1. `00-context-brief.md` — goal, non-goals, constraints, success criteria.
2. `01-hardware-matrix.md` — gfx1100, 780M (gfx1103), MI25 (gfx900), gfx1150,
   gfx906 reference; ROCm and Strata support; risks.
3. `02-capability-abstraction.md` — the descriptor/probe/build/dispatch design
   that makes a new card a data change, not a recode.
4. `03-phased-plan.md` — the P0–P9 escalation annex; the primary route is
   `07` §2.
5. `04-open-questions.md` — the owner decisions the planner must ask for.
6. `05-deepseek-prompt.md` — the planning prompt and the red-team pass.
7. `06-mi25-feasibility.md` — the separate 5× MI25 / OCuLink general-LLM
   feasibility test (deferred; not on the Strata critical path).
8. `07-plan-audit.md` — the independent audit: Route 2 first, P0–P9 escalation.
9. `08-roadmap-decision.md` — the adopted priority and the gfx1150 first action.
10. `09-model-strategy.md` — the three gfx1150 test beds and the end targets.
11. `10-project-split.md` — Strata (gfx1150) vs the 780M dense continuation.

## The hardware facts that shape the plan

- **780M (gfx1103) is a separate dense project.** It has 32 GB unified RAM; it
  continues `gfx-inference` (Phase 8, `GFX_ARCH`, 780M validation), not Strata.
  It is not an end-target host. See `10-project-split.md`.
- **MI25 (gfx900) is deferred.** You own five 16 GB MI25 cards (80 GB
  aggregate) for $200, but the OCuLink adapters and a hardware build are not
  ready. `06-mi25-feasibility.md` is the test plan for when they are; it is not
  a Strata task now. The Strata plan is **gfx1150 first**.

## How to use the pack with DeepSeek

1. Upload all eleven files (about 11K words; well within a large context).
2. Paste the prompt from `05-deepseek-prompt.md`.
3. Answer the "decisions needed" list before accepting the plan; the pack marks
   what is UNKNOWN on purpose.
4. Run the red-team prompt as a second pass.
5. Keep the resulting `PLAN.md` in the repo; use OpenCode for the coding
   phases, not for the architecture pass.

## What the pack deliberately does not do

- It does not pick the model or the gfx1100 card; those are owner decisions.
- It does not claim the MI25 works; `06-mi25-feasibility.md` is the gate, and
  the Strata plan treats the MI25 as deferred.
- It does not replace P0; the ADR is still the first gate.
