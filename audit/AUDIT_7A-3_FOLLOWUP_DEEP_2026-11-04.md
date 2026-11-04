# Independent 7A-3 Follow-up Audit — C-7A3-1 (SentencePiece golden coverage)

**Auditor:** independent audit session (per handoff §1 and `PHASE7_7A-3_FOLLOWUP_BRIEF.md`)
**Date:** 2026-11-04
**Target:** `wp/7A-3-followup` @ `8378499`
**Work commits:** `c66728c` (prep), `ec72104` (the golden coverage), `8378499` (CI/SHA/diffstat record)
**Base:** `9b042e8` (7A-3 audit commit; work candidate `2c59c5e`)
**Coder:** GLM5.3 · **QAQC:** independent session (`audit/evidence/G1/7A-3-followup/qaqc-probes/`)
**Scope:** 7A-3 follow-up only. **G1 remains unsigned** (see §3).

---

## 1. Verdict

**PASS — C-7A3-1 is closed; 7A-3 is complete with no open conditions.**

The follow-up adds exactly what the 7A-3 audit's one condition demanded: the
SentencePiece golden family now covers plain text, double spaces, multibyte (`café`,
`Ω`, emoji with byte fallback), punctuation/digits, both contractions, the BOS switch
(on/off/absent), and the control token both literal and parsed — 11 cases in
`tests/fixtures/stories260k_tokenizer_golden.json`, with the provenance row, command
and output hash updated, and a coverage test that asserts the SentencePiece family (not
only GPT-2). The two genuine mismatches are pinned as `xfail(strict=True)` with
`--runxfail` red evidence, and the score arithmetic in `runxfail.log` proves the
reference segmentation is the correct one per the vocabulary's own unigram scores
(−384 vs −632, delta 248). The accepted GPT-2/quant/GGUF goldens are byte-identical to
the parent — the "empty prompt" scare was the display pipeline stripping `<|…|>` text.

## 2. Reproduction

| Check | Result |
|---|---|
| Scope `git diff --name-only 9b042e8..8378499` | exactly the brief's allowed set: 4 fixture/test files + brief + evidence bundle; no `src/`, CMake, packaging, CI, ledger, baseline |
| GPT-2 golden/vocab, SPM vocab, quant blocks, `tiny_gguf.gguf`, expectations JSON | empty diff vs parent (byte-identical) |
| SentencePiece golden | 11 cases, coverage as advertised; `add_bos` recorded per case |
| No new test module | `EXPECTED_LANES` untouched |
| CPU lane | 100 passed / 24 deselected / 4 xfailed (QAQC sandbox repro: 98 passed + 2 env-only skips, consistent) |
| `--runxfail` | exactly the 4 known mismatches fail for the documented reasons |
| `test_cpu_only.py` | 12/12 in normal and `-O` mode |
| Provenance verifier | 137/137 |
| sdist | ships the updated golden (11 cases; 13 fixture files) |
| Score arithmetic | recomputed from the GGUF: reference −384 vs greedy −632, delta 248 — reference correct |
| xfails | `strict=True` on both new SPM mismatches; suite fails if they start passing unnoticed |
| CI | run 41754490013 on `wp/7A-3-followup` (`ec72104`): `completed`/`success`, verified via the public API |
| QAQC | independent PASS, all claims reproduced (`qaqc-probes/qaqc-report.md`) |

## 3. Conditions and gate impact

- **C-7A3-1:** closed. The SentencePiece family is represented by the full required
  case set, pinned by an independent (llama.cpp) reference, not omitted or weakened.
- **7A-3:** PASS — complete. This was the package gating 7B ("7B is gated by 7A-3
  goldens"); that gate condition is now satisfied.
- **G1:** still unsigned. The remaining 7A exit criteria are outstanding — 7A-4
  (deterministic hypothesis fuzz) has no branch or audit yet, and the completed 7A
  branches still need merging into the Phase 7 integration branch (PR #8). The QAQC
  verdict's "G1 signed" reads as "the 7A-3 condition for G1 is signed off"; the gate
  itself cannot be signed until 7A-4 lands.
- **7B:** remains blocked until G1 is signed, as stated in the handoff and the QAQC
  report. The two pinned SPM mismatches (`spm_contraction_dont`,
  `spm_control_token_parsed`) are 7B/7C work items now backed by goldens.

---

## 4. Sign-off

**7A-3 follow-up decision: PASS.** C-7A3-1 is closed with QAQC-verified evidence; the
7A-3 goldens are accepted. G1 remains unsigned pending 7A-4 and the 7A merges; 7B
stays blocked.

**Sign-off:** independent audit session, 2026-11-04.
