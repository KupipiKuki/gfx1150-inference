# 11 — Model-class support and low-tier tests (post-HO-001)

**Status:** planned; starts **after HO-STRATA-001 is SIGNED**. Not an active
handoff yet.
**Owner directive:** low-tier tests on **all model classes**, not Qwen-only.
**Current build (pinned `baf16363`):** supports only `qwen4exp`
(Qwen3.8-Flash-Next) and `qwen35moe` (Qwen3.6-35B-A3B). Mixtral 8x7B,
Qwen3-30B-A3B and DeepSeek are **not** in the compiled family list (HO-001
evidence: `--families`, `src/program/generate.cpp`).

## 1. Sequence

1. **HO-001 completes** — QAQC (Gemini) → auditor (DeepSeek, WAIVER-001) →
   architect signs. No new scope before the signature.
2. **HO-006 — model-support investigation** (read-only): a support matrix and an
   effort/risk estimate for each class; recommend the cheapest first family.
3. **Add support for the first family** as a proof of concept (a code handoff,
   with a deviation because 001 kept Strata read-only).
4. **Low-tier tests on every supported class** (the definition below).
5. **HO-005 — Route 2 vs Route 3 decision** with the low-tier results.

HO-STRATA-002/003/004 (the original test beds) are **blocked on HO-006**; they
change from "run the model" to "run the model after its family is supported".

## 2. Low-tier test definition

For each class, the smallest meaningful test, not a benchmark:

- smallest practical quant (Q2/Q3/Q4 as the family supports);
- short context (512–2,048 tokens);
- 16–64 deterministic tokens, one fixed prompt;
- correctness against the model's reference/CPU path where possible;
- record the model hash, quant, flags, raw output, environment, limits;
- **no performance, quality or support claim** beyond the recorded run.

## 3. Classes and representative models

| Class | Representative | Status in the pinned build |
|---|---|---|
| Qwen Next | Qwen3.8-Flash-Next (`qwen4exp`) | supported |
| Qwen MoE | Qwen3.6-35B-A3B (`qwen35moe`) | supported |
| Qwen MoE (smaller) | Qwen3-30B-A3B | **unsupported**; investigate |
| Mistral / Mixtral | Mixtral 8x7B | **unsupported**; investigate |
| DeepSeek | DeepSeek-V2-Lite or DeepSeek-MoE-16B | **unsupported**; investigate |

The end targets (Mistral 8x22B, DeepSeek v2/V4, Qwen Next) share the path with
their small representatives; a support claim for the small model does not
transfer to the end target without a test.

## 4. Investigation questions (HO-006)

1. **Family registration:** where is the compiled-in list
   (`qwen4exp`, `qwen35moe`) and what does an entry control? Is there a model
   catalog, a GGUF arch string, a pack, or all three?
2. **Family descriptor:** which per-family fields exist (layers, hidden size,
   experts, active experts, routing, attention, RoPE, tokenizer, chat template,
   MTP, quantization)?
3. **Reuse:** can Mixtral reuse the existing MoE routing/grouped GEMM? Can
   Qwen3-30B-A3B reuse `qwen35moe`? Does DeepSeek need MLA/attention work that
   `qwen4exp`/`qwen35moe` do not have?
4. **Model conversion:** what converts a Hugging Face model to the pack/GGUF
   form this engine expects? What is the minimal conversion for a low-tier run?
5. **Test harness:** is there a family smoke test, a tiny synthetic fixture, or
   a reference implementation to compare against?
6. **Effort/risk:** per family, S/M/L with the files/kernels that must change;
   which is the cheapest proof of concept; which is the highest risk.
7. **Support boundary:** what does "supported" mean for this engine — load,
   generate, a golden, a performance baseline? The low-tier test only needs
   load + correct short generation.

## 5. Support-matrix template (HO-006 output)

| Class | Representative | Registration | Tokenizer/template | Routing/expert layout | Attention/RoPE | MTP/spec | Quant/kernels | Effort | Risk | First low-tier test |
|---|---|---|---|---|---|---|---|---|---|---|
| Qwen Next | Qwen3.8-Flash-Next | supported | | | | | | — | — | after 001 |
| Qwen MoE | Qwen3.6-35B-A3B | supported | | | | | | — | — | after 001 |
| Qwen MoE (small) | Qwen3-30B-A3B | | | | | | | | | |
| Mixtral | Mixtral 8x7B | | | | | | | | | |
| DeepSeek | V2-Lite / MoE-16B | | | | | | | | | |

## 6. Guard rails for HO-006

- Read-only Strata checkout; no source edits, no model downloads.
- File/line references for every claim; no "supported" assertion without a
  code path.
- No performance/quality claim; the output is a support matrix and a
  recommendation.
- A family that needs a new kernel/attention path is a **large** deviation;
  the architect decides whether to add it or descope before any low-tier test.

## 7. Decision

`DECISIONS.md` **DEC-010** records: support-first, then low-tier tests on all
classes; HO-002/003/004 blocked on HO-006; no class is declared supported until
its low-tier test passes.
