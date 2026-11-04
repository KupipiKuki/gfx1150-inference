# QAQC Report — Work package 7A-3 follow-up (SentencePiece golden coverage, C-7A3-1)

**Role:** QAQC (independent session, per handoff §1 and `PHASE7_7A-3_FOLLOWUP_BRIEF.md`)
**Date:** 2026-11-04
**Tree tested:** tip `8378499` on `wp/7A-3-followup` (parent `9b042e8`; prep/work/record
commits `c66728c`, `ec72104`, `8378499`). CI verified against the **public GitHub API**:
run 41754490013, head branch `wp/7A-3-followup`, head `ec72104`, status `completed`,
conclusion `success`.
**Probes:** `probe-commands.log` (this directory).

---

## Verdict

**PASS.** All claims in the coder's report reproduce. The 7A-3 goldens are verified and
acceptable: the coverage gap the audit flagged (C-7A3-1) is closed, the mismatches are
pinned rather than hidden, and the accepted GPT-2 golden was correctly left untouched.
7A-3 can be closed; 7B remains blocked as stated (G1 unsigned until the remaining 7A
packages land).

## 1. Scope

The three follow-up commits touch exactly the four allowed files
(`tests/fixtures/stories260k_tokenizer_golden.json`, `tests/fixtures/PROVENANCE.md`,
`tests/fixtures/make_fixtures.py`, `tests/test_goldens_tokenizer.py`) plus the brief and
the `audit/evidence/G1/7A-3-followup/` bundle — `git diff --name-only 9b042e8..8378499`
reproduced. The GPT-2 golden/vocab, the SentencePiece vocab, all quant blocks,
`tiny_gguf.gguf`, and the expectations JSON show an **empty diff vs the parent** —
byte-identical, as claimed. No new test module, so `EXPECTED_LANES` is untouched.

## 2. The golden

11 SentencePiece cases with the exact advertised coverage: BOS on/off/absent, double
space, `café`, `Ω`, emoji (byte fallback exercised), punctuation+digits, the two
contractions, and the control token both literal and parsed. Case names and reference
vectors re-read from the committed JSON match `notes.md`'s table.

## 3. Score arithmetic for the pinned mismatches

Independently recomputed from the GGUF itself. Parsing `tiny_gguf.gguf`'s tokenizer
metadata directly:

```
reference (llama.cpp)  ▁d(-20) + on(-30) + '(-180) + t(-154) = -384
greedy (repository)    ▁do(-141) + n(-157) + '(-180) + t(-154) = -632
```

— delta exactly **248**. The reference segmentation is correct per the vocabulary's own
scores, so pinning `spm_contraction_dont` and `spm_control_token_parsed` as
`xfail(strict=True)` with reasons referencing 7B/7C is the right call, not an omission.

## 4. Tests (reproduced locally; sandbox lacks pybind11/ROCm, hence 2 environment-only skips)

- CPU lane: **98 passed + 2 env-skips, 24 deselected, 4 xfailed** — consistent with the
  recorded 100/24/4.
- `--runxfail`: exactly the 4 known mismatches fail, each for the documented reason.
- `test_cpu_only.py`: **12/12** in both normal and `-O` mode.
- Provenance verifier: **137/137** passed.

## 5. sdist

Reproduced. Built the sdist locally; it ships the updated golden with all 11 cases
(13 fixture files total).

## 6. CI

Run **41754490013** on `wp/7A-3-followup` is `completed`/`success` — confirmed via the
public API, not just the committed `ci-run.log`.

## 7. Gate impact

- **C-7A3-1:** closed — the SentencePiece family now carries the plain/double-space/
  multibyte/punctuation/BOS cases the 7A-3 brief requires, and the coverage test asserts
  them.
- The two mismatches are the 7B/7C work, pinned by independent goldens and strict
  xfails; `--runxfail` red evidence recorded.
- The "empty prompt" scare on the GPT-2 side was the display pipeline stripping `<|…|>`
  text; the accepted GPT-2 golden is correctly untouched.
- **7A-3:** acceptable/closed. **7B:** remains blocked as stated.
