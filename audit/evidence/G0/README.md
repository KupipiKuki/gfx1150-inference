# G0 — Baseline freeze evidence bundle

Baseline SHA: see `7.0-baseline/candidate-sha.txt` (tree under test: `7.0-baseline/parent-sha.txt`).
Work branch: `wp/7.0-baseline`.

**Status: EXECUTED — 2026-11-01.** Gate G0 verdict: **PASS WITH CONDITIONS**
(see `7.0-baseline/baseline-report.md`).

## Contents

| File | Description |
|---|---|
| `7.0-baseline/env.txt` | `uname -a`, OS, ROCm/HIP/AMD clang versions, `rocminfo` GPU agents, CMake/gcc/Python/NumPy/pybind11/pytest versions, CPU, memory, storage, `git rev-parse HEAD` |
| `7.0-baseline/parent-sha.txt` | The commit whose tree was tested |
| `7.0-baseline/candidate-sha.txt` | The G0 candidate commit |
| `7.0-baseline/diffstat.txt` | `git diff --stat` for the baseline and for the 7.0 package; proves the source/test/workflow/packaging diff is empty |
| `7.0-baseline/build.log` | Clean configure + build. Attempt 1 = the command documented in README (**fails**, audit B-3); Attempt 2 = with `pybind11_DIR` (succeeds) |
| `7.0-baseline/cpu-suite.log` | `python3 tests/test_cpu_only.py` (12/12), `python3 -O tests/test_cpu_only.py` (12/12), `pytest -m "not gpu"` (30 passed) |
| `7.0-baseline/gpu-suite.log` | All five GPU suites on the gfx1150 host, with the measured baseline performance figures |
| `7.0-baseline/sdist-install.log` | `setup.py sdist`; sdist contents + sha256; **full** clean-venv `pip install` (real HIP build); `GFX1150_SKIP_CMAKE=1` clean-venv install; installed CPU suite in both venvs |
| `7.0-baseline/gate-commands.log` | Every command run with its exit code |
| `7.0-baseline/claims-check.log` | Manual claims-ledger review (the checker `scripts/qa/check_claims.py` lands in 7A-6) |
| `7.0-baseline/notes.md` | Baseline provenance, environment delta, defects, ledger corrections, rollback |
| `7.0-baseline/baseline-report.md` | Gate G0 exit-criteria table, conditions, baseline reference values, auditor decision |
| `7.0-baseline/qaqc-probes/` | QAQC's independent re-run, **completed 2026-11-01**: `qaqc-report.md` (verdict **PASS WITH CONDITIONS**), `probe-commands.log`, `claims-spotcheck.log`. The G0 execution was performed and signed by the gate-owning role; per handoff §1 it is now *self-tested, independently re-run* (see the independence note and erratum in the baseline report) |

## Deviations from the generic §4 evidence list

`red.log` and `green.log` are **not applicable at G0**: 7.0 introduces no behavioural fix,
so there is no parent/candidate red→green pair. The green state of the baseline suites *is*
the artifact (`cpu-suite.log`, `gpu-suite.log`).

## Carried forward

| ID | Condition | Owner | Target |
|---|---|---|---|
| C-1 | README's documented `cmake -B build` fails on a clean tree (audit B-3) | 7A-5 | G1 |
| C-2 | Four published performance figures do not reproduce (1.12 TFLOPS, 983.4 tok/s, 0.50 ms, 2.76 ms) | 7F-3 | G6 |

QAQC conditions from the independent re-run (`7.0-baseline/qaqc-probes/qaqc-report.md`):
**QAQC-1** — bundle erratum (SHA typo, sdist-hash ambiguity, diagram, row list, wording;
landed as the correction commit that added the probes), **QAQC-2** → 7A-1 (G1): pytest
must collect without a pre-built extension, **QAQC-3** → 7F-3 (G6): no single-run
performance figure may serve as a baseline (correctness is stable; throughput is not).
