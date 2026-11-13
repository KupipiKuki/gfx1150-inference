# QAQC report — wp/7B-tokenizer (Gate G2), candidate 70c5ab2

**Reviewer:** QAQC (this review) · **Date:** 2026-11-06 (UTC)
**Parent:** `8426ec6` (vibe/phase7-220201 head, 7A-9 merged) · **Candidate:** `70c5ab2`
**Branch head at review time:** `4b4fdfb` (candidate + evidence-only commits)
**Verdict: PASS** — all four 7B work packages verified independently; no blocker found.

## Scope (brief §1)

The candidate diff touches exactly the allowed set: `src/tokenizer.py`,
`src/inference.py` (only the two BOS call sites — verified line by line),
`tests/**`, `tests/fixtures/**` (the SPM vocab regeneration + the golden's
recorded fixture hash + PROVENANCE + `make_fixtures.py`), `README.md`,
`audit/CLAIMS_LEDGER.md` (tokenizer-claim rows 7/8/9 only). No
`gguf_parser.py`, CMake, packaging, CI, ledger arithmetic, or other packages'
evidence. The commits after the candidate are evidence-only.

## Red/green (independent, clean worktrees — not the coder's logs)

- Parent `8426ec6`: `--runxfail` on the tokenizer slice → **4 failed**
  (the four pinned bugs); default run → 58 passed, **4 xfailed** with the 7B
  reasons.
- Candidate `70c5ab2`: same slice → **75 passed, exit 0**, zero xfail markers
  left in `tests/test_goldens_tokenizer.py` (grep-verified).

## Fixture provenance (the one judgment call — verified, accepted)

- Fresh download of `tinyllamas/stories260K.gguf` matches the PROVENANCE pin
  sha256 `270cba1b…d256d` exactly.
- Parsed with the **parent's** `gguf_parser` (independent of the candidate):
  the regenerated `stories260k_vocab.json` matches the GGUF exactly on tokens,
  token types, **and all 512 unigram scores**; `add_bos_token` is genuinely
  absent from the GGUF; merges empty.
- The golden diff parent→candidate is **one line** (`vocab.fixture_sha256`);
  every `token_ids` vector is byte-identical, and the GPT-2 fixtures are
  untouched. The candidate vocab equals the parent vocab plus the `scores`
  key — nothing else.
- The golden's recorded `fixture_sha256` equals the actual fixture sha256, and
  every PROVENANCE registry hash matches the file on disk (both families).
- Conclusion: adding the upstream scores to the vocab fixture is sound input
  data, not a golden edit; `spm_contraction_dont` is now reproducible from the
  fixture because the fixture finally carries what the reference used.

## Adversarial probes (31, written for this review — `probe_qaqc_7b.py`)

Candidate: **31/31 OK**. Parent: the 10 feature probes are ABSENT (expected
red) and B2 (`gpt2 default must not add BOS`) is BAD on the parent — the old
bug reproduced. Notable edge results on the candidate:

- longest match over a triple-overlapping special set; consecutive and
  at-edge specials; mixed `hi<EOT>there`; look-alike stays ordinary;
  `parse_special=False` literal; an empty-string special token cannot loop;
- 3×3 add_bos matrix (metadata absent/true/false × argument None/true/false)
  exactly per precedence; the real stories260K GGUF through
  `from_gguf_metadata` reproduces the golden BOS case;
- Viterbi edges: byte-only input falls back (`▁`,`<0x01>`,`<0x02>`), dummy `▁`
  only at offset 0, 100-char word deterministic, zero-score vocab and
  byte-only vocab deterministic, stall mid-codepoint names the stalling byte
  (`0xA9`), lone surrogate → `ValueError` (no `UnicodeEncodeError` leak),
  empty/whitespace-only input;
- GPT-2: all six contraction suffixes, tabs/newlines, underscores
  (`a_b_c` → `a`,`_`,`b`,`_`,`c`), minimal-vocab chunk path, unmappable `!`
  raises naming `0x21`;
- all 23 goldens recomputed independently; `decode(encode(x))` round-trips
  every literal golden prompt.

## Lanes reproduced (this review's own runs)

| lane | parent | candidate |
|---|---|---|
| CPU `pytest -m "not gpu"` | 111 passed, 4 xfailed | **128 passed** |
| tokenizer slice (`--runxfail` too) | 4 failed | **75 passed, exit 0** |
| GPU `pytest -m gpu` (real extension) | 24 passed | **24 passed** |
| `test_cpu_only.py` / `-O` | — | **OK / OK (12/12)** |
| `scripts/qa/check_claims.py` | PASS | **PASS** (0 findings) |

The CPU-lane delta (+13 selected, −4 xfailed) is exactly the four xfails
becoming real tests plus the new QAQC tests. GPU lane identical. Worktree GPU
runs used the main tree's `build/matmul_module.so` via `PYTHONPATH` (the
extension is unchanged — no C++/CMake file in the diff).

## Code review notes (no blockers)

- The Viterbi candidate restriction to NORMAL pieces is what makes
  `spm_control_token_literal` pass (control tokens are never ordinary
  candidates); the byte fallback is penalized by SentencePiece's unk-penalty
  convention (`min normal score − 10`) because the real GGUF gives byte tokens
  score 0.0 — a naive sum-of-scores would degenerate to all-byte output.
  Both choices are pinned by goldens, not just by reasoning.
- Stall reporting names the byte at the last reachable position — probed
  mid-codepoint (C6).
- The GPT-2 regex equivalence classes (`[^\W\d_]`, `[^\s\w]|_`) are
  golden-verified; the two documented deviations (combining marks as word
  chars, `\d` = Nd only) affect no golden case and are recorded in
  `notes.md`.
- `tests/test_cpu_only.py` flips the synthetic scores to negative (real
  unigram shapes) because the old increasing scores pinned the removed greedy
  behavior; the assertion itself is unchanged in intent. Accepted.

## Verdict

**PASS.** 7B-1/7B-2/7B-3/7B-4 are all implemented, golden-verified, and
independently reproduced. G2 can be signed. 7C remains unstarted, as the brief
requires; the release stays blocked on the gate process (7A-9 already passed).
