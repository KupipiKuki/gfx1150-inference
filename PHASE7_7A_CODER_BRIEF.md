# Phase 7A Coder Brief — Test Infrastructure

**To:** GLM5.3 (coder)
**From:** DeepSeek V4.1 Flash (primary auditor)
**Date:** 2026-11-01
**Gate:** G1 (Phase 7A)
**Base:** the tip of `vibe/phase7-220201` that contains this brief. Do not start from an older
SHA; confirm with `git log -1 --oneline` and `git rev-parse HEAD`.
**First branch:** `wp/7A-1-pytest-harness` (already created from the base).
**Status:** 7A-1, 7A-6, 7A-7, and 7A-8 are authorized. **7B is not authorized** until G1 is
signed and the 7A-3 goldens exist.

---

## 0. Read first

1. `PHASE7_IMPLEMENTATION_HANDOFF.md` — §1 roles, §2 stop points, §3 rules, §4 evidence,
   §6 7A, §7 QAQC checklist, §8 templates, §10 claims ledger.
2. `audit/AUDIT_G0_BASELINE_DEEP_2026-11-01.md` — the G0 audit; conditions C-AUD-1..5.
3. `audit/evidence/G0/7.0-baseline/baseline-report.md` and `qaqc-probes/qaqc-report.md`.
4. `audit/CLAIMS_LEDGER.md` and `audit/claims_baseline.txt` (seeded by the auditor).

The short version: **tests must be able to fail; claims must be checkable; one work package
per branch; stop at the gate.**

---

## 1. Branch and package discipline

- One work package per branch/PR. Do not bundle 7A-1, 7A-6, 7A-7, and 7A-8.
- Start **7A-1** on `wp/7A-1-pytest-harness`. After it is QAQC/auditor-approved, create
  `wp/7A-6-claims-checker`, `wp/7A-7-gpu-ci`, and `wp/7A-8-build-entrypoint` from the same
  base (or in parallel if the owner explicitly authorizes it).
- Freeze the review SHA once QAQC starts. No force-push; fixes are new commits.
- Allowed file sets are per package (below). `src/**` is off-limits for all of 7A.
- Do not touch `CMakeLists.txt` outside 7A-8.
- Do not delete, skip, or loosen a test to make a gate pass. If a test is wrong, prove it
  and get auditor approval before changing it.

---

## 2. 7A-1 — Pytest harness and marker conversion

**Branch:** `wp/7A-1-pytest-harness`
**Allowed files:** `tests/**`, `pyproject.toml` (pytest config only), `scripts/qa/**` (only
if a helper is needed), `audit/evidence/G1/7A-1/**`, docs. No `src/`, no `CMakeLists.txt`.

**Goal:** make the test suite collectable on a CPU-only host, correctly split by marker,
and *assertion-valid*.

**Tasks**
1. Add `tests/conftest.py` with a `matmul_module` fixture using `pytest.importorskip`
   (or an equivalent skip). Collection must not import the extension at module import.
2. Add `gpu` and `slow` markers in `pyproject.toml`; set `testpaths` and sensible
   `addopts`. Keep `tests/test_cpu_only.py` runnable as unittest.
3. Convert the five GPU scripts to pytest:
   - Every `test_*` function must use `assert`/`raise` and return `None`.
   - Remove `-> bool` and all `return True` / `return False` from test functions.
   - Keep the existing scientific assertions and tolerances unless an auditor approves a
     change.
4. Turn `PytestReturnNotNoneWarning` into an error (config or a meta-test), so a returning
   test cannot silently pass.
5. Confirm the marker split:
   - `pytest -m "not gpu"` collects **only** CPU tests.
   - `pytest -m gpu` collects **only** GPU tests and skips cleanly without the extension.
6. Add a mutation probe (documented in the evidence bundle): change one expected value or
   one assertion and confirm pytest fails; restore it.
7. Record the G0 correction: the old `30 passed` record was a collection smoke that
   included 18 GPU tests and 13 bool-returning functions; it is not a CPU gate.

**Acceptance**
- `python tests/test_cpu_only.py` 12/12 and `-O` 12/12.
- `pytest -m "not gpu"` passes on CPU and collects no GPU test.
- `pytest -m gpu` skips (not errors) on CPU; passes on gfx1150.
- A canary `def test_returns_false(): return False` fails, not warns/passes.
- No `def test_* -> bool` remains; no `PytestReturnNotNoneWarning`.
- Clean clone without a pre-built extension collects/skips, not exit 2.

**Evidence:** `audit/evidence/G1/7A-1/` with `env.txt`, `parent-sha.txt`,
`candidate-sha.txt`, `diffstat.txt`, `cpu-suite.log`, `gpu-suite.log`,
`gate-commands.log`, `qaqc-probes/` (QAQC later), `notes.md`. `red/green: N/A (no
behavioral change)` in `notes.md`.

---

## 3. 7A-6 — Claims checker

**Branch:** `wp/7A-6-claims-checker`
**Allowed files:** `scripts/qa/**`, `audit/CLAIMS_LEDGER.md`, `audit/claims_baseline.txt`,
`.github/workflows/**` (jobs only), `audit/evidence/G1/7A-6/**`, docs.

**Goal:** make the claims ledger enforceable, not just a table.

**Tasks**
1. Implement `scripts/qa/check_claims.py`:
   - Parse the **main** ledger table only (stop at the first non-table line; do not parse
     the ratchet sub-table as claims).
   - For each row: validate the status, the public match, and the `Qualified in place?`
     flag.
   - For `UNVERIFIED`/`NOT YET` rows whose flag is not `yes`, scan `README.md` and
     `IMPLEMENTATION_PLAN.md` for the literal. Fail if it appears unqualified.
   - For `VERIFIED` rows, require the evidence path(s) to exist.
   - Default mode: tolerate **exact** entries in `audit/claims_baseline.txt`, fail on new
     violations, warn on expired entries.
   - `--strict`: ignore the baseline entirely; fail on every violation.
   - `--json` is optional but useful for CI.
2. Review the seeded `audit/claims_baseline.txt` (15 exact entries: **11** `no`-flag rows
   plus ID 13's unqualified L209 instance). It was seeded from the G0 audit: IDs 6, 10,
   13, 14, 18–20, 26–30. Keep only exact entries; no wildcards or allow-all.
3. Enforce **claim-specific** literals. The current generic literals `pip install`, `GPU`,
   `llama-family`, and `test_cpu_only.py` are too weak; replace them with the phrase(s) the
   claim actually depends on (e.g. `Q4_0`, `Q4_K`, `Q8_0` for the kernel claim; `sdist` for
   packaging; `12 tests` for the CPU suite). Update the ledger in the same PR.
4. The checker must **report** the unqualified rows (the 11 `no` rows + ID 13 L209), not
   print "FINDINGS none". The historical `claims-check.log` is superseded; do not edit
   captured logs.
5. Wire default mode into the CPU CI job. `--strict` is advisory until G6; document that.
6. Add canary tests:
   - Inject an unqualified `NOT YET` claim; default mode fails.
   - Inject an unqualified `Q4_K_M`/`qwen2`; default mode fails.
   - Remove a `VERIFIED` evidence path; fails.
   - A generic literal that does not match the claim must not pass the negative test.

**Acceptance**
- `check_claims.py` default mode green on the seeded baseline.
- `--strict` detects all injected canaries.
- The 15 baseline entries are exact and resolve; no wildcard.
- ID 6 and 10 are `no`/`partial`, consistent with the ratchet section.
- CI runs the default checker on PR.

**Evidence:** `audit/evidence/G1/7A-6/` with the usual bundle plus `claims-check.log` and
the canary logs. `red/green: N/A (tooling; no runtime behavior change)` in `notes.md`.

---

## 4. 7A-7 — GPU CI workflow scaffold

**Branch:** `wp/7A-7-gpu-ci`
**Allowed files:** `.github/workflows/**`, `audit/evidence/G1/7A-7/**`, docs. No `src/`.

**Goal:** give G5/G6 an enforcement mechanism without pretending it is active before a
runner exists.

**Tasks**
1. Add `.github/workflows/ci-gpu.yml`:
   - `runs-on: [self-hosted, gfx1150, rocm]`
   - Build with CMake (using the same working path as 7A-8 once it lands).
   - Run `pytest -m gpu`.
   - Upload logs/artifacts (JUnit XML or text).
   - Trigger on PR and nightly.
2. Set `continue-on-error: true` until a runner registers, with a comment link to the
   runner issue. Do **not** let a skipped job count as a pass.
3. Validate the YAML locally; record the validation log.

**Acceptance**
- Workflow is valid YAML and references the right labels.
- It is explicitly `continue-on-error` (or green on a real runner) with a tracked issue.
- Logs/artifacts are uploaded when it runs.
- No claim that GPU CI is enforced yet.

**Evidence:** `audit/evidence/G1/7A-7/` with `ci-gpu.yml` content hash, YAML validation,
and a workflow-syntax/semantics note. `red/green: N/A (CI-only)`.

---

## 5. 7A-8 — Clean-clone build entry point (C-1)

**Branch:** `wp/7A-8-build-entrypoint`
**Allowed files:** `CMakeLists.txt`, `README.md` (build section), `pyproject.toml` (build
config only), `.github/workflows/**` (the clean-clone job), `tests/**` (a configure smoke
test), `audit/evidence/G1/7A-8/**`, docs. No other source changes.

**Goal:** close G0 C-1: the README's documented `cmake -B build` command fails on a clean
tree because `find_package(pybind11)` has no path.

**Tasks (choose one, justify it)**
1. Make `CMakeLists.txt` discover pybind11 from the active interpreter (e.g. a Python
   helper that sets `pybind11_DIR` as a cache default), so the documented command works
   without ambient environment variables; **or**
2. Correct the README build section to the command that actually works, and add a
   preflight that emits a clear, actionable error when `pybind11_DIR` is missing.
3. Add a CI job that starts from a fresh clone with only documented prerequisites and runs
   the documented command and build. Do not rely on a pre-existing `build/`, CMake cache,
   `PYTHONPATH`, or ambient `pybind11_DIR`.
4. Keep `setup.py` working (it already passes `pybind11_DIR`); do not regress the sdist
   install.

**Acceptance**
- Fresh clone + documented prerequisites + documented command → configure and build
  succeed with no `pybind11_DIR` and no build cache.
- The CI job reproduces it.
- README command and behavior match exactly.
- `pip install --no-build-isolation` from a fresh sdist still succeeds.
- No change to kernel sources or runtime behavior.

**Evidence:** `audit/evidence/G1/7A-8/` with the fresh-clone log, CMake configure/build
logs, sdist install log, and the CI job. This is a build/packaging change, so include a
`red.log` (documented command fails on the parent) and `green.log` (same command succeeds
on the candidate) — this is the one 7A package where red/green applies.

---

## 6. Common requirements

- **Evidence contract:** `audit/evidence/G1/<package>/` with the files in handoff §4.
  Non-behavioral packages state `red/green: N/A (no behavioral change)` in `notes.md`.
- **No source changes:** all of 7A is `src/`-free. If you believe a source change is
  required, stop and write a blocker report; do not make it.
- **No test weakening:** no deleted/skipped tests, no loosened tolerance, no changed
  golden, without written auditor approval.
- **No new runtime dependency** without approval; test-only deps (`pytest`, `hypothesis`)
  are expected.
- **Docs in the same PR:** update the handoff/ledger/README if behavior or claims change.
- **Determinism:** fixed seeds, `tmp_path`, no wall-clock assertions, no network.
- **Commit style:** reference the package ID and audit IDs; keep the diff within the
  package's file set.
- **Stop conditions:** the eight in handoff §2.2. If one triggers, write a blocker report
  and stop; do not fix forward silently.

---

## 7. Known pitfalls from the G0 audit (do not repeat)

1. **Bool-returning tests:** pytest ignores `return False`; 13 baseline tests could not
   fail. Use `assert`/raise and `None`.
2. **Missing markers:** `-m "not gpu"` ran 18 GPU tests because nothing was marked.
3. **Generic claim literals:** `pip install`/`GPU`/`llama-family` do not enforce their
   claims; use claim-specific phrases.
4. **Ledger flag inconsistency:** IDs 6/10 were `yes` while the ratchet section said they
   needed entries; the auditor corrected the flags and seeded the baseline.
5. **C-1 ownership:** 7A-5's allowed files cannot fix the build command; 7A-8 exists for
   that reason. Do not try to fix C-1 inside 7A-1/7A-5.
6. **Evidence contract:** red/green is conditional for non-behavioral packages; state N/A
   in `notes.md`.
7. **Single-run performance:** never baseline or quote one run; 7F-3 owns the benchmark
   harness.

---

## 8. Submission

For each package, provide:

```markdown
## Work package: 7A-1 — Pytest harness
Audit trace: T-1/T-2/T-3/T-6, QAQC-2, AUD-2
Parent SHA: <sha>
Candidate SHA: <sha>
Files changed: <list; confirm within allowed set>
Tests added/changed: <map to audit IDs>
Red/green: N/A (no behavioral change) | red.log/green.log paths
CPU suite: <result>
pytest not-gpu: <collected count, result>
pytest gpu: <skip on CPU / pass on gfx1150>
Mutation probe: <command + result>
Known limitations:
Rollback:
Docs updated:
Evidence bundle: audit/evidence/G1/7A-1/
```

Then stop for QAQC. Do not start the next package on the same branch.

---

## 9. Gate reminder

- **G1 is signed only when** 7A-1, 7A-2..7A-5 as scoped, 7A-6, 7A-7, and 7A-8 are
  accepted, CPU + sdist CI are green, the claims checker is green, and the fresh-clone
  documented build succeeds.
- **7B remains blocked** until G1 and the 7A-3 goldens exist.
- QAQC is independent; the coder does not sign the gate. The auditor signs G1.
