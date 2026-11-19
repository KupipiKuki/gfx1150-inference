# HO-STRATA-008-QAQC — family probe review

| Field | Value |
|---|---|
| **ID** | HO-STRATA-008-QAQC |
| **Type** | CODER_TO_QAQC |
| **State** | READY |
| **Created / updated (UTC)** | 2026-11-18T04:18:54Z |
| **From → To** | Primary Coder → QAQC |
| **Work package** | strata-008-family-probe |
| **Branch / base commit** | `wp/strata-008-family-probe` / `d9725cfafbcf3d3010cb61a3d8b03802175e2d83` |
| **Priority / timebox** | P1 · 1 working day |

## 1. Scope (in)

- Independently review the evidence bundle for HO-STRATA-008 at
  `workflow/evidence/HO-STRATA-008/`.
- Re-run the acceptance checks the original handoff named:
  - clean Strata checkout (HEAD `baf16363…`, empty `git status --porcelain`);
  - binary SHA256 `d58ee239…`;
  - both GGUF hashes match `workflow/MODELS.md`;
  - both probe commands run exactly as §4;
  - each attempt classified REFUSED / LOADED-UNSUPPORTED / FAILED-OTHER with the
    justifying output line;
  - resource envelope and `dmesg` recorded;
  - no source edits, no flag tuning, no support claims.
- Write `workflow/reports/qaqc/HO-STRATA-008-qaqc.md` with PASS/FAIL and findings.

## 2. Out of scope

- Do not edit source, tests, docs, handoffs, or configuration.
- Do not merge or push to `main`.
- No new model downloads or quant changes.

## 3. Inputs

| Input | Path / hash | Status |
|---|---|---|
| Original handoff | `workflow/handoffs/HO-STRATA-008.md` | CODER_DONE |
| Evidence bundle | `workflow/evidence/HO-STRATA-008/` | ready |
| Model inventory | `workflow/MODELS.md` @ `d9725cfafbcf3d3010cb61a3d8b03802175e2d83` | ready |
| Signed binary | `/home/kupipi/Documents/git/strata/build-hip/strata` `d58ee239…` | ready |

## 4. Acceptance criteria

| # | Criterion | Command / check | Expected |
|---|---|---|---|
| 1 | Evidence bundle complete | `ls workflow/evidence/HO-STRATA-008/` | `manifest.md`, `commands.log`, `test-output.txt`, `hashes.txt`, `hashes-notes.txt`, `artifacts/` |
| 2 | Hashes verify | `sha256sum -c workflow/evidence/HO-STRATA-008/hashes.txt` | all OK |
| 3 | Clean checkout + correct binary | `git -C /home/kupipi/Documents/git/strata status --porcelain && git rev-parse HEAD && sha256sum build-hip/strata` | empty; `baf16363…`; `d58ee239…` |
| 4 | Model hashes match MODELS.md | `sha256sum` on each GGUF | Mixtral `542d2453…`, DeepSeek `f00ecd83…` |
| 5 | Classifications justified | inspect `test-output.txt` and stderr artifacts | one of REFUSED / LOADED-UNSUPPORTED / FAILED-OTHER per attempt, with exact justifying line |
| 6 | No tokens silently generated | inspect stdout/stderr | no `gen:` line unless classification is LOADED-UNSUPPORTED |
| 7 | No out-of-scope work | `git diff` in gfx1150-inference; Strata status | only HO-008 evidence/handoffs; Strata clean |

## 5. Evidence required

- `workflow/reports/qaqc/HO-STRATA-008-qaqc.md` from `templates/QAQC_REPORT.md`.
- Embedded `QAQC_TO_AUDITOR` block per DEC-018.

## 6. Guard rails

- Read-only outside `workflow/reports/qaqc/`.
- Do not modify `HO-STRATA-008.md`; the architect mirrors the QAQC verdict.
- No performance/support/quality claims beyond the evidence.

## 7. Dependencies / blockers

None.

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

- [ ] QAQC report written and committed on the branch
- [ ] Acceptance criteria re-run; raw output recorded
- [ ] Verdict PASS or FAIL with findings
- [ ] No code/docs/tests/config changes
- [ ] No secrets

## 10. Signatures

| Role | Name/agent | Date | Decision |
|---|---|---|---|
| Sender (Coder) | `coder-primary` | 2026-11-18T04:18:54Z | READY |
| Receiver (QAQC) | | | |

## 11. Log

- 2026-11-18T04:18:54Z Coder: created CODER_TO_QAQC after completing
  the evidence bundle and marking HO-STRATA-008 CODER_DONE.
