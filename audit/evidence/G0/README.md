# G0 — Baseline freeze evidence bundle

Baseline SHA: `cca793e` (branch `vibe/audit-remediation-220201`, merged via PR #7).
Successor work branch: `vibe/phase7-220201`.

## Contents (to be filled at G0 execution)
- `env.txt` — `uname -a`, `rocminfo` GPU line, ROCm/HIP/CMake/Python/NumPy/pybind11 versions, `git rev-parse HEAD`
- `cpu-suite.log` — `python tests/test_cpu_only.py` and `python -O tests/test_cpu_only.py` (expected: 12/12 OK)
- `gpu-suite.log` — all five GPU suites on the gfx1150 host (manual run; `ci-gpu.yml` scaffold lands in 7A-7)
- `sdist-install.log` — clean-venv `pip install --no-build-isolation dist/*.tar.gz` (full CMake build) + `GFX1150_SKIP_CMAKE=1` CPU-only install
- `claims-check.log` — `python scripts/qa/check_claims.py` once 7A-6 lands; until then, manual review of `audit/CLAIMS_LEDGER.md` vs README
- `baseline-report.md` — auditor signoff

## Status
Layout created; logs pending G0 execution on the gfx1150 host.
