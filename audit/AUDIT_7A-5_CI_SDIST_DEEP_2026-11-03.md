# Independent 7A-5 Audit — CPU/Sdist CI and C-7A1-5

**Auditor:** DeepSeek V4.1 Flash (independent of the coder and QAQC)
**Date:** 2026-11-03
**Target:** `wp/7A-5-ci-sdist` @ `e3d2d58` (work commit `3635151`)
**Base:** `180fc2d` (branch base; `6a6dd20` integration base)
**Coder:** GLM5.3 · **QAQC:** independent session (`qaqc-probes/qaqc-report.md`)
**Scope:** 7A-5 only. **G1 remains unsigned.**

---

## 1. Verdict

**PASS.** C-7A1-5 is closed, the CPU pytest and sdist-install jobs are green on an
API-verified Actions run, the installed module split is correct, the 7A-2 closeout is
recorded, and the scope is clean.

One **observation**, not a condition: the sdist-install job is host-dependent. On the
ubuntu-latest target it skips the HIP build-configure test and is green; on this
gfx1150 audit host (ROCm present, pybind11 absent from the sdist venv) that test runs
and fails. The workflow does not set `ROCM_ROOT=/nonexistent-rocm`; the QAQC rehearsal
did. CI on the declared target is authoritative and green, so this does not block G1,
but a future CI edit should make the job host-independent (set
`ROCM_ROOT=/nonexistent-rocm` or install pybind11 for the lane steps).

---

## 2. Reproduction

| Check | Result |
|---|---|
| CI run `41739977786` (head `3635151`) | API: **success**; both jobs and every step green |
| Tip `e3d2d58` check-runs | Sdist Install **success**, CPU suite **success**, Clean-clone build **success** |
| Sdist build | exit 0; **48 entries**; `tests/conftest.py` **present**; 9 `tests/*.py` |
| Clean venv `GFX1150_SKIP_CMAKE=1` install | exit 0 |
| Module split from a neutral dir | `gguf_parser`/`tokenizer`/`weight_loader` import from the venv; `matmul_module` absent; `kv_cache`/`layer`/`inference` raise the actionable `ImportError` |
| Extracted-tree CPU lane (CPU-simulated) | 41 passed, 2 skipped, exit 0 |
| Extracted-tree full lane (CPU-simulated) | 41 passed, 20 skipped, exit 0; skips visible |
| 7A-2 verifier | **17/17** pass |
| `test_cpu_only.py` / `-O` | 12/12 each |
| Scope | only `MANIFEST.in`, `ci-cpu.yml`, and 7A-5 evidence; restricted diff empty |
| Host caveat (this ROCm host, no `ROCM_ROOT` override) | `test_build_configure_succeeds_with_the_hip_toolchain` runs and fails because pybind11 is absent from the sdist venv; with `ROCM_ROOT=/nonexistent-rocm` it skips and the lane is 41/2, exit 0 |

The CI run is on the workflow’s declared target (ubuntu-latest / Python 3.12), so the
host caveat does not invalidate the acceptance. It is recorded for a future CI
determinism edit.

---

## 3. C-7A1-5 closure

`MANIFEST.in` now has `recursive-include tests *.py`; the sdist contains
`tests/conftest.py` and `tests/test_harness_contract.py` plus all nine test modules.
Without it, the extracted tree’s GPU tests request a missing `matmul_module` fixture
and error (16 errors on the parent); with it they skip visibly. The sdist-install job
runs both the CPU lane and the full lane, which is the guard that actually detects the
condition. Closed.

## 4. 7A-2 closeout

`verify-pytest-config.py` is **17/17**: declared config (minversion, testpaths, markers,
strict markers/config, `-ra`, return-warning escalation) and behavioural checks
(unknown marker/ini option and returning test all fail). `test_cpu_only.py` is 12/12
normal and `-O`. `pyproject.toml` was not changed.

## 5. Gate impact

- **7A-5:** PASS; merge-approved.
- **C-7A1-5:** closed.
- **7A-2:** closeout recorded.
- **G1:** only **7A-3 (goldens)** and **7A-4 (fuzz)** remain open; 7A-7 stays
  queued-not-green until 7F-1 registers the runner.
- **7B:** blocked until G1 and the 7A-3 goldens.
- **Observation:** make the sdist-install job host-independent before it is used on a
  ROCm self-hosted runner.

## 6. Sign-off

**7A-5 decision: PASS.** The CI/sdist deliverable and C-7A1-5 are accepted.

**Sign-off:** DeepSeek V4.1 Flash, 2026-11-03.
