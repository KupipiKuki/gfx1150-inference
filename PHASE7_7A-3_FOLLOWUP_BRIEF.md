# 7A-3 Follow-up Brief — SentencePiece Golden Coverage (C-7A3-1)

**To:** GLM5.3 (coder), QAQC
**From:** DeepSeek V4.1 Flash (primary auditor)
**Date:** 2026-11-04
**Branch:** `wp/7A-3-followup`
**Base:** `wp/7A-3-goldens` @ `9b042e8` (audit commit; work candidate `2c59c5e`)
**Gate:** 7A-3 follow-up only. **G1 remains unsigned.**

The GPT-2, quant, and GGUF goldens are accepted. This closes the one open condition in
`audit/AUDIT_7A-3_GOLDENS_DEEP_2026-11-04.md` §3: the SentencePiece family is represented
by only the BOS-absent case, not the plain/double-space/multibyte/BOS cases the 7A-3
brief requires.

---

## 1. Allowed files

- `tests/fixtures/stories260k_tokenizer_golden.json` (the sparse fixture)
- `tests/fixtures/PROVENANCE.md` (update its row/command/output hash)
- `tests/fixtures/make_fixtures.py` only if the generator needs the new cases
- `tests/test_goldens_tokenizer.py` (cases/coverage)
- `tests/test_harness_contract.py` only if a new test module is added (prefer extending
  the existing module, so no lane change is needed)
- `audit/evidence/G1/7A-3-followup/**`
- docs

**No** `src/`, CMake, setup.py, pyproject, README, PLAN, scripts/qa, ledger, baseline,
CI, or GPT-2/quant/GGUF fixture changes. Keep the existing GPT-2/BPE goldens exactly as
they are.

---

## 2. Required cases

Using the **pinned stories260K vocabulary** and `llama-tokenize` from the pinned
llama.cpp (`@149f5641…`), add SentencePiece golden cases for at least:

- plain text: `"Hello world"`;
- double spaces: `"Hello  world"`;
- multibyte: `"café"`, `"Ω"`, an emoji;
- punctuation/digits: `"hello, world! 123"`;
- `add_bos` on/off/absent: the reference with BOS (default/absent metadata) and with
  `--no-bos`, and the explicit repository `encode(..., add_bos=...)` behavior.

Record the exact `llama-tokenize` flags and the output hashes in the registry. Update
`stories260k_tokenizer_golden.json` to carry the cases (same schema as the GPT-2
golden), and extend `test_the_golden_cases_cover_the_required_inputs` so it checks the
SentencePiece inputs too, not only GPT-2.

If the repository’s SentencePiece path genuinely disagrees with llama.cpp (the coder
measured a BPE-vs-unigram difference), mark the affected cases
`xfail(strict=True, reason="7B/7C: ...")` and record `--runxfail` red evidence. Do **not**
omit the family or weaken the comparison; the goldens must exist and be independent.

---

## 3. Acceptance

- `stories260k_tokenizer_golden.json` contains the required plain/double-space/multibyte/
  punctuation and BOS cases; provenance row/command/hash updated.
- `pytest -m "not gpu"` green on the current tree (xfails only for documented 7B/7C
  mismatches, `strict=True`); `--runxfail` shows those failures for the expected reason.
- `pytest -m gpu` unchanged (24 passed).
- `test_the_golden_cases_cover_the_required_inputs` checks both GPT-2 and SentencePiece.
- The sdist still contains the updated golden; provenance verifier passes.
- GPT-2 goldens, quant blocks, GGUF fixture, and lane counts otherwise unchanged.
- No `src/`, CMake, packaging, CI, README/PLAN, ledger, or baseline change.

---

## 4. Evidence

`audit/evidence/G1/7A-3-followup/` with:

```
env.txt  parent-sha.txt  candidate-sha.txt  diffstat.txt
generation-commands.log  provenance.log
tokenizer-spm.log  runxfail.log  cpu-lane.log  gpu-lane.log
sdist-contents.log  notes.md
```

`red/green`: the SentencePiece cases (and any documented xfail) are the new evidence;
the existing GPT-2/quant/GGUF logs remain the green baseline.

---

## 5. Stop

After the follow-up commit, stop for QAQC. Do not start 7A-4 or 7B on this branch. 7A-3
stays open until the SPM goldens are accepted; G1 remains unsigned.
