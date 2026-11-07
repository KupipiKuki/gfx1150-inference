# Phase 7 / Gate 1 Review: Work Package `7A-6` (Claims Checker & Canary Suite)

**Review Date:** 2026-11-01  
**Target Branch:** `vibe/phase7-220201` (`4bcffeb35862c3d0b12fa54aac2f2d27bdc9ec60`)  
**Work Package Branch:** `wp/7A-6-claims-checker`  
**Candidate Commit:** [`994d629`](file:///home/kupipi/Documents/git/gfx1150-inference) (*"G1/7A-6: add the claims checker, its canaries and the ledger scope annotations"*)  
**Evidence Record Commit:** [`f0a73a1`](file:///home/kupipi/Documents/git/gfx1150-inference) (*"G1/7A-6: record the candidate SHA in the evidence bundle"*)  
**Status:** **RECOMMENDED FOR APPROVAL / MERGE**

---

## 1. Executive Summary

Work package `7A-6` implements the automated claims integrity verification pipeline required for Gate 1 of Phase 7, as specified in [`PHASE7_IMPLEMENTATION_HANDOFF.md` §10](file:///home/kupipi/Documents/git/gfx1150-inference/PHASE7_IMPLEMENTATION_HANDOFF.md#L1012-L1052) and [`PHASE7_7A_CODER_BRIEF.md` §3](file:///home/kupipi/Documents/git/gfx1150-inference/PHASE7_7A_CODER_BRIEF.md#L45-L162).

The coding changes have been evaluated for accuracy, scope compliance, functional correctness, and evidence fidelity. All 6 tasks, 10 canaries, and the full test suite pass cleanly without regressions.

---

## 2. Scope & File Isolation Compliance

Per the coder brief and handoff specification, modifications for `7A-6` were strictly confined to `scripts/qa/**`, `audit/CLAIMS_LEDGER.md`, `audit/claims_baseline.txt`, `.github/workflows/**`, `audit/evidence/G1/7A-6/**`, and documentation.

- **Diffstat Inspection (`git diff --stat 4bcffeb..HEAD`)**:
  - `17 files changed, 2520 insertions(+), 18 deletions(-)`
  - **Core C++ / HIP / Python code (`src/**`)**: 0 files modified.
  - **Test suite (`tests/**`)**: 0 files modified.
  - **Build / Packaging (`CMakeLists.txt`, `setup.py`, `pyproject.toml`)**: 0 files modified.
  - **Baseline file ([`audit/claims_baseline.txt`](file:///home/kupipi/Documents/git/gfx1150-inference/audit/claims_baseline.txt))**: Exactly preserved (0 diffs), maintaining the 15 exact (no-wildcard) baseline records.

---

## 3. Verification Against Acceptance Criteria

### Task 1: Robust Table Parser & Scanner ([`scripts/qa/check_claims.py`](file:///home/kupipi/Documents/git/gfx1150-inference/scripts/qa/check_claims.py))
- **Header & Scope Delimitation**: The parser strictly scans only the markdown table in [`audit/CLAIMS_LEDGER.md`](file:///home/kupipi/Documents/git/gfx1150-inference/audit/CLAIMS_LEDGER.md) and terminates upon hitting the first non-table line (e.g. `### Summary of Non-Verified Claims`), eliminating false-positive parses.
- **Strict Enum Validation**: Column 3 (`Status`) enforces `{VERIFIED, NOT_YET, UNVERIFIED, CONTEXT}`, and Column 7 (`Public?`) enforces `{yes, no}`.
- **Evidence Path Existence**: Validates that any `VERIFIED` claim provides an existing, non-empty evidence path in `audit/evidence/`.
- **Targeted Document Scanning**: Scans `README.md` and `IMPLEMENTATION_PLAN.md` for occurrences of non-verified claim literals.

### Task 2: Baseline Handling ([`audit/claims_baseline.txt`](file:///home/kupipi/Documents/git/gfx1150-inference/audit/claims_baseline.txt))
- Baseline entries use exact `(claim_id, path, line_no)` triples without wildcards.
- Correctly parses the 15 baseline entries matching the 12 unqualified rows (claims 6, 10, 13, 14, 18, 19, 20, 26, 27, 28, 29, and 30).
- Expiry detection is implemented: baseline entries referencing lines that no longer match are flagged as errors.

### Task 3: Claim-Specific Literals & Anti-Generic Filter
The 4 overly broad / generic search literals flagged in the brief were replaced with exact phrases:
1. Claim 10: `'pip install'` $\rightarrow$ `'sdist'`
2. Claim 18: `'test_cpu_only.py'` $\rightarrow$ `'Self-contained CPU-only test suite'`
3. Claim 19: `'GPU'` $\rightarrow$ `'PYTHONPATH=build'`
4. Claim 27: `'llama-family'` $\rightarrow$ `'Q4_0'`, `'Q4_K'`, `'Q8_0'`

`check_claims.py` incorporates a `GENERIC_LITERALS` rejection set (`{"pip install", "GPU", "test_cpu_only.py", "llama-family"}`) that refuses to execute if a generic literal is reintroduced.

### Task 4: Unqualified Rows Reporting
- In default mode (`python3 scripts/qa/check_claims.py`), the script prints all 12 un-verified claims across 17 occurrences explicitly with line numbers and file paths before reporting that they are covered by the baseline.
- It avoids emitting an unqualified `"FINDINGS none"` that could obscure the existence of baselined debt.
- In strict mode (`--strict`), it treats baselined occurrences as blocking failures, outputting all 17 violations with exit code `1`.

### Task 5: CI Integration ([`.github/workflows/ci-cpu.yml`](file:///home/kupipi/Documents/git/gfx1150-inference/.github/workflows/ci-cpu.yml))
Added 3 automated steps to the `cpu-tests` workflow:
1. `Verify claims ledger (baseline mode)`: Blocking run of `check_claims.py`.
2. `Run claims checker canaries`: Blocking run of `canary_claims.py`.
3. `Audit claims ledger (strict mode, advisory)`: `continue-on-error: true` run of `check_claims.py --strict` to log the backlog without breaking CI.

### Task 6: Canary Suite ([`scripts/qa/canary_claims.py`](file:///home/kupipi/Documents/git/gfx1150-inference/scripts/qa/canary_claims.py))
Implements 10 synthetic mutation tests verifying checker sensitivity across isolated temporary trees:
1. `not_yet_claim`: Unproven claim in `README.md` fails.
2. `unqualified_q4_k_m`: Unqualified mention fails.
3. `unqualified_qwen2`: Unqualified model mention fails.
4. `missing_evidence`: Non-existent evidence file for `VERIFIED` fails.
5. `generic_literal`: Blacklisted generic literal fails.
6. `strict_detects_baseline`: Baselined claims fail under `--strict`.
7. `baseline_is_exact`: Non-exact baseline format fails.
8. `expired_baseline_entry`: Stale baseline entry fails.
9. `wrong_lane`: Claim in an unauthorized file fails.
10. `nested_bullet`: Unterminated / malformed table parsing fails.

---

## 4. Live Execution & Verification Results

All verification commands were executed directly against the branch:

| Verification Target | Command | Result | Notes |
|:---|:---|:---:|:---|
| **Default Claims Check** | `python3 scripts/qa/check_claims.py` | **PASS (Exit 0)** | 30 claims parsed, 17 baselined violations, 0 new violations, 0 expired baseline entries. 1 expected warning on claim 21 (`ci-cpu.yml` missing link to workflow run). |
| **Strict Claims Check** | `python3 scripts/qa/check_claims.py --strict` | **PASS (Exit 1)** | Successfully caught all 17 baselined violations as blocking failures. |
| **JSON Output Mode** | `python3 scripts/qa/check_claims.py --json` | **PASS (Exit 0)** | Valid structured JSON emitted. |
| **Canary Test Suite** | `python3 scripts/qa/canary_claims.py` | **PASS (Exit 0)** | 10/10 canaries passed in 0.28s. |
| **CPU Test Suite** | `pytest -m "not gpu" -q` | **PASS** | 37 passed, 18 deselected in 0.82s. |
| **GPU Test Suite** | `pytest -m gpu -q` | **PASS** | 18 passed, 37 deselected in 1.66s. |
| **Combined Tests** | `pytest -q` | **PASS** | Full 55/55 test suite green. |

---

## 5. Audit Evidence Bundle Review ([`audit/evidence/G1/7A-6/`](file:///home/kupipi/Documents/git/gfx1150-inference/audit/evidence/G1/7A-6/))

The evidence bundle contains 13 artifacts corresponding to the execution logs:
- `parent-sha.txt`: Matches `4bcffeb35862c3d0b12fa54aac2f2d27bdc9ec60`.
- `candidate-sha.txt`: Matches `994d62922af7ed9f5b9546d787d8c05606cdb8f1`.
- `gate-commands.log`, `claims-check.log`, `canary-claims.log`, `pytest-cpu.log`, `pytest-gpu.log`: Log contents match live execution outputs byte-for-byte.
- `git-diff.patch` / `git-status.txt`: Clean tree representation.

*Minor Non-Blocking Observation:* In `audit/evidence/G1/7A-6/env.txt`, the candidate SHA string was captured during staging prior to commit finalization (re-recorded accurately in `candidate-sha.txt` by commit `f0a73a1`). This is cosmetically transparent and has no functional impact.

---

## 6. QAQC Recommendation

The coder's implementation of `7A-6` is complete, robust, and strictly adheres to all architectural boundaries, constraints, and acceptance criteria. 

**Recommendation:** **PASS — Approve and merge `wp/7A-6-claims-checker` into `vibe/phase7-220201`.**

