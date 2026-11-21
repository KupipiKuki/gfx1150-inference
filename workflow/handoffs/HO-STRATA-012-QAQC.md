# HO-STRATA-012-QAQC — DeepSeek S1–S3: independent review

| Field | Value |
|---|---|
| **ID** | HO-STRATA-012-QAQC |
| **Type** | CODER_TO_QAQC |
| **State** | PROPOSED |
| **Created / updated (UTC)** | 2026-11-20 |
| **From → To** | Primary Coder (`coder-primary`) → QAQC (`qaqc`) |
| **Work package** | `strata-012-deepseek-s1` |
| **Branch / base commit** | `wp/strata-012-deepseek-s1` / `bac859ef9` (Strata) |
| **Priority / timebox** | P1 · 1 working day |

## 1. Scope (in)

Independently review HO-STRATA-012 (DeepSeek S1–S3) and its evidence bundle:

- Verify the Strata patch (`bac859ef9` vs `baf16363`) is limited to recognition, geometry, layout, `--inspect`, and tests — no forward path, no kernels, no attention/routing.
- Re-run the acceptance commands in `workflow/evidence/HO-STRATA-012/commands.log` and check the outputs against `workflow/evidence/HO-STRATA-012/manifest.md`.
- Confirm `--inspect` inventories the DeepSeek pack with 363 tensors and the §2 geometry.
- Confirm `--native` refuses DeepSeek with the named message and does not mention PLE.
- Confirm `--families` is unchanged.
- Confirm the Qwen regression token IDs match `workflow/evidence/HO-STRATA-007/artifacts/generated-token-ids.txt`.
- Confirm unit tests pass.
- Confirm `build-hip/strata` hash is still `d58ee239…`.
- Confirm the patch applies cleanly with `git apply --check` to a clean `baf16363` tree.

## 2. Out of scope

- Do not modify Strata source, tests, docs, or configuration.
- Do not run DeepSeek forward generation (S4 is not authorized).
- Do not merge or push to `main`.

## 3. Inputs

| Input | Path / hash | Status |
|---|---|---|
| Handoff | `workflow/handoffs/HO-STRATA-012.md` | READY → IN_PROGRESS |
| Evidence bundle | `workflow/evidence/HO-STRATA-012/` | complete |
| Strata branch | `strata-012-deepseek-s1` @ `bac859ef9` | committed locally; push failed (HTTPS credentials) |
| Strata base | `baf16363b4403ef0ed4f538f5d5ed11c43fb9535` | pinned |
| DeepSeek pack | `…/deepseek-moe-16b-base-q4_k_m.gguf` | `f00ecd83…` |
| Qwen pack | `…/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf` | `55983c5a…` |

## 4. Acceptance criteria

| # | Criterion | Command / check | Expected |
|---|---|---|---|
| 1 | Family recognized | `model_family_test` output | deepseek → `DeepseekMoe`, title printed |
| 2 | Named refusal | C6 from `commands.log` | exit 2, named `model_family_not_supported` text, no PLE |
| 3 | `--families` unchanged | C4 | `qwen4exp qwen35moe` |
| 4 | Geometry matches §2 | `inspect-deepseek.txt` vs handoff §2 | all 12 fields equal |
| 5 | 363 tensors | `inspect-deepseek.txt` | `tensors: 363` |
| 6 | Mismatch refused | `inspect-mismatch.txt` | exit 2, names tensor and both shapes |
| 7 | Qwen regression | `qwen-regression.txt` vs HO-007 reference | 32 IDs identical |
| 8 | Signed binary intact | `sha256sum build-hip/strata` | `d58ee239…` |
| 9 | Patch stat | `git diff --stat bac859ef9^..bac859ef9` | 6 files / 234 insertions (DR approved) |
| 10 | Patch applies cleanly | `git apply --check` on clean `baf16363` tree | exit 0 |

## 5. Evidence required

- `workflow/evidence/HO-STRATA-012/manifest.md`
- `workflow/evidence/HO-STRATA-012/commands.log`
- `workflow/evidence/HO-STRATA-012/hashes.txt`
- `workflow/evidence/HO-STRATA-012/hashes-notes.txt`
- `workflow/evidence/HO-STRATA-012/artifacts/*.txt`
- `workflow/evidence/HO-STRATA-012/patches/0001-deepseek-family.patch`

## 6. Guard rails

- Do not edit Strata source, tests, docs, or configuration.
- Do not change acceptance criteria or scope.
- Do not merge or push to `main`.
- No new dependencies.
- No secrets in reports.

## 7. Dependencies / blockers

| Dependency | Owner | Status | Needed by |
|---|---|---|---|
| Strata branch push | Coder / environment | blocked (HTTPS credentials) | optional — review can use local checkout |

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

- [ ] QAQC report written in `workflow/reports/qaqc/HO-STRATA-012-qaqc.md`
- [ ] Every acceptance criterion re-run independently
- [ ] PASS or FAIL verdict recorded
- [ ] Handoff state transitioned per `ENGINEERING_WORKFLOW.md` §6

## 10. Signatures

| Role | Name/agent | Date | Decision |
|---|---|---|---|
| Sender (Coder) | `coder-primary` | 2026-11-20 | CODER_DONE |
| Receiver (QAQC) | `qaqc` | | |

## 11. Log

- 2026-11-20 Coder: created `HO-STRATA-012-QAQC` after `CODER_DONE`; evidence bundle complete.
