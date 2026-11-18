# 13 — Test plan for adding model families (Mixtral, DeepSeek-MoE, Qwen3-MoE)

**Status:** prepared 2026-11-18 · **execution held** under DEC-016 · owner decision
needed before any stage starts.
**Profile:** gfx1150 only (Radeon 890M, 92 GiB RAM, ~45.97 GiB GTT, ROCm 10.1).
**Basis:** HO-001 (build/support surface), HO-007 (qwen35moe baseline), HO-008
(family probe, DEC-026), `workflow/MODELS.md`.

---

## 1. Objective and the definition of "capability added"

Add at least one non-Qwen family to the signed engine, proven by **correctness
parity first**, not by "it produced text".

A family is **added** only when all six hold:

| # | Criterion | Evidence |
|---|---|---|
| A1 | The engine recognizes the GGUF architecture and refuses unknown ones with `model_family_not_supported` (a named refusal, not the PLE message) | `tests/core/model_family_test.cpp`; CLI run |
| A2 | It loads the pack: every tensor mapped, sizes reported, no unread tensors | load log; tensor inventory vs reference |
| A3 | **Token parity**: 3 fixed prompts × 16 greedy tokens are identical to llama.cpp on the same GGUF | token-ID diff, zero mismatches |
| A4 | **Layer parity**: per-layer hidden-state dumps agree within a stated tolerance, and teacher-forced KL is below the stated bound | `compare_dumps`/`kl` output |
| A5 | Envelope and stability: peak GTT, `dmesg` clean, no reset | `amd-smi` samples, `dmesg` |
| A6 | **Regression**: the qwen35moe and qwen4exp paths are unchanged — the HO-007 run still emits the recorded 32 token IDs | bit-identical re-run |

No performance, throughput or support claim is made by any stage. Numbers are
observations until a separate benchmark handoff says otherwise.

## 2. Why this is not a flag change (what the probe proved)

- `include/strata/artifact/model_family.hpp` knows exactly two families:
  `qwen4exp`, `qwen35moe`. Everything else is `Unknown` and is refused.
- `src/program/generate.cpp:3644-3656` dispatches only `qwen35moe` to its own
  engine (`src/qwen35/`); every other file falls to the generic engine.
- The generic engine is **PLE-mandatory** (`generate.cpp:4810-4823`): no
  `per_layer_token_embd.weight` → refuse. Mixtral and DeepSeek have no such
  tensor, and `--no-ple` is a refused diagnostic.
- The `qwen35` path is the template: a 4,146-line engine, an 832-line reference
  (`q36ref.cu`), a 399-line kernel header, and a parity harness under
  `tools/qwen35/` that compares per-layer dumps, greedy tokens and teacher-forced
  KL against llama.cpp.

So "adding a family" = enum + geometry + loader + forward + reference + harness,
~5 layers of work, with the q36 port as the worked example.

### One cost fact worth knowing

Upstream **removed** a separate DeepSeek engine in `e5806740a`
("DeepSeek out (6/7)"): 112 files, 49,354 lines, `src/dsv41`, `strata-dsv41`,
`tools/dsv41_lab`. It is present in tags `v0.2.12`/`v0.2.13` and absent from
`v0.2.14`+. That engine targeted **DeepSeek V4.1-Flash**, not the 16B MoE, so it
is not a drop-in — but it is prior art for a second family as a separate target,
and worth reading before writing a DeepSeek path.

## 3. Test strategy

The project already has the right shape: **reference first, parity gates, then a
baseline**. Copy it.

```text
GGUF + token IDs
      │
      ├─ llama.cpp (pinned, CPU)  ──► dumps: per-layer hidden, greedy ids, logits
      │
      └─ strata (new family)      ──► same dumps
                    │
                    └─ compare: tokens (exact) → layers (tolerance) → KL (bound)
```

- **Oracle:** llama.cpp built locally at a **pinned commit**, same GGUF, same
  token IDs, greedy. Pin and hash the binary; record the build command.
- **Tokenizer** is verified *before* any inference: encode/decode parity with
  llama.cpp on the fixed prompts.
- **Tolerance policy:** tokens are exact (no tolerance). Layer dumps use a
  relative-error bound fixed **before** the first comparison and recorded in the
  handoff; a bound is never widened after seeing a failure — that is a deviation.

## 4. Stages and gates

Each stage is a separate handoff, with its own evidence bundle. A failed gate
stops the chain; it does not get "adjusted".

### S0 — Oracle and harness (no engine change)

- Build llama.cpp at the pinned commit; run Mixtral Q3_K_M and DeepSeek Q4_K_M
  on one prompt, 16 tokens, greedy; save token IDs, per-layer dumps, logits.
- Verify the tokenizer against the engine's `tools/strata_tokenizer.py`.
- Write the prompt set (3 prompts: prose, code, list) and the token-ID files.
- **Gate:** reference outputs reproducible from a clean build; hashes recorded.
- Deliverable: `workflow/evidence/HO-0xx/` + a reusable harness script.

### S1 — Recognition and refusal

- Add the arch to `ModelFamily`, the arch string mapping, and `model_family_runs`.
- Unit tests: known arch → family; unknown arch → refusal; **dense `llama` must
  not be mistaken for Mixtral** (the arch string is shared — detect expert
  tensors before claiming MoE).
- **Gate:** `strata --families` reports the new family; a dense Llama GGUF is
  refused with the right message; `model_family_test` green.

### S2 — Geometry and layout

- Block count, head counts, head dims, GQA ratio, rope base/scaling, expert count,
  top-k, shared-expert presence, vocab, norm eps — all **read from GGUF metadata**,
  not assumed.
- **Gate:** printed geometry matches the reference model's config for every field,
  field by field.

### S3 — Load without forward

- Map every tensor; refuse on missing/extra; report bytes per tensor class.
- **Gate:** tensor inventory matches the reference's list exactly (names + shapes);
  no silent skip; load completes without allocation beyond the pack size + KV.

### S4 — Layer parity (short context)

- Dump per-layer hidden states for a 4-token prompt; compare to the reference.
- **Gate:** every layer within the pre-registered bound; the worst layer is named
  in the report; a mismatch is investigated, not averaged away.

### S5 — Token parity and KL

- 3 prompts × 16 greedy tokens: **zero** mismatches.
- Teacher-forced KL over 16 steps below the pre-registered bound; near-ties
  reported (the q36 practice).
- **Gate:** exact token match; KL within bound; otherwise stop and rework.

### S6 — Baseline, envelope, regression

- One low-tier run at a documented context, with `amd-smi` sampling and `dmesg`.
- Re-run the HO-007 command: the 32 token IDs must be **bit-identical**.
- **Gate:** envelope recorded, no faults, regression exact; baseline signed.

### S7 — QAQC, audit, owner acceptance

- Independent QAQC re-runs the acceptance commands; auditor verifies claims;
  architect signs; owner accepts (Mistral 4 audit optional per DEC-019).

## 5. Family order and cost

| Order | Family | Arch | Pack (downloaded) | Why this position |
|---|---|---|---|---|
| **1** | Mixtral 8x7B v0.1 | `llama` | **Q3_K_M, 18.96 GiB** | Downloaded; simplest routing (top-2 of 8); forces the dense-vs-MoE arch detection that will recur; new tokenizer (SP) |
| **2** | DeepSeek-MoE-16B-base | `deepseek` | **Q4_K_M, 10.10 GiB** | Downloaded; smallest; distinct arch string (clean dispatch); fine-grained + shared experts (top-6 of 64) is the real routing work |
| 3 (optional) | Qwen3-30B-A3B | `qwen3moe` | **not downloaded** (~18 GiB at Q4) | Architecturally closest to `qwen35moe` (GQA + top-8 MoE); cheapest *if* a pack is fetched, but it teaches the least about new families |

**Recommendation:** Mixtral first. It is the hardest *dispatch* case (arch `llama`
is also a dense model) and the easiest *math* case (top-2 routing), so it forces
the structural decisions early while the arithmetic is simple. DeepSeek second has
the opposite shape and tests whether the layout abstraction actually generalizes.

### Effort (estimates, not commitments)

| Work | Estimate | Basis |
|---|---|---|
| S0 oracle + harness | 1 day | llama.cpp build + dump tooling; mostly reuse of `tools/qwen35/` |
| S1–S3 recognition/layout/load | 1–2 days | enum + geometry tables + tensor mapping |
| S4–S5 parity | 2–3 days | the real work: attention, rope, MoE routing |
| S6–S7 baseline + review | 1 day | mirrors HO-007 |
| **Per family** | **5–7 days** | q36 precedent: 5.4k lines engine+ref, plus harness |

These are working estimates with a stated basis; they are not measurements, and a
handoff that exceeds them is a deviation, not a silent overrun.

## 6. Risks and mitigations

| Risk | Why it bites | Mitigation |
|---|---|---|
| Dense `llama` misread as Mixtral | Same arch string | S1 requires expert-tensor detection + a dense-Llama refusal test |
| Quant dequant drift | Q3_K_M/Q4_K_M block formats | The engine already has dequant parity tests; run them for the family's tensor shapes before forward parity |
| Tokenizer mismatch | SP vs BPE changes every token | S0 verifies encode/decode before any inference; a tokenizer bug looks like a model bug |
| RoPE/attention assumptions | Head dims, GQA, rope base differ per family | All read from metadata in S2, asserted field by field |
| Routing semantics | top-k normalisation, shared experts, softmax placement | S4 layer parity catches it; do not "fix" by relaxing the bound |
| Memory | Mixtral Q3 + KV near the Qwen peak | S3 records allocation; S6 samples GTT |
| Scope drift to "make it fast" | Correctness is the goal | Guard rail: no perf claim; benchmarks are a separate handoff |

## 7. Abort and escalation

- **Stop** if S4 layer parity fails after the planned investigation and the
  difference is structural (wrong attention/MoE semantics): write a deviation,
  do not widen tolerance.
- **Escalate to the owner** if a family needs a change larger than a localized
  path — that is DEC-021 **T2/T3** territory and may reopen Route 3.
- **Never** declare support because output "looks right"; A3 is exact tokens.

## 8. Handoff skeleton (for the architect, once the hold lifts)

| ID | Scope | Stage |
|---|---|---|
| HO-010 | reference oracle + harness (llama.cpp pinned, prompts, dumps) | S0 |
| HO-011 | Mixtral recognition, geometry, load | S1–S3 |
| HO-012 | Mixtral layer + token parity | S4–S5 |
| HO-013 | Mixtral baseline, regression, signoff | S6–S7 |
| HO-014 | DeepSeek-MoE (same template) | S1–S7 |
| HO-015 | Qwen3-30B-A3B (optional, needs a pack) | S1–S7 |

Each must carry: base commit, the pinned llama.cpp commit, the tolerance values,
the prompt IDs, the evidence paths, and the guard rail "no perf claim".

## 9. What the owner is deciding

1. **Lift DEC-016** for S0 only (oracle + harness, no engine change) — the
   cheapest way to start, and useful even if the family work is later cancelled.
2. Or lift it for the full **S0–S7 for Mixtral**.
3. Or keep the hold and use this plan as a costed annex to the route decision.

Nothing in this plan changes the signed baselines; the qwen35moe regression gate
(A6) exists to prove exactly that.
