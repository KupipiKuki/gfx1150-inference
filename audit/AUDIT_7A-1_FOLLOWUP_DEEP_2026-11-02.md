# Independent 7A-1 Follow-up Audit — Conditions C-7A1-1/2/3

**Auditor:** DeepSeek V4.1 Flash (independent of the coder and QAQC)
**Date:** 2026-11-02
**Target:** `wp/7A-1-followup` @ `2af8369e02bb85b355796a7bd8da88f78404cb3f`
**Content candidate:** `ea8e84a1e708ee114ae611f2b257b81eaa57c12a`
**Parent:** `4e87e1274d3843aa09d4cff78e707c03c3327c3a` (branch base)
**Coder:** GLM5.3 · **QAQC:** independent session (`qaqc-probes/qaqc-report.md`)
**Scope:** 7A-1 follow-up only. **G1 remains unsigned** (7A-2..7A-8 outstanding).

---

## 1. Verdict

**PASS — all three auditor conditions are closed.**

C-7A1-1, C-7A1-2, and C-7A1-3 are genuinely fixed. I reproduced the strengthened lane
check, the nested-def pruning, the two canaries, the two additional rejection paths QAQC
added, the QF-1/QF-2/QF-3 corrections, and the full CPU/GPU suite. No stop condition was
triggered, no source/build/packaging/CI surface changed, and no scientific assertion or
tolerance changed.

The follow-up is merge-approved. The auditor's ignored `probe-commands.log` is now
force-added, so the 7A-1 P-AUD-1/P-AUD-2 transcript is part of the record.

---

## 2. Method and reproduction

Fresh clone of `wp/7A-1-followup` at `2af8369` (no in-tree `build/`, `dist/`, or cache);
fresh out-of-repo CMake build. Probe logs in
`audit/evidence/G1/7A-1-followup/audit-probes/`.

| Check | Result |
|---|---|
| Candidate/tip test surface | `git diff ea8e84a..HEAD -- tests pyproject.toml` empty |
| `pytest -m "not gpu"` with extension | **37 passed, 18 deselected**, exit 0 |
| `pytest -m "not gpu"` without extension | **37 passed, 18 deselected**, exit 0 |
| `pytest -m gpu` with extension (gfx1150) | **18 passed, 37 deselected**, exit 0 |
| `pytest -m gpu` without extension | **18 skipped**, exit 0 |
| `python tests/test_cpu_only.py` / `-O` | 12/12 each, exit 0 |
| Exact-lane meta-test | passes on the real suite |
| Nested-def assertion meta-test | passes on the real suite |
| Allowed file set | only `tests/test_harness_contract.py`, the two 7A-1 evidence markdowns, and the follow-up bundle; `src/`, `pyproject.toml`, build, CI, README, ledger unchanged |

---

## 3. Condition closure

### C-7A1-1 — exact lane check: **CLOSED**

The presence-only check was replaced by
`test_every_test_module_declares_its_exact_lane` with an `EXPECTED_LANES` mapping and a
`_module_lane` AST reader. I reproduced all three rejection paths:

| Probe | Result |
|---|---|
| Temporary `cpu`-marked module using `matmul_module`, not in the mapping | **fails** — “not classified — add it to EXPECTED_LANES” |
| Existing `test_layer.py` marker temporarily changed `gpu` → `cpu` | **fails** — “test_layer.py: pytestmark is 'cpu', expected 'gpu'” |
| Temporary `cpu`-classified module using `matmul_module` | **fails** — “uses the matmul_module extension but is in the 'cpu' lane” |

The temporary files/edits were removed; `git diff` was empty afterward. The `if`-guarded
`pytestmark` in `test_cpu_only.py` is read correctly (the suite passes 37/18).

### C-7A1-2 — nested failure paths: **CLOSED**

`_OwnBodyVisitor` now collects `assert`, `raise`, `self.assertX(...)`, and `doraise=True`
without descending into nested `FunctionDef`/`AsyncFunctionDef`/`Lambda`/`ClassDef`.

I reproduced two rejection paths:

- a test whose only `raise` is inside a nested, never-called helper → **fails**;
- a test whose only `assert` is inside a nested helper → **fails**.

Both temporary files were removed; the suite returned to green.

### C-7A1-3 — record corrections: **CLOSED**

- **QF-1:** the corrected text says only `tests/conftest.py` is absent from the sdist and
  `tests/test_harness_contract.py` is packaged. I rebuilt the sdist: confirmed.
- **QF-2:** “two commits” is now “a content commit plus follow-up commits”.
- **QF-3:** the corrected text is **13 bool-returners, 4 with asserts, 9 with no failure
  mechanism, 1 tuple-returner**. My independent AST count against `2659e6c` matches
  exactly. (QAQC's original “5 with asserts” was arithmetically wrong; QAQC appended a
  dated erratum to its own 7A-1 report.)

Captured logs were not edited; the corrections live only in `notes.md` and
`coder-report.md`.

---

## 4. Additional findings / forward flags

No findings against this package.

1. **Auditor artifact fixed.** `audit/evidence/G1/7A-1-pytest-harness/audit-probes/probe-commands.log`
   was ignored by the global `*.log` rule and never force-added. It is force-added in this
   audit commit; the coder correctly did not touch it (outside its allowed set).
2. **Forward flag (7A-3/7A-4):** `EXPECTED_LANES` deliberately requires every new test
   module to be classified. The goldens and fuzz packages must add their entries or the
   CPU lane will fail. Already documented by the coder; repeated on the G1 checklist.
3. **Carry-forward (7A-5):** `conftest.py` is still absent from the sdist; add
   `recursive-include tests *.py` and assert the installed tree collects. (C-7A1-5)
4. **Carry-forward (7A-7/G5/G6):** the GPU lane skips without the extension; the CI gate
   must assert 18 passed / 0 skipped on gfx1150. (C-7A1-6)

---

## 5. Gate impact

- **7A-1:** conditions closed; **merge-approved** with the follow-up.
- **7A-6:** may start from the corrected integration tip. Its new test module must be added
  to `EXPECTED_LANES`.
- **7A-7/7A-8:** may start from the corrected integration tip when authorized.
- **G1:** still unsigned — 7A-2..7A-5 and C-7A1-5 remain.
- **7B:** blocked until G1 and the 7A-3 goldens.

---

## 6. Sign-off

**7A-1 follow-up decision: PASS.** Conditions C-7A1-1/2/3 are closed and independently
reproduced. Merge approved.

**Sign-off:** DeepSeek V4.1 Flash, 2026-11-02.
