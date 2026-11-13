# G2 / 7B — Tokenizer Correctness (Gate G2)

**Package:** 7B (tokenizer correctness: 7B-1 special tokens, 7B-2 `add_bos_token`,
7B-3 GPT-2 regex / SentencePiece unigram, 7B-4 unmappable bytes)
**Branch:** `wp/7B-tokenizer`
**Parent:** `8426ec6` (`vibe/phase7-220201` head: G1 signed, the 7A-9 parser fix merged;
7B is independent of 7A-9 per the brief)
**Candidate:** `70c5ab2` (work commit; see `candidate-sha.txt`)

---

## TL;DR

All four tokenizer `xfail`s are closed: every 7A-3 golden (12 GPT-2 + 11
SentencePiece) passes, `--runxfail` is a clean pass, the CPU lane is
128 passed / 0 xfailed, the GPU lane is unchanged (24/24 on both parent and
candidate), `test_cpu_only.py` is 12/12 normal and `-O`, and the claims
checker is green.

## The work, per package

**7B-1 — special tokens on encode.** `encode()` now splits the input on the
special tokens (`tokenizer.ggml.token_type` CONTROL or USER_DEFINED, plus
the BOS/EOS token strings) with a longest-match table, so a special token is
emitted as its own ID even when it is a proper prefix of another special
token, with no byte mapping inside it, and text that merely looks like a
special token stays ordinary text. `encode(text, parse_special=True)` is the
default, matching llama.cpp's `--parse-special`; the goldens record the
reference's switch per case and the tests replay it
(`--no-parse-special` ⇒ literal text). QAQC pinned: mixed text
(`hi<EOT>there`), overlapping specials (`<pad>` vs `<pad_word>`), adjacency
to whitespace and punctuation, look-alikes, decode round-trips behind
`skip_special_tokens` both ways.

**7B-2 — the BOS decision.** Precedence: explicit `add_bos` argument >
`tokenizer.ggml.add_bos_token` metadata (now read by `from_gguf_metadata`) >
family default. The family default matches llama.cpp for a missing key:
a BOS for a SentencePiece (`▁`) vocabulary, none for byte-level BPE.
`generate()` and `generate_batch()` in `src/inference.py` no longer hardcode
`add_bos=True` — the only two `src/` call sites changed, as the brief allows.
QAQC pinned: metadata absent/false/true through `from_gguf_metadata`, the
argument overriding the metadata in both directions, no duplicate BOS on a
leading special token, empty-string behavior.

**7B-3 — segmentation.** The SentencePiece path is now a unigram Viterbi over
the UTF-8 byte string of the normalized text, maximizing the sum of the GGUF
scores, with `<0xXX>` byte tokens as the fallback. This replaces the greedy
priority-queue merge, which provably cannot reproduce the reference
(`don't` → the greedy `▁do`+`n` vs the reference's score-optimal
`▁d`+`on`). The GPT-2 pre-tokenizer regex was upgraded to the Unicode
classes of the reference pattern: ` ?[^\W\d_]+` for ` ?\p{L}+`, ` ?\d+` for
` ?\p{N}+`, ` ?(?:[^\s\w]|_)+` for ` ?[^\s\p{L}\p{N}]+` (the underscore is
`\w` but not a letter, so `_` now separates as the reference does).
**Known deviations** (not pinned by any golden; see below): the equivalence
classes treat combining marks (Mn) as word characters — the reference
groups them into the non-letter/non-number class — and `\d` covers `Nd`
only, where `\p{N}` also includes `Nl`/`No` (Roman numerals, fractions).
Both only affect decomposed accents and obscure numerals; all golden cases
(precomposed `café`, `Ω`, emoji) are exact.

**7B-4 — unmappable bytes.** `encode()` validates that the input is UTF-8
encodable (a lone surrogate raises `ValueError`, not a nested
`UnicodeEncodeError`), the Viterbi reports the byte at the last reachable
position when coverage stalls, and both families raise `ValueError` naming
the byte value. No silent character or byte loss: a missing `<0xXX>` token
raises; text decode paths were re-verified for round-trip on every golden
case.

## The SentencePiece fixture carries the scores now — please review

The 7A-3 `stories260k_vocab.json` recorded tokens, token types, and merges
but **not** `tokenizer.ggml.scores`, so the reference's segmentation
(`don't` = `▁d`+`on`, the exact case the auditor pinned as the known
mismatch) could not be reproduced from the committed fixture at all: every
tokenizer built from it had degenerate (all-zero) scores. 7B-3 therefore:

1. `tests/fixtures/make_fixtures.py` writes the scores into the SPM vocab
   payload (the upstream GGUF "already carries the unigram scores"; the
   generator just dropped them);
2. `stories260k_vocab.json` was regenerated from the pinned upstream download
   `ggml-org/models:tinyllamas/stories260K.gguf`, whose sha256 was verified
   against the provenance pin **before extraction**
   (`270cba1bd5109f42d03350f60406024560464db173c0e387d91f0426d3bd256d`, match);
   the extraction used this repository's own (7A-9-fixed) GGUF parser;
3. `stories260k_tokenizer_golden.json`'s recorded `vocab.fixture_sha256` was
   updated to the regenerated fixture's hash. **No golden token vector was
   changed** — the diff on the golden is exactly one line (the fixture hash).

The brief says fixtures change "only if a 7A-3 golden is demonstrably wrong;
prefer not to change goldens". The golden vectors were not wrong; the fix is
the missing input data. This is called out as the one judgment call needing
auditor sign-off: it can be reverted by regenerating the fixture without
scores and by re-pinning `spm_contraction_dont` as an xfail, at the cost of
keeping an unreference-reproducible case open.
`PROVENANCE.md` and the hash test cover the new fixture hash on both
families now.

## Viterbi: design decisions

* **Candidates are NORMAL pieces only** (`token_type == 1`, or non-special
  when a GGUF carries no token-type array). Control/user-defined pieces are
  special tokens (they must not be matched as ordinary text — pinned by the
  `spm_control_token_literal` golden) and BYTE pieces participate only via
  the fallback.
* **Byte fallback is penalized, not scored at face value.** In the real GGUF
  the `<0xXX>` tokens and the control tokens carry `0.0` scores while every
  real piece is negative, so a naive sum-of-scores Viterbi would segment
  *everything* into byte tokens (`▁` → `<0xE2><0x96><0x81>` beats the
  `▁` piece at -151). SentencePiece's own unk penalty (10.0) is applied:
  a byte token scores `min(normal scores) - 10.0`, so any piece that can
  cover a span always beats its byte expansion, and the fallback is used
  only when piece coverage is impossible. This reproduces every byte-fallback
  golden (`Ω`, the emoji, `café`'s `é` piece).
* **The dummy `▁` prefix is applied to the chunk at offset 0 only.** A chunk
  following a special token continues the text without a fresh prefix
  (matching the reference's dummy-prefix semantics for text that starts
  with a special token; the `spm_control_token_parsed` golden - `[1, 1]`,
  no lone `▁` - pins the leading side).
* **Tie-break:** strict `>` (first-found wins). With real unigram scores ties
  across distinct pieces are float-exact and did not occur in any golden; the
  behavior with missing scores is deterministic (documented degenerate).

## Red / green

The four tokenizer `xfail`s are the red. On the parent `8426ec6`:
`--runxfail` fails all four (`tokenizer-golden.log`, exit 1); the default run
shows them as strict xfails with the pinned reasons. On the candidate
`70c5ab2`: the same slice passes 75/75 with no xfail left in the suite
(`runxfail.log`, exit 0). `strict=True` protects against unnoticed fixes, so
all four xfails were removed rather than observed passing.

## Lanes

| lane | parent `8426ec6` | candidate `70c5ab2` |
|---|---|---|
| CPU `pytest -m "not gpu"` | 111 passed, 4 xfailed | **128 passed** |
| tokenizer slice (`-k "tokenizer or bpe or golden"`) | 58 passed, 4 xfailed | **75 passed** |
| `--runxfail` on the slice | 4 failed | **clean pass** |
| GPU `pytest -m gpu` (real gfx1150, same extension) | 24 passed | **24 passed** |
| `tests/test_cpu_only.py` (normal, `-O`) | 12/12, 12/12 | **12/12, 12/12** |
| claims checker | PASS | **PASS** (claim 7/8/9 rows updated) |
| sdist build + clean-venv install + shipped suites | n/a (unchanged packaging) | **green** (`sdist-install.log`) |

The CPU lane moves exactly as the brief allows: the 4 xfails became passing
tests and the 13 new QAQC/golden tests were added; the GPU/claims/unittest
counts are otherwise unchanged. The parent GPU lane ran with
`PYTHONPATH=<repo>/build` because a worktree checkout has no `build/`
directory; the extension is byte-identical (no C++/CMake file changed).

## What was not touched

`src/gguf_parser.py` (7A-9's file — it was only *used*, to extract the
scores from the pinned GGUF), CMake, packaging, CI, the ledger arithmetic,
other packages' evidence, and the 7C model-family claims (10/11/12 still
NOT YET with their baselines). The README's tokenizer wording and ledger
rows 7/8/9 were updated to the implemented state; row 8 is PARTIAL
(tokenizer-side split done; per-family chat templates remain 7C).

## Required commands (all from the repository root)

```
python -m pytest -m "not gpu" -q -k "tokenizer or bpe or golden"    # 75 passed
python -m pytest -m "not gpu" -q --runxfail -k "tokenizer or bpe or golden"   # 75 passed
python -m pytest -m "not gpu" -q                                     # 128 passed
python -m pytest -m gpu -q                                           # 24 passed
python tests/test_cpu_only.py        # OK (12/12)
python -O tests/test_cpu_only.py     # OK (12/12)
python scripts/qa/check_claims.py    # PASS
python audit/evidence/G2/7B/qaqc-probes/probe_tokenizer.py   # ALL PROBES PASS (23)
```

## Stop

Stopped at G2 per §7. 7C is **not** started. The release remains blocked
until 7A-9 and G2 are both accepted (7A-9 already passed its audit; it is
merged in the parent of this branch).

---

## Remediation (2026-11-06, after the FAIL audit)

The 2026-11-05 audit (`audit/AUDIT_7B_TOKENIZER_DEEP_2026-11-05.md`) failed the
first candidate (`70c5ab2`) on **BLOCKER-7B-1** (SPM dummy `▁` prefix omitted
around special tokens) and **BLOCKER-7B-2** (Viterbi vs the reference's
greedy bigram merge). Remediation candidate: **`25e9088`** on
`wp/7B-remediation` (brief: `PHASE7_7B_REMEDIATION_BRIEF.md`).

Fixes, both in `src/tokenizer.py`:

- `encode()` drives the special/raw fragment loop with the reference's
  `is_prev_special` rule: every raw fragment that starts the input or follows
  a special token gets a leading space, escaped to `▁`.
- The SPM path is the reference score-priority greedy bigram merge
  (`_greedy_merge_symbols`, max score / ties leftmost = the
  `llm_bigram_spm` comparator) over UTF-8 chars with the fixture's unigram
  scores; the Viterbi is removed. Surviving non-token symbols emit as `<0xXX>`
  byte tokens or raise `ValueError` naming the byte (7B-4 kept). A `▁`-word
  fallback only rescues minimal synthetic vocabularies that lack byte tokens
  (the phase5 test vocab); real vocabs never reach it — no piece in either
  committed vocab contains an internal `▁`, so word-splitting cannot diverge
  from the whole-text reference merge.
- QF-1: short `token_types` raises at construction. QF-2: SPM mixed-text tests
  assert the pinned reference values; a new 310-case differential golden
  (`tests/fixtures/stories260k_differential_golden.json`, generated with the
  pinned `llama-tokenize` via `make_fixtures.py spm-differential`, PROVENANCE
  row added) replays in the suite.

Stop-gate QAQC (`remediation-*.log`, `qaqc-probes/qaqc-*.log`):

| check | failed 70c5ab2 | remediation 25e9088 |
|---|---|---|
| differential corpus (310 cases) | **75 mismatches** | **0** |
| auditor's 11 probe cases | **10 differ** | **all match** |
| 2,000-prompt seeded differential vs pinned binary | (7,529/20,000 per audit) | **0 mismatches** |
| tokenizer slice `--runxfail` | 75 passed (goldens only) | **386 passed**, 0 xfail |
| CPU / GPU / cpu-only / claims | 128 / 24 / 12+12 / PASS | **439 / 24 / 12+12 / PASS** |

Parent red (the four xfails failing under `--runxfail` on `8426ec6`) is in
`remediation-red-green.log` alongside the failed-candidate red.

Stopped at the G2 stop-gate: ready for the primary auditor's re-review.
7C remains blocked; do not merge until G2 is signed.
