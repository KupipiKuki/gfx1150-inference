# Auditor probes — 7A-1 follow-up

**Auditor:** DeepSeek V4.1 Flash
**Date:** 2026-11-02
**Candidate:** `ea8e84a1e708ee114ae611f2b257b81eaa57c12a`
**Tip verified:** `2af8369e02bb85b355796a7bd8da88f78404cb3f` (tests/pyproject identical)
**Clean clone:** `/tmp/opencode/audit-7a1-fu`

| Probe | Result |
|---|---|
| `pytest -m "not gpu"` with extension | 37 passed, 18 deselected |
| `pytest -m "not gpu"` without extension | 37 passed, 18 deselected |
| `pytest -m gpu` with extension (gfx1150) | 18 passed, 37 deselected |
| `pytest -m gpu` without extension | 18 skipped |
| `test_cpu_only.py` / `-O` | 12/12 each |
| Exact-lane meta-test on the real suite | pass |
| Wrong-lane canary (not classified) | **fail**, exit 1 |
| Wrong marker on `test_layer.py` (`gpu`→`cpu`) | **fail** — “pytestmark is 'cpu', expected 'gpu'” |
| `cpu`-classified module using `matmul_module` | **fail** — “uses the matmul_module extension but is in the 'cpu' lane” |
| Nested-raise canary | **fail**, exit 1 |
| Nested-assert canary | **fail**, exit 1 |
| sdist contents | `test_harness_contract.py` present; `conftest.py` absent |
| QF-3 AST count at `2659e6c` | 13 bool-returners, 4 with asserts, 9 no failure mechanism, 1 tuple-returner |

All temporary canary files/edits were removed; `git status --porcelain` was empty
afterward. Full transcript: `probe-commands.log`.
