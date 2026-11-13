# Primary Auditor Concurrence — 7A-3 Follow-up (C-7A3-1)

**Auditor:** DeepSeek V4.1 Flash (primary auditor)
**Date:** 2026-11-04
**Target:** `wp/7A-3-followup` @ `2fd596c` (work commit `ec72104`)
**Base:** `9b042e8` (7A-3 audit commit; 7A-3 work `2c59c5e`)
**Preliminary audit reviewed:** `audit/AUDIT_7A-3_FOLLOWUP_DEEP_2026-11-04.md`
**Verdict:** **PASS — C-7A3-1 is closed; 7A-3 is accepted. G1 remains unsigned pending 7A-4 and the merges.**

---

## 1. What I verified

| Check | Result |
|---|---|
| SentencePiece golden | **11 cases**: plain text with/without BOS, double space, `café`, `Ω`, emoji (byte fallback), punctuation/digits, two contractions, control token literal/parsed |
| CPU lane | **100 passed / 24 deselected / 4 xfailed** |
| GPU lane | **24 passed** |
| `--runxfail` | exactly 4 expected failures: 2 GPT-2 7B bugs + `spm_contraction_dont` + `spm_control_token_parsed` |
| Provenance verifier | **137/137** |
| Sdist | updated golden with all 11 cases; fixtures ship |
| CI run `41754490013` (head `ec72104`) | API: **completed / success** |
| Scope | only the four allowed files + evidence/brief; no `src/`, CMake, packaging, CI, ledger, baseline |
| Unchanged fixtures | GPT-2 golden/vocab, SPM vocab, quant blocks, `tiny_gguf.gguf`, expectations JSON — byte-identical |
| Lane count/labels | no new module; `EXPECTED_LANES` unchanged |

The two SPM mismatches are correctly pinned as `xfail(strict=True)` with the 7B/7C
reasons; the score arithmetic (−384 vs −632, delta 248) supports the reference
segmentation. The coverage test now asserts the SentencePiece family as well as GPT-2.

## 2. Gate wording

I concur with the preliminary audit’s correction: **7A-3 is signed off, but G1 is not
signed.** The remaining G1 item is **7A-4 (deterministic hypothesis fuzz)**, and the
completed 7A branches still need to be merged into the Phase 7 integration branch
(PR #8). **7B remains blocked** until G1 is signed.

## 3. Observation (not a condition)

`MANIFEST.in` uses `recursive-include tests/fixtures *`. On a working tree where the
generator has been run, this can include `tests/fixtures/__pycache__/*.pyc` in the sdist.
A clean clone and the CI sdist job do not contain that directory, so this does not
affect the current acceptance; the recorded sdist contains the intended fixtures only.
For determinism, a later packaging edit should add
`global-exclude __pycache__ *.py[cod]` (or use explicit fixture globs). This is a
non-blocking hygiene note, not a 7A-3 condition.

## 4. Sign-off

**7A-3 follow-up decision: PASS.** C-7A3-1 is closed; the 7A-3 goldens (GPT-2, SPM,
quant, GGUF) are accepted. Merge approved. G1 remains unsigned pending 7A-4; 7B stays
blocked.

**Sign-off:** DeepSeek V4.1 Flash, 2026-11-04.
