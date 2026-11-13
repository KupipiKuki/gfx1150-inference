# G1 / 7A-3 follow-up — SentencePiece golden coverage (C-7A3-1)

**Package:** 7A-3 follow-up (closes the one open condition of
`audit/AUDIT_7A-3_GOLDENS_DEEP_2026-11-04.md` §3, **C-7A3-1**)
**Branch:** `wp/7A-3-followup`
**Base:** `wp/7A-3-goldens` @ `9b042e8` (the audit commit); branch base
`c66728c`
**red/green:** the SentencePiece cases are the new evidence; the two
mismatches are the red (`runxfail.log`), the eight matching cases and both
lanes are the green.

---

## What was missing, and what is now there

The audit was right: the committed `stories260k_tokenizer_golden.json` carried
**one** SentencePiece case — the BOS-absent one. The 7A-3 brief requires both
a GPT-2 and a SentencePiece family for plain text, multibyte, double spaces
and the BOS switch, and the coverage test only checked the GPT-2 prompts, so
the gap was not even asserted.

The golden now carries **11** SentencePiece cases:

| case | prompt | the reference | `add_bos` |
|---|---|---|---|
| `spm_absent_add_bos_metadata` | `"Hello world"` | `[1, 346, 306, 414, 263, 304, 341]` | yes |
| `spm_plain_text_no_bos` | `"Hello world"` | `[346, 306, 414, 263, 304, 341]` | no |
| `spm_double_space` | `"Hello  world"` | `[1, 346, 306, 414, 410, 263, 304, 341]` | yes |
| `spm_multibyte_accent` | `"café"` | `[1, 280, 412, 431, 485]` | yes |
| `spm_multibyte_greek` | `"Ω"` | `[1, 410, 209, 172]` | yes |
| `spm_multibyte_emoji` | `"😀"` | `[1, 410, 243, 162, 155, 131]` | yes |
| `spm_punctuation_digits` | `"hello, world! 123"` | `[1, 281, 306, 414, 432, 263, 304, 341, 443, 410, 475, 479, 472]` | yes |
| `spm_contraction_were` | `"we're"` | `[1, 382, 439, 276]` | yes |
| `spm_contraction_dont` | `"don't"` | `[1, 279, 289, 439, 413]` | yes |
| `spm_control_token_literal` | `"<s>"` | `[1, 410, 504, 419, 505]` | yes |
| `spm_control_token_parsed` | `"<s>"` | `[1, 1]` | yes |

The class coverage the brief asks for is now complete, and the audit's two
extra items are covered too:

* **byte fallback** — `"Ω"` becomes `['<s>', '▁', '<0xCE>', '<0xA9>']` and the
  emoji becomes four byte tokens (`<0xF0> <0x9F> <0x98> <0x80>`);
* **control-token behaviour** — the same `<s>` is recorded twice: once as
  literal text (`--no-parse-special`) and once as the control token the
  reference parses out of the input.

**Eight** of the eleven match the repository's tokenizer today; **two** do not
and are pinned as strict xfails.

---

## The two known mismatches

The repository's SentencePiece path is a **greedy longest match** over the
vocabulary. llama.cpp's SentencePiece vocabulary is a **unigram** model, and
llama.cpp picks the segmentation with the best total score. The two are not
the same algorithm, and on this vocabulary they differ.

The evidence that the reference is right is in the vocabulary's own scores
(`runxfail.log`):

```
reference (llama.cpp) '▁d' (-20)  + 'on' (-30) + "'" (-180) + 't' (-154) = -384
repository (greedy)  '▁do' (-141) + 'n' (-157) + "'" (-180) + 't' (-154) = -632
```

The reference's segmentation is **248 log-probability units better**, so it is
the one the model was trained to prefer; the greedy longest match is the
defect. This is the 7B/7C work item the 7A-3 notes already recorded, now
pinned by an independent golden instead of only described.

| case | the reference | the repository | reason |
|---|---|---|---|
| `spm_contraction_dont` | `[1, 279, 289, 439, 413]` | `[1, 400, 416, 439, 413]` | `7B/7C`: the SentencePiece path is a greedy longest match; the reference segments with the unigram scores |
| `spm_control_token_parsed` | `[1, 1]` | `[1, 410, 504, 419, 505]` | `7B`: a control token in the input is not parsed as its own token ID |

Both are `xfail(strict=True)`, so G1 stays green and the suite **fails** if
either starts passing — the fix cannot land unnoticed. `--runxfail` shows
exactly these two (plus the two pre-existing GPT-2 ones) failing for the
documented reason.

The family is **not** omitted: the cases are in the golden, the comparison is
the same exact comparison as the passing cases, and the coverage test asserts
that the SentencePiece golden covers the required inputs.

---

## What changed

| file | change |
|---|---|
| `tests/fixtures/stories260k_tokenizer_golden.json` | 1 → 11 cases; each records the `add_bos` switch the reference used |
| `tests/fixtures/make_fixtures.py` | the SentencePiece case list, the `add_bos` field, the recorded reference command |
| `tests/test_goldens_tokenizer.py` | the SentencePiece cases (parametrised), the two strict xfails, and a coverage test for the SentencePiece family |
| `tests/fixtures/PROVENANCE.md` | the SentencePiece golden's row (command, output hash, notes) and the size table |

**Nothing else.** The GPT-2/BPE golden, the GPT-2 vocabulary, the SentencePiece
vocabulary, the quantized blocks and the tiny GGUF fixture are
**byte-identical** — the generator rewrites every tokenizer fixture, so all
three were compared against the committed ones (`generation-commands.log`):

```
58200852...  gpt2_tokenizer_golden.json    (unchanged)
6d69121d...  gpt2_vocab.json               (unchanged)
83087209...  stories260k_vocab.json        (unchanged)
```

No `src/`, CMake, `setup.py`, `pyproject.toml`, README, PLAN, `scripts/qa`,
ledger, baseline or CI change, and no new test module — so `EXPECTED_LANES`
is untouched.

### One schema addition, and why

The SentencePiece cases carry one field the GPT-2 cases do not: `add_bos`.
The reference adds a BOS token for this vocabulary type unless `--no-bos` is
passed, so the test has to call the repository's encoder with the *same*
switch. The alternative was to infer it from the presence of `--no-bos` in
`reference_flags`, which would couple the test to the tool's flag semantics
without saying so. The GPT-2 golden is untouched.

---

## What was verified

| check | result |
|---|---|
| the SentencePiece golden carries the required plain / double-space / multibyte / punctuation / BOS cases | yes — 11 cases (`tokenizer-spm.log`) |
| `pytest -m "not gpu"` | **100 passed, 24 deselected, 4 xfailed**, exit 0 |
| `pytest -m gpu` | **24 passed**, 104 deselected — **unchanged** |
| `pytest --runxfail` | **4 failed** (the two pre-existing GPT-2 mismatches and the two new SentencePiece ones), 124 passed |
| the xfails are `strict=True` | yes — a fix that lands unnoticed fails the suite |
| the coverage test checks both families | yes — `test_the_sentencepiece_golden_covers_the_required_inputs` asserts the SentencePiece prompts and both BOS switches |
| the provenance verifier | **137/137** (`provenance.log`) |
| the sdist contains the updated golden, and the golden tests run in the extracted tree | yes — 23 passed, 4 xfailed, exit 0 (`sdist-contents.log`) |
| `test_cpu_only.py` | **12/12** in normal and `-O` mode |
| the claims checker / canaries | PASS / 12 of 12 — unchanged |
| the GPT-2 golden, the quantized blocks and the tiny GGUF | **byte-identical** |
| no `src/`, CMake, packaging, CI, README/PLAN, ledger or baseline change | confirmed by `diffstat.txt` |
| no test deleted, skipped or weakened | confirmed — the two GPT-2 xfails and their test are untouched; the existing SentencePiece test was kept and now uses the switch recorded in the golden |

---

## Two things worth recording

### The `add_bos` switch is not a detail

The SentencePiece vocabulary's GGUF carries **no**
`tokenizer.ggml.add_bos_token` key at all. The reference's behaviour then
depends on the vocabulary *type*: for this SentencePiece vocabulary it adds a
BOS, and for the GPT-2 byte-level BPE vocabulary it does not. The golden
records the switch per case, so the test compares like with like. This is the
same metadata the GPT-2 family already pins, now on the other side of the
`add_bos_token` question.

### The difference is an algorithm difference, not a rounding difference

The greedy longest match and the unigram Viterbi agree on eight of the eleven
cases — including every multibyte case and the punctuation case — and differ
on `"don't"`. The score table shows why: the greedy match takes `▁do` because
it is longer, although `▁d` + `on` is 248 log-probability units more likely.
A rounding difference would have been a tolerance question; this is a
different algorithm, and it is the 7B/7C work item.

---

## Limitations and follow-ups

1. **The vocabulary is tiny.** The `stories260K` vocabulary has 512 tokens, so
   the SentencePiece cases exercise the byte fallback heavily. A larger
   SentencePiece vocabulary would cover more of the model's merges; it would
   also be a much larger fixture, and the brief's size rule (≤ 2 MB per
   fixture) is the binding constraint here.
2. **Two of the eleven cases do not match today.** That is the 7B/7C work,
   pinned by the golden and the strict xfails — not a gap in this package.
3. **`stories260k_vocab.json` carries no scores.** The scores are only needed
   for the mismatch analysis in the evidence, and the repository's tokenizer
   does not use them, so the fixture stays as it is (and the brief's allowed
   file list does not include it).
4. **7A-4 and 7B are not started here.**

---

## Rollback

Revert the commit: the golden returns to its single SentencePiece case, the
generator's case list shrinks, the test module loses the two new tests and the
coverage test, and the registry row returns to its old command and hash.
Nothing else in the repository changes, so the rollback cannot affect the
build, the CI jobs or any other package's evidence.

## Claims changed

None. No public claim was added, removed or re-qualified. This package adds
golden cases, the tests that pin them, and the registry rows that describe
them.
