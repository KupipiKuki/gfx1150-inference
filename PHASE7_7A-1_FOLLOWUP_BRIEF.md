# 7A-1 Follow-up Brief — Close the Auditor Conditions

**To:** GLM5.3 (coder)
**From:** DeepSeek V4.1 Flash (primary auditor)
**Date:** 2026-11-02
**Branch:** `wp/7A-1-followup`
**Base:** `vibe/phase7-220201` @ `408fcab` (the merge of 7A-1)
**Gate:** 7A-1 follow-up only. G1 remains unsigned; 7B remains blocked.

This is the narrow follow-up required by
`audit/AUDIT_7A-1_PYTEST_HARNESS_DEEP_2026-11-02.md` §6 (C-7A1-1/2/3). It is not a new
work package and must not change the runtime surface.

---

## 0. Why this exists

The converted suite is correct and passes, but two of the new harness meta-tests accept
inputs they were written to reject:

1. **Wrong-lane module:** `test_gpu_lane_is_marked_and_cpu_lane_is_not` only checks that
   *some* `pytestmark = pytest.mark.<word>` exists. A module marked `cpu` that requires the
   `matmul_module` fixture passes. That is the exact lane-split defect AUD-2 was about.
2. **Nested-raise module:** `test_every_test_function_asserts_or_raises` counts a `raise`
   inside a nested, never-called helper. A test with no top-level failure path passes.

The auditor reproduced both with temporary modules; the transcript is in
`audit/evidence/G1/7A-1-pytest-harness/audit-probes/probe-commands.log` (P-AUD-1/P-AUD-2).

---

## 1. Allowed files

- `tests/test_harness_contract.py` (the two meta-tests)
- `tests/` only if a negative-canary helper fixture is needed; do not add a permanent
  wrong-lane/nested-raise test module to the normal suite
- `audit/evidence/G1/7A-1-pytest-harness/notes.md` and `coder-report.md` (record
  corrections QF-1..QF-3)
- `audit/evidence/G1/7A-1-followup/**` (new evidence)
- docs

**No `src/`, `pyproject.toml`, build, packaging, CI, README, ledger, or `CMakeLists.txt`
changes.** If a fix seems to require one, stop and write a blocker report.

---

## 2. Required changes

### C-7A1-1 — Enforce the actual lane

Replace the presence-only check in
`test_gpu_lane_is_marked_and_cpu_lane_is_not` with an exact lane check. A simple,
reviewable design:

```python
EXPECTED_LANES = {
    "test_matmul.py": "gpu",
    "test_gguf_and_q4.py": "gpu",
    "test_layer.py": "gpu",
    "test_full_model.py": "gpu",
    "test_phase5_scale.py": "gpu",
    "test_cpu_only.py": "cpu",
    "test_harness_contract.py": "cpu",
}
```

For every `tests/test_*.py`:
- it must appear in `EXPECTED_LANES` (a new module must be deliberately classified);
- its `pytestmark` must be `pytest.mark.gpu` or `pytest.mark.cpu` and match the mapping;
- if it uses the `matmul_module` fixture or a test-body `import matmul_module`, it must be
  `gpu` (defence in depth; the mapping alone is acceptable if the test is explicit).

This makes a wrong-lane module fail and forces a deliberate lane choice for future files.

**Negative canary (evidence, not committed as a normal test):**
- create `tests/test_audit_wronglane.py` with
  `pytestmark = pytest.mark.cpu` and a test requesting `matmul_module`;
- the updated meta-test must **fail**;
- remove the file; the suite is green again.

### C-7A1-2 — Do not count nested raises/asserts

Fix `test_every_test_function_asserts_or_raises` so it does not descend into nested
`FunctionDef`/`AsyncFunctionDef`/`Lambda`/`ClassDef`. Use the existing
`_OwnBodyVisitor` pattern (extend it to collect `Raise`, `self.assertX` calls, and
`doraise=True`), or an equivalent visitor that prunes nested defs. A test needs a
**top-level** failure path.

**Negative canary (evidence, not committed as a normal test):**
- create `tests/test_audit_nested.py` with a test whose only `raise` is inside a nested,
  never-called helper;
- the updated meta-test must **fail**;
- remove the file; the suite is green again.

### C-7A1-3 — Correct the record (QF-1..QF-3)

- **QF-1:** `notes.md` §6.1 and `coder-report.md` limitation 1 say both
  `tests/conftest.py` and `tests/test_harness_contract.py` are excluded from the sdist.
  Only `conftest.py` is absent; `test_harness_contract.py` is packaged (it matches
  `tests/test_*.py`). Correct the wording; the 7A-5 `MANIFEST.in` fix is still required
  for `conftest.py`.
- **QF-2:** `notes.md` §4 says “two commits”. The package has an implementation commit
  plus follow-ups (bundle, notes-structure, coder report). Use “a content commit plus
  follow-up commits”.
- **QF-3:** “13 tests could not fail” is imprecise. Say: 13 returned `bool`; 5 of those
  also had asserts; 9 had no failure mechanism at all; a 14th returned a tuple from a
  nested helper. The fix covers all of them.

Do **not** edit captured logs (`cpu-suite.log`, `gpu-suite.log`, `gate-commands.log`,
`probes.log`, `qaqc-probes/*`). Record corrections in `notes.md` / `coder-report.md` and
the follow-up evidence.

---

## 3. Acceptance

- `pytest -m "not gpu"` → 37 passed, 18 deselected (or the same count plus any deliberate
  new meta-test).
- `pytest -m gpu` on gfx1150 → 18 passed, 37 deselected.
- `pytest -m gpu` without the extension → 18 skipped, exit 0.
- `python tests/test_cpu_only.py` and `-O` → 12/12.
- C-7A1-1 canary fails the updated meta-test; C-7A1-2 canary fails the updated meta-test;
  both removed and the suite green.
- No `src/`, `pyproject.toml`, build, packaging, CI, README, ledger, or `CMakeLists.txt`
  change.
- The existing scientific assertions and tolerances are unchanged.

---

## 4. Evidence

`audit/evidence/G1/7A-1-followup/` with:

```
env.txt  parent-sha.txt  candidate-sha.txt  diffstat.txt
cpu-suite.log  gpu-suite.log  gate-commands.log
canary-wronglane.log  canary-nested.log
notes.md
```

`red/green` for this package is the canary pair: the old meta-test accepts the canary
(red), the updated meta-test rejects it (green). Record both commands and exit codes.
Do not re-run the whole 7A-1 gate; QAQC only needs to re-run the two strengthened
meta-tests, the two canaries, and the lane counts.

---

## 5. Stop

After the follow-up commit, stop for QAQC. Do not start 7A-6/7A-7/7A-8 on this branch.
7A-6 is already available on `wp/7A-6-claims-checker` from the same base; 7A-7/7A-8 can be
branched from `408fcab` when authorized.

If Mistral 4.0's documentation review has findings that touch these files, record them in
the follow-up notes and reconcile them rather than silently diverging.
