# G1 / 7A-8 — clean-clone build entry point: coder report

**Branch:** `wp/7A-8-build-entrypoint` · **Base:** `4bcffeb`
**Audit trace:** G0 C-1 (`AUD-9`, `AUD-4`), handoff §6 (7A-8 row)
**Status:** complete and ready for QAQC. The coder does not sign G1.

## Summary

The README documented `cmake -B build -DCMAKE_BUILD_TYPE=Release`, and on a clean tree
that failed with exit 1: `find_package(pybind11 REQUIRED)` cannot see the CMake package
that ships inside `site-packages`. The command only worked if the caller happened to
export `pybind11_DIR` — which is what `setup.py` does for `pip install`, so the
developer build and the packaging build silently had different prerequisites.

The build now discovers pybind11 from the interpreter it is building for, exactly as
`setup.py` does. The documented command works on a fresh clone with only the documented
prerequisites, no ambient hint and no CMake cache.

## What changed

| file | change |
|---|---|
| `CMakeLists.txt` | pybind11 discovery from the interpreter (`-m pybind11 --cmakedir`, falling back to `pybind11.get_cmake_dir()`), before `project()`; actionable error when it cannot be found; a status line reporting what was found. An explicit `-Dpybind11_DIR=` still wins. |
| `tests/test_build_configure.py` | **new** — the regression test: the documented command, a fresh build dir, `pybind11_DIR` removed. |
| `tests/test_harness_contract.py` | the new module is registered in `EXPECTED_LANES` as a CPU-lane test (7A-1's lane contract). |
| `README.md` | build section gained a **Prerequisites** table and states that no `pybind11_DIR` is needed; the documented command itself is unchanged. |
| `.github/workflows/ci-build.yml` | **new** — runs the documented command on every push/PR from a fresh checkout, then builds, runs the smoke test, and installs the sdist in a clean venv. |
| `setup.py`, `pyproject.toml`, `MANIFEST.in`, `src/` | **unchanged** |

## The one thing worth reviewing

**The discovery runs before `project()`.** That reorders the build's error reporting:
a missing pybind11 is now reported before a missing HIP toolchain, and the pybind11
discovery can be exercised on a host without ROCm. The ROCm paths (`ROCM_ROOT`,
`CMAKE_HIP_COMPILER`, `CMAKE_PREFIX_PATH`) are still set before `project()`, so the HIP
compiler detection is untouched.

The practical payoff: the regression test and the CI job can check the C-1 fix on any
runner, not only on a machine with ROCm. If the auditor prefers the original order,
the discovery can move back below `project()` — but then the CI job's coverage of the
fix depends on a ROCm-equipped runner.

**A detail the G0 audit did not record.** The parent's failure was environment
dependent. CMake also searches prefixes derived from `PATH`, so on a host whose `PATH`
contains the interpreter's own `bin` directory, the interpreter's prefix is searched and
pybind11 is found there — the parent's command *worked* by luck. Both cases are in
`red.log`. The fix depends on neither.

## Verification

| check | result |
|---|---|
| documented command, fresh clone, no `pybind11_DIR`, no cache | **exit 0** (was exit 1) — `red.log` → `green.log` |
| same, with the interpreter's prefix on `PATH` | exit 0, and now for the right reason |
| same with an explicit `-Dpybind11_DIR=` | exit 0 — no regression |
| `cmake --build build -j` | exit 0, extension linked |
| `pytest -m gpu` | 18 passed, 43 deselected |
| `pytest -m "not gpu"` | 43 passed, 18 deselected |
| full `pytest -q` | 61 passed |
| `test_cpu_only.py` / `-O` | 12/12 each |
| sdist build + **full** clean-venv install | exit 0; imports and the CLI work (`sdist-install.log`) |
| the new smoke test against the **parent** | **fails** — the guard works |
| `audit/claims_baseline.txt` | untouched |
| `scripts/qa/**`, the ledger, the 7A-6 evidence | untouched |

## Not done here (and why)

- **The GPU CI workflow** (build + `pytest -m gpu` on a real runner) is 7A-7's
  `ci-gpu.yml`, with 7F-1 registering the self-hosted gfx1150. The new job here
  configures and *builds* on `ubuntu-24.04`, which is what C-1 is about.
- **C-7A1-5** (`conftest.py` missing from the sdist) is 7A-5's. `tests/` is not
  shipped in the sdist, so the new test module does not change the sdist contents.
- **The ledger-vs-README release diff** is 7F-5's.

## Files touched

`CMakeLists.txt`, `README.md` (build section), `tests/test_build_configure.py` (new),
`tests/test_harness_contract.py` (lane registration),
`.github/workflows/ci-build.yml` (new), `audit/evidence/G1/7A-8/**`.

No `src/`, `setup.py`, `pyproject.toml`, `MANIFEST.in`, `scripts/qa/**`,
`audit/CLAIMS_LEDGER.md` or `audit/claims_baseline.txt` change.
