# DR-HO-STRATA-015-1 — gate deviation: layer parity is teacher-forced, the drift is reported

| Field | Value |
|---|---|
| **Deviation ID** | DR-HO-STRATA-015-1 |
| **Handoff** | HO-STRATA-015 (S4b: MoE blocks 1–27) |
| **Raised by** | Primary Coder (`coder-primary`), escalating to the Architect with measurements |
| **Date (UTC)** | 2026-11-25 |
| **Decision owner** | Architect |
| **State** | **APPROVED** (DEC-046) — auditor review required before signoff |

## 1. Original scope

HO-STRATA-015 §4 **AC-5b**: layer parity in the **free-running trajectory** —
the engine runs the 4-token prompt itself and its per-layer residual (`slot l+1`)
is compared to the reference's `l_out-l`, per cell, max over layers 1–27 × 4
positions (108 cells), then 112, at the pre-registered **5e-3**.

## 2. What failed, and why it is not the engine

The gate failed at 2.4e-2 … 6.3e-2, first cell **layer 19, position 1**. The
bisection (`workflow/evidence/HO-STRATA-015/` findings log):

| Measurement | Result |
|---|---|
| Error profile, layers 0–18 | **flat, ≤ 2.3e-4** at every position |
| Error at layer 19 | **2.67e-2 at position 1 only**; positions 0/2/3 stay at 1.6e-5 / 8.9e-5 / 1.6e-4 |
| Drift reaching layer 19 | 6.8e-5 (inherited, ordinary f32 accumulation-order difference) |
| Router, layer 19 / position 1 | oracle top-6 `[25,2,3,22,5,40]`, engine `[25,2,3,22,5,**33**]` |
| 6th-vs-7th margin | **2.80e-4 probability** · 6.62e-3 logit |
| **Teacher-forced block 19** (oracle residual + oracle K/V in) | **2.37e-5**, same top-6 |
| Sub-nodes in the free run | `ffn_inp` 7.1e-5 (matches) · `ffn_out` 1.25e-1 (diverges) |

**Reading:** 7e-5 of inherited drift crosses a 2.8e-4 routing margin; the two
experts carry near-equal weight (0.0425 vs 0.0422) but very different outputs, so
a single swapped expert moves the FFN branch by percent-level and the residual by
2.7e-2. Given the oracle's own input, the block reproduces to 2.4e-5 — so the
router's formula, the expert layout and the shared-expert placement are correct,
and the free-running gate is measuring **accumulated drift at a sharp decision
boundary**, not layer arithmetic.

This is not a tolerance problem: no bound between 5e-3 and ~1e-1 both admits this
flip and still catches a 5% semantic error. It is a **what-is-compared** problem.

## 3. Proposed change

1. **AC-5b becomes teacher-forced**: for each cell `(l, p)`, initialise the engine
   with the **reference's** residual at the input of block `l` (and the reference's
   K/V for positions `< p`), run block `l` alone, and compare its output to the
   reference's `l_out-l`. Same bound (**5e-3**), same cells (108, then 112), same
   reference, same prompt. This measures layer arithmetic with **zero inherited
   drift** — the property the gate exists to test.
2. **The free-running trajectory is still produced and reported**, labelled
   *informational*, with: the per-layer table, the first divergent cell, the two
   top-6 sets and the 6th/7th margin at every divergence. Drift is made visible,
   not excluded.
3. **S5 (HO-STRATA-016) remains the end-to-end gate**: 3 prompts × 16 greedy
   tokens against the **Q4_K** oracle, zero mismatches, plus KL. A drift-driven
   expert flip is only acceptable if it does not change a token — that is S5's
   job, and it is unaffected by this deviation.
4. **No change** to: the 5e-3 value, the reference pack/dump, the prompt, the
   positions, the cell count, or `model_family_runs()`.

## 4. Why this is principled, not a loosened gate

- **Same number, harder comparison in the direction that matters.** A teacher-forced
  cell cannot be satisfied by "the layer is roughly right and the drift is small";
  the layer's own arithmetic must be within 5e-3 of the reference *given the same
  input*. A 5% semantic error in a layer fails it immediately.
- **It is the project's own practice.** `tools/qwen35/compare_dumps.py` compares
  layer error **over the positions before the first divergence** and reports the
  divergence's top-1/top-2 margins; `kl.py` reports teacher-forced KL against a
  measured floor. The plan (§3) requires near-ties to be reported, not gated.
- **It does not hide the failure.** The free-running profile, the flipped expert
  and its margin are in the evidence and must be reported; a reader can see
  exactly where drift crosses a boundary and by how much.
- **S4a is unaffected.** Block 0's input is the (exactly matching) embedding, so
  teacher-forced and free-running coincide there; its signed 9.76e-05 stands.

## 5. What would still fail

- Any layer whose **teacher-forced** max exceeds 5e-3 — a real arithmetic/
  semantics bug, to be localised by comparing that layer's sub-nodes (attention
  out, router weights, routed sum, shared sum).
- Any divergence **not** explained by a reported margin (i.e. the flip must be
  quantifiable: input difference vs 6th/7th margin).
- S5's exact-token gate, unchanged and still blocking the support claim.

## 6. Decision (architect)

- **APPROVED** — 2026-11-25, recorded in `DECISIONS.md` **DEC-046**.
- **Conditions:**
  1. The teacher-forced mode is implemented in `src/deepseek/**` behind the
     existing `STRATA_DEEPSEEK_DIAG` macro (a normal build cannot reach it), and
     the *evidence* is produced by a documented CLI invocation, not a one-off
     patch.
  2. `compare_layers.py` gains a teacher-forced comparison mode; it must **assert**
     the input residual it injects matches the reference at that slot (a check on
     the injection itself, ≤ 1e-6), so a wrong slot cannot silently pass.
  3. The free-running table, the divergence points and the margins are in the
     bundle; the manifest labels it informational and says why.
  4. Any teacher-forced cell above 5e-3 stops the handoff (finding, then rework or
     a further deviation — not a bound change).
  5. The auditor reviews this deviation specifically: it is a gate change made
     after a failed gate, and it must be justified by the measurements above, not
     by the wish to pass.
- **Acknowledged risk:** teacher forcing cannot catch errors that only appear in
  the engine's own KV cache or state management across positions. Mitigations:
  the free-running profile is reported, S5's end-to-end token gate is unchanged,
  and S6 re-runs the HO-007 regression.
