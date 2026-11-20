# DR-HO-STRATA-012-1 — patch touches 6 Strata files, exceeding DEC-021 T2's 5-file threshold

| Field | Value |
|---|---|
| **Deviation ID** | DR-HO-STRATA-012-1 |
| **Handoff** | HO-STRATA-012 |
| **Raised by** | Primary Coder (`coder-primary`) |
| **Date (UTC)** | 2026-11-20 |
| **Decision owner** | Architect |
| **State** | PROPOSED |

## 1. Original scope

HO-STRATA-012 authorizes S1–S3 for DeepSeek-MoE-16B-base:

- Add `DeepseekMoe` to `ModelFamily` with arch string `deepseek` and a title.
- Keep `model_family_runs()` false, so `--native <deepseek.gguf>` refuses with the named `model_family_not_supported` message (no PLE text).
- Read the §2 geometry keys into `ModelGeometry` (shared-expert count and leading dense block as explicit fields).
- Add tensor layout expectations and a read-only `--inspect <gguf>` mode (no GPU, no forward) that prints family, geometry fields, and all tensor names+shapes, exiting 0; refuse metadata/tensor mismatches.
- Extend `tests/core/model_family_test.cpp` for arch→family, unknown refusal, deepseek geometry fields, layout completeness, and dense first block.
- Build only in `build-deepseek/`, keep `build-hip/strata` untouched.
- Guard rail (DEC-021 T2): patch must not exceed 5 files or 300 lines; if it does, stop and raise a deviation.

## 2. Proposed change

Proceed with the S1–S3 implementation even though the patch touches **6 files** in the Strata checkout:

1. `include/strata/artifact/model_family.hpp` — add `DeepseekMoe` enum value, arch mapping, title, and generic refusal message.
2. `include/strata/core/geometry.hpp` — add `n_expert_shared`, `n_dense_first_blocks`, `n_ff_dense`, `rope_freq_base` fields.
3. `include/strata/core/family_layout.hpp` — add DeepSeek geometry reading, layer/global tensor layout, complete-table flag, and `--inspect` helper.
4. `include/strata/artifact/gguf_reader.hpp` — accept `deepseek` in `check_architecture()` so `check_engine_architecture()` can return the named refusal instead of the PLE/"unknown architecture" text.
5. `src/program/generate.cpp` — add the `--inspect <gguf>` CLI flag and dispatch.
6. `tests/core/model_family_test.cpp` — extend tests for deepseek recognition, geometry, layout completeness, and dense first block.

Current patch stat (working tree, not committed):

```text
 include/strata/artifact/gguf_reader.hpp  |  18 +++++
 include/strata/artifact/model_family.hpp |   9 ++-
 include/strata/core/family_layout.hpp    | 121 +++++++++++++++++++++++++++++--
 include/strata/core/geometry.hpp         |   6 ++
 src/program/generate.cpp                 |  10 +++
 tests/core/model_family_test.cpp         | 101 ++++++++++++++++++++------
 6 files changed, 234 insertions(+), 31 deletions(-)
```

The line count (234 insertions, 31 deletions, total 265 delta) is **under** the 300-line T2 bound; only the file count exceeds the threshold by one.

## 3. Reason

The natural S1–S3 implementation requires touching the four architectural layers that already exist in Strata:

- **Family enum/title** (`model_family.hpp`) — required by "Recognition."
- **Geometry struct** (`geometry.hpp`) — required by "Geometry" (explicit shared-expert and dense-block fields).
- **Geometry reader + layout table + `--inspect` helper** (`family_layout.hpp`) — required by "Geometry" and "Inventory + `--inspect`."
- **CLI `--inspect` entry point** (`generate.cpp`) — required by "Inventory + `--inspect`."
- **Unit tests** (`model_family_test.cpp`) — required by "Tests."

The sixth file, `gguf_reader.hpp`, is unavoidable because the generic `--native` path in `generate.cpp` reaches the existing refusal gate at `src/program/generate.cpp:4800-4807`, which calls `strata::model_family_not_supported(strata::model_family(meta))` **after** `strata::check_architecture()` succeeds. Today `check_architecture()` falls through to `read_geometry()`, which only knows `qwen4exp`; for `deepseek` it returns `architecture is 'deepseek', this engine requires 'qwen4exp'` — the wrong message, and not the named `model_family_not_supported` text the acceptance criterion requires. To make the named refusal appear, `check_architecture()` must recognize `deepseek` as a supported-architecture guard pass. That guard lives in `gguf_reader.hpp` alongside the existing `qwen35moe` guard.

I explored alternatives that avoid editing `gguf_reader.hpp`:

- Handling the deepseek guard only in `family_layout.hpp::geometry_from_gguf` leaves `check_architecture()` returning the qwen4exp-only error, so `--native` prints the wrong refusal.
- Handling refusal entirely in `generate.cpp` would duplicate `check_engine_architecture()` logic and would not fix `check_engine_architecture()` callers in `src/core/native_*.cpp` or the tests that verify the named message.
- Forward-declaring a deepseek guard from `family_layout.hpp` into `gguf_reader.hpp` still modifies `gguf_reader.hpp`.

No design I found satisfies the named-refusal acceptance criterion without editing `gguf_reader.hpp`, so the minimum file count for a correct S1–S3 is six.

## 4. Impact

| Dimension | Impact |
|---|---|
| Cost / effort | No increase; the work is already scoped and implemented. |
| Schedule | One-file deviation approval is the only added step; no re-design needed. |
| Risk | Low. The changes are read-only / refusal-only; no forward path, no kernel, no attention, no routing. The qwen regression gate (AC-7) still proves no qwen behavior changed. |
| Evidence / claims | All AC-1…AC-10 evidence remains valid. The patch stat itself becomes an additional evidence artifact. |
| Dependencies | None. |

## 5. Options

| # | Option | Pros | Cons | Recommendation |
|---|---|---|---|---|
| 1 | **Approve the 6-file patch** and record that DEC-021 T2's file threshold is exceeded by exactly one file for DeepSeek S1–S3. | Satisfies every acceptance criterion; no technical debt or duplicated logic; keeps the refusal message correct and tested. | Breaches the 5-file working threshold by one. | **Recommended.** |
| 2 | Reject and demand a 5-file implementation. | Keeps T2 literal. | Would require either (a) moving `check_architecture` logic and breaking include layering, (b) accepting a non-named refusal message and failing AC-2, or (c) dropping tests and failing AC-1/AC-5/AC-6. All are worse. | Not recommended. |
| 3 | Split S1–S3 into two handoffs to keep each patch ≤5 files. | Strictly honors T2 per handoff. | Adds process overhead and a bisected evidence bundle; the two patches together still touch the same six files, and the second handoff cannot run until the first is approved. | Not recommended for a bounded read-only package. |

## 6. Decision (architect)

- **APPROVED / REJECTED**
- Conditions:
- Updated scope / criteria / evidence:
- Recorded in `DECISIONS.md` on <date>

## 7. Consequences

- If **approved**: continue with build, tests, evidence bundle, and `CODER_DONE`; record the 6-file patch stat in the evidence manifest.
- If **rejected**: stop S1–S3 implementation; revert or stash the Strata working-tree changes; await a revised handoff or split plan.
