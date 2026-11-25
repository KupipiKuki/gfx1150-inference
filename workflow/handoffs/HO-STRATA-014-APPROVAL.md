# Architect approval — HO-STRATA-014

| Field | Value |
|---|---|
| **Handoff** | HO-STRATA-014 (DeepSeek **S4a**: forward skeleton + block-0 layer parity) |
| **Architect** | `architect` (`opencode-go/deepseek-v4-pro#max`) |
| **Date (UTC)** | 2026-11-24 |
| **Decision** | **SIGNED** |
| **Merge commit** | `TBD` — merge via `merge/*` PR with a merge commit (DEC-040); **blocked** while 3 of 4 required checks cannot run (GitHub Actions billing, 2026-11-23) |
| **Evidence** | `workflow/evidence/HO-STRATA-014/` · `reports/qaqc/HO-STRATA-014-qaqc.md` · `reports/audit/HO-STRATA-014-audit.md` · `DR-HO-STRATA-014-1.md` |

## 1. Criteria trace

| # | Criterion | Evidence | QAQC | Audit | Architect |
|---|---|---|---|---|---|
| AC-1 | build in `build-deepseek/`; signed binary untouched | `artifacts/signed-binary-hash.txt` = `d58ee239…` | PASS | PASS | PASS |
| AC-2 | normal refusal verbatim; `--families` unchanged | `artifacts/refusal.txt`, `artifacts/families.txt` | PASS | PASS (byte-identical to HO-012 C6) | PASS |
| AC-3 | `--parity-run` explicit, three cases | `test-output.txt` AC-3a/b/c | PASS | PASS | PASS |
| AC-4 | dump layout `k × 2 × 2048 × 4`, finite | `81,920` B; `1 layer + the input x 1 streams x 2048` | PASS | PASS | PASS |
| **AC-5a** | **layer parity, block 0, 4 cells ≤ 5e-3 vs exact reference** | `artifacts/compare-layers.txt`: max **9.757537e-05** | PASS | PASS (regenerated the oracle itself) | **PASS** |
| AC-5a floor | Q4_K comparison, informative only (DEC-044) | max `2.054810e-02`, labelled | PASS | PASS | PASS |
| AC-6 | determinism | `dump-run-1/2` identical; 2 fresh runs identical | PASS | PASS | PASS |
| AC-7 | Qwen regression 32 IDs + unit tests | `artifacts/qwen-regression.txt`; 39 checks, geometry test | PASS | PASS | PASS |
| AC-8 | patch measured/exported/applies | S4a 10 files/+839; cumulative 14/+1,073/−31; `apply-check.txt` | PASS | PASS (`cmp` against live diff) | PASS |
| AC-9 | evidence gate `--strict` | `RESULT: PASS (31 checks, 0 warnings)` | PASS | PASS | PASS (re-ran) |
| AC-10 | plan + graph citations + deviation before code | `artifacts/plan.md`; DR approved at `672beee` before engine commit `ad214242a` | PASS | PASS | PASS |

## 2. Gate evidence

- [x] QAQC report: `workflow/reports/qaqc/HO-STRATA-014-qaqc.md` — **PASS**, committed verbatim (DEC-041 §3)
- [x] Audit report: `workflow/reports/audit/HO-STRATA-014-audit.md` — **PASS** (auditor content; materialised by the architect after a step-budget stop, noted in the report)
- [x] Evidence manifest complete; 23/23 hashes verify from a fresh `git archive`
- [x] Scope matches the handoff; the deviation (DR-1) is recorded and approved (DEC-043); no drift beyond it
- [x] Guard rails respected: no `src/core/**`, shared-kernel, `qwen35`, tokenizer or `model_family_runs()` edits; `build-hip/` untouched; no new dependency; no signed bundle edited
- [x] No secrets; **no support or performance claim** — the claim is "block 0 computes correctly on this profile", and nothing else

## 3. What was actually decided in this handoff

The gate did its job twice, which is the reason to sign rather than rework:

1. **DR-HO-STRATA-014-1 (DEC-043).** AC-10 found that extending the generic engine
   is a structural change (T1) and that a dedicated `src/deepseek/` path crosses
   T2. The architect verified the citation sites independently, approved the
   path on Route 2 (the ~5k lines are additive new files; the upstream-facing
   edits are three small hunks), and **split the stage** on the oracle's per-layer
   resolution — block 0 first, the MoE blocks in S4b — and cut `dsref.cu`.
2. **DEC-044.** The first AC-5a failed at 1.83e-2 … 1.23e-1. The bisection proved
   the signed Q4_K oracle computes its matmuls with **q8_K-quantised
   activations** (reproduced to 1.2e-7 / 3.3e-7), i.e. the reference, not the
   engine, was the lossy side. The **reference** was replaced with an
   arithmetic-exact f32 conversion of the same pack; **the 5e-3 bound was not
   touched**. With the exact reference the gate immediately exposed a real bug —
   NEOX-style RoPE where llama.cpp uses NORM-style pairs — and then passed with a
   ~50× margin. Against the Q4_K reference that bug was invisible.

Had the bound been widened instead, S4a would have been "signed" with a broken
rope path. This is the strongest evidence yet that the pre-registration rule and
the T2/audit chain are worth their cost.

## 4. Conditions / follow-ups

All carried; none touches the claim. Each becomes an **acceptance criterion** in
HO-STRATA-015 (S4b), per the auditor's AUDITOR_TO_ARCHITECT block.

| # | Severity | Condition | Owner | Due |
|---|---|---|---|---|
| A1 | Major (carry) | Record the gate reference's generating command (`oracle_nodes … --tokens 549,6077,280,7239 --n 0 --dump-layers`) in HO-015's `commands.log`/manifest. Accepted as a carry because **both** reviewers regenerated the reference independently, so the claim does not depend on the missing line | Coder (HO-015) | S4b CODER_DONE |
| A2 | Major (carry) | `hashes-notes.txt` must use the `## Commit pins` table with **all** digests inlined, so `B6-pins` runs mechanically; and the architect decides whether `check_bundle.py` should warn when a `hashes-notes.txt` yields no pin rows (it currently reports a clean PASS while skipping the check) | Coder + Architect | S4b CODER_DONE / next tool touch |
| A3 | Minor | `compare_layers.py` must not accept a caller-supplied bound ≠ 5e-3, and must echo the bound it used | Coder (HO-015) | S4b |
| **A4** | **Minor → Major for S4b** | The slot/`N` derivation picks the smallest divisor of `R`, so an **S4b** dump (4 records × 29 slots, `R = 116`) would be read as `N = 1` and **pass on block 0 alone**. HO-015 must pass `--slots 29` (or read the engine's `N layers + the input` line) and assert `N == 28` before comparing | Coder (HO-015) | **blocking S4b's gate** |
| A5 | Minor | Receiver signature row — filled at this signoff | Architect | done |
| A6 | Observation | HO-015's manifest must state that this parity validates dequant→f32 GEMV, not the production quantized GEMM | Coder (HO-015) | S4b |
| A7/A8 | Observation | Extra `strata-deepseek` entry point (harmless, record); manifest commit-label wording | Coder (HO-015) | S4b |

QAQC Minors F1–F3 are folded into A2, F2's fix and A4-material respectively: the
`--parity-run` gating gap (F2) and the dual-allocation `upload_weight` (F3) are
**HO-015 acceptance criteria**, not S4a rework — the S4a bundle is a verified
fixed point and editing it now would invalidate the 23 digests both reviewers
checked (DEC-030 B-class precedent).

## 5. Decision

- **SIGNED** → state `DONE` (S4a only). `model_family_runs()` stays `false`,
  normal runs keep the named refusal, and **no support claim is made**.
- **Merge**: authorized per DEC-040 via a `merge/*` PR with a merge commit. It
  **cannot proceed** until the GitHub Actions billing block is cleared (3 of 4
  required checks cannot start, 2026-11-23); `STATUS.md` records `DONE · MERGE
  BLOCKED (billing)` until then. The signed work-package commits stay reachable
  by SHA either way.
- **Next**: HO-STRATA-015 (S4b, MoE blocks 1–27, 108 then 112 cells) with
  A1–A4/F2/F3 as criteria; then S5 = HO-016 (token parity + KL + the support
  flip); S6/S7 = HO-017.

| Role | Signature | Date |
|---|---|---|
| Architect | `architect` (`opencode-go/deepseek-v4-pro#max`) — **SIGNED** | 2026-11-24 |
