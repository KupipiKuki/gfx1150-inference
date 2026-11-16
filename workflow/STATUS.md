# Status board

One row per handoff. The architect/auditor keep it current. A handoff without a
row is invisible.

| ID | Title | State | Owner | Branch | Next action | Blocker | Evidence |
|---|---|---|---|---|---|---|---|
| OT-STRATA-001 | Owner: start Strata on gfx1150 | INTAKE | Auditor | — | auditor: owner decisions 2–5 (packs, timebox) + **DEC-003 family deviation** before HO-002 | owner decisions 2–5; Mixtral/DeepSeek unsupported at pin | `workflow/evidence/HO-STRATA-001/` |
| HO-STRATA-001 | gfx1150 build, support, engine boundary | **DONE** (SIGNED 2026-11-16) | Architect | `wp/strata-001-gfx1150-build` @ `76034a0` (bundle) | merge per DEC-015 when the branch is quiet | merge deferred (DEC-015), not a defect | `workflow/evidence/HO-STRATA-001/`, `reports/qaqc/`, `reports/audit/`, `HO-STRATA-001-APPROVAL.md` |
| RW-HO-STRATA-001-1 | rework: family mapping + tuning-gate citations | **CLOSED — PASS** | QAQC | `wp/strata-001-gfx1150-build` @ `76034a0` | none (F1–F7 + N1–N3 closed) | — | bundle at `76034a0` |
| HO-STRATA-002 | Mixtral 8x7B baseline | **DEFERRED** | Architect | — | after HO-006; family unimplemented at `baf16363` | Mixtral not in `--families` (DEC-010) | — |
| HO-STRATA-003 | Qwen3-30B-A3B baseline | **DEFERRED** | Architect | — | after HO-006; **not** `qwen35moe` (that is Qwen3.6-35B-A3B) | family unimplemented at `baf16363` | — |
| HO-STRATA-004 | DeepSeek baseline | **DEFERRED** | Architect | — | after HO-006; retired family refused by the Control | not implemented; needs attention path | — |
| HO-STRATA-005 | Route 2 vs Route 3 decision | PROPOSED | Architect | — | after HO-006 + the first low-tier test (DEC-010) | support results | — |
| HO-STRATA-006 | model-support investigation (read-only) | **READY** | Coder (`coder-primary`) | `wp/strata-006-model-support` | coder accepts → IN_PROGRESS | — | `workflow/evidence/HO-STRATA-006/` |

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
