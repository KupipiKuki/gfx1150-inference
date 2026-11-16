# 12 — Large-model feasibility: DeepSeek V4 Flash + MiniMax M3.1 Flash

**Status:** north-star investigation, **not an implementation commitment**.
**Sequence:** after HO-001 signs and after **HO-006** (the small-model family
support map). Does not block the small-model low-tier tests.
**Decision:** `DECISIONS.md` DEC-011.

---

## 1. Why this is a different tier

HO-006 is about small representatives (Qwen3-30B-A3B, Mixtral 8x7B,
DeepSeek-V2-Lite/MoE-16B) and the family-registration mechanics. These two are
large frontier MoEs:

| | **DeepSeek V4 Flash** | **MiniMax M3.1 Flash** |
|---|---|---|
| Total / active | 284B / 13B (V4 Flash); V4.1 Flash 552B backbone + 196B Engram, 8B input / 16B output | 428B / 23B |
| Context | 1M | 1M |
| Weights | MIT, open (Hugging Face) | open weights (Oct 23) |
| GGUF | Q4_K_M exists (Unsloth); ~167 GB weights | 2-bit ~143.9 GB; 4-bit larger |
| Architecture | MoE + hybrid compressed / DSA attention | MoE + MiniMax Sparse Attention, NVFP4 KV and MoE, DSpark draft |
| Engine gap | new attention, routing, FP4/FP8, tokenizer, conversion | new sparse attention, NVFP4, DSpark, tokenizer, conversion |

They are **not** a catalog entry. The current Strata build supports only
`qwen4exp`/`qwen35moe`; these models require new attention and quantization
paths, not just a family descriptor.

## 2. Hardware reality

- **gfx1150 (current):** 91.94 GiB RAM / 45.92 GiB GTT. Both models exceed it
  at usable quants (167 GB and 143.9 GB), even before KV/context. The engine’s
  current design pins all experts in RAM; the low-RAM/SSD mode is a different
  regime, not a proven path for these sizes.
- **gfx1100 (future):** 16–24 GB VRAM + **large host RAM** (128–256 GB) + SSD
  is the realistic target. The Strata design (VRAM hot set, RAM all experts,
  SSD table) is the right shape, but the host RAM is the gating cost.
- **780M (32 GB):** out. **MI25 (5×16 GB, gfx900):** out; legacy ISA, no
  bf16, deferred, and 80 GB is below the model size.
- **1M context:** another gap. The current measured profile is 32K; 1M needs
  KV compression/streaming that these models assume (DSA/sparse attention,
  NVFP4 KV) and the engine does not have.

## 3. Investigation questions (HO-007)

1. **Exact target:** V4 Flash (284B/13B) vs V4.1 Flash (552B/8–16B); MiniMax
   M3 vs M3.1. Which release has stable open weights, GGUF, and a reference?
2. **Attention:** what exactly do DSA/hybrid-compressed and MiniMax Sparse
   Attention require? Which parts can reuse the existing Qwen attention, and
   which are new kernels?
3. **MoE routing/expert layout:** expert count/active, routing, grouped GEMM;
   can the Qwen family path be generalized, or is it a new path?
4. **Quantization/KV:** FP4/FP8 mixed, NVFP4 KV, NVFP4 MoE; what do gfx1150
   and gfx1100 support natively, and what must be dequantized?
5. **Tokenizer/template/MTP:** SentencePiece/BPE, chat template, MTP/DSpark
   draft; what is reusable?
6. **Conversion:** the Hugging Face → pack/GGUF path; the minimal low-tier
   conversion; the license/provenance.
7. **Capacity:** Q4/Q2/1-bit sizes vs host RAM/VRAM/SSD; what is the minimum
   host; what is the measured KV footprint at a short context?
8. **Test harness:** a reference implementation (llama.cpp/vLLM) and a
   low-tier smoke test; what “supported” means for these models.
9. **Effort/risk:** XL per model; which is cheaper; what is the smallest
   proof of concept that is still honest (short context, few tokens, no
   performance claim).

## 4. Sequencing

1. **HO-001** signs.
2. **HO-006** produces the small-family support map (registration, routing,
   tokenizer, test harness). This is the learning step.
3. **HO-007** (this note) produces a capacity report + architecture-gap matrix
   + effort/risk + a go/no-go recommendation.
4. Only then an implementation decision, with a **deviation** and a hardware
   decision (gfx1100 host + RAM).
5. **HO-005** (Route 2 vs Route 3) uses both the small-model results and the
   large-model feasibility.

## 5. Preliminary assessment

- **DeepSeek V4 Flash** is the more natural first large target: MIT weights,
  a GGUF path, 13B active, and a clear V4 family lineage. The DSA/hybrid
  attention and FP4/FP8 are the hard parts.
- **MiniMax M3.1 Flash** is a strong second: 23B active, open weights, but
  sparse attention + NVFP4 + DSpark is a larger new-path surface.
- **Both** need a host beyond the current gfx1150. The first honest deliverable
  is not a run; it is a **capacity report** that says which host and quant can
  load the model and what the engine must add.
- No performance, quality or support claim until a measured low-tier run.

## 6. Guard rails for HO-007

- Read-only investigation; no model downloads, no source edits.
- File/line references for every engine claim; external sources linked and
  marked as external.
- The output is a capacity report, an architecture-gap matrix, an effort/risk
  estimate, and a recommendation — not a promise.
- A model that requires a new attention/quantization path is a **large
  deviation**; the architect and owner decide whether to fund it.

## 7. Sources (external; verify at investigation time)

- DeepSeek V4 Flash model card / Unsloth GGUF / V4 guide.
- MiniMax M3.1 Flash model card / Unsloth GGUF / vLLM day-0 note.
- The numbers above are from those sources and are **not** a measured claim on
  this host.
