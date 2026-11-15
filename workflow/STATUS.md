# Status board

One row per handoff. The architect/auditor keep it current. A handoff without a
row is invisible.

| ID | Title | State | Owner | Branch | Next action | Blocker | Evidence |
|---|---|---|---|---|---|---|---|
| HO-STRATA-001 | gfx1150 Stage 1 spike | PROPOSED | Architect | `wp/strata-001-gfx1150-spike` | write the handoff (DoR) | model/support check | — |
| HO-STRATA-002 | Mixtral 8x7B baseline | PROPOSED | Architect | — | after 001 | 001 | — |
| HO-STRATA-003 | Qwen3-30B-A3B baseline | PROPOSED | Architect | — | after 001 | 001 | — |
| HO-STRATA-004 | DeepSeek baseline | PROPOSED | Architect | — | after 001 | 001 | — |
| OT-STRATA-001 | Owner: first milestone | INTAKE | Auditor | — | owner decisions | — | — |

## States

`PROPOSED → READY → IN_PROGRESS → CODER_DONE → QAQC_REVIEW → AUDIT_REVIEW →
ARCHITECT_APPROVAL → DONE`

Side: `NEEDS_INFO`, `REWORK`, `BLOCKED`, `DEVIATION`, `DEFERRED`, `CANCELLED`.

## Rules

- Add the row when the handoff becomes `READY`; update it on every transition.
- The **Owner** column is the role accountable for the next action, not the
  author.
- The evidence link points to `workflow/evidence/<ID>/`.
- A blocker names the owner and the expected resolution.
