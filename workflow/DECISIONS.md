# Decision log

Dated decisions with ID, context, options, decision, consequences and affected
handoffs. Only the architect decides; the auditor reviews. A decision not in
this file did not happen.

## DEC-001 — Split the 780M out of Strata

- **Date:** 2026-11-15
- **Context:** the 780M has 32 GB unified RAM; the Strata end targets need
  gfx1150's 92 GB (or gfx1100 + RAM/SSD). The dense engine and Strata have
  different abstractions and evidence.
- **Options:** keep the 780M in Strata; split it; drop it.
- **Decision:** split. The 780M is a full `gfx-inference` dense continuation
  (Phase 8); Strata is gfx1150-only for now.
- **Consequences:** separate branch/evidence; no Strata 780M claims; the 780M
  may later consume a small Strata model if it fits.
- **Affected:** `00`–`05`, `08`, `09`, `10`; agent scope.

## DEC-002 — Route 2 before Route 3

- **Date:** 2026-11-15
- **Context:** the audit showed the P0–P9 fork framework front-loads work for
  four hardware classes before validating Strata on the hardware we own.
- **Options:** Route 1 (current engine), Route 2 (modify Strata directly),
  Route 3 (fork + P0–P9).
- **Decision:** Route 2, as a pinned patch overlay; upstream PRs optional.
  Route 3 is the escalation annex.
- **Consequences:** gfx1150 Stage 1 spike first; P0–P9 only on an escalation
  trigger.
- **Affected:** `07`, `08`, `03`.

## DEC-003 — Three gfx1150 test beds

- **Date:** 2026-11-15
- **Context:** Strata's design center is Qwen, Mistral and DeepSeek.
- **Options:** one model; one per family; the full end targets.
- **Decision:** one small MoE per family: Mixtral 8x7B, Qwen3-30B-A3B,
  DeepSeek-V2-Lite or DeepSeek-MoE-16B. End targets stay on gfx1150/gfx1100.
- **Consequences:** model-family support work is exercised early; the
  architecture-adjacent test is preferred (8x7B → 8x22B, V2-Lite → v2).
- **Affected:** `09`, `08`.

## DEC-004 — MI25 deferred

- **Date:** 2026-11-15
- **Context:** five MI25 cards owned, but the OCuLink adapters and a hardware
  build are not ready; gfx900 is not in current ROCm.
- **Options:** start the feasibility now; defer; drop.
- **Decision:** defer. `06-mi25-feasibility.md` is the plan for when one card is
  physically usable; it never blocks Strata.
- **Consequences:** no MI25 work in P0–P9; no MI25 claims.
- **Affected:** `06`, `08`, `03` S0.

## DEC-005 — Handoff-contract workflow adopted

- **Date:** 2026-11-15
- **Context:** the previous project had road bumps from implicit scope and
  late evidence.
- **Options:** ad-hoc chat; a formal handoff contract; a full ticketing system.
- **Decision:** adopt this handoff-contract workflow and the OpenCode role
  agents/skills.
- **Consequences:** no handoff, no work; no evidence, no done; the auditor is
  the owner-task intake; the architect is the final approver.
- **Affected:** `workflow/`, `.opencode/agents`, `.opencode/skills`.
