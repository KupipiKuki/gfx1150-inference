# 05 — DeepSeek planning prompt

Upload the pack to the DeepSeek API and paste this prompt. The prompt is
deliberately strict about evidence: the model must plan from the supplied
facts, mark unknowns, and not invent ROCm/hardware support.

---

## Prompt

You are a senior systems architect. Expand the attached planning pack into a
detailed, phased implementation plan for a Strata-class MoE inference engine on
mixed AMD hardware.

### Inputs

- `00-context-brief.md` — goal, non-goals, constraints, success criteria.
- `01-hardware-matrix.md` — gfx1100, gfx1103 (780M), gfx900 (MI25), gfx1150,
  gfx906 reference; ROCm/build support; risks.
- `02-capability-abstraction.md` — descriptor, probe, build matrix, dispatch
  ladder, telemetry, tests.
- `03-phased-plan.md` — the P0–P9 skeleton to expand.
- `04-open-questions.md` — the owner decisions you must ask for, not invent.
- Optional: `auditor-memo.md`, `b-vs-c.md`, and the Strata
  `HOW_IT_WORKS.md` / `AMD_HIP.md` excerpts.

### Task

Produce a plan with these sections, in order:

1. **Assumptions and decisions needed.** List what the pack leaves open; ask
   for the answers. Do not silently assume hardware, model or license.
2. **Architecture.** The capability descriptor, runtime probe, build matrix
   and dispatch/fallback ladder as concrete components with interfaces. Name
   the files/modules and the data that flows between them.
3. **Phased plan (P0–P9).** For each phase: goal, work packages (IDs), tasks,
   deliverables/artifacts, acceptance criteria (measurable), dependencies,
   effort (S/M/L), and the gate. Expand the skeleton; do not just repeat it.
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

### Constraints

- Use only the supplied facts. Mark anything else **UNKNOWN**.
- Do not invent ROCm versions, kernel support, model licenses, or benchmark
  numbers.
- The 780M and MI25 are **experimental**; the MI25 may descope to CPU-only if
  the gfx900 toolchain fails. Say so explicitly.
- Early capability inclusion is mandatory: the gfx1103/gfx900 descriptors and
  build targets exist before the first MoE kernel, not after.
- Evidence discipline: no performance claim without an artifact; one row per
  `(capability_profile, model_family, workload)`; the strict claims gate stays.
- One person, limited hours: prefer the smallest plan that reaches a measured
  gfx1100 result, then the 780M, then the MI25.
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
