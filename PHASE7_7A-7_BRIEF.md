# Phase 7A-7 Coder Brief — GPU CI Scaffold

**To:** GLM5.3 (coder)
**From:** DeepSeek V4.1 Flash (primary auditor)
**Date:** 2026-11-03
**Branch:** `wp/7A-7-gpu-ci`
**Base:** `vibe/phase7-220201` @ `a873a9c` (includes Mistral’s PASS verification and all merged 7A packages)
**Gate:** G1 item 7. **G1 remains unsigned**; 7B remains blocked.

This is the last of the initially authorized 7A-7/7A-8 packages. The build entry point
(7A-8) is already merged; this package adds the self-hosted GPU workflow and the
skip-is-not-a-pass guard.

---

## 1. Goal

Add `.github/workflows/ci-gpu.yml` for a self-hosted gfx1150 runner:

1. build the extension from a clean checkout using the **documented** configure path
   (no ambient `pybind11_DIR`; 7A-8’s fix is already merged);
2. run the GPU lane (`pytest -m gpu`);
3. **fail if the lane skips** — a skipped GPU lane is not a pass (C-7A1-6 / QF-5);
4. upload logs/artifacts;
5. remain `continue-on-error: true` until the runner registers, with a tracked issue in
   the workflow comment. Once the runner exists, the job must be required and must not
   accept a skip.

Do not claim GPU CI is enforced while the runner is absent.

---

## 2. Allowed files

- `.github/workflows/**` (the new workflow; no change to existing workflows unless
  strictly needed)
- `audit/evidence/G1/7A-7/**` (new evidence bundle)
- docs

**Do not touch** `src/`, `tests/**`, `CMakeLists.txt`, `README.md`, `setup.py`,
`pyproject.toml`, `MANIFEST.in`, `scripts/qa/**`, the ledger, or the baseline. If a
change seems to require one, stop and write a blocker report.

---

## 3. Workflow requirements

- `runs-on: [self-hosted, gfx1150, rocm]`.
- Trigger: PR + nightly (or PR + manual while stabilizing).
- Steps:
  1. checkout;
  2. use the host Python/pip; install the documented test/build prerequisites
     (`numpy`, `setuptools`, `wheel`, `pybind11`, `pytest`; no ROCm pip package);
  3. `env -u pybind11_DIR cmake -B build -DCMAKE_BUILD_TYPE=Release`
     (the README-documented command, with the 7A-8 discovery fix);
  4. `cmake --build build -j`;
  5. `pytest -m gpu` with a **no-skip guard**: the step must fail if any test is
     skipped, not merely if the exit code is non-zero. A robust pattern:
     ```bash
     set -o pipefail
     out=$(python -m pytest -m gpu -q -rs 2>&1 | tee gpu-lane.log)
     echo "$out"
     echo "$out" | grep -qE '[0-9]+ passed'
     ! echo "$out" | grep -q 'skipped'
     ```
     Adjust the exact count only if the suite legitimately changes; assert at least one
     passed and zero skipped, and fail on `failed`/`error`.
  6. upload `gpu-lane.log` (and any configure/build logs) with
     `actions/upload-artifact@v4`.
- `continue-on-error: true` until the self-hosted runner is registered. Add a comment
  with the tracking issue/owner. The job must not be counted as a G1 pass in this state.
- Valid YAML; reference the runner labels exactly.
- No secrets, no prompt/model data in logs.

---

## 4. Acceptance

- Workflow exists, is valid YAML, and targets `[self-hosted, gfx1150, rocm]`.
- The build uses the documented clean-clone path (no `pybind11_DIR`).
- The GPU step **fails on any skip** and on any failure; `18 passed / 0 skipped` is the
  expected healthy result on gfx1150 (the suite count may change only with an approved
  test addition).
- Artifacts upload.
- `continue-on-error: true` with a tracked runner issue while no runner exists; remove it
  and make the job required once the runner registers.
- No `src/`, tests, CMake, packaging, ledger, or docs outside the allowed set.

---

## 5. Evidence

`audit/evidence/G1/7A-7/` with:

```
env.txt  parent-sha.txt  candidate-sha.txt  diffstat.txt
workflow.yml  yaml-validation.log  notes.md
gpu-lane.log            # if a runner exists; otherwise record the gate state
```

`red/green` is **N/A (CI-only)** unless a runner is available and the first run is red
for a fixable environment reason; if so, record that pair. State explicitly whether the
workflow was executed or only validated.

---

## 6. Stop

After the workflow and evidence are ready, stop for QAQC. Do not start 7A-3/7A-4/7A-5 on
this branch. G1 remains unsigned; 7B remains blocked until G1 and the 7A-3 goldens.
