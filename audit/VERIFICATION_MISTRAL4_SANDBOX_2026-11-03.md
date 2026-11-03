# Sandbox-Side Verification Report — Mistral 4.0 (Vibe, non-GPU sandbox)

**Date:** 2026-11-03
**Branch / SHA under review:** `vibe/phase7-220201` @ `cb74921` ("G1 merge: refresh 7A-6 ledger refs after 7A-8 README shift")
**Environment:** Python 3.12.15, NumPy 2.5.4, pytest 9.2.0, Linux x86_64, **no ROCm/HIP/gfx1150** — all GPU-lane execution is out of scope here; hardware execution is covered by the DeepSeek-on-Opencode audits referenced per package.
**Role:** independent sandbox-side reviewer (per the earlier note: DeepSeek via Opencode on the test machine is auditor-of-record with full build/GPU verification; this report is the complementary CPU-only reproduction).

---

## 1. Scope reviewed

Phase 7 work merged into `vibe/phase7-220201` since PR #7 merge (`089ed8e`):

| Package | Branch tip merged | Auditor verdict (DeepSeek, on-host) |
|---|---|---|
| G0 / 7.0 baseline | `57ddafd` via `5345d04`, `1980695` | PASS WITH CONDITIONS |
| 7A-1 pytest harness + follow-up | `e0a0af4` via `408fcab`; follow-up via `bae84e2` | PASS (conditions closed) |
| 7A-6 claims checker + follow-up | `b626c94` via `43642b5`; follow-up `b371364` | PASS (C-7A6-1/2/3/4 closed) |
| 7A-8 clean-clone build + follow-up | `cb4655c` via `84f6fd6`; follow-up `4fcb104` | PASS (QF-1/QF-2 closed) |

## 2. Commands run and results (all on `cb74921`)

| # | Command | Result |
|---|---|---|
| 1 | `python3 -m py_compile src/*.py tests/*.py setup.py scripts/qa/*.py` | ✅ OK |
| 2 | `python3 -m pytest -m "not gpu" -q` | ✅ **41 passed, 2 skipped, 18 deselected** (skips = `test_build_configure.py` correctly skipping without a ROCm toolchain) |
| 3 | `python3 -m pytest -m gpu --collect-only -q` (no extension present) | ✅ **18/61 collected, exit 0** — clean clone no longer errors with exit 2 (AUD-2 fixed); GPU lane skips visibly |
| 4 | `python3 tests/test_cpu_only.py` | ✅ 12/12 OK |
| 5 | `python3 -O tests/test_cpu_only.py` | ✅ 12/12 OK |
| 6 | `python3 scripts/qa/check_claims.py` | ✅ exit 0 — `RESULT: PASS - 0 new, 17 baselined, 0 expired, 0 findings` |
| 7 | `python3 scripts/qa/check_claims.py --strict` | ✅ exit **1** — `RESULT: FAIL - 17 unqualified occurrence(s)`; exit code verified separately from printed text (C-7A6-1 fix confirmed at the process level, not just the log line) |
| 8 | CI on branch (`gh run list`) | ✅ CPU-Only CI + Clean-Clone Build CI both `success` on `cb74921` (runs 41550809514/41550809523 push, 41550816115/41550816131 PR) |
| 9 | Allowed-file-set spot check (7A packages) | ✅ restricted surfaces (`src/`, packaging, ledger semantics) unchanged per package diffstats |

## 3. Findings

- **No issues found.** All sandbox-reproducible claims of the merged packages hold: pytest lanes split correctly (37→41 CPU incl. new meta/config tests, 18 GPU deselected/skipped without the extension), the bool-return defect stays fixed (return warning is an error), the claims checker is baseline-aware by default and strict-failing with a correct exit code, and the clean-clone build fix is guarded by `tests/test_build_configure.py` (skipping cleanly here, running on the gfx1150 host).
- **Carried conditions unchanged:** C-7A1-5 (`conftest.py` must be added to the sdist via `recursive-include tests *.py` — 7A-5), C-7A1-6 (GPU CI must fail on any skip at G5/G6 — 7A-7), C-2/QAQC-3 (perf figures UNVERIFIED until 7F-3 re-record). G1 remains unsigned pending 7A-2..7A-5 and 7A-7; 7B blocked until G1 + 7A-3 goldens.
- **Process note:** DeepSeek's on-host audits (fresh clone, real CMake build, 5/5 GPU suites, clean-venv sdist installs) remain the authoritative hardware evidence; this report covers only the CPU-only surface. Where the two reviewer roles disagree, the discrepancy should be recorded in the next gate bundle per handoff §6.

## 4. Sign-off

**PASS (CPU-only surface), no conditions.** Concurrence recorded for packages G0, 7A-1(+follow-up), 7A-6(+follow-up), 7A-8(+follow-up) as merged at `cb74921`.

— Mistral 4.0 (Vibe sandbox reviewer), 2026-11-03
