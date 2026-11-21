# HO-STRATA-012 — DeepSeek S1–S3: recognition, geometry, tensor inventory

| Field | Value |
|---|---|
| **ID** | HO-STRATA-012 |
| **Type** | ARCHITECT_TO_CODER |
| **State** | **DONE** (SIGNED 2026-11-20) — READY → DEVIATION (DR-1 approved) → CODER_DONE → QAQC PASS (Sonnet) → AUDIT PASS → **DONE** (DEC-037) |
| **Created / updated (UTC)** | 2026-11-20 |
| **From → To** | Architect → Primary Coder (`coder-primary`) |
| **Work package** | `strata-012-deepseek-s1` |
| **Branch / base (workflow)** | `wp/strata-012-deepseek-s1` / `main` at the branch point (record the SHA) |
| **Branch (Strata checkout)** | `strata-012-deepseek-s1`, cut from `baf16363…` (record the new branch SHA) |
| **Priority / timebox** | P1 · 2 working days |
| **Owner task** | OT-STRATA-001 (S1–S3 authorized 2026-11-20, DEC-033) |
| **Plan** | `planning/strata-engine/13-family-support-test-plan.md` §4 (S1–S3) |

## 1. Purpose

Teach the engine to **recognize** the `deepseek` architecture, **read its
geometry**, and **inventory its tensors** — and to refuse it cleanly when asked to
run, because the forward pass is not implemented yet.

This is the first handoff that changes Strata source. It is deliberately bounded:
no kernels, no attention, no routing, no tokenizer. Those are S4–S5, and they are
not authorized here.

Why DeepSeek first: its architecture string is unambiguous (`deepseek`, not a
shared `llama`), its tokenizer **is** supported at the pin
(`tokenizer.ggml.pre = deepseek-llm`, which `strata_tokenizer.py` already
accepts), and the pack is 10.10 GiB.

## 2. The pack's actual geometry (verified by the orchestrator)

Read from the GGUF header of
`deepseek-moe-16b-base-q4_k_m.gguf` (10,850,181,856 B, SHA256 `f00ecd83…`,
363 tensors):

| Key | Value |
|---|---|
| `general.architecture` | `deepseek` |
| `deepseek.block_count` | **28** |
| `deepseek.embedding_length` | **2048** |
| `deepseek.attention.head_count` | **16** |
| `deepseek.attention.head_count_kv` | **16** (MHA, not GQA) |
| `deepseek.expert_count` | **64** |
| `deepseek.expert_used_count` | **6** |
| `deepseek.expert_shared_count` | **2** |
| `deepseek.expert_feed_forward_length` | **1408** |
| `deepseek.feed_forward_length` | **10944** |
| `deepseek.leading_dense_block_count` | **1** — block 0 is a **dense** FFN |
| `deepseek.rope.freq_base` | **10000.0** |
| `deepseek.attention.layer_norm_rms_epsilon` | **1e-6** |
| `tokenizer.ggml.model` / `.pre` | `gpt2` / `deepseek-llm` |

The dense first block is a real structural difference from the Qwen families:
a loader that assumes "every block has experts" will mis-map the first one.

## 3. Scope (in)

1. **Recognition.** Add `DeepseekMoe` to `ModelFamily`, the `deepseek` arch
   mapping, and the family title. `model_family_runs()` stays **false** for it
   until S4/S5 land, so the engine refuses rather than mis-runs.
2. **Refusal quality.** `strata --native <deepseek.gguf>` must exit non-zero with
   the named `model_family_not_supported` message — **not** the PLE message and
   **not** "unknown architecture".
3. **Geometry.** Read the §2 keys into `ModelGeometry` (or the deepseek-specific
   fields), with the shared-expert count and the leading dense block represented
   explicitly. Values must come from metadata, never from constants that happen to
   match.
4. **Tensor inventory.** Add the deepseek layout/tensor expectations and a
   **read-only inspection mode** (`--inspect <gguf>`, no GPU, no forward) that
   prints: detected family, every geometry field, and every tensor name + shape,
   then exits 0. It must refuse a file whose tensors disagree with the metadata.
5. **Tests.** Extend `tests/core/model_family_test.cpp` (and any geometry/layout
   test) for: arch → family; unknown arch refused; deepseek geometry fields;
   layout completeness for deepseek; the dense first block.

## 4. Out of scope

- Any forward pass, kernel, attention, or MoE routing code (S4–S5).
- Tokenizer changes (DeepSeek already works).
- `qwen4exp` / `qwen35moe` behaviour changes of any kind.
- Model conversion, downloads, or performance work.
- OLMoE (separate work package).

## 5. Acceptance criteria

| # | Criterion | Check |
|---|---|---|
| 1 | `deepseek` is a recognized family with a title | `model_family_test` green; `--inspect` prints it |
| 2 | `--native` on the pack refuses with the **named** message, exit ≠ 0, no PLE text | run it; quote the line |
| 3 | `--families` still prints exactly `qwen4exp qwen35moe` | run it |
| 4 | Geometry read matches §2 field by field | `--inspect` output vs §2 table, one row per field |
| 5 | `--inspect` prints **363** tensors with name + shape, exit 0 | count + a sample diff vs the reference list |
| 6 | A GGUF with a metadata/tensor mismatch is refused, not silently loaded | synthetic or mutated fixture; record the refusal |
| 7 | **Regression:** the new build produces the HO-007 32 tokens exactly | run the HO-007 command with the new binary; compare IDs |
| 8 | The **signed** binary is untouched | `build-hip/strata` still `d58ee239…`; new build in a separate directory |
| 9 | Patch size recorded against DEC-021 **T2** (>5 files or >300 lines ⇒ flag) | `git diff --stat` in the Strata checkout |
| 10 | Patch exported into the workflow evidence | `patches/0001-…patch` + `git apply --check` clean |

## 6. Evidence required

`workflow/evidence/HO-STRATA-012/`: `manifest.md`, `commands.log`, per-command raw
transcripts, the `--inspect` output, the refusal output, the regression token IDs,
the unit-test output, `patches/` (the exported patch), `hashes.txt` (immutable
only), `hashes-notes.txt` (commit pins **with** digests, DEC-024).

## 7. Guard rails

- **Edits are authorized in the Strata checkout for this handoff only** (DEC-033):
  work on the `strata-012-deepseek-s1` branch, never on `main`, and export the
  patch. Outside this handoff the checkout stays read-only (DEC-008).
- **Build in a separate directory** (`build-deepseek/`), so the signed
  `build-hip/strata` and its hash stay intact for regression.
- No forward path: if a change would make the engine *run* deepseek, stop — that is
  S4.
- No qwen edits; the regression in AC-7 is the proof.
- If the patch exceeds T2's bound (5 files / 300 lines), stop and raise a deviation
  rather than continue silently.
- No secrets, no weights, no perf claim.

## 8. Definition of Ready — MET

- [x] ID/type/from/to/title/work package
- [x] Workflow and Strata branches named; base recorded
- [x] Scope/out-of-scope explicit
- [x] Inputs available (pack verified; geometry in §2; Qwen baselines signed)
- [x] Every criterion has a check
- [x] Evidence requirements runnable
- [x] Guard rails explicit (including the read-only relaxation)
- [x] Dependencies resolved
- [x] Priority/timebox set
- [x] No `NEEDS_INFO`
- [x] Owner authorization (DEC-033)

## 9. Definition of Done

- [x] Family recognized; named refusal verified
- [x] Geometry matches metadata field by field
- [x] `--inspect` inventories 363 tensors, exit 0
- [x] Mismatch refused
- [x] Qwen regression exact; signed binary intact
- [x] Patch measured and exported
- [x] Evidence complete; `CODER_DONE`; QAQC handoff created

## 10. Why the refusal matters

A recognized family that the engine does not run must say so by name. Today the
DeepSeek pack dies on a PLE message that has nothing to do with the real reason.
After S1–S3 the message will be true, and S4 can start from a clean statement of
what is missing.

## 11. Signatures

| Role | Name/agent | Date | Decision |
|---|---|---|---|
| Sender (Architect) | architect | 2026-11-20 | READY |
| Receiver (Coder) | `coder-primary` | | |

## 12. Log

- 2026-11-20 Architect: created READY after the owner chose S1 on DeepSeek
  (DEC-033). Geometry in §2 was read from the pack header by the orchestrator.
- 2026-11-20 Coder: implemented S1–S3; measured patch at 6 files / 265 delta lines,
  exceeding DEC-021 T2's 5-file threshold. Raised DR-HO-STRATA-012-1 and paused
  pending architect decision. No commit, no build, no evidence bundle yet.
- 2026-11-20 Coder: patch reached 6 files / 234 insertions, raising T2; paused and
  opened `DR-HO-STRATA-012-1` instead of proceeding silently.
- 2026-11-20 Architect: **DR approved** (DEC-034) — metadata-only, no kernels; S1–S3
  resume. The trigger worked as intended: it forced a decision, not a ban.
- 2026-11-20 Coder: **CODER_DONE** at `66267d2`; patch exported and
  `git apply --check` clean; 363 tensors; named refusal; Qwen regression exact;
  signed binary untouched. Strata branch `bac859ef9` is local only (upstream is
  third-party).
- 2026-11-20 Architect: paused at the QAQC gate — Gemini returned
  `429 billing cap exceeded` and the OpenCode weekly cap is near (DEC-035). No
  work is lost; resumption starts at QAQC on `66267d2`.
- 2026-11-20 Architect: **SIGNED** → `DONE`. Auditor conditions C1–C4 closed
  (pins, fixture recipe, record corrections, state mirror). F1 accepted as scope,
  F2 carried to S4. See `HO-STRATA-012-APPROVAL.md`.
