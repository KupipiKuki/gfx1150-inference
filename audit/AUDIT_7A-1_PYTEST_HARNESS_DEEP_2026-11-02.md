# Independent 7A-1 Audit — Pytest Harness

**Auditor:** DeepSeek V4.1 Flash (independent of the coder and QAQC)
**Date:** 2026-11-02
**Target:** `wp/7A-1-pytest-harness` @ `cefebef9b78aa022b5ffe8d5dae13a31b3c83ef4`
**Content candidate:** `f0ce20e0021a313d3cb23a33f9b97b2638f56176`
**Parent:** `2659e6c33fec50a6768cd35bb264d6f7453e6c0e`
**Coder:** GLM5.3 · **QAQC:** independent session (report in `qaqc-probes/`)
**Gate:** G1 / work package 7A-1 only. **G1 itself remains unsigned** (7A-2..7A-8 outstanding).

---

## 1. Verdict

**PASS WITH CONDITIONS — 7A-1 meets its stated acceptance criteria and is accepted in
substance, but is not merge-approved until C-7A1-1/2/3 land.**

The harness conversion is real and well done: the extension is obtained through a
fixture, the lanes are correctly split, all 18 GPU tests and the CPU lane pass, a clean
clone no longer errors with exit 2, and the bool-return defect is fixed in the actual
tests. I reproduced the full gate independently.

Two of the **new meta-tests that are supposed to prevent AUD-2 from regressing do not
enforce what they claim**: a wrong-lane module and a test with only a nested, never-called
`raise` both pass the contract. These are defects in the guard, not in the converted
suite, so they are conditions rather than a rejection. Three documentation errors from the
QAQC report (QF-1..3) also need correction. The QAQC artifacts were staged but not
committed; they are included in this audit commit.

---

## 2. Method

Fresh clone of `wp/7A-1-pytest-harness` at `cefebef` (no in-tree `build/`, `dist/`, or
cache), fresh out-of-repo CMake build, and the probes in
`audit/evidence/G1/7A-1-pytest-harness/audit-probes/`.

---

## 3. Reproduction results

| Check | Result |
|---|---|
| Candidate/tip test surface | `git diff f0ce20e..HEAD -- tests pyproject.toml` empty |
| `pytest -m "not gpu"` with extension | **37 passed, 18 deselected**, exit 0 |
| `pytest -m "not gpu"` without extension | **37 passed, 18 deselected**, exit 0 |
| `pytest -m gpu` with extension (gfx1150) | **18 passed, 37 deselected**, exit 0 |
| `pytest -m gpu` without extension | **18 skipped**, exit 0 (actionable reason) |
| `pytest -m gpu --collect-only` without extension | 18/55 collected, exit 0 (was exit 2) |
| `python tests/test_cpu_only.py` / `-O` | 12/12 each, exit 0 |
| Five GPU scripts standalone | exit 0 each |
| `def test_* -> bool` | none |
| Canary `return False` / `return True` | **5 failed**, exit 1 (both canaries + 3 contract tests) |
| Mutation (`test_layer` rmsnorm `2e-3`→`1e-12`) | **1 failed**, exit 1; restored → pass |
| `pytest -m cpu` | 37 passed, 18 deselected |
| Allowed file set | only `tests/**`, pytest config, evidence bundle; `src/`/build/CI/docs diffs empty |
| Test names/tolerances | identical to parent; assertions strictly stronger (QAQC static check confirmed) |

No previously green suite regressed. No stop condition in handoff §2.2 was triggered by
the converted suite.

---

## 4. Findings

### AUD-7A1-1 (Medium) — The lane meta-test only checks that *some* marker exists

`tests/test_harness_contract.py::test_gpu_lane_is_marked_and_cpu_lane_is_not` searches for
`pytestmark\s*=\s*pytest\.mark\.\w+` and accepts any marker. It does not verify that GPU
modules use `.gpu` and CPU modules use `.cpu`.

Probe: a temporary module marked `pytestmark = pytest.mark.cpu` whose test requests the
`matmul_module` fixture (a GPU test by construction) passes the contract:

```
pytest tests/test_harness_contract.py::test_gpu_lane_is_marked_and_cpu_lane_is_not -q
1 passed
```

That is the exact lane-split defect AUD-2 was about, now unguarded for future modules.

**Required:** assert the exact lane per module (GPU modules → `pytest.mark.gpu`; CPU
modules → `pytest.mark.cpu`) or compare collected node sets for `-m gpu` / `-m "not gpu"`
against the expected module lists. Add the wrong-lane module as a negative canary that
must fail the contract.

### AUD-7A1-2 (Medium) — The assertion meta-test counts raises inside nested functions

`test_every_test_function_asserts_or_raises` walks each test body with `ast.walk` for
`Raise`, `self.assertX`, and `doraise=True`. Unlike `_OwnBodyVisitor`, it descends into
nested function definitions. A test whose body contains only a nested, never-called helper
with `raise` passes:

```
pytest tests/test_harness_contract.py::test_every_test_function_asserts_or_raises -q -k test_audit_nested
1 passed
```

The test has no top-level failure path but satisfies the contract.

**Required:** use the same nested-def-pruning visitor for all failure mechanisms (assert,
raise, `self.assertX`, `doraise`), or require a top-level failure path. Add the
nested-raise-only module as a negative canary that must fail the contract.

### AUD-7A1-3 (Minor) — QAQC record corrections QF-1..QF-3

- **QF-1:** `notes.md` §6.1 and the coder report say both `tests/conftest.py` and
  `tests/test_harness_contract.py` are excluded from the sdist. Only `conftest.py` is
  absent; `test_harness_contract.py` is packaged (it matches `tests/test_*.py`). Verified
  by building the sdist. Correct the wording; the 7A-5 conclusion (add
  `recursive-include tests *.py` for `conftest.py`) stands.
- **QF-2:** `notes.md` §4 says “two commits”; the package is four (implementation,
  bundle, notes-structure, coder report). Use “a content commit plus follow-ups”.
- **QF-3:** “13 tests could not fail” is imprecise: 13 returned `bool`, 5 of those also
  had asserts, 9 had no failure mechanism at all, and a 14th returned a tuple from a
  nested helper. The fix covers all of them; state it precisely.

These are record corrections only; captured logs must not be edited.

### AUD-7A1-4 (Process) — QAQC artifacts were staged, not committed

The QAQC report and probe log are in the index (`A`), not in a commit. This audit commit
includes them. No further action for 7A-1; future packages must commit QAQC artifacts
before the auditor signs.

### AUD-7A1-5 (Carry-forward) — `conftest.py` is missing from the sdist

Confirmed: an sdist-installed tree has no `conftest.py`, so no `matmul_module` fixture and
no GPU-lane skip. A CPU CI job running `pytest -m gpu` from such a tree would error. 7A-5
must add `recursive-include tests *.py` and assert that the installed tree collects cleanly.

### AUD-7A1-6 (Carry-forward) — GPU lane must fail on a skip at G5/G6

Without the extension the lane correctly skips (18 skipped). On gfx1150 the lane must be
asserted to **run** (18 passed, 0 skipped); 7A-7's workflow must fail on any skip in the
GPU lane, not accept it.

### AUD-7A1-7 (Observation) — CPU count composition

“37 passed” is 12 `test_cpu_only` tests + 25 harness meta-tests. That is fine; state it so
the G0 “30 passed” correction is not confused with “37 real CPU runtime tests”.

---

## 5. What is confirmed (no action)

- The four AUD-2 failure modes are fixed in the actual suite: no bool returns, no
  module-scope extension import, correct lane split, and the return warning is an error.
- Assertions and tolerances are unchanged; test names are identical; the suite is
  strictly stronger.
- The clean-clone exit-2 defect is gone; CPU-only hosts get 37 passed + 18 skipped.
- The standalone script mode still works; `test_cpu_only.py` still runs without pytest.
- No `src/`, build, packaging, CI, ledger, or public-doc change.
- The mutation and canary probes genuinely fail, not warn/pass.

---

## 6. Conditions and gate impact

| ID | Condition | Owner | Target | Blocks |
|---|---|---|---|---|
| **C-7A1-1** | Strengthen the lane meta-test to assert the actual marker per module; add a wrong-lane negative canary. | 7A-1 coder | before 7A-1 merge | 7A-1 merge / G1 |
| **C-7A1-2** | Strengthen the asserts/raises meta-test to ignore nested defs; add a nested-raise negative canary. | 7A-1 coder | before 7A-1 merge | 7A-1 merge / G1 |
| **C-7A1-3** | Correct QF-1/QF-2/QF-3 wording in `notes.md` and the coder report; do not edit captured logs. | 7A-1 coder | before 7A-1 merge | 7A-1 merge / G1 |
| **C-7A1-4** | Commit QAQC artifacts. | auditor | done in this audit | — |
| **C-7A1-5** | Add `recursive-include tests *.py`; assert the installed sdist tree collects cleanly (conftest present). | 7A-5 | G1 | G1 |
| **C-7A1-6** | GPU CI must fail on a skip; require 18 passed / 0 skipped on gfx1150. | 7A-7 / G5/G6 | G5/G6 | G5/G6 |

**Gate impact:**
- 7A-1 is **accepted in substance** and may proceed to a small follow-up commit for
  C-7A1-1/2/3. No re-run of the whole gate is required; QAQC should re-run the two
  strengthened meta-tests and the negative canaries.
- **7A-6, 7A-7, and 7A-8 may start in parallel** from `2659e6c`; they do not depend on the
  harness meta-test internals.
- **G1 remains unsigned**: 7A-2..7A-5 and the C-7A1-5 carry-forward are still outstanding.
- **7B remains blocked** until G1 is signed and the 7A-3 goldens exist.

---

## 7. Sign-off

**7A-1 decision: PASS WITH CONDITIONS.** The work is real and the acceptance criteria are
met; the two meta-test guards need strengthening before merge, and the record needs the
QAQC corrections. This is a narrow follow-up, not a redesign.

**Sign-off:** DeepSeek V4.1 Flash, 2026-11-02.
