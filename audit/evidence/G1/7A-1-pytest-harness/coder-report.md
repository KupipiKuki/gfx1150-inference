# Work package: 7A-1 — Pytest harness

**Audit trace:** AUD-2, QAQC-2, T-1, T-3
**Parent SHA:** `2659e6c33fec50a6768cd35bb264d6f7453e6c0e`
**Candidate SHA:** see `audit/evidence/G1/7A-1-pytest-harness/candidate-sha.txt` (`f0ce20e`)
**Branch:** `wp/7A-1-pytest-harness`
**Allowed file set:** `tests/**`, `pyproject.toml` (pytest config only), `scripts/qa/**` (unused), `audit/evidence/G1/7A-1/**`, docs — **respected** (see §Files changed)

---

## Files changed

```
 pyproject.toml                 |  23 ++++
 tests/conftest.py              |  78 +++++++++++++      (new)
 tests/test_cpu_only.py         |  10 ++
 tests/test_full_model.py       |  77 ++++++---
 tests/test_gguf_and_q4.py      |  80 ++++++++++---------
 tests/test_harness_contract.py | 242 +++++++++++++++++++  (new)
 tests/test_layer.py            | 116 +++++++++++++------
 tests/test_matmul.py           | 109 +++++++++++++------
 tests/test_phase5_scale.py     |  69 +++++--
```

**Within the allowed set — confirmed.** `git diff --name-only 2659e6c..HEAD`
contains only `tests/`, `pyproject.toml` and `audit/evidence/G1/`. The diff for
`src/`, `CMakeLists.txt`, `setup.py`, `MANIFEST.in`, `.github/`, `README.md`,
`IMPLEMENTATION_PLAN.md` and `audit/CLAIMS_LEDGER.md` is **empty** (proved in
`diffstat.txt`). No `src/` change was needed or made.

## Tests added/changed

| Test | Audit ID | What it proves |
|---|---|---|
| `tests/conftest.py::matmul_module` | AUD-2 | The HIP extension is obtained through a fixture that **skips** when unavailable, never fails and never silently passes. |
| `tests/conftest.py::pytest_collection_modifyitems` | AUD-2 | Without the extension the whole `gpu` lane is **skipped with an actionable reason** — visible in the report, not a silent pass (handoff §9). |
| `tests/test_harness_contract.py::test_no_test_function_returns_a_value` | AUD-2 | No `test_*` function may return a value — the exact defect that made 13 baseline tests unfailable. |
| `tests/test_harness_contract.py::test_no_test_function_is_annotated_bool` | AUD-2 | No `-> bool` annotation on a test function. |
| `tests/test_harness_contract.py::test_every_test_function_asserts_or_raises` | AUD-2 | Every test can actually fail. |
| `tests/test_harness_contract.py::test_gpu_lane_is_marked_and_cpu_lane_is_not` | AUD-2 | Every module declares `pytestmark`; an unmarked module lands in **both** lanes (the AUD-2 defect). |
| `tests/test_harness_contract.py::test_cpu_only_module_is_not_marked_gpu` | AUD-2 | The CPU suite is in the CPU lane. |
| `tests/test_harness_contract.py::test_no_module_level_matmul_module_import` | AUD-2 | No module-scope extension import — the cause of the G0 "exit 2, 4 collection errors". |
| `tests/test_harness_contract.py::test_pytest_config_declares_required_markers` | AUD-2 | `gpu`/`cpu`/`slow` registered; the warning escalation present. |
| `tests/test_matmul.py::test_matmul_correctness` | AUD-2 | Was `return True`/`return False`; now asserts. |
| `tests/test_matmul.py::test_edge_cases` | AUD-2 | Was `return bool`; now asserts, including the `matmul_nt` shape rejection. |
| `tests/test_gguf_and_q4.py::test_gguf_and_streamer` | AUD-2 | Unchanged assertions; now returns `None`. |
| `tests/test_gguf_and_q4.py::test_dequantize_q4_0_hip` | AUD-2 | Was `return bool`; now asserts `max_err < 1e-3`. |
| `tests/test_gguf_and_q4.py::test_fused_matmul_q4_0_hip` | AUD-2 | Was `return bool`; now asserts per shape. |
| `tests/test_layer.py::test_rmsnorm_kernel` | AUD-2 | Was `return bool`; now asserts per shape. |
| `tests/test_layer.py::test_rope_kernel` | AUD-2 | Was `return bool`; now asserts per style/shape. |
| `tests/test_layer.py::test_gqa_attention_kernel` | AUD-2 | Was `return bool`; now asserts per mode. |
| `tests/test_layer.py::test_swiglu_kernel` | AUD-2 | Was `return bool`; now asserts. |
| `tests/test_layer.py::test_end_to_end_transformer_layer` | AUD-2 | Was `return bool`; now asserts prefill **and** decode separately. |
| `tests/test_full_model.py::test_tokenizer_and_embedding` | AUD-2 | Unchanged assertions; now returns `None`. |
| `tests/test_full_model.py::test_gpu_kv_cache_manager` | AUD-2 | Was `return bool`; now asserts. |
| `tests/test_full_model.py::test_full_model_inference` | AUD-2 | Was `return bool`; now asserts. |
| `tests/test_phase5_scale.py` (5 tests) | AUD-2 | Already assert-based; extended with the `matmul_module` fixture and deferred imports. |
| `tests/test_cpu_only.py` | AUD-2 | Marked `cpu`; still runs standalone with or without pytest. |

**Red/green:** N/A (no behavioral change) — stated in
`audit/evidence/G1/7A-1-pytest-harness/notes.md` §3. `src/` and all packaging
and CI files are untouched.

### Record corrections (QF-1 / QF-2 / QF-3, applied in the follow-up)

These are wording corrections to this report and to `notes.md`. **Captured logs
were not edited.**

- **QF-1 — sdist packaging.** This report's limitation 1 said both
  `tests/conftest.py` and `tests/test_harness_contract.py` are excluded from
  the sdist. **Only `conftest.py` is excluded** — setuptools' default sdist
  includes `tests/test_*.py`, and `test_harness_contract.py` matches that
  pattern (verified by building the sdist). The 7A-5 `MANIFEST.in` fix
  (`recursive-include tests *.py`) is still required, for `conftest.py` alone.
  This is audit condition **C-7A1-5**, carried forward to 7A-5.
- **QF-2 — commit count.** `notes.md` §4 said "two commits". The package is a
  **content commit plus follow-up commits** (implementation, evidence bundle,
  bundle-structure note, coder report). Corrected in `notes.md` §4.
- **QF-3 — the "13 tests could not fail" claim was imprecise.** Precisely:
  **13 test functions returned `bool`**; **4 of those also contained asserts**
  (masked failure paths); **9 had no failure mechanism at all**; and a **14th**
  returned a tuple from a nested helper, which pytest likewise ignores. The
  conversion covers all of them. Corrected in `notes.md` §1 and here.

## Suite results

| Suite | Result |
|---|---|
| **CPU suite** — `pytest -m "not gpu"` | **37 passed**, 18 deselected — exit 0 |
| **CPU suite** — `python tests/test_cpu_only.py` | **12/12** — exit 0 |
| **CPU suite** — `python -O tests/test_cpu_only.py` | **12/12** — exit 0 |
| **GPU suite** — `pytest -m gpu` (gfx1150) | **18 passed**, 37 deselected — exit 0 |
| **GPU suite** — five scripts standalone | exit 0 each |
| **Clean clone, no extension** — `pytest -m "not gpu"` | 37 passed, exit 0 (was **exit 2**) |
| **Clean clone, no extension** — `pytest -m gpu` | **18 skipped**, exit 0 |
| **pytest not installed** — `test_cpu_only.py` | 12/12 normal and `-O`, exit 0 |

Logs: `audit/evidence/G1/7A-1-pytest-harness/{cpu-suite.log,gpu-suite.log,gate-commands.log,probes.log}`

## Mutation probe

`audit/evidence/G1/7A-1-pytest-harness/probes.log` §PROBE 3.

Mutation: `tests/test_matmul.py` — `assert max_error < tolerance` →
`assert max_error < 1e-12`.

```
python3 -m pytest -m gpu -k matmul_correctness -q
  FAILED tests/test_matmul.py::test_matmul_correctness - AssertionError: Max er...
  1 failed, 54 deselected          exit 1
```

File restored byte-for-byte (`git diff --stat` empty), then:

```
  1 passed, 54 deselected          exit 0
```

Additional probes, same file:

- **PROBE 1 — clean clone:** fresh `git clone`, `PYTHONPATH` unset, no `build/`.
  `pytest -m "not gpu"` → 37 passed (exit 0); `pytest -m gpu` → **18 skipped**
  with the build-command reason (exit 0); `--collect-only` → exit 0. Directly
  fixes the G0 audit's "exit 2, 4 collection errors".
- **PROBE 2 — canary:** `def test_returns_false(): return False` →
  **FAILED**, `1 failed`, **exit 1**. Not a warning, not a pass.
- **PROBE 4 — script mode:** all five GPU scripts exit 0 standalone.
- **PROBE 5 — no pytest:** `test_cpu_only.py` 12/12 normal and `-O` with
  `pytest` blocked at import (keeps the pytest-free `ci-cpu.yml` job green).

## G0 record correction (7A-1 task 7)

The G0 "30 passed" record was a collection smoke including **18 GPU tests and
13 bool-returning functions** (of those 13, 4 also contained asserts and 9 had
no failure mechanism at all; a 14th returned a tuple from a nested helper); it
was not a CPU gate. The corrected records are `pytest -m "not gpu"` → **37
passed / 18 deselected** and `pytest -m gpu` → **18 passed on gfx1150**. The
captured G0 logs were **not edited** (handoff §4 forbids editing captured logs);
the correction is recorded in the 7A-1 notes and here. Details in `notes.md` §5.

## Known limitations

1. `tests/conftest.py` is **not** packaged in the sdist — setuptools' default
   sdist includes `tests/test_*.py`, so `tests/test_harness_contract.py` **is**
   packaged, but `conftest.py` is **not**. Fixing this needs `MANIFEST.in`,
   which is outside 7A-1's allowed file set. **7A-5 should add
   `recursive-include tests *.py`** so the CPU CI job can run
   `pytest -m "not gpu"` from the installed tree. Flagged, not actioned. This is
   audit condition **C-7A1-5**.
2. **CI is not wired to pytest.** `.github/workflows/ci-cpu.yml` still runs only
   `python tests/test_cpu_only.py`. The pytest CPU job is **7A-5**; `.github/`
   is outside 7A-1's allowed file set, so it was not touched.
3. **`ci-gpu.yml` does not exist** — that is **7A-7**.
4. **The `gpu` lane skips rather than fails when the extension is missing.**
   Correct for a CPU-only host, but a GPU host whose extension silently failed
   to build would *skip* the lane. G1/G5/G6 must assert the lane **runs**
   (18 passed, 0 skipped) — `gpu-suite.log` does exactly that, and 7A-7's
   workflow should assert the same rather than accept a skip.
5. **`slow` is advisory.** Applied to the three heaviest GPU tests; the whole
   GPU lane runs in ~1.6 s on this host, so the marker gates nothing yet.
6. **The `cpu` marker is registered but unused for selection**; the CPU lane is
   selected with `-m "not gpu"`. `cpu` exists so the CPU suite is explicitly
   marked rather than unmarked.
7. **`test_cpu_only.py` gained a guarded `import pytest`** so it stays importable
   without pytest (probe 5).

## Rollback

`git revert` the 7A-1 commits. Only `tests/**` and the pytest section of
`pyproject.toml` are involved, so rollback cannot change runtime behaviour; it
restores the previous bool-returning tests and the previous collection
behaviour exactly.

## Docs updated

**None.** 7A-1 changes no public capability, correctness or performance claim
and no user-facing behaviour, so `README.md` and `IMPLEMENTATION_PLAN.md` need
no change. `audit/CLAIMS_LEDGER.md` is **unchanged** — no claim changed status.
The handoff and the ledger are auditor-owned documents and were not edited by
the coder.

## Claims changed

**None.** `audit/CLAIMS_LEDGER.md` is unchanged. `scripts/qa/check_claims.py`
is **7A-6** and does not exist at this commit, so no `claims-check.log` is
included (the 7A-1 brief does not list it in this package's bundle). Ledger IDs
13/27 (`983.4 tok/s`) remain `UNVERIFIED`; 7F-3 owns re-recording or removing
them. Throughput numbers printed by `pytest -m gpu` are single-run observations,
recorded as such, not baselined figures.

## Evidence bundle

`audit/evidence/G1/7A-1-pytest-harness/`

```
env.txt  parent-sha.txt  candidate-sha.txt  diffstat.txt
cpu-suite.log  gpu-suite.log  gate-commands.log  probes.log  notes.md
```

## Self-assessment against the 7A-1 acceptance criteria

| Criterion | Result |
|---|---|
| `python tests/test_cpu_only.py` 12/12 and `-O` 12/12 | PASS |
| `pytest -m "not gpu"` passes on CPU and collects no GPU test | PASS — 37 passed, 18 deselected |
| `pytest -m gpu` skips (not errors) on CPU; passes on gfx1150 | PASS — 18 skipped exit 0 on a clean clone; 18 passed on gfx1150 |
| A canary `def test_returns_false(): return False` fails, not warns/passes | PASS — exit 1 (`probes.log` PROBE 2) |
| No `def test_* -> bool` remains; no `PytestReturnNotNoneWarning` | PASS — grep empty; the warning is escalated to an error in config |
| Clean clone without a pre-built extension collects/skips, not exit 2 | PASS — exit 0 (`probes.log` PROBE 1) |
| Mutation probe: one mutated assertion fails | PASS — exit 1, then restored → exit 0 (PROBE 3) |
| Scientific assertions and tolerances unchanged | PASS — per-file threshold sets identical to the parent; no comparison loosened |
| No `src/` diff | PASS — `diffstat.txt` |
| Within the allowed file set | PASS — `diffstat.txt` |
| No test deleted, skipped or weakened | PASS — no test was removed or skipped; 13 previously unfailable tests became able to fail |
| No new runtime dependency | PASS — pytest is a test-only dep, already expected per the brief |

**Stop condition check:** none of the eight stop conditions in handoff §2.2
was triggered. No claim was made without a reproducible command and artifact.

**Stopping here for QAQC.** Per brief §8, the next package is not started on
this branch. QAQC must be an independent session; the coder does not sign G1.
