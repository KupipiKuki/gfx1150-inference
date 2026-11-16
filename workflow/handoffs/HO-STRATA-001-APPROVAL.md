# Architect approval — HO-STRATA-001

| Field | Value |
|---|---|
| **Handoff** | HO-STRATA-001 |
| **Architect** | `architect` (opencode-go/deepseek-v4.1-flash) |
| **Date (UTC)** | 2026-11-16 |
| **Decision** | **SIGNED** |
| **Merge commit** | deferred — see condition C1 and DEC-015 |
| **Audited tree** | `wp/strata-001-gfx1150-build`, evidence bundle at `76034a0` |
| **Profile** | AMD Radeon 890M (`gfx1150`), Ryzen AI 9 HX 370, ROCm `/opt/rocm/core-10.1`, HIP 7.16.26385 — **no model loaded** |

## 1. Criteria trace

| # | Criterion | Evidence | QAQC | Audit | Architect |
|---|---|---|---|---|---|
| 1 | Pinned commit verified | `artifacts/verify-pin.txt`, `manifest.md` §2 | PASS | PASS | PASS |
| 2 | Toolchain recorded | `artifacts/toolchain.txt`, `hipblaslt-version-probe.txt` | PASS | PASS | PASS |
| 3 | gfx1150 build | `configure.log`, `build.log`, `build-hip/strata` `d58ee239…f5858` (39,736,088 B) | PASS | PASS | PASS |
| 4 | Support surface | `families.txt` (`qwen4exp qwen35moe`), `geometry.txt` (`flash_next`) | PASS after RW-1 | PASS | PASS |
| 5 | Control plan (no changes) | `launch-plan.txt` — exit 2, refusal verbatim, nothing installed | PASS | PASS | PASS |
| 6 | Engine-boundary note | `artifacts/engine-boundary.md` — headless **yes**, three evidence lines | PASS | PASS | PASS |
| 7 | Tuning table match/fallback | `artifacts/tuning-table.md`, `tuning-table-raw.txt` — header/version **match**, default **plain hipBLAS**, opt-in via `STRATA_HIPBLASLT_TUNING` | PASS (after F2 citation fix) | PASS | PASS |
| 8 | Evidence bundle complete | 19/19 hashes recomputed independently by QAQC and auditor; no secrets; no weights | PASS | PASS | PASS |

## 2. Gate evidence

- [x] QAQC report: `workflow/reports/qaqc/HO-STRATA-001-qaqc.md` — FAIL (§1–6), re-check (§7), **independent separation check on `gemini-4-argon` (§8) — PASS**
- [x] Audit report: `workflow/reports/audit/HO-STRATA-001-audit.md` — **PASS** (deepseek-v4.1-flash under DEC-009/WAIVER-001, disclosed)
- [x] Evidence manifest complete (`manifest.md`, `commands.log`, `test-output.txt`, `hashes.txt`, 16 artifacts)
- [x] Scope matches the handoff; no drift (documentation-only rework; no Strata edit; `git -C …/strata status --porcelain` empty)
- [x] Guard rails respected (no model download or run, no package installs, no source patch, no perf/support claim, one profile)
- [x] No secrets; no unsupported claims (the one false claim, F1, was caught by QAQC, withdrawn with an explicit record, and re-verified from source by two independent reviews)

## 3. Conditions / follow-ups

| # | Condition | Owner | Due |
|---|---|---|---|
| **C1** | **Merge is deferred and selective.** The branch carries four workstreams over a base that is not on `main` (audit finding P1). When it is merged, take the evidence bundle from **one commit**, the three handoffs, the QAQC report, the audit report, and the `.gitignore` log negation; decide `DECISIONS.md`/`STATUS.md`/`OT-STRATA-001.md` hunk by hunk; do **not** carry the PENDING `MODEL_POLICY.md`, `model_policy.json`, `check_model_policy.py`, the agent files, or `planning/` as part of this work package. Never fast-forward; never rewrite `290922d`. Recorded as DEC-015. | Architect | at merge |
| **C2** | The first review's FAIL was substantive and correctly handled; no residual action. The record keeps FAIL → REWORK → PASS rather than a clean history. | — | closed |
| **C3** | `290922d`'s commit message still contains the withdrawn family claim and the old `gemm.cu:310-311` citation. The commit is immutable under §9; superseded by `RW-HO-STRATA-001-1` and by the correction in `a7f303c`/`76034a0`. Recorded so `git log` cannot resurrect it. | Auditor (recorded) | closed |
| **C4** | Model-policy application is **PENDING** (`check_model_policy.py --strict` exits 2; architect/coders unset). This sign-off is a WAIVED row under DEC-009, not a PASS. The architect and auditor share a base model; the compensating check for this handoff was the gemini-4-argon QAQC session (§8) plus source re-derivation. | Architect / Owner | before the next coding handoff |
| **C5** | The `.gitignore` evidence-log negation (DEC-008) must reach `main` with the bundle, or the contract-required `commands.log` is untracked by rule. | Architect | at merge |
| **C6** | Nice-to-have, not blocking: a second cold build would prove reproducibility end-to-end. The build was verified by artifact hash + configure/build logs + QAQC re-configure, not by a second full compile. State this as the bundle's residual limit; it is already stated in the manifest. | — | optional |

## 4. Decision

**SIGNED** → state `DONE`.

This is the owner's first acceptance, and it is a **build + support surface +
engine boundary** acceptance, nothing more:

- Strata at `baf16363` builds for `gfx1150` from upstream source with a recorded
  toolchain, verified by a binary hash and both build logs.
- The engine's support surface is measured, not assumed: `qwen4exp`
  (Qwen3.8-Flash-Next) and `qwen35moe` (Qwen3.6-35B-A3B) only.
- The engine runs headless without `apps/` and `serve/`, evidenced three ways.
- The gfx1150 hipBLASLt table is present and version-matched but **not taken by
  default**; plain hipBLAS is the actual default. No speed claim is made, and
  none may be inferred from this bundle.

**No performance, throughput, quality or support claim is approved by this
signature, for any model.** Two host obstacles (configure needs
`CMAKE_PREFIX_PATH`; the binary needs `LD_LIBRARY_PATH`) are recorded as real
friction for HO-002 and later, not as defects.

| Role | Signature | Date |
|---|---|---|
| Architect | `architect` — SIGNED | 2026-11-16 |
