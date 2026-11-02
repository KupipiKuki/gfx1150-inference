# G1 / 7A-1 follow-up — Close the auditor conditions

**Work package:** 7A-1 follow-up (not a new work package)
**Audit trace:** C-7A1-1, C-7A1-2, C-7A1-3 (`audit/AUDIT_7A-1_PYTEST_HARNESS_DEEP_2026-11-02.md` §6); AUD-7A1-1/2/3, QF-1/QF-2/QF-3
**Parent SHA:** `4e87e1274d3843aa09d4cff78e707c03c3327c3a` (branch base)
**Candidate SHA:** see `candidate-sha.txt`
**Branch:** `wp/7A-1-followup`
**Base:** `vibe/phase7-220201` @ `408fcab` (the merge of 7A-1)
**Host:** gfx1150 (Radeon 890M), ROCm 10.1 / HIP 7.16.26385, Python 3.14.10, pytest 9.1.1

**red/green:** the canary pair — the **old** meta-test accepts the canary (red),
the **strengthened** meta-test rejects it (green). See `canary-wronglane.log` and
`canary-nested.log`.

---

## 1. Summary

The G1 audit accepted 7A-1 "in substance" but found that **two of the new
harness meta-tests accept inputs they were written to reject**:

1. **AUD-7A1-1 — the lane check was presence-only.** It searched for
   `pytestmark = pytest.mark.<word>` and accepted *any* marker. A module marked
   `cpu` whose test requests the `matmul_module` fixture passed. That is exactly
   the lane-split defect AUD-2 was about, left unguarded.
2. **AUD-7A1-2 — the assertion check counted nested raises.** It walked each
   test body with `ast.walk`, which descends into nested function definitions. A
   test whose only `raise` sits in a nested, never-called helper passed, even
   though the test itself has no failure path.

Both are fixed here. The runtime surface is unchanged: `src/`,
`pyproject.toml`, the build files, CI, `README.md` and the claims ledger are
all untouched (`diffstat.txt` proves it).

---

## 2. C-7A1-1 — Enforce the actual lane

`test_gpu_lane_is_marked_and_cpu_lane_is_not` (presence-only) is replaced by
`test_every_test_module_declares_its_exact_lane`.

Every `tests/test_*.py` must:

1. appear in `EXPECTED_LANES` — a new test file must be **deliberately
   classified**, so a new module forces a lane choice instead of defaulting to
   one;
2. declare exactly the expected marker (`pytest.mark.gpu` / `pytest.mark.cpu`);
3. if it is in the `cpu` lane, **not hard-depend** on the compiled extension.

The marker is now read from the AST at module scope (`_module_lane`) rather
than by regex, so a `pytestmark` inside a function or class body is not
mistaken for a module-level marker, while a module-level `if` guard — as
`test_cpu_only.py` uses to import pytest optionally — is still honoured.

### What counts as a hard dependency on the extension

`_uses_matmul_module` treats a module as a GPU test when it either:

- requests the `matmul_module` fixture, or
- imports `matmul_module` **unguarded** inside a test body.

A **guarded** import — inside a `try` whose handler catches `ImportError`,
with a stub fallback — is *optional*: the test still runs on a CPU-only host,
so the module belongs in the `cpu` lane. `tests/test_cpu_only.py` uses exactly
that pattern (line ~404) to exercise the CPU paths when the extension is
absent, and it is correctly classified as `cpu`. Treating it as a GPU
dependency would have been a false positive on the suite's own CPU module.

The strengthened check produces three distinct rejections, each verified:

| Rejection | Message |
|---|---|
| not classified | `test_audit_x.py: not classified — add it to EXPECTED_LANES with its lane` |
| wrong marker | `test_audit_y.py: pytestmark is 'gpu', expected 'cpu'` |
| cpu lane, needs the extension | `test_audit_z.py: uses the matmul_module extension but is in the 'cpu' lane` |

---

## 3. C-7A1-2 — Do not count nested raises/asserts

`test_every_test_function_asserts_or_raises` now measures **all four** failure
mechanisms through the single nested-def-pruning visitor `_OwnBodyVisitor`:

- `assert` statements,
- `raise` statements,
- `self.assertX(...)` calls (unittest style),
- calls with `doraise=True` (e.g. `py_compile.compile`).

The visitor does not descend into nested `FunctionDef` / `AsyncFunctionDef` /
`Lambda` / `ClassDef`, so a `raise` inside a nested, never-called helper no
longer satisfies the contract. A test needs a **top-level** failure path.

The same visitor was already used for the return-value check; the two checks
are now consistent.

---

## 4. C-7A1-3 — Correct the record (QF-1 / QF-2 / QF-3)

**Captured logs were not edited.** The corrections are recorded in
`audit/evidence/G1/7A-1-pytest-harness/notes.md` and `coder-report.md`.

- **QF-1 — sdist packaging.** The 7A-1 notes and coder report said *both*
  `tests/conftest.py` and `tests/test_harness_contract.py` are excluded from
  the sdist. **Only `conftest.py` is excluded.** setuptools' default sdist
  includes `tests/test_*.py`, and `test_harness_contract.py` matches that
  pattern — verified by building the sdist:

  ```
  gfx1150_inference-0.6.1/tests/test_cpu_only.py
  gfx1150_inference-0.6.1/tests/test_full_model.py
  gfx1150_inference-0.6.1/tests/test_gguf_and_q4.py
  gfx1150_inference-0.6.1/tests/test_harness_contract.py   <-- packaged
  gfx1150_inference-0.6.1/tests/test_layer.py
  gfx1150_inference-0.6.1/tests/test_matmul.py
  gfx1150_inference-0.6.1/tests/test_phase5_scale.py
  (no tests/conftest.py)                                   <-- absent
  ```

  The 7A-5 conclusion stands unchanged: add `recursive-include tests *.py` to
  `MANIFEST.in` so the CPU CI job can run `pytest -m "not gpu"` from the
  installed tree. That is audit condition **C-7A1-5**, carried forward to
  7A-5; `MANIFEST.in` is outside this package's allowed file set.

- **QF-2 — commit count.** The 7A-1 notes said "two commits". The package is a
  **content commit plus follow-up commits** (implementation, evidence bundle,
  bundle-structure note, coder report). Corrected in `notes.md` §4.

- **QF-3 — "13 tests could not fail" was imprecise.** Verified by AST against
  the parent commit `2659e6c`:

  > **13 test functions returned `bool`**; **4 of those also contained asserts**
  > (so their failure path was masked rather than absent); **9 had no failure
  > mechanism at all**; and a **14th** returned a tuple from a nested helper,
  > which pytest likewise ignores.

  The 7A-1 conversion covered all of them. Corrected in `notes.md` §1 and §5
  and in the coder report.

---

## 5. Evidence

| File | Content |
|---|---|
| `env.txt` | host, ROCm/HIP, GPU, toolchain, git SHAs |
| `parent-sha.txt` / `candidate-sha.txt` | exact commits |
| `diffstat.txt` | diffstat + proof that the runtime/build/CI/doc/ledger and GPU-test diffs are empty |
| `cpu-suite.log` | `pytest -m "not gpu"`, `test_cpu_only.py` normal and `-O`, lane split |
| `gpu-suite.log` | `pytest -m gpu` on gfx1150, the two strengthened meta-tests, clean-clone skip |
| `gate-commands.log` | every required command with its exit code |
| `canary-wronglane.log` | C-7A1-1 red/green pair |
| `canary-nested.log` | C-7A1-2 red/green pair |
| `notes.md` | this document |

### Results

| Check | Result |
|---|---|
| `pytest -m "not gpu"` | **37 passed**, 18 deselected — exit 0 |
| `pytest -m gpu` (gfx1150) | **18 passed**, 37 deselected — exit 0 |
| `pytest -m gpu` (clean clone, no extension) | **18 skipped** — exit 0 |
| `python tests/test_cpu_only.py` | **12/12** — exit 0 |
| `python -O tests/test_cpu_only.py` | **12/12** — exit 0 |
| C-7A1-1 canary | old check **passes** (exit 0, defect) → new check **fails** (exit 1, fixed) |
| C-7A1-2 canary | old check **passes** (exit 0, defect) → new check **fails** (exit 1, fixed) |
| suite green after the canaries are removed | **37 passed**, 18 deselected — exit 0 |
| runtime / build / CI / doc / ledger diff | **empty** |
| GPU test files + `test_cpu_only.py` diff | **empty** (no assertion or tolerance changed) |

The CPU lane count is unchanged at 37, as the brief's acceptance requires.
**The 37 are not "37 CPU runtime tests"**: 12 are the `test_cpu_only.py`
runtime suite and 25 are harness meta-tests (audit observation AUD-7A1-7).

---

## 6. Known limitations and follow-ups

1. **`tests/conftest.py` is still absent from the sdist** — unchanged by this
   package (QF-1 corrected the *record*; the packaging fix is **C-7A1-5**, owned
   by 7A-5).
2. **CI is still not wired to pytest** — 7A-5 (`.github/` is outside this
   package's allowed file set).
3. **The GPU lane still skips rather than fails without the extension** —
   **C-7A1-6**, owned by 7A-7 / G5 / G6. The G5/G6 gates must assert the lane
   *runs* (18 passed, 0 skipped) on gfx1150.
4. **The strengthened lane check requires every new test module to be added to
   `EXPECTED_LANES`.** This is deliberate — it forces a deliberate lane choice —
   but it means a future package that adds a test file must update
   `tests/test_harness_contract.py`. 7A-3 (goldens) and 7A-4 (fuzz) will add
   test files and **must** add their entries, or the CPU lane will fail. Flagged
   prominently here so it is not discovered as a surprise at G1.
5. **The old meta-test name is gone.** `test_gpu_lane_is_marked_and_cpu_lane_is_not`
   was replaced by `test_every_test_module_declares_its_exact_lane`. QAQC's
   re-run instruction names the old test; the new name is recorded here and in
   the commit message. `test_cpu_only_module_is_not_marked_gpu` is retained so
   the specific regression stays named.

---

## 7. Rollback

`git revert` the follow-up commit. The package touches only
`tests/test_harness_contract.py` and two markdown evidence files; reverting
restores the previous meta-tests exactly. No runtime, build, packaging, CI or
documentation file is involved, so rollback cannot change behaviour.

---

## 8. Claims changed

**None.** The follow-up changes no public capability, correctness or performance
claim and no user-facing behaviour. `audit/CLAIMS_LEDGER.md` is unchanged, and
`audit/claims_baseline.txt` is unchanged. No ledger row changes status and no
`claims-check.log` applies: `scripts/qa/check_claims.py` is **7A-6** and does
not exist at this commit.
