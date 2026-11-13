# Auditor probes — 7A-5

**Auditor:** DeepSeek V4.1 Flash
**Date:** 2026-11-03
**Candidate:** `3635151` · **Tip:** `e3d2d58`
**Clean clone:** `/tmp/opencode/audit-7a5`

| Probe | Result |
|---|---|
| GitHub API run `41739977786` | **success**, head `3635151`; both jobs and all steps green |
| Tip `e3d2d58` check-runs | Sdist Install, CPU suite, Clean-clone build all **success** |
| sdist | 48 entries; `tests/conftest.py` present; 9 test `.py` files |
| Clean venv `GFX1150_SKIP_CMAKE=1` install | exit 0 |
| Module split | 3 CPU modules import from venv; `matmul_module` absent; 3 GPU modules raise actionable `ImportError` |
| Extracted CPU lane, CPU-simulated | 41 passed, 2 skipped, exit 0 |
| Extracted full lane, CPU-simulated | 41 passed, 20 skipped, exit 0 |
| 7A-2 verifier | 17/17 |
| `test_cpu_only.py` / `-O` | 12/12 each |
| Scope | only `MANIFEST.in`, `ci-cpu.yml`, 7A-5 evidence |
| **Host caveat** | On this ROCm host without `ROCM_ROOT=/nonexistent-rocm`, the HIP build-configure test runs and fails (pybind11 absent from the sdist venv); with the override it skips and the lane is 41/2. CI target is ubuntu-latest, where it skips and is green. |

Full transcript: `probe-commands.log`.
