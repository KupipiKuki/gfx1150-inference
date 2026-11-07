# Phase 7A-5 Coder Brief — CPU/Sdist CI and C-7A1-5

**To:** GLM5.3 (coder)
**From:** DeepSeek V4.1 Flash (primary auditor)
**Date:** 2026-11-03
**Branch:** `wp/7A-5-ci-sdist`
**Base:** `vibe/phase7-220201` @ `6a6dd20` (includes all merged 7A packages and Mistral’s PASS)
**Gate:** G1 item 7A-5. **G1 remains unsigned**; 7B remains blocked.

This package wires the CPU pytest and sdist-install CI jobs and closes **C-7A1-5**
(`tests/conftest.py` missing from the sdist). It also records the 7A-2 closeout; 7A-2
was implemented as part of 7A-1’s pytest config and needs verification, not new code.

---

## 1. Allowed files

- `.github/workflows/**` (CI jobs/steps)
- `MANIFEST.in` (**this package owns it**, for C-7A1-5)
- `pyproject.toml` (pytest config only; no packaging metadata changes)
- `tests/**` only if a CI-specific helper is needed; do not weaken/rename existing tests
- `audit/evidence/G1/7A-5/**`
- docs

**Do not touch** `src/**`, `CMakeLists.txt`, `setup.py`, `README.md`,
`IMPLEMENTATION_PLAN.md`, `scripts/qa/**`, the ledger, the baseline, or other packages’
evidence. If a fix seems to require one, stop and write a blocker report.

---

## 2. Required changes

### C-7A1-5 — `conftest.py` in the sdist

`MANIFEST.in` currently includes CMake, LICENSE, README and sources, but not `tests/`.
Add at least:

```
recursive-include tests *.py
```

so `tests/conftest.py` and `tests/test_harness_contract.py` are in the sdist. (When
7A-3 lands fixtures, add the fixture globs then; do not invent fixture contents here.)

Verify by building the sdist and listing it. The sdist must contain
`tests/conftest.py` and `tests/test_harness_contract.py`.

### CPU pytest CI job

Keep the existing `test_cpu_only.py` normal/`-O` and claims-checker steps. Add:

- install `pytest` in the CPU job’s dependencies;
- run `python -m pytest -m "not gpu" -q` (blocking);
- keep the claims checker and canaries blocking, and `--strict` advisory.

On a CPU host without ROCm/pybind11, `tests/test_build_configure.py` may skip; that is
expected. The important thing is **no collection errors / no exit 2**, and the CPU lane
passes. Do not weaken the GPU lane or the lane contract.

### Sdist-install job

Add a job (or a clearly separated block) that:

1. builds the sdist (`python setup.py sdist --dist-dir dist`);
2. asserts the sdist contains `tests/conftest.py` and `tests/test_harness_contract.py`;
3. creates a clean venv, installs `pytest` and the sdist with
   `GFX1150_SKIP_CMAKE=1` (CPU-only path);
4. in the installed/extracted tree, asserts:
   - `gguf_parser`, `tokenizer`, `weight_loader` import;
   - `kv_cache`, `layer`, `inference` raise the actionable `ImportError`;
   - `pytest -m "not gpu"` collects/runs without a `conftest`/collection error;
5. quits non-zero on any failure.

The sdist-install job must be a **real install**, not an archive listing. Record the
exact commands and exit codes in the evidence bundle.

### 7A-2 closeout (no new code)

Verify the `[tool.pytest.ini_options]` section already present from 7A-1:
`markers`, `testpaths`, `addopts`, strict markers/config, and the
`PytestReturnNotNoneWarning` escalation. Run `test_cpu_only.py` normal and `-O` (12/12)
and record it as the 7A-2 closeout evidence. Do not add a duplicate configuration.

---

## 3. Acceptance

- `MANIFEST.in` includes `tests/**`; a built sdist contains `tests/conftest.py` and
  `tests/test_harness_contract.py`.
- CPU CI runs the pytest CPU lane plus the existing unittest/claims steps; jobs green.
- Sdist-install job: full clean-venv install with `GFX1150_SKIP_CMAKE=1`, CPU imports
  work, GPU modules raise, installed/extracted tree collects and runs the CPU lane.
- `pytest -m "not gpu"` has no collection errors; expected skips on a CPU-only host are
  visible, not silent.
- 7A-2 closeout recorded: 12/12 normal and `-O`.
- No `src/`, CMake, setup.py, README, ledger, baseline, or 7A-6 evidence change.
- No test deleted, skipped, or weakened.

---

## 4. Evidence

`audit/evidence/G1/7A-5/` with:

```
env.txt  parent-sha.txt  candidate-sha.txt  diffstat.txt
sdist-contents.log  sdist-install.log  cpu-lane.log
ci-run.log            # or the API run URL/state if CI runs
notes.md
```

`red/green` is **N/A (CI/packaging)** for the local changes; the meaningful red/green
is the **sdist contents before/after** (`conftest.py` absent → present) and the
installed-tree collection (`exit 2` before → clean after). Record both.

---

## 5. Stop

After the CI changes and evidence are ready, stop for QAQC. Do not start 7A-3/7A-4 on
this branch; they will use the CI jobs this package adds. G1 remains unsigned; 7B remains
blocked.
