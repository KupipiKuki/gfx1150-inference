# QAQC Report — Work package 7A-5 (CPU/Sdist CI and C-7A1-5)

**Role:** QAQC (independent session, per handoff §1 and `PHASE7_7A-5_BRIEF.md`)
**Date:** 2026-11-03
**Tree tested:** work commit `36351518903a2f5efd6f011f3e54e760a16a79f0` on `wp/7A-5-ci-sdist`
(tip `e3d2d58`; prep/brief `180fc2d`; base `6a6dd20` — all merged 7A packages). The CI
run verified against the **public GitHub API**; the red/green reproduced from fresh
builds of both the candidate's and the parent's `MANIFEST.in`.
**Probes:** `probe-commands.log` (this directory).

---

## Verdict

**PASS.** Every acceptance criterion in the brief is met and independently reproduced:
C-7A1-5 is closed with a genuine sdist red/green (47→48 entries, `conftest.py`
absent→present), the new CI jobs are green on a **real, API-verified Actions run**
of the work commit (ubuntu-latest / Python 3.12), the sdist-install job is a real
install with the module split asserted from a neutral directory, the full-lane
regression guard reproduces exactly (16 fixture errors on the parent, 41 passed /
20 skipped on the candidate), the 7A-2 closeout is recorded, the scope is exactly
the brief's, and no test was weakened. No conditions.

## 1. C-7A1-5 — closed, red/green reproduced from fresh builds

| | RED (parent `MANIFEST.in`) | GREEN (candidate) |
|---|---|---|
| sdist entries | **47** | **48** |
| `tests/conftest.py` | **absent** | **present** |
| `tests/*.py` shipped | 8 (the `test_*.py` glob) | **all 9** (verified per file) |

The notes' diagnosis of why the defect survived is correct and worth keeping:
distutils' default sdist rule is the *filename glob* `tests/test*.py`, so the eight
test modules shipped while `conftest.py` — the one file the harness needs — did not.
The manifest rule `recursive-include tests *.py` is exactly the brief's fix, with no
fixture globs invented (7A-3 owns those).

## 2. The two-lane design — the blind spot confirmed, the guard reproduced

The package's central insight is that the brief's own acceptance step
(`pytest -m "not gpu"` in the extracted tree) **cannot detect C-7A1-5**, because
`tests/test_cpu_only.py` puts `src/` on `sys.path` itself. My reproduction confirms
both sides:

- **RED CPU lane** (parent sdist, extracted): **exit 0** — the blind spot is real;
  a job with only the brief's step would have been green while the condition was open.
- **RED full lane** (parent sdist, extracted): **43 passed, 2 skipped, 16 errors,
  exit 1** — the GPU tests request a `matmul_module` fixture that does not exist
  without `conftest.py`, exactly as recorded.
- **GREEN full lane** (candidate sdist, extracted, CPU-simulated): **41 passed,
  20 skipped, exit 0**, with every skip reason printed (`-rs`) — the skips are
  visible, never silent.

## 3. The sdist-install job — a real install, verified

- Clean venv, `GFX1150_SKIP_CMAKE=1` (exported, so the build backend inherits it):
  **install exit 0**.
- **Module split asserted from a neutral directory** (my re-run with the venv
  interpreter): `matmul_module` is genuinely absent (so the GPU assertions cannot be
  vacuous); `gguf_parser`/`tokenizer`/`weight_loader` import **from the venv's
  site-packages** (location checked); `kv_cache`/`layer`/`inference` raise the
  **actionable** ImportError ("Failed to import 'matmul_module' HIP extension.
  Build it first with: …"). This implements the G0 baseline report's governance note
  for 7A-5 exactly.
- The rehearsal honesty is exemplary: the Python 3.14-vs-3.12 deviation is disclosed
  **and closed by the CI run** (which executed the same scripts on 3.12); the
  `ROCM_ROOT=/nonexistent-rocm` simulation puts the host on exactly the CPU-runner
  code path; and the rehearsal **caught a real defect** (the venv needs `setuptools`
  for the shipped packaging test) rather than shipping a job that had never run.

## 4. The CI run — API-verified

Run **41739977786** verified against the public GitHub API: head
`3635151…` (the work commit), branch `wp/7A-5-ci-sdist`, event push, conclusion
**success** — matching `ci-run.log`, whose step table shows every step of both jobs
green (CPU job: unittest ×2, pytest CPU lane, claims default, canaries, strict
advisory; sdist job: build, harness assertion, venv install, module split, both
lanes). This is the authoritative check on the workflow's target runner.

## 5. The 7A-2 closeout — verified, no duplicate config

`verify-pytest-config.py`: **17/17** — declared (`minversion`, `testpaths`, the three
markers, `--strict-markers`/`--strict-config`, `-ra`, the
`PytestReturnNotNoneWarning` escalation in both `addopts` and `filterwarnings`) and
behavioural (unknown marker → error; unknown ini option → error; returning test →
error). `test_cpu_only.py`: **12/12 normal and `-O`**. `pyproject.toml` untouched ✅
(the closeout is a verification, as the brief required).

## 6. Scope and the merged state

- Changed files (excluding evidence and the auditor's prep): **`MANIFEST.in` and
  `.github/workflows/ci-cpu.yml` only** — exactly the package's ownership; restricted
  diff (src, CMake, setup.py, pyproject, README, PLAN, tests/, scripts/qa, ledger,
  baseline) **empty**. No test deleted, skipped, or weakened.
- The tip's evidence commits record the candidate SHA (`3635151`) and diffstat
  correctly; the `e3d2d58` correction (two counts in the notes) was made by a new
  commit, not a rewrite.
- Merged checks still hold on this branch (my runs): claims checker default
  **PASS** (0 new / 17 baselined / 0 expired / 0 findings); canaries **12/12**;
  CPU lane **43 passed / 18 deselected**.
- YAML valid; two jobs (`cpu-smoke`, `sdist-install`).

## 7. Observations (no action required)

1. My own first module-split probe failed because I ran it with the *system*
   interpreter instead of the venv's — my error, corrected in the transcript; the
   package's CI step activates the venv and is correct as written.
2. The "What was verified" table summarises steps 8–9 as "exit 0 (41 passed /
   20 skipped)" — that parenthetical is step 9's numbers (step 8 is 41 passed /
   2 skipped per the red/green table). Trivial ambiguity; the red/green table is
   precise and the raw logs have the exact counts.
3. The sdist job adds ~1–2 min of cheap ubuntu-latest time per push (no ROCm
   download) — no cost concern.

## 8. Disposition

**7A-5 passes QAQC unconditionally.** C-7A1-5 is closed with genuine red/green
evidence, both CI jobs are green on an API-verified Actions run of the work commit,
the sdist-install job is a real install that asserts the exact CPU/GPU module split
the G0 baseline report demanded, and the 7A-2 closeout is recorded. With 7A-5,
7A-1 (+follow-up), 7A-6 (+follow-up), 7A-7 and 7A-8 (+follow-up) all QAQC-passed,
**only 7A-3 (goldens) and 7A-4 (fuzz) remain open for G1** (per the handoff's
sequencing). G1 remains unsigned; 7B remains blocked until G1 and the 7A-3 goldens.

**QAQC sign-off:** 2026-11-03. Probes: `probe-commands.log` (this directory).
Scratch retained at `/tmp/opencode/qaqc-75/`.
