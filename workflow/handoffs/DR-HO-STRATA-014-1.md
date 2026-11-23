# DR-HO-STRATA-014-1 — deviation / scope-drift request

| Field | Value |
|---|---|
| **Deviation ID** | DR-HO-STRATA-014-1 |
| **Handoff** | HO-STRATA-014 |
| **Raised by** | Primary Coder (`coder-primary`, `opencode-go/kimi-k2.7-code`) |
| **Date (UTC)** | 2026-11-23 |
| **Decision owner** | Architect |
| **State** | **APPROVED with conditions** (2026-11-23, DEC-043) |

## 1. Original scope

HO-STRATA-014 §1.1–1.3: implement the DeepSeek-MoE-16B forward pass and layer-parity gate, choose shape (A) "extend the generic path" or shape (B) "dedicated path in the `src/qwen35` mould", and report the choice at AC-10. The overlay is tracked against DEC-021 T2 (currently **6 files / 234 insertions / 31 deletions** vs `baf16363`). T1 fires if the family cannot be expressed as a localized patch (structural engine change).

## 2. Proposed change

Continue HO-STRATA-014 with **shape (B)**: add a self-contained `src/deepseek/` engine path, switched to from `src/program/generate.cpp` for `deepseek` GGUFs under `--parity-run`, instead of extending the generic GDN/QSA engine. This crosses DEC-021 T2 and is therefore a deviation requiring architect approval with a Route 3 comparison on the table (DEC-034).

Files/areas touched:
- New: `src/deepseek/ds_engine.cu`, `src/deepseek/ds_kernels.cuh`, `src/deepseek/ds_main.cpp`, `src/deepseek/dsref.cu`, `include/strata/deepseek/engine.hpp`, `include/strata/deepseek/context_fit.hpp`.
- Modified: `cmake/strata_gpu_engine.cmake`, `src/program/generate.cpp`, `tests/core/model_family_test.cpp`.
- Workflow repo (not counted against T2): `workflow/evidence/HO-STRATA-014/scripts/compare_layers.py` and bundle artifacts.

## 3. Reason

Shape (A) is not a localized patch. The generic engine in `src/core/layer.cpp`/`src/core/session.cpp` is built for two layer kinds only: GDN (`gdn_layer`) and QSA (`qsa_layer`). `qsa_layer` hard-codes dependencies on indexer tensors (`indexer.k_proj.weight`, `indexer.q_proj.weight`, `attn_q_norm.weight`, `attn_k_norm.weight`, etc.) that DeepSeek-MoE-16B does not possess (`include/strata/core/family_layout.hpp:196-220`). There is no existing standard MHA/RoPE/dense-FFN path. Adding one would be a structural change to the generic engine (DEC-021 T1), with high regression risk to the supported `qwen4exp` path.

Shape (B) avoids T1 by following the established `src/qwen35/` precedent: a dedicated engine that `generate.cpp` switches to only for `deepseek`, leaving `qwen4exp` and `qwen35moe` untouched. The cost is size: a dedicated engine is necessarily thousands of lines and several new files, crossing T2.

## 4. Impact

| Dimension | Impact |
|---|---|
| Cost / effort | High. Estimated 4,800–6,200 inserted lines in Strata (dedicated engine + reference + kernels + build plumbing). Comparable to the qwen35 engine precedent (~5,500 lines). |
| Schedule | P1 · 2 working days was the coder estimate for the original handoff. Shape B will likely need the full 2 days plus the normal gate cycle; a split into S4a (block-0 dense parity) / S4b (MoE blocks) is an alternative the architect may prefer. |
| Risk | Lower regression risk than shape A because the generic/qwen35 paths are untouched. Main risks: correctness of MHA/RoPE, MoE routing weights (no re-normalisation over selected set), shared-expert placement, dense-first block. |
| Evidence / claims | All AC-1…AC-10 evidence must still be produced. No performance or support claim is added. The layer-parity bound stays the pre-registered 5e-3 over 112 cells. |
| Dependencies | Same as handoff: oracle dump `db6eccb3…`, pack `f00ecd83…`, ROCm 10.1, `build-deepseek/`. No new third-party dependencies. |

## 5. Options

| # | Option | Pros | Cons | Recommendation |
|---|---|---|---|---|
| 1 | **Shape A: extend the generic path** | Smaller file count; reuses `--dump-layers`, session loop, MoE routing, memory management. | Structural engine change (T1): generic engine lacks standard MHA/RoPE/dense-FFN; must add them to `src/core/layer.cpp`. Touches the qwen4exp path directly; high regression risk. Still likely >300 lines. | No — T1 makes this not a localized Route-2 patch. |
| 2 | **Shape B: dedicated `src/deepseek/` engine** (proposed) | Follows proven `src/qwen35/` precedent; isolates qwen4exp/qwen35moe; implements the llama.cpp graph verbatim (`artifacts/llama-ref-graph.md`). | Large: 6–7 new files, ~5,000–6,200 inserted lines. Crosses T2. | **Yes** — the only Route-2 option that does not trigger T1. |
| 3 | **Route 3: fork + P0–P9** | Independent engine branch; no Strata overlay constraints. | Must rebase and re-validate the existing S1–S3 patch (6 files / 234 lines) on the fork; rebuild gfx1150 baseline; much larger scope than a Route-2 patch; owner scope decision required per DEC-021. | Not recommended now: the overlay is still small enough that Route 2 with a dedicated path is cheaper and reversible. |

## 6. Decision (architect)

- **APPROVED** — 2026-11-23, recorded in `DECISIONS.md` **DEC-043**.
- **T1 confirmed, independently verified.** `include/strata/core/family_layout.hpp:178-181`
  makes every layer `Attention` (QSA) or `Gdn`; the QSA tensor set at `:262-269`
  requires `attn_q_norm` / `attn_k_norm` / `indexer.*`, none of which the
  DeepSeek layout declares (`:196-220`). There is no standard-MHA path to extend,
  so shape (A) is structural (T1) and would put the supported `qwen4exp` path at
  regression risk for a feature it does not need.
- **T2 reviewed, Route 2 continues.** Route 3 would remove the rebase cost of the
  overlay, but the ~5k lines are **additive new files** (`src/deepseek/**`); the
  upstream-facing edits stay at three small hunks (`cmake/strata_gpu_engine.cmake`,
  the `generate.cpp` dispatch, the test). A pin bump therefore rebases ~100 lines,
  not 5,000, and T3's rebase-conflict trigger is not at risk. T4 (second hardware
  class) and T5 (independent machine-gated engine with its own API) have not
  fired — gfx1150 only, no product API — and those, not size, are what would make
  a fork cheaper. **Re-review the calculus** if the DeepSeek path ever needs
  changes to shared code (`src/core/**`, shared kernels) rather than new files.
- **Conditions (the scope is amended, not widened):**
  1. **Split into two increments, gated on the oracle's own per-layer
     resolution.** `HO-STRATA-014` = **S4a**: skeleton, tensor mapping, geometry,
     RMSNorm/rope/MHA, **block 0 dense FFN**, `--dump-layers` plumbing,
     `--parity-run`, tests, comparison tool. Gate = layer 0 at 4 positions
     (4 cells). **`HO-STRATA-015`** = **S4b**: the MoE blocks (router, top-6 with
     **no** renormalisation, 2 shared experts, expert matmuls). Gate = layers
     1–27 (108 cells) and then the full 112-cell AC-5.
  2. **`dsref.cu` is out of scope.** llama.cpp's dumps are the reference for S4;
     a second in-repo implementation would double the parity work with no gate
     value before any optimisation exists. A reference path is a later, separate
     work package if the engine is ever optimised.
  3. **The engine stays deliberately simple:** no expert pooling/cache/streaming,
     no batching, no MTP, no new fast-path kernels — correctness only. Reuse the
     existing dequant/GEMM where the arithmetic is identical.
  4. **The shared-file hunks stay minimal** (dispatch + build + test); each
     increment re-measures T2 and records the cumulative number.
  5. **The §12 bound is unchanged** — 5e-3, max over the cells in scope. S4a does
     not widen it to pass on 4 cells; a single failing cell stops S4a.
  6. `--parity-run` and the unchanged refusal/`--families` behaviour land in
     **S4a**, so AC-2/AC-3 hold from the first increment.
- **Updated scope / criteria / evidence:** `HO-STRATA-014` AC-5 becomes **AC-5a**
  (layer 0, 4 cells); AC-5b and the MoE §1.1 rows move to `HO-STRATA-015` with
  this file as an input. Everything else (AC-1…AC-4, AC-6…AC-10, §5 evidence,
  §6 guard rails) is unchanged.
- **Recorded:** `DECISIONS.md` DEC-043 (2026-11-23).

## 7. Consequences

If approved:
- HO-STRATA-014 proceeds with shape (B).
- The Strata overlay grows by 6–7 new files and several thousand lines; cumulative T2 is explicitly recorded.
- Qwen4exp and qwen35moe paths remain unchanged; regression gate AC-7 still runs the HO-012 command bit-for-bit.
- If the architect prefers a smaller increment, this deviation can be amended to a split proposal (S4a block-0 dense parity / S4b MoE blocks) before code starts.

If rejected:
- Work stops pending a revised approach (e.g., shape A with T1 accepted and explicit regression plan, or descoping S4).
