# 7F-2 — Real-GGUF goldens vs pinned llama.cpp (G6 evidence)

## Result (read this first)

**The exact-token golden does NOT pass.** Three runs (Q4_K_M prompt 1,
Q4_K_M prompt 2, Q6_K prompt 1) show the same, measured, reproducible
pattern:

* the engine's greedy chain matches the pinned llama.cpp reference
  **token-for-token until a near-tie step**, where the top-1 margin is
  far below the FP16-vs-F32 implementation noise — then the chains fork
  (all subsequent logits are computed on different states, so their
  difference is meaningless: ~10–30 absolute);
* up to the fork, logits agree within the stated tolerance scale
  (observed pre-fork max |Δ|: 0.89 (Q4_K_M p1), 0.33 (pre-fork steps of
  p2), 0.71 (Q6_K pre-fork)).

| Run | Model | Steps matched | First fork | Margin at fork (ours / ref) |
|---|---|---|---|---|
| q4km-prompt1 | TinyLlama-1.1B-Chat Q4_K_M | 14 / 16 | step 14 | 0.031 / 0.156 |
| q4km-prompt2 | TinyLlama-1.1B-Chat Q4_K_M | 3 / 16 | step 3 | 0.008 / 0.059 |
| q6k-prompt1 | TinyLlama-1.1B-Chat Q6_K | 4 / 16* | step 4 | 0.164 / 0.113 (step 4) |

\* exact count in `verdict-q6k-prompt1.json` (`token_mismatch_first_step`).

Evidence discipline (brief 7F-2: *token IDs exactly, logits within a
stated tolerance, no "close enough"*): the outcome above is a FAIL for
the acceptance criterion — recorded, not explained away. Consequences
applied elsewhere in this bundle: no real-Q4_K_M/Q6_K flavor claim is
promoted (claim 6 stays **PARTIAL**, qualified in place; claim 5's
VERIFIED status remains the G0 synthetic-kernel evidence), and the README
"Verified release scope" states the measured outcome. A pass would have
required exact IDs over all 16 steps.

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

* **Token IDs exactly**: both prompt tokens and every greedy step;
  the pass criterion requires identical IDs for all steps.
* **Prompt states identical**: the reference's prompt token IDs are fed
  to the engine (the engine's own tokenization is computed and recorded
  — see the finding below).
* **Logits within a stated, pre-registered tolerance**:
  `LOGITS_MAX_ABS_DIFF = 0.5` and `PROBS_MAX_ABS_DIFF = 0.02` bound the
  accumulated FP16 numeric noise between the two implementations for
  *matching states*; token-ID equality is the actual acceptance gate.
  Measured pre-fork noise: max 0.89 (one step of q4km-prompt1) — i.e.
  the 0.5 logits bound is itself violated by one noise sample, so the
  logits criterion fails alongside the token criterion; the recorded
  numbers are honest about this rather than widened post-hoc.

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

## Recorded findings for the auditor (not fixed in 7F — out of scope)

1. **Tokenizer divergence on a real SentencePiece vocab (7B-scope flag).**
   The engine's `tokenizer.encode()` of the plain-text prompts does not
   match llama.cpp's on the real TinyLlama vocabulary
   (`prompt_tokenization_engine_matches_reference: false` in all three
   verdicts; e.g. prompt-1 "jumps" → engine `432,17204` vs llama.cpp
   `12500,29879`; both add BOS `1`). The G2 goldens cover the GPT-2 BPE
   and stories260K (llama) SentencePiece vocabularies; this is a real
   TinyLlama GGUF divergence in the merge behavior. Per the brief ("do
   not reopen 7A/7B/7C/7D/7E without a written auditor finding") this is
   recorded as a finding, not re-remediated in 7F.
2. **Near-tie fork sensitivity.** Exact greedy-chunk equality between an
   FP16-A-pipeline and llama.cpp's CPU path is only achievable at steps
   whose top-1 margin exceeds the implementation noise (~0.3–0.9
   logits). Any future "golden" scheme that keeps the exact-token
   acceptance must restrict the compared steps to decisive margins
   (e.g. compare until the first margin < 1.0) — a spec decision for
   the auditor, not silently applied here.
