# 05 — DeepSeek planning prompt

Upload the pack to the DeepSeek API and paste this prompt. The prompt is
deliberately strict about evidence: the model must plan from the supplied
facts, mark unknowns, and not invent ROCm/hardware support.

---

## Prompt

You are a senior systems architect. Expand the attached planning pack into a
detailed, phased implementation plan for a Strata-class MoE inference engine
that starts on **gfx1150** (the current host), then the **780M** (gfx1103). The
starting route is **Route 2** — modify Strata directly with a pinned patch
overlay — per `07-plan-audit.md`; the P0–P9 fork plan is the escalation annex.

### Inputs

- `00-context-brief.md` — goal, non-goals, constraints, success criteria.
- `01-hardware-matrix.md` — gfx1100, gfx1103 (780M), gfx900 (MI25), gfx1150,
  gfx906 reference; ROCm/build support; risks.
- `02-capability-abstraction.md` — descriptor, probe, build matrix, dispatch
  ladder, telemetry, tests.
- `03-phased-plan.md` — the P0–P9 escalation annex (not the starting plan).
- `04-open-questions.md` — the owner decisions you must ask for, not invent.
- `06-mi25-feasibility.md` — the separate 5× MI25 / OCuLink test (**deferred**;
  not on the Strata critical path).
- `07-plan-audit.md` — the independent audit (Route 2 first).
- `08-roadmap-decision.md` — the adopted priority and first action.
- Optional: `auditor-memo.md`, `b-vs-c.md`, and the Strata
  `HOW_IT_WORKS.md` / `AMD_HIP.md` excerpts.

### Task

Produce a plan with these sections, in order:

1. **Assumptions and decisions needed.** List what the pack leaves open; ask
   for the answers. Do not silently assume hardware, model or license.
2. **Architecture.** The gfx1150/gfx1103 **APU profile** (unified memory,
   Wave32, WMMA, iGPU switches), the Strata engine boundary (what can be
   patched without forking), and the evidence harness. The full
   descriptor/dispatch framework is the escalation annex.
3. **Phased plan.** Start from the audit's 4-stage lean plan (`07` §2, `08`):
   gfx1150 baseline/tune, gfx1103 promote, evidence/packaging. For each stage:
   goal, work packages, tasks, deliverables, measurable acceptance criteria,
   dependencies, effort (S/M/L), gate. Then give the P0–P9 escalation annex in
   a separate, clearly-labelled section.
4. **Build and validation matrix.** One row per target (gfx1100, gfx1103,
   gfx900, gfx1150, gfx906 reference): ROCm/LLVM, CMake flags, table, model
   families, smoke test, expected refusal messages.
5. **Risk register.** Likelihood, impact, mitigation, trigger, owner. Include
   the MI25 toolchain, 780M firmware resets, fork drift, model/license,
   hardware availability, and the one-person schedule.
6. **First two weeks.** The smallest ordered experiments that reduce the most
   uncertainty, each with a success criterion and an artifact. The first must
   be doable on the current gfx1150 host or with a borrowed gfx1100.
7. **What would make this plan wrong.** The evidence that would invalidate the
   phase order, the fork choice, or the capability design.
8. **Red-team your own plan.** Find the missing work, the hidden dependency,
   the place where "early capability inclusion" becomes a late port, and the
   claim that has no artifact.
9. **Stretch track (separate).** Plan the MI25 / OCuLink general-LLM
   feasibility test in `06-mi25-feasibility.md` as its own track with its own
   go/no-go. It must not block the starting plan.

### Constraints

- Use only the supplied facts. Mark anything else **UNKNOWN**.
- Do not invent ROCm versions, kernel support, model licenses, or benchmark
  numbers.
- **gfx1150 is primary; the 780M is next; gfx1100 is future; the MI25 is
  deferred.** Do not put gfx1100/MI25 on the critical path.
- Design the APU profile for gfx1150/gfx1103 now; the full descriptor/dispatch
  framework is escalation.
- Evidence discipline: no performance claim without an artifact; one row per
  `(capability_profile, model_family, workload)`; the strict claims gate stays.
- One person, limited hours: prefer the smallest plan that reaches a measured
  gfx1150 result, then the 780M.
- Use tables and short bullets. No filler.

### Output

A single Markdown plan, ready to become the project's `PLAN.md`, plus a short
"decisions needed from the owner" list at the top.

---

## Red-team prompt (second pass)

Take the plan you just produced and attack it:

- Which phase assumes a toolchain or model that the pack marks UNKNOWN?
- Where does the plan still port a card late instead of encoding it in the
  capability descriptor?
- Which acceptance criterion is not measurable?
- Which claim would fail the current project's `check_claims.py --strict`?
- What is the smallest experiment that could kill the plan, and is it in the
  first two weeks?

Return a prioritized list of fixes, not a rewrite.
