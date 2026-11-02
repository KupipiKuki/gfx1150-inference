# Auditor probes — 7A-1

**Auditor:** DeepSeek V4.1 Flash
**Date:** 2026-11-02
**Candidate:** `f0ce20e0021a313d3cb23a33f9b97b2638f56176`
**Tip verified:** `cefebef9b78aa022b5ffe8d5dae13a31b3c83ef4` (tests/pyproject identical to candidate)
**Clean clone:** `/tmp/opencode/audit-7a1` (no in-tree `build/`, `dist/`, or cache)

The full transcript is `probe-commands.log`. Summary:

| Probe | Result |
|---|---|
| `pytest -m "not gpu"` with extension | **37 passed, 18 deselected**, exit 0 |
| `pytest -m "not gpu"` without extension | **37 passed, 18 deselected**, exit 0 |
| `pytest -m gpu` with extension (gfx1150) | **18 passed, 37 deselected**, exit 0 |
| `pytest -m gpu --collect-only` without extension | 18/55 collected, exit 0 |
| `pytest -m gpu` without extension | **18 skipped**, exit 0 |
| `python tests/test_cpu_only.py` / `-O` | 12/12 each, exit 0 |
| Five GPU scripts standalone | exit 0 each |
| `grep -rn "def test_.*-> bool" tests/` | no matches |
| Canary `return False` / `return True` | **5 failed**, exit 1 (both canaries + 3 contract tests) |
| Mutation (`test_layer` rmsnorm `2e-3`→`1e-12`) | **1 failed**, exit 1; restored → pass |
| `pytest -m cpu` | 37 passed, 18 deselected |
| sdist contents | `tests/test_harness_contract.py` **present**; `tests/conftest.py` **absent** |

## Additional adversarial probes (findings)

### P-AUD-1 — wrong-lane module passes the lane meta-test

A temporary module marked `pytestmark = pytest.mark.cpu` but requesting the
`matmul_module` fixture (a GPU test by construction) is accepted by
`test_gpu_lane_is_marked_and_cpu_lane_is_not`:

```
pytest tests/test_harness_contract.py::test_gpu_lane_is_marked_and_cpu_lane_is_not -q
1 passed
```

The meta-test only checks that *some* `pytestmark = pytest.mark.<word>` exists; it does not
verify that GPU modules use `.gpu` and CPU modules use `.cpu`.

### P-AUD-2 — nested, never-called raise passes the assertion meta-test

A temporary module whose test body contains only a nested helper with `raise` (and never
calls it) is accepted by `test_every_test_function_asserts_or_raises`:

```
pytest tests/test_harness_contract.py::test_every_test_function_asserts_or_raises -q -k test_audit_nested
1 passed
```

`has_raise` walks into nested function definitions; `_OwnBodyVisitor` correctly skips them
for asserts, but the raise/unittest/doraise paths do not. The test has no top-level failure
path but passes the contract.

Both temporary files were removed; `git status --porcelain` was empty afterward.
