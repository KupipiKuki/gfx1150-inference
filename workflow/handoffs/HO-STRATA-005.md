# HO-STRATA-005 — Route 2 vs Route 3 decision (evidence-backed)

| Field | Value |
|---|---|
| **ID** | HO-STRATA-005 |
| **Type** | ARCHITECT_TO_CODER (decision document; the architect decides, the coder assembles the evidence pack) |
| **State** | **PROPOSED** — DoR **not** met; do not start |
| **Created / updated (UTC)** | 2026-11-16 |
| **From → To** | Architect → Primary Coder (evidence pack), Architect (decision) |
| **Work package** | `strata-005-route-decision` (not yet branched) |
| **Branch / base commit** | `wp/strata-005-route-decision` — **not created** (created when the DoR can be met) |
| **Priority / timebox** | P1 · 1 day, after HO-STRATA-006 and the first low-tier test |

## 1. Scope (in)

A one-page recommendation, `DECISIONS.md`-ready, choosing between:

- **Route 2** — modify Strata directly as a pinned patch overlay (the current
  decision, DEC-002), bounded to the patch set the evidence justifies;
- **Route 3** — the fork with the P0–P9 capability framework (the escalation
  annex).

The document must carry: what actually blocked gfx1150 (from HO-001), what the
family support costs (from HO-006), what the first low-tier run measured, and
the operational cost of carrying a patch overlay (rebase cadence against the
Strata pin, conflict surface, who owns it).

## 2. Out of scope

- Starting the Route 3 framework, or any fork work, before the decision.
- New measurements: the document consumes HO-001/006 and the first low-tier
  results; it does not produce evidence of its own.
- 780M / MI25 / gfx1100 / gfx1151 / gfx1201.
- Any performance claim beyond what those handoffs measured on this profile.

## 3. Inputs (none available yet — this is why the handoff is not READY)

| Input | Path | Status |
|---|---|---|
| HO-STRATA-001 evidence + approval | `workflow/evidence/HO-STRATA-001/`, `HO-STRATA-001-APPROVAL.md` | **available** |
| HO-STRATA-006 support matrix | `workflow/evidence/HO-STRATA-006/` | **missing — blocked** |
| First low-tier run (one class) | a later handoff, per DEC-010 §1 step 3–4 | **missing — blocked** |
| DEC-002, DEC-010 | `workflow/DECISIONS.md` | available |

## 4. Acceptance criteria (draft — finalised when the DoR is met)

| # | Criterion | Command / check | Expected |
|---|---|---|---|
| 1 | Three options costed | document review | Route 1 (status quo), Route 2 (pinned overlay), Route 3 (fork + P0–P9), each with effort, risk, and maintenance cost |
| 2 | Each claim cites a handoff | `grep` of the citations | every factual sentence points to an HO ID + evidence file |
| 3 | Recommendation + reversal cost | document review | one recommendation, the condition that would reverse it, and what is lost if it is wrong |
| 4 | Recorded | `DECISIONS.md` | a decision entry with context/options/decision/consequences |

## 5. Evidence required

When it starts: `workflow/evidence/HO-STRATA-005/` with the decision document,
the citation map, and the hashes of the inputs it consumed. No new measurements.

## 6. Guard rails

- No code, no fork, no patch until the decision is recorded.
- No silent scope expansion from "decide" to "implement".
- No claims beyond HO-001/006 and the low-tier results.

## 7. Dependencies / blockers

| Dependency | Owner | Status | Needed by |
|---|---|---|---|
| HO-STRATA-006 (support matrix) | Architect/Coder | **open** | DoR |
| First low-tier run | Architect | **open** | DoR |
| Owner decision on DEC-010 (support-first vs descope) | Owner via Auditor | **open** | DoR |

## 8. Definition of Ready — **NOT MET**

- [x] ID/type/from/to/title/work package present
- [ ] Branch and base commit named — **no**, deliberately: the branch is created only when the inputs exist
- [x] Scope and out-of-scope explicit
- [ ] Inputs linked and available — **no** (HO-006 and the low-tier run are missing)
- [ ] Every criterion has a command/check — draft only
- [ ] Evidence requirements runnable — draft only
- [x] Guard rails explicit
- [x] Dependencies named with an owner
- [x] Priority/timebox set
- [x] No open `NEEDS_INFO`

## 9. Definition of Done (draft)

- [ ] Options costed and cited
- [ ] Recommendation with reversal cost
- [ ] Recorded in `DECISIONS.md`
- [ ] Handoff `DONE` after architect sign-off

## 10. Signatures

| Role | Name/agent | Date | Decision |
|---|---|---|---|
| Sender (Architect) | architect | 2026-11-16 | PROPOSED — not ready |
| Receiver (Primary Coder) | — | — | not started |

## 11. Log

- 2026-11-16 Architect: created as `PROPOSED` to keep the owner's planned
  sequence visible. It is deliberately **not** `READY`: writing it now would
  mean inventing the inputs. DEC-010 moved the sequence to
  HO-006 → implement the first family → low-tier tests → this decision.
