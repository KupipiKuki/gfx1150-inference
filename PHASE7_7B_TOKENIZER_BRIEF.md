# Phase 7B Coder Brief — Tokenizer Correctness (Gate G2)

**To:** GLM5.3 (coder)
**From:** DeepSeek V4.1 Flash (primary auditor)
**Date:** 2026-11-04
**Branch:** `wp/7B-tokenizer`
**Base:** `vibe/phase7-220201` @ `e9b6b80` (G1 signed; 7A-3 goldens merged)
**Gate:** G2. **7B is authorized**; the P0 parser fix 7A-9 has landed and is accepted, so 7B is independent of it. 7C is not authorized until G2 is signed.

The acceptance vectors already exist in `tests/fixtures/` from 7A-3. This package makes
the tokenizer match them and removes the tokenizer `xfail`s.

---

## 1. Allowed files

- `src/tokenizer.py`
- `src/inference.py` (BOS call sites only)
- `tests/**` (tokenizer/golden tests, lane registration)
- `tests/fixtures/**` only if a 7A-3 golden is demonstrably wrong; prefer not to change goldens
- `README.md` (tokenizer/claims wording)
- `audit/CLAIMS_LEDGER.md` only for tokenizer-claim status/scope changes
- `audit/evidence/G2/7B/**`
- docs

**Do not touch** `src/gguf_parser.py` (7A-9 owns it), CMake, packaging, CI, the ledger
arithmetic, or other packages’ evidence.

---

## 2. Work packages

| ID | Task | Acceptance |
|---|---|---|
| **7B-1** | Special-token split on **encode**: longest-match trie over control/user-defined tokens; emit the special ID directly; no byte mapping inside a special token; no splitting inside ordinary text | `encode("<\|im_start\|>")` → `[special_id]`; `"hi<\|im_start\|>there"` splits correctly; plain text unchanged; `<\|endoftext\|>` and SPM `<s>` cases pass |
| **7B-2** | Read `tokenizer.ggml.add_bos_token`; precedence explicit `add_bos` argument > metadata > default; `generate()` / `generate_batch_ids()` stop hardcoding `True` | Metadata true/false/absent tested; no duplicate BOS; GPT-2 (no BOS) and SentencePiece (BOS by default) behave correctly |
| **7B-3** | GPT-2 spec regex (Unicode `\p{L}`/`\p{N}`) or a golden-verified equivalent; resolve the SentencePiece golden mismatches or explicitly re-scope them with auditor approval | All 7A-3 GPT-2 cases pass; SPM plain/double/multibyte/BOS cases pass; `spm_contraction_dont` and `spm_control_token_parsed` pass or have an approved scope decision |
| **7B-4** | Uniform unmappable-byte handling: try `<0xXX>` before raising; never silently drop | Minimal GPT-2 and SentencePiece vocabs: missing byte raises `ValueError` with the byte value; no silent loss |

The four tokenizer `xfail`s in `tests/test_goldens_tokenizer.py` are the current
acceptance targets:

1. `test_add_bos_default_matches_the_reference_tokenizer`
2. `test_special_token_is_encoded_as_its_id`
3. `test_spm_known_mismatches_are_pinned[spm_contraction_dont]`
4. `test_spm_known_mismatches_are_pinned[spm_control_token_parsed]`

Remove each `xfail` only when the golden passes; `strict=True` will fail on an unnoticed
fix.

---

## 3. Required checks

```bash
python -m pytest -m "not gpu" -q -k "tokenizer or bpe or golden"
python -m pytest -m "not gpu" -q --runxfail -k "tokenizer or bpe or golden"
python tests/test_cpu_only.py
python -O tests/test_cpu_only.py
# independent probe: special token, mixed text, add_bos true/false/absent
```

Expected final CPU lane: no tokenizer xfails remain; all 7A-3 tokenizer goldens pass.
GPU/claims/unittest counts otherwise unchanged.

---

## 4. QAQC adversarial checks

- Special token that is a prefix of another special token (longest match).
- Special token adjacent to whitespace and punctuation.
- `add_bos` metadata absent vs `false` vs `true`; explicit argument overrides.
- Text that looks like a special token but must not be treated as one, if the spec requires it.
- Multi-byte UTF-8, lone surrogate, empty string.
- Decode round-trip with `skip_special_tokens` true/false.
- All 7A-3 goldens: zero tokenizer failures under `--runxfail`.
- SPM segmentation: if the repo cannot match the reference unigram scores, do not
  hand-wave; either implement the correct scoring or ask the auditor to scope it
  explicitly.

---

## 5. Acceptance

- 7A-3 tokenizer goldens all pass; no tokenizer `xfail` remains without written auditor
  approval.
- No silent character/byte loss; missing bytes raise.
- Existing parser/quant/GGUF goldens and GPU lane unchanged.
- `test_cpu_only.py` 12/12 normal and `-O`; claims checker green.
- README tokenizer/claims updated honestly; 7C model-family claims remain untouched.
- No `src/` change outside `tokenizer.py` and the BOS call sites in `inference.py`.
- 7A-9 parser fix is independent; do not wait for it, but do not claim release/fail-closed
  parser status.

---

## 6. Evidence

`audit/evidence/G2/7B/` with:

```
env.txt  parent-sha.txt  candidate-sha.txt  diffstat.txt
tokenizer-golden.log  special-token.log  add-bos.log
unmappable-byte.log  runxfail.log
cpu-lane.log  gpu-lane.log  sdist-install.log
notes.md
```

`red/green`: the four tokenizer `xfail`s are the red on the parent; the same tests
passing without xfail on the candidate are the green.

---

## 7. Stop

Stop for QAQC at G2. Do not start 7C. 7A-9 is the P0 parser fix and may land in parallel;
the release remains blocked until both 7A-9 and G2 are accepted.
