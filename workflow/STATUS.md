# Status board

One row per handoff. The architect/auditor keep it current. A handoff without a
row is invisible.

| ID | Title | State | Owner | Branch | Next action | Blocker | Evidence |
|---|---|---|---|---|---|---|---|
| OT-STRATA-001 | Owner: start Strata on gfx1150 | **ACCEPTED (build/support portion)** | Owner | — | HO-007 qwen35moe low-tier; cross-family beds blocked (DEC-016) | cross-family support not implemented | `workflow/evidence/HO-STRATA-001/` |
| HO-STRATA-001 | gfx1150 build, support, engine boundary | **DONE** (SIGNED 2026-11-16) | Architect | `wp/strata-001-gfx1150-build` @ `76034a0` (bundle) | merge per DEC-015 when the branch is quiet | merge deferred (DEC-015), not a defect | `workflow/evidence/HO-STRATA-001/`, `reports/qaqc/`, `reports/audit/`, `HO-STRATA-001-APPROVAL.md` |
| RW-HO-STRATA-001-1 | rework: family mapping + tuning-gate citations | **CLOSED — PASS** | QAQC | `wp/strata-001-gfx1150-build` @ `76034a0` | none (F1–F7 + N1–N3 closed) | — | bundle at `76034a0` |
| HO-STRATA-002 | Mixtral 8x7B baseline | **BLOCKED** | Architect | — | nothing until the family exists in a runnable build + owner pack decision | family unimplemented at `baf16363`; DEC-003 kept, DEC-016 | — |
| HO-STRATA-003 | Qwen3-30B-A3B baseline | **BLOCKED** | Architect | — | nothing until the family exists (**not** `qwen35moe`) | unimplemented at `baf16363`; DEC-003 kept, DEC-016 | — |
| HO-STRATA-004 | DeepSeek baseline | **BLOCKED** | Architect | — | nothing until the family exists; needs an attention path | unimplemented; Control refuses it | — |
| HO-STRATA-005 | Confirm Route 2; define the Route 3 triggers | **DONE (SIGNED 2026-11-17) · MERGED #19** · DEC-021 | Architect | `main` | — | — | `workflow/evidence/HO-STRATA-005/` · `workflow/handoffs/HO-STRATA-005-APPROVAL.md` |
| HO-STRATA-008 | family probe: engine behaviour on unsupported GGUFs (Mixtral, DeepSeek) | **DONE (SIGNED 2026-11-18) · MERGED #20** · DEC-026 | Architect | `main` | owner decides whether to open HO-006 with the sharpened question (DEC-016 hold) | — | `workflow/evidence/HO-STRATA-008/` · `workflow/handoffs/HO-STRATA-008-APPROVAL.md` |
| HO-STRATA-006 | model-support investigation (read-only) | **DEFERRED** (owner hold) | Architect | `wp/strata-006-model-support` @ `750dd2f` | restart only on the owner's go-ahead (DEC-016) | owner hold; OT decisions 2–5 | `workflow/evidence/HO-STRATA-006/` |
| HO-STRATA-007 | qwen35moe low-tier baseline (Qwen3.6-35B-A3B) | **DONE (SIGNED 2026-11-16) · MERGED #15** | Architect | `main` @ `a18f12f` | HO-005 route decision | — | `workflow/evidence/HO-STRATA-007/` · `workflow/reports/qaqc/HO-STRATA-007-qaqc.md` · `workflow/reports/audit/HO-STRATA-007-audit.md` · `workflow/handoffs/HO-STRATA-007-APPROVAL.md` |
| HO-STRATA-012 | DeepSeek S1–S3: recognition, geometry, tensor inventory | **DONE (SIGNED 2026-11-20) · MERGE IN PR** · DEC-037 | Architect | `merge/ho-012-2026-11-22` @ `381b148` (merge of `wp/strata-012-deepseek-s1` @ `135989a`) | merge the PR (branch-protected `main`); S4 (forward) needs a separate authorization | — | `workflow/evidence/HO-STRATA-012/` · `workflow/handoffs/HO-STRATA-012-APPROVAL.md` |
| — | family-support test plan (planning 13) | **PREPARED (execution held, DEC-027) · MERGED #21** | Architect | `main` | owner decides: S0 only / Mixtral S0–S7 / keep hold | DEC-016 | `planning/strata-engine/13-family-support-test-plan.md` |
| HO-STRATA-010 | reference oracle + parity harness (S0) | **DONE (SIGNED 2026-11-19) · MERGED #22** · DEC-030 | Architect | `main` | — | B-1/B-2/B-4 carried to S1 | `workflow/evidence/HO-STRATA-010/` · `workflow/handoffs/HO-STRATA-010-APPROVAL.md` |
| HO-STRATA-011 | OLMoE oracle extension (S0b) | **DONE (SIGNED 2026-11-19) · MERGED #23** · DEC-032 | Architect | `main` | — | — | `workflow/evidence/HO-STRATA-011/` · `workflow/handoffs/HO-STRATA-011-APPROVAL.md` |

**Project state (2026-11-22):** the signed baseline stands — `qwen35moe` loads
and generates 32 deterministic tokens on gfx1150 (#15). DeepSeek S1–S3
(recognition, geometry, `--inspect`, named refusal) is **DONE, SIGNED and merged
locally** (DEC-037); the model still does **not** run, and **S4 (the forward
pass) is not authorized**. The oracle chain S0/S0b is merged (#22, #23). HO-002/003/004
remain BLOCKED by DEC-016; HO-006 is DEFERRED. QAQC is back on Gemini Argon
(DEC-039; DEC-036 expired). The live llama.cpp reference server on `:9931` was
**not running** at the 2026-11-22 resume — S4 iteration needs either that server
or the CLI oracle rebuilt from `HO-STRATA-010` §4.

Pinned inputs: Strata `baf16363b4403ef0ed4f538f5d5ed11c43fb9535` (DEC-007) at
`/home/kupipi/Documents/git/strata`; profile **gfx1150 / Radeon 890M / Ryzen AI 9
HX 370**, no model loaded in 001. Key decisions: DEC-007 (pin), DEC-008 (two checkouts), DEC-009 (auditor waiver), DEC-016 (owner hold on cross-family beds), DEC-017 (qwen35moe test).

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
