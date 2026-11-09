# 7F-2 — Real-GGUF goldens vs pinned llama.cpp (G6 evidence)

## Result (read this first)


**Rework (2026-11-08, PHASE7_7F_REWORK_BRIEF.md): BLOCKER-7F-2 fixed**
(engine tokenization now reference-exact on all three prompts) **and
BLOCKER-7F-3 adjudicated**: the strict 16-step criterion FAIL is kept
verbatim, and a pre-registered decisive-margin criterion (token IDs exact
while the top-1 margin on BOTH sides is >= 1.0 logit, walk stops at the
first indecisive step) is added. Current outcomes:

| Run | Model | Tokenizer (rework) | Strict 16-step | Decisive-margin (>= 1.0 both sides) |
|---|---|---|---|---|
| rework q4km-prompt1 | TinyLlama Q4_K_M | **exact** (31/31) | FAIL — first fork step 14 (margins 0.031/0.156) | **INCONCLUSIVE** — step 0 indecisive (margins 1.086/0.950) -> walk stops, 0 compared |
| rework q4km-prompt2 | TinyLlama Q4_K_M | **exact** (35/35) | FAIL — first fork step 3 (margins 0.008/0.059) | **INCONCLUSIVE** — step 0 indecisive (margins 0.781/0.749) -> 0 compared |
| rework q6k-prompt1 | TinyLlama Q6_K | **exact** (31/31) | FAIL — first fork step 4 (margins 0.164/0.113) | **PASS** — steps 0-1 decisive (margins >= 1.78) and token-exact; stops at the indecisive step 2 (margins 0.266/0.203) |

Reading: **where the two implementations produce decisive evidence
(margin above the measured 0.3-0.9 FP16-vs-F32 noise), the greedy tokens
are exactly equal** (Q6_K). At near-tie steps (margins below the noise)
the chains fork for a single ~50/50 token; post-fork logits compare
different states and are meaningless (10-30 absolute, per-step in the
verdicts). Two Q4_K_M prompts contain no decisive step at all: recorded
INCONCLUSIVE, never counted as pass. Pre-fork logits: max abs diff 0.89
observed (one sample above the pre-registered 0.5 bound: reported as a
diagnostic, not widened; `logits_role: diagnostic`). The pre-rework
verdicts are kept next to the rework verdicts so both the criterion change
and the tokenizer fix are auditable.

## Original candidate result (pre-rework, kept verbatim)

**The exact-token golden does NOT pass.** Three runs (Q4_K_M prompt 1,
Q4_K_M prompt 2, Q6_K prompt 1) show the same, measured, reproducible
pattern: the engine's greedy chain matches the reference token-for-token
until a near-tie step (first forks at steps 14 / 3 / 4, at margins
0.031/0.156, 0.008/0.059, 0.164/0.113 — all below the 0.3–0.9
cross-implementation noise), then the chains fork (post-fork logits are
measured on different states and differ by 10–30 absolute). Pre-fork
logits agree within ≤0.9. Recorded, not explained away: no flavor claim
was promoted (claims 5/6 unchanged), and the tolerance bound was not
widened. The pre-rework runs fed the reference prompt IDs
(the engine tokenization diverged — see the tokenizer finding below,
fixed by the rework).

## Provenance

* Engine: this repo (`src/inference.py`, HIP FP16/Q4_K/Q6_K kernels, gfx1150).
* Reference: **llama.cpp commit `7d7f0287530bc8981690f361d8c1627dbae1c99a`**
  (cloned 2026-11-08, `--depth 1` master; CPU backend, default flags;
  `llama-ref` program source: `golden_ref.cpp`, in `qaqc-probes/` in the
  bundle root — checks its output files open, argmax over raw logits,
  `llama_tokenize(add_special=true, parse_special=false)`).
* Models (not committed; acquisition below):

| File | sha256 | bytes |
|---|---|---|
| tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf | `9fecc3b3cd76bba89d504f29b616eedf7da85b96540e490ca5824d3f7d2776a0` | 668,788,096 |
| tinyllama-1.1b-chat-v1.0.Q6_K.gguf | `9fb2be7c8bbc0ca358ae88cef6d9e6844b81929eaffa5016a543e6f56b22cb6d` | 904,385,920 |

Acquisition (both files resolvable):

```bash
wget https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF/resolve/main/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf
wget https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF/resolve/main/tinyllama-1.1b-chat-v1.0.Q6_K.gguf
sha256sum tinyllama-1.1b-chat-v1.0.{Q4_K_M,Q6_K}.gguf   # compare with the table
```

* Prompts: `prompt1.txt` / `prompt2.txt` (fixed, committed here).
* Reference commands (run from a checkout of pinned llama.cpp with
  `golden_ref` built against it):

```bash
./golden_ref --model tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf \
    --prompt-file prompt1.txt --steps 16 --out-prefix ref
./golden_ref --model tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf \
    --prompt-file prompt2.txt --steps 16 --out-prefix ref2
./golden_ref --model tinyllama-1.1b-chat-v1.0.Q6_K.gguf \
    --prompt-file prompt1.txt --steps 16 --out-prefix ref
```

* Engine commands (from the repo root):

```bash
python scripts/qa/real_gguf_golden.py \
    --model tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf \
    --prompt-file prompt1.txt --steps 16 --ref-prefix <ref-dir>/ref \
    --out-dir <out>
# exit 1 = mismatch (the recorded outcome); --tolerance-report-only for probes
```

## Comparison contract (`scripts/qa/real_gguf_golden.py`)

Amended by the rework (BLOCKER-7F-3 pre-registration; the original strict
criterion is kept in each verdict under `strict_16_step`):

* **Prompt token IDs exactly** — the prompt tokenization must match the
  reference (the BLOCKER-7F-2 fix makes this true; the rework runs use
  `--engine-prompt-ids` so the engine's own tokenization is fed to the
  model and still has to equal the reference's).
* **Decisive-margin token IDs exactly** (`decisive_margin`): while the
  top-1 margin on BOTH sides is ≥ `DECISIVE_MARGIN_THRESHOLD` (1.0
  logits — above the measured noise), greedy IDs must match exactly;
  the walk stops at the first below-threshold step (reported as the
  decisive fork). Zero compared steps = `INCONCLUSIVE`, never a pass.
* **Logits/probabilities are diagnostics**:
  `LOGITS_MAX_ABS_DIFF = 0.5` / `PROBS_MAX_ABS_DIFF = 0.02` are recorded
  per run (matching-state noise: max 0.89 observed, one sample above the
  0.5 bound — reported, never widened silently); they do not gate `pass`.

## Artifacts here

* `verdict-q4km-prompt1.json` / `verdict-q4km-prompt2.json` /
  `verdict-q6k-prompt1.json` — full comparison: per-step
  `max_abs_diff`, top-1 margins (both sides), argmax-probability
  differences, top-8 logit excerpts for the first three steps, logits
  sha256 (ours), token-id streams.
* `ref-*.tokens.txt` / `ours-*.tokens.txt` — prompt + greedy token IDs.
* Logits blobs (2 MB each) are NOT committed; their sha256s:

| Blob | sha256 |
|---|---|
| ref q4km p1 | `fee1feae07698ff0ae63f0a741627381bb555d1c570a43dc6e1c2c1b68d9ad89` |
| ours q4km p1 | `66a199797004d58a4d3f711ba44f56e53dcc6c7608c38dbcf9185b9544af76b3` |
| ref q4km p2 | `952907a3bbf7916d7efa9e6c3d4036dc34be46cdd4c2a236a516a55ec3de0639` |
| ours q4km p2 | `1eded348473ad0dfc9bf79c58a274f556a1ea1debd0b3e54468d0876e6504d04` |
| ref q6k p1 | `2ac130e99d5345aacdaa86ce90fbedbff9eae72dcfac1c037dabbf2973bd9ea6` |
| ours q6k p1 | `cb592a4ff04aa7ede4090f404ae58d448c8dbe411fac2a86e5d874965a0a962a` |

## Recorded findings (auditor-facing; disposition after the rework)

1. **Tokenizer divergence on a real SentencePiece vocab — FIXED**
   (BLOCKER-7F-2, `src/tokenizer.py::use_ranks`; one-line fix + regression
   test; engine tokenization is now reference-exact on all three prompts,
   `../rework-tokenizer-evidence.txt`). The pre-rework verdicts keep the
   original record (`prompt_tokenization_engine_matches_reference: false`);
   the rework verdicts (`verdict-rework-*.json`) all record `true`.
2. **Near-tie fork sensitivity — adjudicated** (BLOCKER-7F-3): the auditor
   pre-registered the decisive-margin criterion; implemented as specified
   with the strict 16-step FAIL kept verbatim. Both Q4_K_M prompts contain
   no decisive step (INCONCLUSIVE): whether the Q6_K decisive PASS plus the
   honest INCONCLUSIVEs satisfy the release-scope claim is the auditor's
   call at re-review (the ledger rows 5/6/31 state the measured outcomes
   verbatim).
