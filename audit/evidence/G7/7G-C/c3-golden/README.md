# 7G-C (C3) — re-run goldens: strict result verbatim + decisive result with margins

Model: TinyLlama-1.1B-Chat (llama-family) — `Q4_K_M` (mixed k-quant recipe)
and `Q6_K`, run on the gfx1150 host against pinned llama.cpp (`golden_ref`,
same pinned binary as 7F-2), engine-tokenization mode (BLOCKER-7F-2 fix
re-verified on every run: `prompt_tokenization_engine_matches_reference`:
true everywhere).

## Pre-registration (both committed before the runs / re-adjudication)

1. `PRE-REGISTRATION.md` (commit 7bae2f8) — the two new prompts, chosen from
   the task shape alone:
   - `prompt3.txt` — "The capital city of France is named\\n"
   - `prompt4.txt` — "The opposite of hot is cold. The opposite of big is\\n"
2. `PRE-REGISTRATION-walk-refinement.md` (commit 1943af6) — C3 option (b):
   decisive-walk refinement (a greedy chain forks only at a token MISMATCH;
   token-matching sub-threshold steps keep the states aligned and no longer
   end the walk) + `MIN_DECISIVE_STEPS = 2` for a decisive PASS.
   `DECISIVE_MARGIN_THRESHOLD` stays **1.0** — nothing is widened.

The first-run verdicts under the G6 walk are kept verbatim as
`verdict.c3-q4km-prompt{3,4}.orig-walk.json` (INCONCLUSIVE, 0 compared).

## Results (16 greedy steps, temperature 0)

| run | strict 16-step | decisive (7G-C walk) | decisive steps | fork |
|---|---|---|---|---|
| `c3-q4km-prompt3` (new) | **FAIL** (mismatch at step 13, margins 0.03/0.15) | **PASS** | 8 (margins 1.20–4.52) | 13 (indecisive) |
| `c3-q4km-prompt4` (new) | **FAIL** (mismatch at step 8, margins 0.016/0.026) | **PASS** | 6 (margins 1.27–11.02) | 8 (indecisive) |
| `readj-q4km-prompt1` (G6 prompt 1) | **FAIL** (mismatch at step 14) | **PASS** | 6 | 14 (indecisive) |
| `readj-q4km-prompt2` (G6 prompt 2) | **FAIL** (mismatch at step 3) | **INCONCLUSIVE** | 1 (margins 2.83/2.70) | 3 (indecisive, 0.008/0.059) — below the pre-registered minimum of 2 |
| `readj-q6k-prompt1` (G6 Q6_K) | **FAIL** (fork at a near-tie, step 4) | **PASS** | 3 (G6 walk: 2; ≥ 2 minimum) | 4 (indecisive) |

Every verdict JSON carries the full per-step margin list
(`per_step_summary`) and the decisive block (`decisive_margin`,
`min_decisive_steps: 2`).

## Ledger wording (rows 5, 6, 31) — unchanged in kind

No exact real-GGUF golden is claimed anywhere: the strict 16-step result
stays **FAIL** verbatim on all five runs; the decisive comparisons are
recorded with their margins; one prompt (original q4km-prompt2) stays
**INCONCLUSIVE** and is never counted as a pass.
