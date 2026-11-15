# 7G-C (C3) — pre-registered prompts for the decisive-margin goldens

**Pre-registration (committed before any run).** The two G6 Q4_K_M mixed
k-quant prompts are INCONCLUSIVE at the 1.0-logit decisive threshold because
step 0 is already below it (margins 0.95/1.086 and 0.749/0.781 — G6-QF-3).
Per the closure brief C3, option (a): add prompts whose *first* steps are
decisive, chosen **before** the run from the shape of the task, not from any
engine or reference output:

| file | prompt text (verbatim, no trailing newline beyond the one shown) | why it should be decisive at step 0 |
|---|---|---|
| `prompt3.txt` | `The capital city of France is named\n` | strongly-forced one-token factual completion; the next token (` Paris`) should dominate by many logits on both implementations |
| `prompt4.txt` | `The opposite of hot is cold. The opposite of big is\n` | paired-antonym continuation with a single obvious completion (` small`), same argument |

Design rule (pre-registered): completion-style raw text. No chat template, no
question mark (a question invites many plausible continuations), the final
token leaves exactly one natural continuation. Same style as the G6
`prompt1`/`prompt2` files (plain prose, no system framing).

Acceptance for this package (brief C3): the **strict 16-step result stays
recorded verbatim** (unchanged FAIL — the strict gate never passes on this
model), and the **decisive result** is recorded with its margins. A decisive
PASS requires the decisive walk to compare ≥ 1 steps with matching token IDs
(`DECISIVE_MARGIN_THRESHOLD` stays 1.0 — not widened).

Run matrix (Q4_K_M only — that is the flavor whose goldens are INCONCLUSIVE;
`golden/README.md` in the G6 bundle keeps the Q6_K PASS):

- `ref-c3-prompt3` / `ref-c3-prompt4`: pinned `golden_ref` artifacts,
- `rework-c3-q4km-prompt3` / `rework-c3-q4km-prompt4`: our engine, compared
  against them by `scripts/qa/real_gguf_golden.py` (engine tokenization mode,
  as in the G6 rework).

If a pre-registered prompt still turns out indecisive at step 0, it is
recorded INCONCLUSIVE verbatim — no prompt iteration until something passes.
