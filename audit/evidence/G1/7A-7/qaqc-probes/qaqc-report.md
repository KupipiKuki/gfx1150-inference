# QAQC Report — Work package 7A-7 (GPU CI scaffold + skip-is-not-a-pass guard)

**Role:** QAQC (independent session, per handoff §1 and `PHASE7_7A-7_BRIEF.md`)
**Date:** 2026-11-03
**Tree tested:** tip `8b38e99d88f5bed5b6c735e031aef4722e503912` on `wp/7A-7-gpu-ci`
(work commit `955fa04`; base `a873a9c` — the merged 7A state). CI/gate-state facts
verified against the **public GitHub API**; the guard re-verified by extracting it
verbatim from the parsed workflow.
**Probes:** `probe-commands.log` (this directory).

---

## Verdict

**PASS WITH CONDITIONS.** The workflow is complete, correct, and every claim about it
reproduces — the guard's four cases (extracted from the workflow's own text), the 20/20
mechanical validation, the verbatim step execution on gfx1150 (18 passed / 0 skipped),
the honest not-a-G1-pass gate state, and the API-side facts. One condition: the evidence
bundle's README (and the handoff summary) name an `actions-state.log` that **was never
committed** — every fact it would have contained is true and is verified in my probes,
but the manifest references an artifact that does not exist (QF-1). Fix by committing
the API-state capture or removing the row; my `probe-commands.log` §API is the interim
record. One observation corrects the stated rationale for the junit-vs-grep deviation
(QF-2) — the deviation itself is endorsed.

## 1. The workflow — verified clause by clause

- `runs-on: [self-hosted, gfx1150, rocm]`, triggers `pull_request` + nightly `schedule`
  (03:00 UTC) + `workflow_dispatch`, `continue-on-error: true` with the tracking issue
  (PR #8) and 7F-1 named in the header, `timeout-minutes: 60`, six steps in the brief's
  order, artifact upload `if: always()`, no secrets. **My run of the committed
  `validate-workflow.py`: 20/20 checks** (matches `yaml-validation.log`). Valid YAML.
- The bundle's `workflow.yml` is **byte-identical** to `.github/workflows/ci-gpu.yml`.
- **Steps executed verbatim on this gfx1150 host from a clean clone** (my re-run):
  `rm -rf build` → `env -u pybind11_DIR cmake -B build …` exit 0 (discovery marker
  present) → `cmake --build` exit 0 → `pytest -m gpu -v -rs --junitxml` →
  **18 passed, 43 deselected, 0 skipped** → guard exit 0. The recorded
  `configure.log`/`build.log`/`gpu-lane.log` match (same host).

## 2. The skip-is-not-a-pass guard — all four cases reproduced

The guard was **extracted verbatim from the parsed workflow** (27 lines, exactly what
the runner's shell would execute), then driven through the four cases:

| Case | Result |
|---|---|
| Real lane (extension built) | `18 passed, 0 skipped, 0 failed, 0 errors, 18 collected` → **exit 0** |
| Extension not importable | pytest itself exits **0** (the silent pass, reproduced); guard: `FAIL: the GPU lane reported no passing test` → **exit 1** |
| 3 passed + 1 skipped (synthetic junit) | `FAIL: the GPU lane skipped 1 test(s) -- a skip is not a pass` → **exit 1** |
| Nothing collected (synthetic junit) | `FAIL: the GPU lane collected no tests` → **exit 1** |

Matches `skip-guard.log` line for line. The guard's arithmetic is correct
(`passed = tests − skipped − failures − errors`), it handles both junit root shapes,
and the C-7A1-6 / QF-5 condition is genuinely closed at the design level.

## 3. The gate state — honest, and API-verified

The package claims: never executed by Actions, not a G1 pass, job will queue. All
verified against the public API:
- `ci-gpu.yml` **is on the remote** at `wp/7A-7-gpu-ci` (blob `a4dd9b1d`, 4617 bytes =
  the bundle copy).
- The repo's **workflow list contains only 2 workflows** (ci-build, ci-cpu) — the GPU
  workflow has never registered/run (its triggers don't fire on push; no PR targets
  the branch). Zero runs.
- The tip's check-runs: exactly the two push-triggered workflows, **both success**
  (the merged 7A-8 build fix included), and **no workflow-file-error check** — the
  YAML is machine-acceptable to GitHub, not just locally valid.
- **PR #8 exists, open** ("Phase 7: testing phase & evidence gates"), names 7A-7 and
  C-7A1-6 under "Still open for G1" — the tracking link in the workflow header is real.

## 4. Findings

### QF-1 (Condition — evidence manifest names a file that does not exist)
`actions-state.log` appears in the bundle README's file table ("what the GitHub REST
API knows about the workflow right now") and in the handoff summary ("records the
API-side facts"), but **it was never committed** — it is absent from the bundle, from
every commit, and from history. Every fact it would have carried is true (verified in
my §3 above), so nothing substantive is missing — the brief itself only requires
"record the gate state" (done, in `env.txt` and notes.md). But a manifest naming a
nonexistent artifact is precisely the defect class this project has flagged before
(the 7A-6 probe-log condition, Gemini's hallucinated files). **Fix**: commit an
API-state capture (trivially regenerable — my probe log shows the calls) or remove
the README row and the summary claim. Either is a one-commit, evidence-only fix.

### QF-2 (Observation — the junit-vs-grep rationale is overstated)
The notes justify junit over the brief's grep pattern by claiming a bare
`grep -q skipped` "matches text that has nothing to do with a skipped test". I tested
the brief's pattern against both real lane outputs: on the **green** lane it behaves
correctly (matches `passed`, no `skipped` substring anywhere); on the **no-extension**
lane it also behaves correctly (no `passed` match → fails; `skipped` matches are all
genuine). The claimed false positive does not materialise. The junit guard is still
the **better design** — exact counts instead of string-matching, robust to prose
changes, and it reports *how many* skipped — so the deviation stands; but the record's
stated reason should be corrected to robustness/exactness, not a phantom grep failure.

### Precision note (no action)
The candidate-SHA correction narrative is slightly off: the observed sequence is
`1986d38` (records the correct work SHA `955fa04` + adds diffstat) → `99d3802`
(wrongly re-records `1986d38`'s own SHA) → `8b38e99` (corrects back to `955fa04`,
fixes diffstat, documents the correction). The end state is correct, the
no-force-push decision was right, and the tip's `candidate-sha.txt` = `955fa04` ✅ —
only the "first push" attribution in the summary is imprecise.

## 5. Scope and the merged state

- Scope: only `ci-gpu.yml`, the 7A-7 evidence bundle, and the auditor's brief —
  restricted diff (src, tests, CMake, README, setup, pyproject, MANIFEST, scripts/qa,
  ledger, baseline) **empty** ✅.
- Merged packages still hold on this branch (my runs): claims checker default
  **PASS** (0 new / 17 baselined / 0 expired / 0 findings); canaries **12/12**;
  CPU lane **43 passed / 18 deselected** ✅.

## 6. Disposition

7A-7 **passes QAQC with one condition** (QF-1: the missing `actions-state.log` —
deliver or de-list it, evidence-only). The workflow satisfies the brief's acceptance
as far as it can without a runner, the not-a-G1-pass discipline is intact, and the
guard genuinely closes C-7A1-6/QF-5 at design level. Per the brief: G1 remains
unsigned (7A-2…7A-5 outstanding); 7B remains blocked; 7F-1 owns runner registration
and the removal of `continue-on-error`.

**QAQC sign-off:** 2026-11-03. Probes: `probe-commands.log` (this directory).
Scratch retained at `/tmp/opencode/qaqc-77/`.
