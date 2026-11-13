# Independent 7A-3 Audit — Golden Data and Provenance

**Auditor:** DeepSeek V4.1 Flash (independent of the coder and QAQC)
**Date:** 2026-11-04
**Target:** `wp/7A-3-goldens` @ `a9c5785` (work commit `2c59c5e`)
**Base:** `34f1686` (branch base; `a8c3dbe` integration base)
**Coder:** GLM5.3 · **QAQC:** independent session (`qaqc-probes/qaqc-report.md`)
**Scope:** 7A-3 only. **G1 remains unsigned.**

---

## 1. Verdict

**PASS WITH CONDITIONS — one condition, one scope gap.**

The package meets the hard requirement: the goldens are genuinely independent,
pinned, machine-checked, and exact. I reproduced the provenance run (**137/137**), the
CPU/GPU lanes (**91 + 2 xfailed / 24**), the two strict xfails and their `--runxfail`
failures, the offline golden run from a clean clone (**36 + 2 xfailed**), the sdist
contents (**13 fixture entries**), and the API-verified CI run **41749187809** (success).
The scope is clean.

The condition is the **SentencePiece half of 7A-3**: the committed
`stories260k_tokenizer_golden.json` has only one case — the BOS-absent `add_bos` case.
There are no SentencePiece golden vectors for plain text, double spaces, multibyte, or
BOS on/off, while the 7A-3 brief explicitly requires “GPT-2/SentencePiece token IDs for
plain text, multibyte, double spaces, … `add_bos` on/off.” QAQC’s observation 3 noticed
the gap but did not make it a condition. I do: the repository advertises SentencePiece
support, and 7B/7C need an independent gate for it.

This is a data/test follow-up, not a rejection of the package. The GPT-2/BPE half is
excellent and should be kept exactly as is.

---

## 2. Reproduction

| Check | Result |
|---|---|
| `verify-provenance.py` | **137/137** checks pass; every tracked fixture hash matches its registry row |
| `make_fixtures.py` independence | imports only stdlib + NumPy; no `src/` reference; drives llama.cpp tools/gguf-py |
| Tracked fixtures | 12 files, **2.75 MiB total**, each ≤ 2 MB |
| CPU lane | **91 passed, 24 deselected, 2 xfailed** |
| GPU lane | **24 passed, 93 deselected** |
| `--runxfail` | exactly 2 failures: `test_add_bos_default…`, `test_special_token_is_encoded_as_its_id` — the known 7B bugs |
| Offline golden modules, no extension | **36 passed, 2 xfailed**, exit 0 |
| `test_cpu_only.py` / `-O` | 12/12 each |
| Sdist | 13 fixture entries, including `tiny_gguf.gguf`, goldens, generator, registry |
| CI run `41749187809` | API: **success**, head `2c59c5e` |
| Scope | only `tests/**`, `tests/fixtures/**`, fixture globs in `MANIFEST.in`, evidence; restricted diff empty |
| Lane registration | four new modules in `EXPECTED_LANES` (3 cpu, 1 gpu) |

The provenance is not self-referential: the GGUF expectations come from llama.cpp’s
reader; token IDs from `llama-tokenize`; quant blocks from `llama-quantize`/`gguf-py`.
The Q4_0 byte-identity cross-check is genuine; the Q4_K/Q6_K unavailability is disclosed.
`tiny_gguf.gguf` is upstream-verbatim with matching input/output hashes.

---

## 3. Condition

### C-7A3-1 (Medium) — SentencePiece golden coverage is incomplete

`tests/fixtures/stories260k_tokenizer_golden.json` contains **one** case:

```
spm_absent_add_bos_metadata  prompt "Hello world"
```

There is no SentencePiece golden for:

- plain text beyond that one prompt;
- double spaces;
- multibyte (`café`, `Ω`, emoji);
- punctuation/digits;
- `add_bos` on/off (only the metadata-absent default is represented);
- byte-fallback/control-token behaviour.

The brief’s 7A-3 row requires both GPT-2 and SentencePiece vectors for those classes.
The current test `test_the_golden_cases_cover_the_required_inputs` only checks the GPT-2
prompts, so the gap is not even asserted.

**Required:** add SentencePiece cases using the pinned stories260K vocabulary and
`llama-tokenize` (same provenance discipline), update the registry/coverage test, and
register the cases in the existing CPU lane. If the repository’s SentencePiece path
genuinely disagrees with llama.cpp (the coder measured a BPE-vs-unigram difference),
mark the affected cases `xfail(strict=True)` with the 7B/7C reason and record the
`--runxfail` red evidence — do **not** omit the family. Keep the GPT-2 goldens unchanged.

No other 7A-3 condition remains. The Q4_K/Q6_K byte-identity caveat and the GPT-2 BPE
choice are documented and acceptable.

---

## 4. Gate impact

- **7A-3:** not G1-complete until C-7A3-1 lands. The package is otherwise accepted.
- **7A-4:** still open; can proceed in parallel.
- **7A-7:** queued-not-green until 7F-1 registers the runner.
- **G1:** unsigned; **7B:** blocked until G1 and the completed 7A-3 goldens.
- If SentencePiece support is intentionally out of scope, the alternative is to amend
  the README/compatibility claims and the handoff explicitly; silently leaving the
  golden family out is not acceptable.

---

## 5. Sign-off

**7A-3 decision: PASS WITH CONDITIONS.** The independent goldens are real and the
GPT-2/quant/GGUF evidence is excellent; the SentencePiece vectors are the remaining gap.

**Sign-off:** DeepSeek V4.1 Flash, 2026-11-04.
