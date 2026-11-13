# Independent 7B Audit — Tokenizer Correctness (Gate G2)

**Auditor:** DeepSeek V4.1 Flash (primary auditor)
**Date:** 2026-11-05
**Target:** `wp/7B-tokenizer` @ `e091fcf`
**Work commit:** `70c5ab2` · **Parent:** `8426ec6` (`vibe/phase7-220201`, 7A-9 merged)
**Coder:** GLM5.3 · **QAQC:** independent session (`audit/evidence/G2/7B/qaqc-probes/`)
**Gate:** G2. **Decision: FAIL — G2 NOT SIGNED.** Two implementation blockers.

---

## 1. Verdict

**FAIL.** The package closes the four pinned `xfail`s and passes all 23 7A-3
goldens, and its fixture regeneration is sound. But the SentencePiece path does
not reproduce llama.cpp’s tokenizer on ordinary text or on mixed text around
special tokens. The 7A-3 goldens are too narrow to detect either defect; the
candidate passes them by coincidence on the covered strings.

This is not a documentation or scope issue: the release scope is llama-family
SentencePiece GGUFs, and the token IDs a llama model sees must be the ones the
reference produces.

Two blockers:

- **BLOCKER-7B-1:** SPM special-token chunk handling omits the reference’s
  dummy `▁` prefix on text before and after a special token.
- **BLOCKER-7B-2:** the SPM segmentation algorithm is Viterbi, but the
  reference at the pinned commit is a score-priority greedy bigram merge; the
  two disagree on common English words and realistic prompts.

---

## 2. What passes

| Check | Result |
|---|---|
| Four former xfails | removed; `--runxfail` tokenizer slice **75 passed**, exit 0 |
| 7A-3 goldens | all 12 GPT-2 + 11 SPM pass |
| Tokenizer slice | **75 passed** |
| CPU lane | **128 passed / 24 deselected / 0 xfailed** |
| GPU lane | **24 passed / 128 deselected** |
| `test_cpu_only.py` / `-O` | **12/12 / 12/12** |
| Claims checker | **PASS** — 0 new / 17 baselined / 0 findings |
| Scope | allowed files only; no `gguf_parser.py`, CMake, packaging, CI, ledger arithmetic |
| Fixture provenance | `stories260k_vocab.json` sha256 `8577a797…` matches the recorded hash; the scores are byte-for-byte the pinned upstream GGUF’s 512 scores; tokens/types also match |
| Golden vectors | SPM golden diff is exactly the one `fixture_sha256` line; no token vector changed |
| Byte safety | no silent loss on the tested cases; lone surrogate raises `ValueError`; missing bytes raise naming the byte |
| `add_bos` precedence | explicit argument > metadata > family default, tested in all 9 combinations |

The QAQC report’s lane numbers and provenance checks reproduce. The fixture
regeneration (adding the upstream unigram scores) is accepted: it is input
data, not a golden edit.

---

## 3. BLOCKER-7B-1 — SPM dummy prefix around special tokens

**Reference:** `llama.cpp @149f5641b931aaf33697d70f9abc90c3e5300247`,
`src/llama-vocab.cpp`, SPM tokenize path:

```cpp
bool is_prev_special = true;  // prefix with space if first token
...
for (const auto & fragment : fragment_buffer) {
    if (fragment.type == RAW_TEXT) {
        std::string text;
        if (add_space_prefix && is_prev_special) {
            text = ' ';
        }
        text += fragment.raw_text.substr(fragment.offset, fragment.length);
        llama_escape_whitespace(text);  // ' ' -> '▁'
        ...
        is_prev_special = false;
    } else { // special token
        output.push_back(fragment.token);
        is_prev_special = true;
    }
}
```

Every raw-text fragment gets the dummy `▁` prefix when it starts the input
**or immediately follows a special token**. The candidate only considers
`prepend_dummy=offset == 0`, and its offset is computed after consuming the
special token:

```python
i += length
...
out.append(("".join(buf), i - len(buf), None))   # should be the chunk start
...
ids.extend(self._encode_plain(chunk, prepend_dummy=offset == 0))
```

Result: the chunk before a special is not recognised as starting at offset 0,
and a chunk after a special is never prefixed.

Reference outputs below are from the pinned `llama-tokenize` (built from the
same tarball; it reproduces all 11 SPM goldens exactly). Candidate outputs are
`encode(..., add_bos=False, parse_special=True)`.

| Input | Reference | Candidate |
|---|---|---|
| `a<s>b` | `[261, 1, 268]` = `▁a`, `<s>`, `▁b` | `[412, 1, 430]` = `a`, `<s>`, `b` |
| `hi<s>there` | `[270, 417, 1, 383]` = `▁h`,`i`,`<s>`,`▁there` | `[415, 417, 1, 413, 260, 276]` = `h`,`i`,`<s>`,`t`,`he`,`re` |
| `" <s>"` | `[410, 410, 1]` = `▁`,`▁`,`<s>` | `[410, 1]` = `▁`,`<s>` |
| `<s>b` | `[1, 268]` = `<s>`, `▁b` | `[1, 430]` = `<s>`, `b` |
| `hello<s>there` | `[281, 306, 414, 1, 383]` | `[260, 306, 414, 1, 413, 260, 276]` |
| `<s></s>` | `[1, 2]` | `[1, 2]` (no raw text; matches) |

The tests do not catch this:

- `test_special_token_split_preserves_the_ordinary_text_around_it` uses the
  **GPT-2** vocabulary, where there is no dummy prefix; it never exercises SPM.
- `test_no_duplicate_bos_is_added_on_top_of_a_leading_special_token` expects
  `[1, 1, b]`; the reference gives `[1, 1, ▁b]`.
- `test_empty_and_whitespace_special_splitting` expects `[1, 410, 1]` for
  `" <s>"`; the reference gives `[1, 410, 410, 1]`.

**Required fix:** mirror the reference’s `is_prev_special` semantics — prepend
a space/`▁` to every raw fragment that starts the input or follows a special
token — and fix the offset calculation (or remove the offset entirely once
the flag is tracked). Add SPM mixed-text golden cases (leading text, trailing
text, whitespace, consecutive specials) generated with the pinned
`llama-tokenize`, with provenance.

---

## 4. BLOCKER-7B-2 — SPM segmentation is Viterbi, the reference is greedy

The reference SPM tokenizer is a score-priority **greedy bigram merge**:
`llm_tokenizer_spm_session` seeds every adjacent pair whose concatenation is a
token, then repeatedly merges the highest-scoring such bigram
(`src/llama-vocab.cpp`, `try_add_bigram` / `work_queue`). It is not a global
Viterbi.

The candidate implements Viterbi over the byte string, maximising the **sum**
of unigram scores (`_viterbi_unigram`). These are different algorithms and
they produce different token IDs. The 7A-3 goldens happen to be in the
intersection.

Reference vs candidate, `encode(..., add_bos=False, parse_special=False)`:

| Input | Reference | Candidate |
|---|---|---|
| `the` | `[265]` = `▁the` | `[259, 260]` = `▁t`, `he` |
| `and` | `[269]` = `▁and` | `[261, 264]` = `▁a`, `nd` |
| `time` | `[378]` = `▁time` | `[259, 369]` = `▁t`, `ime` |
| `the quick brown fox jumps over the lazy dog` | `[265, 410, 456, …]` | `[259, 260, 410, …]` (differs from token 1) |
| `Once upon a time there was a little girl named Lily` | `[403, 407, 261, 378, 383, 286, …]` | `[321, 331, 350, 289, 261, 259, …]` |

On a 39-word common-English sample, **14/39** differ. On a 20,000-string
piece-concatenation differential against a faithful port of the reference
algorithm, **7,529** differ. The reference binary reproduces all 11 SPM
goldens exactly, so this is not a reference-version mismatch.

Why the goldens pass: they cover `Hello world`, `hello, world! 123`, `don't`,
`we're`, `café`, `Ω`, the emoji, double spaces, and the control-token cases —
strings on which Viterbi and the reference happen to agree. They do not cover
common function words or general prose.

**Required fix (default):** implement the reference’s score-priority greedy
merge exactly, then add a fixed differential corpus (at least a few hundred
common words and sentences) checked against the pinned `llama-tokenize`, not
just the 23 goldens. Alternatively, if the project intentionally chooses
canonical SentencePiece Viterbi rather than llama.cpp compatibility, that is
an explicit auditor/owner scope decision and the README/claims must say the
tokenizer may differ from llama.cpp; the current “reference” framing and
release scope imply compatibility, so the default is to match.

---

## 5. Minor findings

- **QF-1 (robustness):** `_is_normal_piece` does
  `self._token_types[idx] == 1` without a length check. A caller passing a
  `token_types` sequence shorter than `tokens` gets `IndexError` during
  `encode`. Reproduced with a 3-entry list. Guard with
  `idx < len(self._token_types)` or validate at construction.
- **QF-2 (test coverage):** the new SPM mixed-text tests assert the
  implementation’s current no-prefix behaviour rather than the reference’s.
  They must be regenerated from the reference, not hand-written to match the
  code.
- **QF-3 (claims):** the ledger/README upgrades are not accepted until G2 is
  signed. Row 8 is correctly `PARTIAL`; row 7 (GPT-2) and row 9 (`add_bos`)
  are accurate. The README’s “all 7A-3 goldens pass” is true but is not
  evidence of general reference compatibility; if the Viterbi is retained by
  an explicit scope decision, that wording must be narrowed.

---

## 6. Evidence / reproduction

- Reference binary: built from the pinned tarball
  `llama.cpp@149f5641b931aaf33697d70f9abc90c3e5300247`; it matches all 11 SPM
  goldens.
- `audit/evidence/G2/7B/audit-probes/probe_commands.log` — exact commands and
  outputs.
- `audit/evidence/G2/7B/audit-probes/probe_reference_diff.py` — reproducible
  reference-vs-candidate differential (uses `LLAMA_TOKENIZE` if available).
- Candidate lanes: `audit-7b-*.log` in the audit run (75 tokenizer / 128 CPU /
  24 GPU / 12/12 CPU-only / claims PASS).
- Fixture provenance: upstream sha256 `270cba1b…`; fixture sha256
  `8577a797…`; scores/tokens/types match the upstream GGUF.
- Reference source: `src/llama-vocab.cpp` at the pinned commit, SPM tokenize
  path and `llm_tokenizer_spm_session`.

---

## 7. Gate impact

- **7B:** FAIL. G2 **not signed**.
- **7C:** remains blocked (G2 is not signed).
- **Release/G6:** remains blocked.
- **7A-9:** unchanged and accepted.
- **Blocker IDs:** **BLOCKER-7B-1** (SPM special-token prefix),
  **BLOCKER-7B-2** (SPM algorithm).
- **Resubmission:** coder fixes both, adds reference-generated differential
  vectors, QAQC re-runs, then the primary audit re-reviews. Do not merge the
  current branch into `vibe/phase7-220201`.

---

## 8. Sign-off

**7B decision: FAIL — G2 NOT SIGNED.** The package is close, but it does not
yet reproduce the reference tokenizer on common SentencePiece text or around
special tokens. Both blockers are fixable within the existing allowed file
set (`src/tokenizer.py`, tests/fixtures, evidence).

**Signed:** DeepSeek V4.1 Flash, primary auditor — 2026-11-05.
