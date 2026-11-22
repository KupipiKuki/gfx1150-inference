# HO-STRATA-013-QAQC — `check_bundle.py`: independent review

| Field | Value |
|---|---|
| **ID** | HO-STRATA-013-QAQC |
| **Type** | CODER_TO_QAQC |
| **State** | PROPOSED |
| **Created / updated (UTC)** | 2026-11-22 / 2026-11-22 |
| **From → To** | Primary Coder (`coder-primary`) → QAQC (`qaqc`) |
| **Work package** | `check-bundle` |
| **Branch / base commit** | `wp/strata-013-check-bundle` / `5080ef6` |
| **Priority / timebox** | P1 · 1 working day |

## 1. Scope (in)

Independently review HO-STRATA-013 and its evidence bundle:

- Read `workflow/handoffs/HO-STRATA-013.md` and `workflow/evidence/HO-STRATA-013/manifest.md`.
- Re-run the acceptance commands in `workflow/evidence/HO-STRATA-013/commands.log`.
- Verify `workflow/tools/check_bundle.py` is stdlib-only and has no network calls at runtime.
- Verify the eight check codes (B1–B8) are implemented with the semantics in the handoff table.
- Verify `--self-test` demonstrates all seven negative-control fixtures plus the clean PASS.
- Verify `--all` processes every `workflow/evidence/HO-*` directory and reports pre-existing defects in HO-001/007/008/011 without modifying anything.
- Verify the README section includes both commands and the "run before CODER_DONE" rule.
- Write the QAQC report in `workflow/reports/qaqc/HO-STRATA-013-qaqc.md`.

## 2. Out of scope

- Do not modify `workflow/tools/check_bundle.py`, `workflow/README.md`, any evidence bundle, `workflow/DECISIONS.md`, `workflow/STATUS.md`, `.opencode/**`, `.github/**`, the Strata checkout, `build-hip/`, or `build-deepseek/`.
- Do not fix defects the tool finds in other bundles; report only.
- Do not merge or push to `main`.

## 3. Inputs

| Input | Path / hash | Status |
|---|---|---|
| Handoff | `workflow/handoffs/HO-STRATA-013.md` | CODER_DONE |
| CODER_TO_QAQC handoff | `workflow/handoffs/HO-STRATA-013-QAQC.md` | this file |
| Evidence bundle | `workflow/evidence/HO-STRATA-013/` | complete |
| Tool | `workflow/tools/check_bundle.py` | committed at `5080ef6` |
| Reference bundle | `workflow/evidence/HO-STRATA-012/` | positive control |

## 4. Acceptance criteria

| # | Criterion | Command / check | Expected |
|---|---|---|---|
| 1 | AC-1 reproduced | `python3 workflow/tools/check_bundle.py workflow/evidence/HO-STRATA-012` | exit 0, `RESULT: PASS` |
| 2 | AC-2 reproduced | `python3 workflow/tools/check_bundle.py --all` | exit 1 iff pre-existing FAILs present; `DEC-039` WARN skipped |
| 3 | AC-3 reproduced | `python3 workflow/tools/check_bundle.py --self-test` | exit 0; seven fixtures + clean PASS |
| 4 | AC-4 reproduced | `python3 -I workflow/tools/check_bundle.py --self-test` | exit 0 |
| 5 | AC-5 reproduced | `git status --porcelain` before/after AC-1 + AC-2 | no diff |
| 6 | AC-6 reproduced | fresh clone of `wp/strata-013-check-bundle` into `/tmp/cb-fresh-qaqc`; run AC-1 there | exit 0, same verdict |
| 7 | AC-7 reproduced | `grep -n "check_bundle" workflow/README.md` | section present |
| 8 | AC-8 reproduced | run AC-1 twice; `diff` outputs | identical |
| 9 | Tool diff in scope | `git diff 91eac12..HEAD -- workflow/tools/check_bundle.py workflow/README.md workflow/handoffs/HO-STRATA-013.md workflow/evidence/HO-STRATA-013/` | only these files |
| 10 | No secrets | `python3 workflow/tools/check_bundle.py workflow/evidence/HO-STRATA-013` | `PASS B7-secrets` |

## 5. Evidence required

- `workflow/evidence/HO-STRATA-013/manifest.md`
- `workflow/evidence/HO-STRATA-013/commands.log`
- `workflow/evidence/HO-STRATA-013/test-output.txt`
- `workflow/evidence/HO-STRATA-013/hashes.txt`
- `workflow/evidence/HO-STRATA-013/hashes-notes.txt`
- `workflow/evidence/HO-STRATA-013/artifacts/*.txt`

## 6. Guard rails

- Do not edit code, tests, docs, or configuration.
- Do not change acceptance criteria or scope.
- Do not merge or push to `main`.
- No new dependencies.
- No secrets in reports.

## 7. Dependencies / blockers

| Dependency | Owner | Status | Needed by |
|---|---|---|---|
| `git` ≥ 2.x, `python3` ≥ 3.11 | environment | available | start |
| CODER_DONE evidence | Coder | complete | all criteria |

## 8. Definition of Ready

- [x] ID/type/from/to/title/work package present
- [x] Branch and base commit named
- [x] Scope and out-of-scope explicit
- [x] Inputs linked and available
- [x] Every criterion has a command/check
- [x] Evidence requirements runnable
- [x] Guard rails explicit
- [x] Dependencies resolved or owned
- [x] Priority/timebox set
- [x] No open `NEEDS_INFO`

## 9. Definition of Done

- [ ] QAQC report written in `workflow/reports/qaqc/HO-STRATA-013-qaqc.md`
- [ ] Every acceptance criterion re-run independently
- [ ] PASS or FAIL verdict recorded
- [ ] Handoff state transitioned per `ENGINEERING_WORKFLOW.md` §6 (mirrored by architect per DEC-018)

## 10. Signatures

| Role | Name/agent | Date | Decision |
|---|---|---|---|
| Sender (Coder) | `coder-primary` (`opencode-go/kimi-k2.7-code`) | 2026-11-22 | CODER_DONE |
| Receiver (QAQC) | `qaqc` | — | pending acceptance |

## 11. Log

- 2026-11-22 Coder: created `HO-STRATA-013-QAQC` after `CODER_DONE`; evidence bundle complete.
