# Status board

One row per handoff. The architect/auditor keep it current. A handoff without a
row is invisible.

| ID | Title | State | Owner | Branch | Next action | Blocker | Evidence |
|---|---|---|---|---|---|---|---|
| OT-STRATA-001 | Owner: start Strata on gfx1150 | INTAKE | Auditor | — | validate the OT; assign HO-001 | owner decisions (packs/commit) | — |
| HO-STRATA-001 | gfx1150 build, support, engine boundary | PROPOSED | Architect | `wp/strata-001-gfx1150-build` | pin the Strata commit; DoR; set READY | pinned commit | — |
| HO-STRATA-002 | Mixtral 8x7B baseline | PROPOSED | Architect | — | after 001 SIGNED | 001 | — |
| HO-STRATA-003 | Qwen3-30B-A3B baseline | PROPOSED | Architect | — | after 002 | 002 | — |
| HO-STRATA-004 | DeepSeek baseline | PROPOSED | Architect | — | after 003 | 003 | — |
| HO-STRATA-005 | Route 2 vs Route 3 decision | PROPOSED | Architect | — | after 001–004 | 001–004 | — |

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
