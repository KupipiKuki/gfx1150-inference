# Work package: 7A-1 follow-up — Close the auditor conditions

**Audit trace:** C-7A1-1, C-7A1-2, C-7A1-3 (`audit/AUDIT_7A-1_PYTEST_HARNESS_DEEP_2026-11-02.md` §6); AUD-7A1-1/2/3, QF-1/QF-2/QF-3
**Parent SHA:** `4e87e1274d3843aa09d4cff78e707c03c3327c3a` (branch base)
**Candidate SHA:** see `audit/evidence/G1/7A-1-followup/candidate-sha.txt`
**Branch:** `wp/7A-1-followup`
**Base:** `vibe/phase7-220201` @ `408fcab` (the merge of 7A-1)
**Allowed file set** (follow-up brief §1): `tests/test_harness_contract.py`,
`tests/` (canary helper only — none committed), the two 7A-1 evidence files,
`audit/evidence/G1/7A-1-followup/**`, docs — **respected** (see §Files changed)

---

## Files changed

```
 audit/evidence/G1/7A-1-pytest-harness/coder-report.md |  44 ++-   (QF corrections)
 audit/evidence/G1/7A-1-pytest-harness/notes.md         |  50 ++--  (QF corrections)
 tests/test_harness_contract.py                          | 295 +++++++----
```

**Within the allowed set — confirmed.** The diff for `src/`, `pyproject.toml`,
`CMakeLists.txt`, `setup.py`, `MANIFEST.in`, `.github/`, `README.md`,
`IMPLEMENTATION_PLAN.md` and `audit/CLAIMS_LEDGER.md` is **empty** (proved in
`audit/evidence/G1/7A-1-followup/diffstat.txt`). The five GPU test files and
`test_cpu_only.py` are also untouched, so **no scientific assertion or
tolerance changed** (per-file threshold sets are identical to the parent).

## What changed

### C-7A1-1 — the lane check is now exact

`test_gpu_lane_is_marked_and_cpu_lane_is_not` (presence-only: accepted any
`pytest.mark.<word>`) is replaced by
**`test_every_test_module_declares_its_exact_lane`**:

- every `tests/test_*.py` must appear in `EXPECTED_LANES`, so a new module
  forces a deliberate lane choice;
- the declared `pytestmark` must be exactly the expected marker — read from
  the AST at module scope, so a `pytestmark` inside a function is not mistaken
  for a module-level one, while a module-level `if` guard is honoured;
- a module in the `cpu` lane may not **hard-depend** on the extension.

A hard dependency is a request for the `matmul_module` fixture or an
**unguarded** `import matmul_module` in a test body. A guarded import (inside a
`try` whose handler catches `ImportError`, with a stub fallback) is optional —
`tests/test_cpu_only.py` uses exactly that pattern — so it does not make the
module a GPU test.

### C-7A1-2 — nested raises/asserts no longer count

`test_every_test_function_asserts_or_raises` now measures **all four** failure
mechanisms (`assert`, `raise`, `self.assertX(...)`, `doraise=True`) through the
single nested-def-pruning visitor `_OwnBodyVisitor`, which does not descend into
nested `FunctionDef` / `AsyncFunctionDef` / `Lambda` / `ClassDef`. A test needs
a **top-level** failure path.

### C-7A1-3 — the record is corrected (QF-1 / QF-2 / QF-3)

Applied to the 7A-1 `notes.md` and `coder-report.md`. **Captured logs were not
edited.**

- **QF-1:** only `tests/conftest.py` is absent from the sdist;
  `tests/test_harness_contract.py` **is** packaged (it matches `tests/test_*.py`).
  Verified by building the sdist. The 7A-5 `MANIFEST.in` fix is still required,
  for `conftest.py` alone (**C-7A1-5**).
- **QF-2:** "two commits" → "a content commit plus follow-up commits".
- **QF-3:** "13 tests could not fail" → precisely: **13 returned `bool`**, **4
  of those also had asserts**, **9 had no failure mechanism at all**, and a
  **14th** returned a tuple from a nested helper. Verified by AST against
  `2659e6c`.

## Tests added/changed

| Test | Audit ID | What it proves |
|---|---|---|
| `test_every_test_module_declares_its_exact_lane` | AUD-7A1-1 | Every module is classified in `EXPECTED_LANES`, declares exactly that lane, and a `cpu` module does not hard-depend on the extension. |
| `test_every_test_function_asserts_or_raises` | AUD-7A1-2 | Every test has a **top-level** failure path; a nested helper's `raise` does not count. |
| `test_cpu_only_module_is_not_marked_gpu` | — | Retained so the specific CPU-lane regression stays named (it is now implied by `EXPECTED_LANES`). |

**red/green:** the canary pair — the **old** meta-test accepts the canary
(red), the **strengthened** meta-test rejects it (green). Recorded in
`audit/evidence/G1/7A-1-followup/canary-wronglane.log` and `canary-nested.log`.
The canary files are temporary evidence artifacts and are **not committed**.

## Suite results

| Suite | Result |
|---|---|
| **CPU suite** — `pytest -m "not gpu"` | **37 passed**, 18 deselected — exit 0 |
| **CPU suite** — `python tests/test_cpu_only.py` | **12/12** — exit 0 |
| **CPU suite** — `python -O tests/test_cpu_only.py` | **12/12** — exit 0 |
| **GPU suite** — `pytest -m gpu` (gfx1150) | **18 passed**, 37 deselected — exit 0 |
| **Clean clone, no extension** — `pytest -m gpu` | **18 skipped** — exit 0 |
| **C-7A1-1 canary** | old check **passes** (exit 0, defect) → new check **fails** (exit 1, fixed) |
| **C-7A1-2 canary** | old check **passes** (exit 0, defect) → new check **fails** (exit 1, fixed) |
| Suite green after the canaries are removed | **37 passed**, 18 deselected — exit 0 |

The CPU lane count is unchanged at 37, as the brief's acceptance requires. Per
audit observation AUD-7A1-7, those 37 are **not** "37 CPU runtime tests":
12 are the `test_cpu_only.py` runtime suite and 25 are harness meta-tests.

## Mutation probe

The canaries are this package's mutation probe: each breaks one meta-test
invariant and the suite must reject it.

- C-7A1-1: a module marked `cpu` that requests the `matmul_module` fixture.
- C-7A1-2: a test whose only `raise` is inside a nested, never-called helper.

Both are rejected at the strengthened meta-test (exit 1) and the suite is green
again once removed (exit 0).

## Known limitations

1. **`tests/conftest.py` is still absent from the sdist** — unchanged by this
   package (QF-1 corrected the *record*). The packaging fix is **C-7A1-5**,
   owned by 7A-5: add `recursive-include tests *.py` to `MANIFEST.in` so the CPU
   CI job can run `pytest -m "not gpu"` from the installed tree.
2. **CI is still not wired to pytest** — 7A-5 (`.github/` is outside this
   package's allowed file set).
3. **The GPU lane still skips rather than fails without the extension** —
   **C-7A1-6**, owned by 7A-7 / G5 / G6. Those gates must assert the lane
   *runs* (18 passed, 0 skipped) on gfx1150.
4. **The strengthened lane check requires every new test module to be added to
   `EXPECTED_LANES`.** Deliberate — it forces a lane choice — but 7A-3 (goldens)
   and 7A-4 (fuzz) add test files and **must** add their entries or the CPU
   lane will fail. Flagged so this is not discovered as a surprise at G1.
5. **The old meta-test name is gone.** `test_gpu_lane_is_marked_and_cpu_lane_is_not`
   was replaced by `test_every_test_module_declares_its_exact_lane`; QAQC's
   re-run instruction names the old test. `test_cpu_only_module_is_not_marked_gpu`
   is retained.

## Rollback

`git revert` the follow-up commit. Only
`tests/test_harness_contract.py` and two markdown evidence files are involved, so
rollback restores the previous meta-tests exactly and cannot change runtime
behaviour.

## Docs updated

The 7A-1 `notes.md` and `coder-report.md` (the QF-1/QF-2/QF-3 corrections) and
the new `audit/evidence/G1/7A-1-followup/notes.md`. No public documentation
changed: `README.md` and `IMPLEMENTATION_PLAN.md` are untouched.

## Claims changed

**None.** No public capability, correctness or performance claim changed.
`audit/CLAIMS_LEDGER.md` and `audit/claims_baseline.txt` are unchanged. No
`claims-check.log` applies: `scripts/qa/check_claims.py` is **7A-6** and does
not exist at this commit.

## Evidence bundle

`audit/evidence/G1/7A-1-followup/`

```
env.txt  parent-sha.txt  candidate-sha.txt  diffstat.txt
cpu-suite.log  gpu-suite.log  gate-commands.log
canary-wronglane.log  canary-nested.log  notes.md
```

## Self-assessment against the follow-up brief's acceptance

| Criterion | Result |
|---|---|
| `pytest -m "not gpu"` → 37 passed, 18 deselected | PASS |
| `pytest -m gpu` on gfx1150 → 18 passed, 37 deselected | PASS |
| `pytest -m gpu` without the extension → 18 skipped, exit 0 | PASS |
| `python tests/test_cpu_only.py` and `-O` → 12/12 | PASS |
| C-7A1-1 canary fails the updated meta-test | PASS — exit 1 (`canary-wronglane.log`) |
| C-7A1-2 canary fails the updated meta-test | PASS — exit 1 (`canary-nested.log`) |
| Both canaries removed, suite green | PASS — 37 passed, exit 0 |
| No `src/`, `pyproject.toml`, build, packaging, CI, README, ledger, or `CMakeLists.txt` change | PASS — `diffstat.txt` |
| Scientific assertions and tolerances unchanged | PASS — per-file threshold sets identical; the five GPU test files and `test_cpu_only.py` are untouched |
| Within the allowed file set | PASS — `diffstat.txt` |
| No test deleted, skipped or weakened | PASS — the meta-tests are stricter, not weaker |
| No captured log edited | PASS — the corrections are in `notes.md` / `coder-report.md` |

**Stop condition check:** none of the eight stop conditions in handoff §2.2 was
triggered. No claim was made without a reproducible command and artifact.

**Stopping here for QAQC.** Per the follow-up brief §5, 7A-6/7A-7/7A-8 are not
started on this branch. The coder does not sign G1.
