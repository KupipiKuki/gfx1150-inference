# Architect approval — HO-STRATA-011

| Field | Value |
|---|---|
| **Handoff** | HO-STRATA-011 — OLMoE oracle extension (S0b) |
| **Architect** | architect (session model; WAIVER-001 seat) |
| **Date (UTC)** | 2026-11-19 |
| **Decision** | **SIGNED** → state `DONE`, with **AC-3 amended** by DEC-032 |
| **Evidence** | `workflow/evidence/HO-STRATA-011/` at `c73b424` |
| **Branch / base** | `wp/strata-011-olmoe-oracle` / `main` `6679e938` |

## 1. Result

The oracle now covers all three test families. For OLMoE:

```text
pack    olmoe-1b-7b-0924-instruct-q4_k_m.gguf
        4,213,512,672 B · 8c310f14…32f3f · arch olmoe
gen:    7785 15 187 187 510 14731 273 6181 310 14029 15 187 187 510 3072 273
layers  3c72636a…  [4][16][2048], 16/16 layers at 4/4 positions
logits  a73e3eae…  [16][2][2]
hashes  41/41 OK from the repo root; fresh clone also 41/41
```

Three parties reproduced the run and both dump digests bit-for-bit, and the
bundle passes a **fresh-clone** check, which is the test that would have caught
HO-010's ignored-dump problem.

## 2. AC-3 amendment (DEC-032)

As written, AC-3 required tokenizer parity. It cannot be met at the pin:

```text
UnknownPreTokenizer: This model splits text with a rule Strata doesn't have yet
('olmo'), so it isn't loaded: running it with the wrong rule would change what
it reads.
```

`tokenizer.ggml.pre = olmo`, and `tools/strata_tokenizer.py:104-112` knows only
`qwen35` and `deepseek*`. The engine **fails closed** rather than mis-tokenize,
which is the correct behaviour.

**Ruling:** for S0b, AC-3 is satisfied by *either* parity *or* a recorded engine
refusal with its reason. The oracle may use llama.cpp token IDs until an `olmo`
pre-tokenizer exists. This is an architect amendment to a criterion, recorded in
`DECISIONS.md`, not a coder converting a failure into a finding — the auditor
was right to refuse that.

**Consequence:** OLMoE needs a tokenizer patch (small: one pre-tokenizer rule) in
addition to a family path. That is **T1-relevant evidence**: the gap is not only
routing, it is also tokenization. It belongs in the S1 scope discussion, not in
this handoff.

## 3. Criteria

| # | Criterion | Status |
|---|---|---|
| 1 | Pack identity (size, SHA256, arch) | PASS |
| 2 | Harness built at the pin, provenance | PASS |
| 3 | Tokenizer parity **or** recorded refusal | **PASS as amended** (refusal recorded; FINDING) |
| 4 | Reference tokens, reproducible, truthful exits | PASS (`raw_diff_exit=1`, `normalized=0`) |
| 5 | Layer dump complete and non-degenerate | PASS |
| 6 | Logits dump, shape and layout | PASS |
| 7 | Bundle complete; hashes verify; pins carry digests | PASS after `RW-011-1` |
| 8 | No engine change | PASS (Strata clean, `baf16363…`) |
| 9 | No claim | PASS |

## 4. Rework and findings

`RW-HO-STRATA-011-1` was required: the measurements were right, the bundle was
not. Dumps were git-ignored and never committed, `hashes.txt` only verified from
the bundle directory, `check_layers.py` still hardcoded DeepSeek's 28 layers, and
the pins predated the change they pinned. All four are closed and the fresh-clone
test now passes.

Carried (non-gating, fix at the next bundle touch): the manifest's self-hash
wording, a stale entry count in the curated `test-output.txt`, and two `commands.log`
rows missing their redirects.

## 5. Limits

- The 64-expert / top-8 routing axis is **metadata only** here; the oracle does
  not exercise MoE routing. S4/S5 will.
- One quant, one prompt, 16 tokens. No quality, throughput or support claim.
- OLMoE cannot be tokenized by the engine at this pin; that is recorded, not
  worked around.

| Role | Signature | Date |
|---|---|---|
| Architect | architect | 2026-11-19 |
