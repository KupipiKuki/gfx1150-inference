# Phase 7B Remediation Brief — Tokenizer Correctness (Gate G2 resubmission)

**To:** GLM5.3 (coder)
**From:** primary auditor's FAIL audit, packaged for resubmission
**Date:** 2026-11-06
**Branch:** `wp/7B-remediation` (from `wp/7B-tokenizer` @ `d99fdb0`, the audit commit)
**Base under review:** work commit `70c5ab2`, parent `8426ec6`
**Gate:** G2 re-review. The first candidate closed all four xfails and passed all
23 7A-3 goldens, but the audit (`audit/AUDIT_7B_TOKENIZER_DEEP_2026-11-05.md`,
`audit/G2_SIGNOFF_2026-11-05.md`) found two implementation blockers. **Do not merge
until G2 is signed.** 7C stays blocked.

---

## 1. Verdict recap and what is accepted

Accepted as-is: the fixture regeneration (the stories260k vocab fixture now carries
the upstream unigram scores; the golden diff was one `fixture_sha256` line), the four
xfail removals, the green lanes (75 tokenizer / 128 CPU / 24 GPU / 12-12 CPU-only /
claims PASS), the scope, the `add_bos` precedence, the GPT-2 vectors, byte safety.

## 2. BLOCKER-7B-1 — SPM dummy `▁` prefix around special tokens

The reference (`llama.cpp@149f5641b931aaf33697d70f9abc90c3e5300247`,
`src/llama-vocab.cpp`, SPM branch of `llama_vocab::tokenize`) partitions the input into
fragments (special tokens vs raw text) and then:

```cpp
bool is_prev_special = true;                 // prefix with space if first token
// (adding the BOS keeps it true)
for (const auto & fragment : fragment_buffer) {
    if (fragment.type == RAW_TEXT) {
        std::string text;
        if (add_space_prefix && is_prev_special) text = ' ';
        text += fragment.raw_text.substr(...);
        llama_escape_whitespace(text);        // ' ' -> '▁'
        session.tokenize(text, output);
        is_prev_special = false;
    } else {                                  // special token fragment
        output.push_back(fragment.token);
        is_prev_special = true;
    }
}
```

**Rule:** every raw-text fragment that starts the input **or immediately follows a
special token** gets a leading space, escaped to `▁`. The 7B candidate only prefixed
a chunk at offset 0 (and its offset bookkeeping was computed after advancing past the
special, so even that was wrong).

Reference outputs from the pinned `llama-tokenize` (build recipe in
`audit/evidence/G2/7B/audit-probes/probe_commands.log`; binary reproduces all 11 SPM
goldens), all with `--no-bos`:

| Input | `--parse-special` (default) | `--no-parse-special` |
|---|---|---|
| `a<s>b` | `[261, 1, 268]` | `[261, 504, 419, 505, 430]` |
| `hi<s>there` | `[270, 417, 1, 383]` | — |
| `" <s>"` | `[410, 410, 1]` | — |
| `<s>b` | `[1, 268]` | — |
| `hello<s>there` | `[281, 306, 414, 1, 383]` | — |
| `<s></s>` | `[1, 2]` | — |
| `x<s>y` | `[410, 444, 1, 348]` | `[410, 444, 504, 419, 505, 422]` |

**Fix:** in `encode()`, drive the special/raw fragment loop with `prev_special`
(start `True`; raw fragment → prepend the space/`▁` iff `prev_special`, then set
`False`; special fragment → emit ID, set `True`). Fix or drop the offset bookkeeping
in `_split_special_tokens` accordingly.

## 3. BLOCKER-7B-2 — SPM segmentation algorithm

The pinned reference is **not** Viterbi. `llm_tokenizer_spm_session` splits the
(fragment) text into UTF-8 chars, seeds a priority queue with every adjacent pair
whose concatenation is a token, and repeatedly merges the highest-scoring pair:

```cpp
struct llm_bigram_spm {
    struct comparator {
        bool operator()(llm_bigram_spm & l, llm_bigram_spm & r) {
            return (l.score < r.score) || (l.score == r.score && l.left > r.left);
        }
    };
    ...
};
```

i.e. max score first, ties → smaller left index. After merging, leftover symbols that
are not tokens fall back to `<0xXX>` byte tokens per byte (`resegment` /
`byte_to_token`). This is exactly the pre-7B `_bpe_merge_symbols` with
`use_ranks=False` (heap key `(-score, left, right, ...)`) — the 7B candidate's Viterbi
must be **replaced** by that greedy merge, now that the fixture carries the real
scores. The goldens passed on both algorithms only because they sit in the
intersection; on common words they diverge:

| Input (`--no-bos --no-parse-special`) | reference | 7B candidate |
|---|---|---|
| `the` | `[265]` | `[259, 260]` |
| `and` | `[269]` | `[261, 264]` |
| `time` | `[378]` | `[259, 369]` |

**Fix:** `_encode_spiece` = normalize (prepend per §2, `' '`→`▁`), split into UTF-8
**characters** (not pre-split bytes), run the greedy score-priority merge over
`token_to_id` + `scores`, then emit each surviving symbol as its token or, if it is
not a token, as its `<0xXX>` byte tokens (raise `ValueError` naming the byte if a
byte token is missing — keeps 7B-4). Remove `_viterbi_unigram`/`_UNK_PENALTY`.
Note: do not exclude control tokens from the merge table — the reference's
`token_to_id` includes them; bigram merging cannot form `<s>` from single chars
(`<s` is not a token), which is why the literal golden passes.

**Required differential vectors (audit §7 item 3):** add a new fixture
`tests/fixtures/stories260k_differential_golden.json` — several hundred prompts
(common English words, sentences, mixed special-token text, whitespace/punctuation/
multibyte edges, seeded random concatenations of vocab pieces), each with the token
IDs from the pinned `llama-tokenize` (`-m stories260K.gguf -p <prompt> --ids
[--no-bos] [--no-parse-special]`, recording the flags per case). Extend
`make_fixtures.py` with the mode that regenerates it, and add a PROVENANCE.md row
(input = pinned GGUF sha256 + llama.cpp commit, command, output hash). Add a
parametrized test that replays every case. Do not rewrite the existing 11 SPM golden
vectors; append-only.

## 4. Minor findings

- **QF-1:** guard the short-`token_types` `IndexError` — validate the length at
  construction (raise `ValueError` if `token_types` is shorter than `tokens`); with
  the Viterbi gone, `_is_normal_piece`/`_token_types` should be removed entirely.
- **QF-2:** the SPM mixed-text tests must assert the **reference** values (§2 table),
  not the candidate's current ones. Fix `test_empty_and_whitespace_special_splitting`
  (`" <s>"` → `[1, 410, 410, 1]` with BOS), the no-duplicate-BOS test (`<s>b` →
  `[1, 1, ▁b]`), and add `a<s>b` / `hi<s>there` / `x<s>y` SPM cases.
- **QF-3:** README/ledger upgrades stay unaccepted until G2 is signed. Since the
  remediation matches the reference (no Viterbi scope decision), keep the
  "matches llama.cpp" framing but back it with the differential corpus evidence.

## 5. Allowed files (unchanged from the 7B brief + the audit)

`src/tokenizer.py`, `src/inference.py` (BOS call sites only), `tests/**`,
`tests/fixtures/**` (append-only for the 7A-3 goldens; the new differential fixture
and its PROVENANCE/make_fixtures rows are required additions), `README.md`
(tokenizer wording), `audit/CLAIMS_LEDGER.md` (tokenizer-claim rows only), docs,
`audit/evidence/G2/7B/**`. Do not touch `src/gguf_parser.py`, CMake, packaging, CI,
ledger arithmetic, or other packages' evidence.

## 6. Required checks (stop-gate)

```bash
python -m pytest -m "not gpu" -q -k "tokenizer or bpe or golden"
python -m pytest -m "not gpu" -q --runxfail -k "tokenizer or bpe or golden"
python -m pytest -m "not gpu" -q
python -m pytest -m gpu -q                      # 24 passed; unchanged
python tests/test_cpu_only.py && python -O tests/test_cpu_only.py
python scripts/qa/check_claims.py               # PASS
# differential vs the pinned reference binary (build per probe_commands.log):
LLAMA_TOKENIZE=<pinned build> STORIES260K_GGUF=<pinned gguf> \
  python3 audit/evidence/G2/7B/audit-probes/probe_reference_diff.py   # 0 diffs
# plus the new differential golden test: every case must match
```

## 7. Stop-gate QAQC (before handing back)

QAQC re-runs from clean worktrees at parent `8426ec6` and the new candidate:
red = the four xfails failing under `--runxfail` on the parent (already recorded),
green = everything above passing, **plus** a fresh differential run against the
pinned `llama-tokenize` (expect 0/N mismatches, N = the differential corpus size +
the 11 probe cases), the SPM mixed-text reference table (§2), and the lanes.
Evidence goes to `audit/evidence/G2/7B/` (`remediation-*.log`, updated `notes.md`).
Then **stop**: the primary auditor re-reviews; do not start 7C, do not merge.
