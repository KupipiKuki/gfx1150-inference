# Strata / Llama 1.0.0 decision memo — research run

This directory holds a **prompt** for the Mistral-7B long run and the auditor's
**baseline memo** for comparison.

| File | Purpose |
|---|---|
| `prompt.txt` | the research prompt (manual Mistral `[INST]` format, 841 words) |
| `auditor-memo.md` | the auditor's independent memo (the comparison baseline) |
| `README.md` | this run/comparison note |

## Run

```bash
mkdir -p research/strata-memo
PYTHONPATH=build:src python3 src/inference.py \
  -m /path/to/mistral-7b-instruct-v0.2.Q4_K_M.gguf \
  --prompt-file research/strata-memo/prompt.txt \
  --max-seq-len 4096 \
  --max-new-tokens 2200 \
  --temperature 0.0 --seed 42 \
  --stats > research/strata-memo/mistral-output.md \
  2> research/strata-memo/mistral-stats.log
```

The prompt is ~1.2K tokens; 4K sequence length leaves room for the ~2K-token
memo. For a genuinely long-context run, append the full
`Strata/docs/HOW_IT_WORKS.md`, `Strata/AGENTS.md` and the llama.cpp v1.0.0
release notes before the `## Task` section, then use `--max-seq-len 24576` and
`--offload-kv-cpu`.

## Compare

Use these questions against `auditor-memo.md`:

1. **Recommendation:** does Mistral choose A/B/C/D, and is the reasoning tied to
   the supplied facts (MoE/offload already exists; llama.cpp v1.0.0 is an API
   stability release; Strata is a shipping MIT project with gfx1100 and Strix
   Halo support)?
2. **Abstraction fit:** does it identify the current project's per-layer Python
   boundary and dense-only layout as the wrong base for MoE?
3. **Honesty:** does it avoid inventing stars, licenses, hardware support or
   benchmark numbers? Does it mark unknowns?
4. **Experiments:** are the first three cheap, ordered and M0-relevant?
5. **Disagreement:** where does it differ from the baseline, and is the
   disagreement factual or a reasoning gap?

Record the output and a short diff note; do not treat either memo as
authoritative. The model's training cutoff predates the 2026-11-13 llama.cpp
v1.0.0 release, so the supplied facts are doing the work — which is exactly
what the comparison should test.
