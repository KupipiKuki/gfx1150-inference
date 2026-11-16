# Status board

One row per handoff. The architect/auditor keep it current. A handoff without a
row is invisible.

| ID | Title | State | Owner | Branch | Next action | Blocker | Evidence |
|---|---|---|---|---|---|---|---|
| OT-STRATA-001 | Owner: start Strata on gfx1150 | INTAKE (paused) | Auditor | — | auditor: record the owner's answers (DEC-016) and the still-open decisions 2–5 | owner decisions 2–5; DEC-003 beds unimplemented | `workflow/evidence/HO-STRATA-001/` |
| HO-STRATA-001 | gfx1150 build, support, engine boundary | **DONE** (SIGNED 2026-11-16) | Architect | `wp/strata-001-gfx1150-build` @ `76034a0` (bundle) | merge per DEC-015 when the branch is quiet | merge deferred (DEC-015), not a defect | `workflow/evidence/HO-STRATA-001/`, `reports/qaqc/`, `reports/audit/`, `HO-STRATA-001-APPROVAL.md` |
| RW-HO-STRATA-001-1 | rework: family mapping + tuning-gate citations | **CLOSED — PASS** | QAQC | `wp/strata-001-gfx1150-build` @ `76034a0` | none (F1–F7 + N1–N3 closed) | — | bundle at `76034a0` |
| HO-STRATA-002 | Mixtral 8x7B baseline | **BLOCKED** | Architect | — | nothing until the family exists in a runnable build + owner pack decision | family unimplemented at `baf16363`; DEC-003 kept, DEC-016 | — |
| HO-STRATA-003 | Qwen3-30B-A3B baseline | **BLOCKED** | Architect | — | nothing until the family exists (**not** `qwen35moe`) | unimplemented at `baf16363`; DEC-003 kept, DEC-016 | — |
| HO-STRATA-004 | DeepSeek baseline | **BLOCKED** | Architect | — | nothing until the family exists; needs an attention path | unimplemented; Control refuses it | — |
| HO-STRATA-005 | Route 2 vs Route 3 decision | PROPOSED | Architect | — | after at least one measured baseline | no baseline yet | — |
| HO-STRATA-006 | model-support investigation (read-only) | **DEFERRED** (owner hold) | Architect | `wp/strata-006-model-support` @ `750dd2f` | restart only on the owner's go-ahead (DEC-016) | owner hold; OT decisions 2–5 | `workflow/evidence/HO-STRATA-006/` |

**Project state (2026-11-16):** HO-STRATA-001 is DONE and reproducible; every other
handoff is blocked by an owner decision (DEC-016). No technical work is running.

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
