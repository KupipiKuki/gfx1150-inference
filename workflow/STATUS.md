# Status board

One row per handoff. The architect/auditor keep it current. A handoff without a
row is invisible.

| ID | Title | State | Owner | Branch | Next action | Blocker | Evidence |
|---|---|---|---|---|---|---|---|
| OT-STRATA-001 | Owner: start Strata on gfx1150 | INTAKE | Auditor | — | auditor: owner decisions 2–5 (packs, timebox) + **DEC-003 family deviation** before HO-002 | owner decisions 2–5; Mixtral/DeepSeek unsupported at pin | `workflow/evidence/HO-STRATA-001/` |
| HO-STRATA-001 | gfx1150 build, support, engine boundary | **REWORK** → re-check | QAQC (`qaqc`) | `wp/strata-001-gfx1150-build` @ `a7f303c` | QAQC re-check of F1–F7 (`RW-HO-STRATA-001-1`); then auditor | QAQC FAIL on AC-4 (family mapping); fixed doc-only | `workflow/evidence/HO-STRATA-001/`, `workflow/reports/qaqc/` |
| RW-HO-STRATA-001-1 | rework: family mapping + tuning-gate citations | REWORK → fixed | Coder | `wp/strata-001-gfx1150-build` @ `a7f303c` | QAQC re-check (F1–F7 only) | — | bundle at `a7f303c` |
| HO-STRATA-002 | Mixtral 8x7B baseline | PROPOSED | Architect | — | after 001 SIGNED; needs OT decision 2 | 001, owner pack choice | — |
| HO-STRATA-003 | Qwen3-30B-A3B baseline | PROPOSED | Architect | — | after 002; needs OT decision 3 | 002, owner pack choice | — |
| HO-STRATA-004 | DeepSeek baseline | PROPOSED | Architect | — | after 003; needs OT decision 4 | 003, owner pack choice | — |
| HO-STRATA-005 | Route 2 vs Route 3 decision | PROPOSED | Architect | — | after 001–004 | 001–004 | — |

Pinned inputs: Strata `baf16363b4403ef0ed4f538f5d5ed11c43fb9535` (DEC-007) at
`/home/kupipi/Documents/git/strata`; profile **gfx1150 / Radeon 890M / Ryzen AI 9
HX 370**, no model loaded in 001. Decisions DEC-007, DEC-008 govern this work.

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
