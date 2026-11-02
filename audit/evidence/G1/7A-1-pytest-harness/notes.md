# G1 / 7A-1 — Pytest harness and marker conversion

**Work package:** 7A-1 — Pytest harness
**Audit trace:** AUD-2, QAQC-2, T-1, T-3 (7A-1 in `PHASE7_IMPLEMENTATION_HANDOFF.md` §6)
**Parent SHA:** `2659e6c33fec50a6768cd35bb264d6f7453e6c0e` (branch base)
**Candidate SHA:** see `candidate-sha.txt`
**Branch:** `wp/7A-1-pytest-harness`
**Host:** gfx1150 (Radeon 890M), ROCm 10.1 / HIP 7.16.26385, Python 3.14.10, pytest 9.1.1
**red/green:** N/A (no behavioral change) — see §3

> **Follow-up:** the G1 audit accepted this package "in substance" but found two
> weaknesses in the meta-tests introduced here (AUD-7A1-1: the lane check
> accepted any marker; AUD-7A1-2: the assertion check counted a `raise` inside a
> nested helper) and three record imprecisions (QF-1/QF-2/QF-3). The code fixes
> are on `wp/7A-1-followup`; the record corrections are applied **in this file
> and in `coder-report.md`** (see the "Record corrections" section below).

---

## 1. Summary

The G0 audit found two defects in the baseline test suite (AUD-2):

1. **13 test functions could not fail.** All 13 returned a `bool` instead of
   asserting. Pytest ignores a test's return value and only emits
   `PytestReturnNotNoneWarning`, so a regression that made one of them return
   `False` still reported "passed". Precisely: **13 returned `bool`; 4 of those
   also contained asserts** (so they had a failure path but a masked one), and
   **9 had no failure mechanism at all**. A **14th** function returned a tuple
   from a nested helper, which pytest likewise ignores. The conversion in this
   package covers all 13 bool-returning functions and the nested-tuple case.
2. **`-m "not gpu"` collected 18 GPU tests.** No `gpu` marker existed, so the
   selector matched everything. The G0 record "30 passed" was a collection smoke
   that included 18 GPU tests and 13 bool-returning functions — not a CPU gate.

This package fixes both, and adds the harness the G0 audit and the handoff
require: a `matmul_module` fixture, `gpu`/`cpu`/`slow` markers, and a
`PytestReturnNotNoneWarning` escalation so a returning test can never pass.

---

## 2. What changed

### `tests/conftest.py` (new)

- `matmul_module` — session-scoped fixture returning the compiled HIP extension
  via `pytest.importorskip`. A missing extension **skips** the test; it never
  fails and never silently passes.
- `pytest_collection_modifyitems` — when the extension is not importable, every
  `gpu`-marked item is skipped with an actionable reason naming the build
  command. This makes the skip *visible in the report* (handoff §9) rather than
  relying on the fixture alone, and it covers the two GPU tests that do not
  need the extension directly (`test_gguf_and_streamer`,
  `test_tokenizer_and_embedding`).
- Puts `src/` and `build/` on `sys.path` so the tests import the package
  modules and the extension consistently regardless of the working directory.

### `pyproject.toml` — pytest config only

`[tool.pytest.ini_options]` with `testpaths = ["tests"]`, the `gpu`/`cpu`/`slow`
markers, `--strict-markers --strict-config`, and
`PytestReturnNotNoneWarning` escalated to an error (via both `addopts -W` and
`filterwarnings`, so the escalation holds however pytest is invoked). No build
or packaging fields were touched.

### The five GPU scripts

`test_matmul.py`, `test_gguf_and_q4.py`, `test_layer.py`, `test_full_model.py`,
`test_phase5_scale.py`:

- **Every `test_*` function now asserts and returns `None`.** The 13
  bool-returning functions raise `AssertionError` on failure instead.
- **No module-scope `import matmul_module`.** `src/layer.py`, `src/kv_cache.py`
  and `src/inference.py` import `matmul_module` at module scope, so the
  module-scope imports of those packages were moved into the test bodies as
  well. This is what removes the G0 "exit 2, 4 collection errors" failure on a
  clone with no built extension.
- Each module declares `pytestmark = pytest.mark.gpu`.
- **Scientific assertions and tolerances are unchanged.** Every tolerance
  (`1e-3`, `2e-3`, `5e-3`, `1e-2`, `5e-2`) and every numeric threshold is
  carried over verbatim; only the failure *mechanism* changed from
  `return False` to `raise AssertionError`.
- **Standalone script mode is preserved.** Each file keeps a `main()` that runs
  the same test functions and exits non-zero on failure, so
  `python3 tests/test_layer.py` and the 7E required checks still work. The
  `main()` dispatch inspects the signature so a test that does not take the
  extension is called correctly.

### `tests/test_cpu_only.py`

Marked `pytest.mark.cpu` so it is unambiguously in the CPU lane. It **still runs
as a standalone unittest script with or without pytest installed** (12/12
normal and `-O`) — verified with pytest blocked at import. The existing
`ci-cpu.yml` job installs only `numpy`/`setuptools`/`wheel`, so this matters.

### `tests/test_harness_contract.py` (new)

Meta-tests that enforce the harness contract, so the AUD-2 defects cannot
regress silently:

- no `test_*` function returns a value;
- no `test_*` function is annotated `-> bool`;
- every `test_*` function asserts, raises, or uses `unittest`/`doraise`
  assertions;
- every test module declares `pytestmark` explicitly (a module with no marker
  lands in *both* lanes — the AUD-2 defect);
- `test_cpu_only.py` is not marked `gpu`;
- no module imports `matmul_module` at module scope;
- `pyproject.toml` registers the markers and the warning escalation.

The AST checks use a pruning visitor so that helper functions defined *inside* a
test (e.g. `_cpu_layer_ref`) are not mistaken for the test's own return value.

---

## 3. red/green: N/A (no behavioral change)

7A-1 changes no production behaviour: `src/`, `CMakeLists.txt`, `setup.py`,
`MANIFEST.in`, `.github/` and the public docs are all untouched
(`diffstat.txt` proves the diff is empty for those paths). Per handoff §4,
`red.log`/`green.log` are required only for packages that change behaviour;
this package ships the green suite logs plus `probes.log`, and states the
exemption here.

---

## 4. Evidence

**Commit structure.** A commit cannot contain its own SHA, so 7A-1 is a
**content commit plus follow-up commits**: the content commit (`candidate-sha.txt`)
holds the harness and the converted tests; the follow-ups add the evidence
bundle, the bundle-structure note and the coder report. The reviewed tree is
`candidate-sha.txt` plus the evidence files — none of them touches `src/` or any
runtime behaviour. This mirrors the G0 bundle's convention.

| File | Content |
|---|---|
| `env.txt` | host, ROCm/HIP, GPU, toolchain, git SHAs |
| `parent-sha.txt` / `candidate-sha.txt` | exact commits |
| `diffstat.txt` | diffstat + proof that the src/build/CI diff is empty |
| `cpu-suite.log` | `pytest -m "not gpu"`, `test_cpu_only.py` normal and `-O` |
| `gpu-suite.log` | `pytest -m gpu` on gfx1150, durations, and all five scripts standalone |
| `gate-commands.log` | every required command with its exit code |
| `probes.log` | the five adversarial probes (below) |
| `notes.md` | this document |

### Results

| Check | Result |
|---|---|
| `pytest -m "not gpu"` | **37 passed**, 18 deselected — exit 0 |
| `pytest -m gpu` (gfx1150) | **18 passed**, 37 deselected — exit 0 |
| `pytest -m gpu` (clean clone, no extension) | **18 skipped**, exit 0 |
| `pytest -m gpu --collect-only` (clean clone) | 18 collected, exit 0 (was **exit 2**) |
| `python tests/test_cpu_only.py` | **12/12** — exit 0 |
| `python -O tests/test_cpu_only.py` | **12/12** — exit 0 |
| `test_cpu_only.py` with pytest blocked | **12/12** normal and `-O` — exit 0 |
| `grep -R "def test_.*-> bool" tests/` | no matches |
| All five GPU scripts standalone | exit 0 each |

### Probes (`probes.log`)

1. **Clean clone, no pre-built extension.** A fresh `git clone` with `PYTHONPATH`
   unset and no `build/` directory: `pytest -m "not gpu"` collects and passes
   (37 passed); `pytest -m gpu` **skips all 18** with an actionable reason and
   exits 0; `--collect-only` exits 0. This is the direct fix for the G0 audit's
   "exit 2, 4 collection errors".
2. **Canary.** `def test_returns_false(): return False` → pytest **FAILS** it
   (exit 1) with `PytestReturnNotNoneWarning`, not a warning and not a pass.
3. **Mutation probe.** `assert max_error < tolerance` → `assert max_error < 1e-12`
   in `tests/test_matmul.py`: the test **fails** (exit 1); the file is then
   restored byte-for-byte (empty `git diff --stat`) and the test **passes**
   again (exit 0).
4. **Script mode.** All five GPU scripts exit 0 standalone.
5. **No pytest.** `test_cpu_only.py` runs 12/12 with `pytest` blocked at
   import, so the pytest-free `ci-cpu.yml` job stays green.

---

## 5. The G0 record correction (7A-1 task 7)

The G0 audit required that the baseline's "30 passed" record be re-labelled:
it was a collection smoke that included **18 GPU tests and 13 bool-returning
functions**, and was **not a CPU gate**.

Precisely (verified by AST against the parent commit `2659e6c`): **13 test
functions returned `bool`**; **4 of those also contained asserts**, so their
failure path was masked rather than absent; **9 had no failure mechanism at
all**; and a **14th** returned a tuple from a nested helper, which pytest
likewise ignores. The conversion in this package covers all of them.

- The corrected CPU gate is now **`pytest -m "not gpu"` → 37 passed, 18
  deselected** (12 from the self-contained CPU suite + 25 harness meta-tests).
  Per audit observation AUD-7A1-7, those 37 are **not** "37 real CPU runtime
  tests": 12 are the CPU runtime suite and 25 are harness meta-tests.
- The corrected GPU gate is **`pytest -m gpu` → 18 passed on gfx1150**, the same
  18 tests the G0 record mis-counted as CPU.
- The G0 `audit/evidence/G0/7.0-baseline/` logs are **not edited** — they are
  captured evidence of what was true at G0, and the handoff forbids editing
  captured logs. The correction is recorded here and in the coder report instead.
- `audit/VERIFICATION_2026-11-01.md` §3.1 and the G0 baseline report remain
  historical records of the pre-7A state.

These are record corrections only; captured logs must not be edited.

### Record corrections (QF-1 / QF-2 / QF-3, applied in the follow-up)

The G1 audit recorded three imprecisions in this document and in
`coder-report.md`. The corrections are applied here; **no captured log was
edited**.

- **QF-1 — sdist packaging.** Limitation 1 below originally said both
  `tests/conftest.py` and `tests/test_harness_contract.py` are excluded from the
  sdist. **Only `conftest.py` is excluded** — setuptools' default sdist
  includes `tests/test_*.py`, and `test_harness_contract.py` matches that
  pattern (verified by building the sdist). The 7A-5 `MANIFEST.in` fix is still
  required, for `conftest.py` alone (audit condition **C-7A1-5**).
- **QF-2 — commit count.** §4 said "two commits". The package is a **content
  commit plus follow-up commits** (implementation, evidence bundle,
  bundle-structure note, coder report).
- **QF-3 — "13 tests could not fail".** Precisely: **13 test functions
  returned `bool`**; **4 of those also contained asserts** (masked rather than
  absent failure paths); **9 had no failure mechanism at all**; and a **14th**
  returned a tuple from a nested helper, which pytest likewise ignores. See §1
  and §5.

---

## 6. Known limitations and follow-ups

1. **`tests/conftest.py` is not packaged in the sdist.** setuptools' default
   sdist includes `tests/test_*.py`, so `tests/test_harness_contract.py` **is**
   packaged, but `tests/conftest.py` is **not** (it does not match the
   `test_*.py` pattern). This is **not** a defect of this package (7A-1's
   allowed file set excludes `MANIFEST.in` and packaging), but it means an
   sdist-installed tree has no conftest — hence no `matmul_module` fixture and
   no GPU-lane skip. **7A-5 (CI/sdist-install) should add
   `recursive-include tests *.py` to `MANIFEST.in`** so the CPU CI job can run
   `pytest -m "not gpu"` from the installed tree. Flagged for the auditor; not
   actioned here (would breach 7A-1's allowed file set). This is audit
   condition **C-7A1-5**, carried forward to 7A-5.
2. **CI is not yet wired to pytest.** `.github/workflows/ci-cpu.yml` still runs
   `python tests/test_cpu_only.py` only. The pytest CPU job belongs to **7A-5**.
   This package deliberately did not touch `.github/` (outside 7A-1's allowed
   file set).
3. **`ci-gpu.yml` does not exist.** That is **7A-7**.
4. **The `gpu` lane is skipped, not failed, when the extension is missing.**
   That is the intended behaviour for a CPU-only host, but it means a GPU host
   whose extension silently fails to build would *skip* rather than *fail* the
   lane. The G1/G5/G6 gates must assert that the GPU lane **runs** (18 passed,
   0 skipped) on the gfx1150 host — the `gpu-suite.log` in this bundle does
   exactly that, and 7A-7's workflow should assert the same rather than
   accepting a skip.
5. **`slow` marks only relative weight.** `slow` is applied to the three
   heaviest GPU tests (`test_matmul_correctness`,
   `test_fused_matmul_q4_0_hip`, `test_full_model_inference`). On this host the
   whole GPU lane runs in ~1.6 s, so the marker is advisory; it exists so a
   future slow-test policy has a hook. It is not used to gate anything yet.
6. **The `cpu` marker is registered but not used for selection.** The CPU lane
   is selected by `-m "not gpu"`. `cpu` exists so the CPU suite is explicitly
   marked rather than unmarked, and so `pytest -m cpu` works if wanted.
7. **`test_cpu_only.py` gained a `pytest` import guard.** It is wrapped in
   `try/except ImportError` so the file remains importable without pytest.
   This was verified (probe 5).

---

## 7. Rollback

`git revert` the 7A-1 commit. The package touches only `tests/**` and the
pytest section of `pyproject.toml`; reverting restores the previous
bool-returning tests and the previous collection behaviour exactly. No source,
build, packaging or CI file is involved, so rollback cannot change runtime
behaviour.

---

## 8. Claims changed

**None.** 7A-1 changes no public capability, correctness or performance claim,
so `audit/CLAIMS_LEDGER.md` is unchanged and no ledger row needs a status
update. The claims checker (`scripts/qa/check_claims.py`) is **7A-6** and does
not exist yet at this commit, so no `claims-check.log` is included; the
7A-1 brief does not list it in the bundle for this package.

The `983.4 tok/s` claim (ledger ID 13/27) remains `UNVERIFIED` and is **not**
affected by this package — the G0 baseline measured 849.3 tok/s on this host,
and 7F-3 owns re-recording or removing it. The throughput numbers printed by
`pytest -m gpu` are single-run observations and are recorded here as such, not
as baselined performance figures (7F-3 owns the benchmark harness).
