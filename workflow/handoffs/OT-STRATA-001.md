# OT-STRATA-001 — start the Strata project on gfx1150

| Field | Value |
|---|---|
| **Owner task** | OT-STRATA-001 |
| **Received by** | Auditor (single intake) |
| **Date (UTC)** | 2026-11-15 |
| **State** | INTAKE |
| **Owner intent (quoted)** | “Start the Strata project on the current gfx1150 host; prove upstream Strata builds and runs on the APU; establish one small-MoE baseline per family; decide Route 2 vs Route 3. The 780M is a separate gfx-inference dense project; the MI25 is deferred; gfx1100 is future.” |
| **Priority** | P0 |

## 1. Scope

**In scope (gfx1150 only)**

- Pin the Strata commit and record the toolchain.
- Build Strata for `gfx1150`; record setup/CMake friction and tuning-table match.
- `strata --families` / `--plan`; record supported/unsupported model families.
- Inspect the engine boundary (can it run without `apps/`/`serve/`?).
- One small-MoE baseline per family: Mixtral 8x7B, Qwen3-30B-A3B, DeepSeek
  (V2-Lite or MoE-16B).
- Route 2 vs Route 3 decision with evidence.

**Out of scope**

- The 780M (separate `gfx-inference` dense project), MI25 (deferred), gfx1100
  (future).
- Performance/support claims beyond the measured baselines.
- The P0–P9 capability framework (escalation annex).
- Product/app work (`apps/`, `serve/`) unless it is needed to run the engine.

## 2. Decisions the owner must make

| # | Decision | Options | Recommendation | Owner choice |
|---|---|---|---|---|
| 1 | Strata commit | latest `main` vs a pinned release/tag | pin a commit and record it | |
| 2 | Mixtral pack | Mixtral 8x7B Q4_K_M | start here (8x22B-adjacent) | |
| 3 | Qwen pack | Qwen3-30B-A3B Q4_K_M vs Qwen1.5-MoE-A2.7B | Qwen3-30B-A3B, fallback A2.7B | |
| 4 | DeepSeek pack | DeepSeek-V2-Lite vs DeepSeek-MoE-16B | V2-Lite if supported, else MoE-16B | |
| 5 | Timebox | 1–2 days for the build spike | 1 day build + 1 day first run | |

## 3. Detailed instructions

- **Architect:** write `HO-STRATA-001` (build + support + engine boundary),
  then `HO-STRATA-002` (Mixtral), `HO-STRATA-003` (Qwen), `HO-STRATA-004`
  (DeepSeek), and `HO-STRATA-005` (Route 2 vs Route 3 decision). Validate the
  DoR; set READY; launch `coder-primary`; then `qaqc` and `auditor`.
- **Primary coder:** execute each HO on its work-package branch in the Strata
  checkout; produce the evidence manifest; do not modify Strata source in 001
  — record build blockers instead.
- **QAQC:** re-run the build/commands and the baselines; check the evidence and
  guard rails.
- **Auditor:** verify the evidence, the claims, and the scope; write audit
  reports; track this owner task and report to the owner.

## 4. Evidence requirements

- `workflow/evidence/HO-STRATA-001/`: pinned SHA, `rocminfo`, `hipcc --version`,
  kernel/`linux-firmware`, CMake/build log, `strata --families`, `--plan`,
  tuning-table match, engine-boundary note.
- `HO-STRATA-002/003/004`: one baseline table per family — model hash/quant,
  flags, prompt/decode tok/s, GTT/RAM, `dmesg`, limits; no cross-family claim.
- `HO-STRATA-005`: a one-page Route 2 vs Route 3 recommendation with the
  evidence that supports it.
- No secrets; no model weights in git; hashes only.

## 5. Progress checkpoints

| Checkpoint | Owner | Status |
|---|---|---|
| Model policy applied (`check_model_policy --strict`) | Architect | pending |
| Build spike (001) | Architect/Coder | pending |
| Mixtral baseline (002) | Coder/QAQC | pending |
| Qwen baseline (003) | Coder/QAQC | pending |
| DeepSeek baseline (004) | Coder/QAQC | pending |
| Route decision (005) | Architect | pending |
| Owner acceptance | Owner | pending |

## 6. Acceptance criteria (owner-facing)

1. A reproducible gfx1150 build with the exact toolchain recorded.
2. `strata --families`/`--plan` output and the engine-boundary note.
3. One measured baseline per family, with the model hash and the limits.
4. A Route 2 vs Route 3 decision recorded in `DECISIONS.md`.
5. The evidence bundle is complete; no unsupported claims.

## 7. Owner acceptance

| Decision | Date | Note |
|---|---|---|
| pending | | |
