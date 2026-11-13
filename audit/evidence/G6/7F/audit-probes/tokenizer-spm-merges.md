# Auditor probe — real SentencePiece GGUF with a `merges` array (G6 blocker)

**Date:** 2026-11-08
**Candidate:** `wp/7F-evidence-release` @ `baa3e87`
**Models:** TinyLlama-1.1B-Chat Q4_K_M (sha256 `9fecc3b3…76a0`), Q6_K (`9fb2be7c…cb6d`)
**Prompt files:** `audit/evidence/G6/7F/golden/prompt1.txt`, `prompt2.txt`

## Finding

`src/tokenizer.py::_greedy_merge_symbols` chooses the merge priority with

```python
use_ranks = bool(self.merge_ranks)
```

The real TinyLlama GGUFs carry **both** `tokenizer.ggml.model = "llama"`
(SentencePiece/unigram) **and** `tokenizer.ggml.merges` (61,249 entries), with
`tokenizer.ggml.scores` present but all zero. Because `merge_ranks` is
non-empty, the SPM path takes the **BPE rank** comparator instead of the
reference score comparator. llama.cpp's `llm_tokenizer_spm_session` ignores
`merges` for SPM and, with all-zero scores, merges leftmost-first.

## Reproduction (candidate, before fix)

```
prompt1 engine ids: [1,450,4996,17354,1701,29916,432,17204,975,...]   (29 tokens)
prompt1 ref ids   : [1,450,4996,17354,1701,29916,12500,29879,975,...] (31 tokens)
```

| surface | engine (BPE ranks) | llama.cpp (SPM scores) |
|---|---|---|
| `jumps` | `▁j` (432) + `umps` (17204) | `▁jump` (12500) + `s` (29879) |
| `sources` | `▁sources` (8974) | `▁sou` (3669) + `rc` (2214) + `es` (267) |
| `quoting` | `▁qu` (439) + `oting` (11427) | `▁quot` (13911) + `ing` (292) |

All three committed golden prompts mismatch the reference tokenization
(`prompt_tokenization_engine_matches_reference: false`).

## Fix verified

```python
use_ranks = bool(self.merge_ranks) and self._uses_gpt2
```

With this one-line change:

- `tests/test_goldens_tokenizer.py`: **351 passed**;
- `pytest -m "not gpu"`: **525 passed**;
- engine tokenization equals the reference token IDs exactly for
  Q4_K_M prompt1 (31/31), Q4_K_M prompt2 (35/35), and Q6_K prompt1 (31/31).

End-to-end golden with `--engine-prompt-ids` (fixed tokenizer):
`prompt_len_ours=31`, `prompt_len_ref=31`, `prompt_token_ids_match=true`;
the model still forks at step 14 (near-tie), so the exact-token golden
remains a recorded FAIL. See
`golden-q4km-prompt1-engine-tokenizer-fixed.json`.

## Impact

The 7F-2 golden runner feeds the **reference** prompt IDs to the engine by
default, so it isolated the model comparison from this defect. The real CLI
path (`engine.tokenizer.encode(prompt)`) used the wrong SPM segmentation on a
real llama-family GGUF, so end-to-end output would differ from the reference
even if the model were numerically exact. This is a G2 tokenizer regression
and a G6 release blocker.

## Required remediation

1. Fix `use_ranks` so BPE ranks apply only to byte-level BPE (`_uses_gpt2`).
2. Add a regression test whose vocabulary has `model="llama"`, zero scores,
   and a non-empty `merges` array; assert the SPM path ignores the ranks and
   matches leftmost-score segmentation.
3. Re-run the three 7F-2 goldens with `--engine-prompt-ids` and record the
   prompt-tokenization match plus the decisive-margin result.
