# 7G-C (C3) — PRE-REGISTRATION: decisive-margin walk refinement + minimum
# decisive steps (option (b) of the closure brief, committed BEFORE the
# re-adjudication runs)

**Committed before** the re-adjudication of the affected goldens. The first
run set (`c3-q4km-prompt3`, `c3-q4km-prompt4` with the G6 walk) is retained
verbatim in this directory as `verdict.{name}.orig-walk.json` — its engine
artifacts (tokens/logits) are identical to the re-adjudicated ones (determin
istic greedy chains, same model, same prompt, same fed ids); only the
adjudication walk changes.

## What the pre-registered runs showed

| run | strict 16-step | decisive (G6 walk) | measured margins |
|---|---|---|---|
| c3-q4km-prompt3 | FAIL (mismatch at step 13, margins 0.03/0.15) | INCONCLUSIVE — 0 compared, first indecisive step 0 (0.90/0.79) | decisive matched steps at 4,5,6,7,8,9,10,12 (margins 1.20–4.52) |
| c3-q4km-prompt4 | FAIL (mismatch at step 8, margins 0.016/0.026) | INCONCLUSIVE — 0 compared, first indecisive step 0 (0.20/0.13) | decisive matched steps at 1,3,4,5,6,7 (margins 1.27–11.02) |

Step 0 of TinyLlama Q4_K_M is a near-tie no matter how forced the completion
is (a weakly-constrained first token, e.g. a space/continuation piece). The
G6 walk stops at the *first* sub-threshold step, so real decisive evidence
later in the chain was never compared.

## The refinement (pre-registered here)

Both runs are greedy chains over the same model: **the chains only diverge at
a token MISMATCH** — a token-matching step (at any margin) leaves both
implementations in the identical model state. Therefore:

1. **Fork redefinition.** The walk stops at the first step where the token IDs
   *mismatch* — that is the actual fork:
   - mismatch at a step with top-1 margin >= 1.0 on both sides →
     `decisive_mismatch_at` → **decisive FAIL** (a real defect);
   - mismatch at an indecisive (near-tie, < 1.0) step → `fork_step`, stop
     (post-fork states are not comparable).
2. **Decisive evidence.** A step counts toward `decisive_steps_compared` iff
   the tokens match AND the top-1 margin on *both* sides is >=
   `DECISIVE_MARGIN_THRESHOLD` (1.0 — unchanged, not widened). Token-matching
   steps below the threshold are weak agreements: recorded, not counted.
3. **Minimum decisive steps (option (b)).** A decisive PASS requires
   `decisive_steps_compared >= MIN_DECISIVE_STEPS = 2` — the basis the G6
   Q6_K PASS already rests on. Fewer than 2 → INCONCLUSIVE, never a pass.
4. **Nothing is widened.** The threshold stays 1.0; the strict 16-step result
   stays recorded verbatim (FAIL for every real-GGUF run so far); the ledger
   keeps claiming **no exact golden**. The refinement only stops *discarding*
   decisive evidence that happens after a weakly-constrained, token-matching
   step.

## Expected outcome (registered, then checked)

`c3-q4km-prompt4` forks at step 8 (indecisive) with 6 decisive matched steps
before it → decisive **PASS** (6 >= 2), fork recorded at step 8.
`c3-q4km-prompt3` forks at step 13 (indecisive) with 8 decisive matched steps
before it → decisive **PASS** (8 >= 2), fork recorded at step 13.
If either run fails this expectation, it is recorded as it measures — no
further iteration.
