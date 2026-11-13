# QAQC Report — Work package 7A-8 (clean-clone build entry point, G0 C-1)

**Role:** QAQC (independent session, per handoff §1 and `PHASE7_7A_CODER_BRIEF.md` §5)
**Date:** 2026-11-02
**Tree tested:** work commit `9c049129e2f39ac2022442416d8fcb0feb7b465f` (candidate;
evidence commit `abc5870`; parent `4bcffeb`). Probes ran on **fresh clones** of the
parent and the candidate — no shared cache, no ambient `pybind11_DIR`.
**Probes:** `probe-commands.log` (this directory).

---

## Verdict

**PASS WITH CONDITIONS.** The build fix itself is verified end to end and is exactly
what G0 C-1 demanded: the documented command now works from a fresh clone with no
ambient hints, on both classes of environment, with an explicit `-Dpybind11_DIR`
still winning, a real regression guard, the sdist path unregressed, and the scope
respected. One condition must be closed before the "CI reproduces it" acceptance is
met: **the committed CI job cannot run green** — its smoke-test step runs
`python -m pytest` but nothing in the job installs pytest (QF-1). One merge note
(QF-2) goes on the G1 checklist.

## 1. The red/green deliverable — reproduced from fresh clones

| Probe | Result |
|---|---|
| **P1 RED**: parent `4bcffeb` fresh clone, shims-only PATH, `env -u pybind11_DIR`, no cache | **exit 1** at `CMakeLists.txt:17` — "Could not find a package configuration file provided by pybind11" (the C-1 defect, byte-for-byte the G0 record) |
| **P2 RED, the "lucky" case**: same parent, interpreter's own bin on PATH | **exit 0** — the environment-dependence claim confirmed independently: the parent only ever worked when PATH advertised the interpreter's prefix |
| **P3 GREEN**: candidate fresh clone, shims-only PATH, no `pybind11_DIR`, no cache | **exit 0** with the explicit marker `pybind11 CMake package: <site-packages path>` |
| **P4 GREEN, lucky PATH**: candidate with interpreter bin on PATH | exit 0 — still the explicit discovery (found via the prefix fast path) |
| **P5 override**: explicit `-Dpybind11_DIR=...` on the candidate | exit 0 — no regression for callers that pass the hint |
| **P6 the guard**: `tests/test_build_configure.py` against the **parent's** CMakeLists | **FAILS** (`1 failed`: the locator test) — then passes on the restored candidate. A real guard, not a tautology |
| **P7 build + GPU lane**: `cmake --build` on the P3 configure | exit 0, `matmul_module.so` 592,488 bytes; `pytest -m gpu` **18 passed** with that artifact |
| **P11 sdist**: build sdist + full clean-venv `pip install --no-build-isolation` (live) | exit 0; **all 7 modules import**; `gfx1150-infer --help` exit 0 — the packaging path is unregressed |

Both judgement calls are **endorsed**: (a) discovery before `project()` — I verified
the ROCm paths are still set before `project()` (HIP detection untouched) and that the
guard test and CI can check the fix without ROCm; (b) recording both PATH cases in
`red.log` — I reproduced both myself; a build must not depend on which PATH the caller
happens to have, and now the record proves it doesn't.

## 2. Remaining acceptance items — verified

- **Suites unchanged and explained**: `pytest -m "not gpu"` **43 passed / 18 deselected**,
  `-m gpu` **18 passed / 43 deselected**, full `pytest -q` **61** (live, matches the
  recorded logs). The count arithmetic in the notes is correct: 37 + 3 new tests
  + 3 new parametrized lane-contract items (the contract tests parametrize over test
  modules, so the new module adds items). `test_cpu_only.py` 12/12 normal and `-O`.
- **Lane contract**: `test_build_configure.py` registered in `EXPECTED_LANES` as
  `cpu` with `pytestmark = pytest.mark.cpu` — the 7A-1 follow-up's requirement for new
  modules was followed; the contract tests pass over the new module.
- **README**: documented command unchanged; additions are confined to the build section
  (prerequisites table, project-tree line, discovery explanation) — within 7A-8's
  allowed README scope. The command now matches the verified path.
- **Scope**: `setup.py`, `pyproject.toml`, `MANIFEST.in`, `src/`, `scripts/qa/**`,
  `audit/CLAIMS_LEDGER.md`, `audit/claims_baseline.txt`, and the 7A-6 evidence — all
  **empty diffs**. The evidence commit touches only the evidence bundle.
- **Provenance**: clean this time — `env.txt` records HEAD = candidate `9c04912`
  directly (no amend-cycle artifacts); `candidate-sha.txt`/`parent-sha.txt` correct;
  `diffstat.txt`'s "6 files, 327(+)/3(−)" matches the work commit exactly.
- **The ROCm key claim verified**: the workflow's signing key fingerprint
  (`D0F0 04A0 025A 1145 C780 7FCD 0701 EAC4 D5E0 2107`) matches this host's existing
  `/etc/apt/keyrings/amdrocm.gpg` keyring **exactly** — checked, not assumed, as claimed.
- `ci-build.yml` is valid YAML (10 steps, `runs-on: ubuntu-24.04`, consistent with the
  `ubuntu2404` repo path).

## 3. Conditions and notes

### QF-1 (Condition — blocks the "CI reproduces it" acceptance) — the CI job cannot run green as committed
`ci-build.yml` step "Run the configure smoke test" executes
`python -m pytest tests/test_build_configure.py -v`, but **nothing in the job installs
pytest**: the prerequisites step installs `numpy`, `setuptools`, `wheel`, `pybind11`
only, and `actions/setup-python@v5` provisioners do not ship pytest. On the stock
runner the step will fail with `No module named pytest`, so the job goes red on its
first run — the branch is already pushed, so this will surface immediately. Note the
contrast with `ci-cpu.yml`, which deliberately avoids pytest by running unittest mode;
this job *requires* pytest. **Fix**: add `pytest` to the prerequisites step
(`python -m pip install --upgrade pip numpy setuptools wheel "pybind11>=2.12" pytest`),
then show **one green run** of the job (or record the run log) so the acceptance item
"The CI job reproduces it" is demonstrated, not just designed. This does not affect
the fix itself, the tests, or any local verification.

### QF-2 (Merge note for the G1 checklist) — the README shift moves the 7A-6 ledger's pinned references
This package's README additions (prerequisites table etc.) shift later lines: the
`PYTHONPATH=build` block moves from **L85–L89 to L97–L101** (+12), and lines after the
second insertion shift +18. The 7A-6 branch's ledger scope annotations pin README
lines 103/104 and 109–111 (claims 8–12, 21) and the ID-3 locator prose pins L85–L89.
None of that is on this branch (7A-8 is based on `4bcffeb`, parallel to 7A-6), so
nothing here is wrong — but **at merge time** `check_claims.py` will emit drift
warnings (its designed behavior) and the ledger references will need the same refresh
exercise the 7A-6 follow-up just performed for a +1 shift, only larger. The
`id3_claim_removed` canary is line-number-independent (it reads the literal from the
ledger) and survives. 7A-8's notes don't mention this merge cost; it should be on the
G1 merge checklist, not discovered as a surprise.

### Observation (cost, honestly disclosed)
The job installs ROCm from AMD's stable apt repository on every push/PR — a
multi-gigabyte download. Recorded as an open cost decision in notes §limitations 2
rather than hidden; the auditor may want to decide (narrow to configure-only, or move
the build to the self-hosted runner) before G1.

## 4. Disposition

The **build fix passes QAQC unconditionally** — red→green verified from fresh clones on
both environment classes, the guard test genuinely fails on the parent, the override
still wins, the sdist path is unregressed, the scope is respected, and the keyring
claim checks out. G0 **C-1 is closed in substance** by this package. The package as a
whole is **PASS WITH CONDITIONS**: close QF-1 (pytest in `ci-build.yml` + one green run
or equivalent evidence) before the "CI reproduces it" acceptance is credited at G1;
carry QF-2 to the G1 merge checklist. G1 remains unsigned (7A-2…7A-5, 7A-7
outstanding); 7B remains blocked.

**QAQC sign-off:** 2026-11-02. Probes: `probe-commands.log` (this directory).
Scratch retained at `/tmp/opencode/qaqc-78/` (parent/candidate fresh clones, build
dirs, venv).
