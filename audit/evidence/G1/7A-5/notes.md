# G1 / 7A-5 — CPU/Sdist CI and C-7A1-5

**Package:** 7A-5 (G1 item: CPU pytest job + sdist-install job, and the
`tests/conftest.py`-in-the-sdist fix, **C-7A1-5**)
**Branch:** `wp/7A-5-ci-sdist`
**Base:** `vibe/phase7-220201` @ `6a6dd20`; branch base commit `180fc2d`
**red/green:** **N/A (CI/packaging)** for the local changes, per the brief.
The meaningful red/green is the **sdist contents** (`tests/conftest.py` absent
→ present) and the **installed-tree collection** (16 fixture errors → clean),
both recorded in `sdist-contents.log` and `sdist-install.log`.

---

## What changed

Two files changed, both inside the allowed set (`MANIFEST.in` and
`.github/workflows/ci-cpu.yml`); everything else this package adds is the
evidence bundle under `audit/evidence/G1/7A-5/`.

### 1. `MANIFEST.in` — C-7A1-5

```diff
 recursive-include src/python_bindings *.cpp
+# The pytest harness must ship with the sdist: without tests/conftest.py the
+# installed tree has no `matmul_module` fixture, so the GPU lane errors instead
+# of skipping (G0 condition C-7A1-5). 7A-3 adds the fixture globs when its
+# fixtures land.
+recursive-include tests *.py
```

No fixture globs were invented: 7A-3 owns those, and its fixtures are data
files rather than `*.py`, so the rule above stays correct when they land.

### 2. `.github/workflows/ci-cpu.yml` — the CPU job

* `pytest` added to the job's dependencies;
* a new **blocking** step, `python -m pytest -m "not gpu" -q`;
* everything else kept: `test_cpu_only.py` in normal and `-O` mode, the claims
  checker and the canaries blocking, `--strict` advisory
  (`continue-on-error: true`).

### 3. `.github/workflows/ci-cpu.yml` — the new `sdist-install` job

Nine steps, in this order (the first two are the `actions/*` steps, shown
together):

| step | what it does |
|---|---|
| Checkout / Set up Python 3.12 | `actions/checkout@v4`, `actions/setup-python@v5` |
| Install the packaging prerequisites | `setuptools>=64`, `wheel` |
| Build the sdist | `python setup.py sdist --dist-dir dist` |
| Assert the sdist ships the pytest harness | `tests/conftest.py` and `tests/test_harness_contract.py` must be present, **and every `tests/*.py` in the repository must be in the sdist** |
| Install the sdist into a clean venv | `python -m venv`, `pip install pytest setuptools`, then `GFX1150_SKIP_CMAKE=1 python -m pip install dist/*.tar.gz` — a **real install**, not an archive listing |
| Assert the installed module split | `gguf_parser`/`tokenizer`/`weight_loader` import from the venv; `kv_cache`/`layer`/`inference` raise an actionable `ImportError` |
| Run the shipped CPU lane in the extracted tree | `python -m pytest -m "not gpu" -q` |
| Run the full shipped lane in the extracted tree | `python -m pytest -q -rs` — the C-7A1-5 regression guard |

Every step exits non-zero on failure, and the job as a whole fails if any step
does.

---

## The red/green

### The sdist contents (`sdist-contents.log`)

| | RED (parent `MANIFEST.in`) | GREEN (candidate) |
|---|---|---|
| sdist entries | 47 | 48 |
| `tests/test_*.py` | 8 files | 8 files |
| `tests/conftest.py` | **absent** | **present** |

The reason the defect survived so long is worth recording: distutils'
`sdist.add_defaults()` documents its default file list as *"README or
README.txt / setup.py / **tests/test\*.py and test/test\*.py** / …"*. The
default is a **filename glob**, so it picked up the eight test modules and by
construction excluded `tests/conftest.py` — the one file the pytest harness
needs. The sdist *looked* like it shipped the tests; it shipped eight of the
nine files the harness consists of.

### The installed-tree collection (`sdist-install.log`)

The job was run twice, from the *parsed* workflow, with each step's `run:`
script extracted exactly as the runner would see it
(`rehearse-workflow.py`):

| step | RED | GREEN |
|---|---|---|
| 5 — assert the sdist ships the harness | **exit 1** — `FAIL: the sdist does not contain tests/conftest.py` | exit 0 |
| 6 — install into a clean venv | exit 0 | exit 0 |
| 7 — module split | exit 0 | exit 0 |
| 8 — CPU lane in the extracted tree | exit 0 — 41 passed, 2 skipped | exit 0 — 41 passed, 2 skipped |
| 9 — **full** lane in the extracted tree | **exit 1** — 43 passed, 2 skipped, **16 errors** | exit 0 — 41 passed, 20 skipped |

### The finding that shaped the job: the CPU lane does not detect C-7A1-5

Step 8 is **exit 0 in the RED**. The CPU lane alone cannot catch this defect,
because `tests/test_cpu_only.py` puts `src/` on `sys.path` itself (lines 45–47)
and therefore passes with or without `conftest.py`. Only the **full** lane
detects it: without `tests/conftest.py` the GPU tests request a
`matmul_module` fixture that does not exist, so they **error** (16 fixture
errors) instead of **skipping**.

That is why the job has *two* lane steps. Step 9 is the regression guard, and
step 8 is the brief's acceptance criterion. A CI job with only step 8 would
have been green while C-7A1-5 was still open.

(The brief's acceptance says "no exit 2". The measured RED is **exit 1 with 16
errors**, not exit 2 — exit 2 was the *pre-7A-1* behaviour, when the GPU
modules imported the extension at module scope, as `tests/conftest.py`'s
docstring records. Both are collection failures; the current failure mode is
the fixture error, not the import error.)

---

## The rehearsal caught a real defect in the job

The first run of the rehearsed job failed at step 8:

```
FAILED tests/test_cpu_only.py::TestCPUOnlySuite::test_v8_b1_pyproject_and_sdist_contents
AssertionError: 1 != 0 : setup.py sdist failed:
ModuleNotFoundError: No module named 'setuptools'
```

The shipped suite's packaging test builds an sdist with the interpreter that
runs the tests, so the venv needs `setuptools` — not only for the install
(which pip's build isolation fetches separately) but for the suite itself.
`python -m venv` does not install setuptools on Python ≥ 3.12, so the job now
installs it explicitly. **This is why the job was rehearsed rather than
written and shipped.**

---

## The CI run (`ci-run.log`)

The branch was pushed, so the workflow's `push` trigger ran both jobs on the
runner the workflow targets — **ubuntu-latest, Python 3.12**:

```
CPU-Only Verification & Regression CI   run 41739977786   completed / success
  job  CPU Parser, Tokenizer, Sampler & Packaging Suite   -> success
       ... 5. Run self-contained CPU test suite (standard mode)            success
       ... 6. Run self-contained CPU test suite (optimized -O mode)        success
       ... 7. Run the pytest CPU lane                                      success
       ... 8. Check the claims ledger (default mode, ratchet baseline-aware) success
       ... 9. Check the claims checker canaries                            success
       ...10. Check the claims ledger (strict mode, advisory until G6)     success
  job  Sdist Install (CPU-only path, GFX1150_SKIP_CMAKE=1)                 -> success
       ... 5. Build the sdist                                             success
       ... 6. Assert the sdist ships the pytest harness (C-7A1-5)         success
       ... 7. Install the sdist into a clean venv (CPU-only path)         success
       ... 8. Assert the installed module split (CPU imports; GPU modules raise) success
       ... 9. Run the shipped CPU lane in the extracted sdist tree        success
       ...10. Run the full shipped lane in the extracted sdist tree (C-7A1-5 guard) success
```

Every step of every job is green. The raw step logs need repository admin
rights to download (HTTP 403 on `/actions/jobs/<id>/logs`), so what is
recorded is the run state and each step's conclusion.

**This CI run is the authoritative check** — it closes the only deviation the
local rehearsal carried (the interpreter version, below).

---

## The 7A-2 closeout (`cpu-lane.log`)

7A-2 was implemented inside 7A-1's `[tool.pytest.ini_options]` block, so its
closeout is a **verification, not new code**. No duplicate configuration was
added; the section in `pyproject.toml` is untouched by this package.

`verify-pytest-config.py` checks it two ways — **17/17 pass**:

* **declared** — `minversion`, `testpaths = ["tests"]`, the `gpu`/`cpu`/`slow`
  markers, `--strict-markers`, `--strict-config`, `-ra`, and the
  `PytestReturnNotNoneWarning` escalation in both `addopts` and
  `filterwarnings`;
* **behavioural** (in a scratch directory that reproduces the configuration
  verbatim, so nothing is written into the repository) — an unknown marker is
  an error, an unknown ini option is an error, and a test that *returns* a
  value instead of asserting is an error.

And the two required runs:

| run | result |
|---|---|
| `python tests/test_cpu_only.py` | **Ran 12 tests … OK** (exit 0) |
| `python -O tests/test_cpu_only.py` | **Ran 12 tests … OK** (exit 0) |

---

## What was verified

| check | result |
|---|---|
| `MANIFEST.in` includes `tests/**`; the sdist contains `tests/conftest.py` and `tests/test_harness_contract.py` | yes — `sdist-contents.log`; the job's own assertion, RED exit 1 → GREEN exit 0 |
| the CPU CI job runs the pytest CPU lane plus the existing unittest/claims steps | yes — `cpu-lane.log`, all nine steps, blocking steps exit 0, the advisory `--strict` step exits 1 and the job continues |
| sdist-install: a real clean-venv install with `GFX1150_SKIP_CMAKE=1` | yes — `sdist-install.log` step 6, exit 0 |
| the installed package's CPU modules import; the GPU modules raise the actionable `ImportError` | yes — step 7, exit 0; each CPU module is asserted to come from the venv's site-packages, and `matmul_module` is asserted to be absent so the GPU assertions cannot be vacuous |
| the extracted tree collects and runs the CPU lane, and the full lane has no collection error | yes — steps 8 and 9, exit 0 (41 passed / 20 skipped) |
| no collection errors on a CPU-only host; expected skips are visible | yes — the skip reasons are printed (`-rs`); the two `test_build_configure.py` skips are visible in the log |
| 7A-2 closeout: 12/12 normal and `-O`, and the pytest configuration verified | yes — `cpu-lane.log` |
| the two jobs run green in GitHub Actions on ubuntu-latest / Python 3.12 | yes — `ci-run.log`, run 41739977786, every step of both jobs green |
| no `src/`, CMake, `setup.py`, README, ledger, baseline, or 7A-6 evidence change | confirmed by `diffstat.txt` |
| no test deleted, skipped, or weakened | confirmed — `tests/**` is unchanged; the only test-visible change is that the shipped suite now *runs* from the sdist |

---

## Two deliberate deviations, both stated

1. **The full lane runs in the sdist job, not only the CPU lane.** The brief's
   step 4 asks for `pytest -m "not gpu"`. That is step 8, and it is there. Step
   9 adds the full lane because, as measured above, the CPU lane passes with
   or without `conftest.py` — a job with only step 8 would not have caught
   C-7A1-5. The full lane's skips stay visible (`-rs`), so the GPU lane is
   never a silent pass.

2. **The venv gets `setuptools` explicitly.** Python ≥ 3.12's `venv` does not
   install it, and the shipped packaging test needs it to build an sdist. This
   was found by rehearsing the job, not by inspection.

---

## Limitations and follow-ups

1. **The rehearsal ran on Python 3.14.10, not the workflow's 3.12.** This
   host's `/usr/bin/python3.12` ships without `ensurepip` and without `pip`,
   so `python -m venv` cannot seed a venv there. The commands are unchanged and
   the version does not affect what is proven (the sdist installs; the shipped
   suite runs). **The deviation is closed by the CI run above**, which executed
   the same scripts on Python 3.12 and was green.

2. **The rehearsal host has ROCm; the CI runner does not.** The rehearsal
   exported `ROCM_ROOT=/nonexistent-rocm` so the suite takes exactly the
   same code path as a CPU-only runner. The extension is absent either way
   (`GFX1150_SKIP_CMAKE=1` never builds it; the extracted tree has no
   `build/`).

3. **`tests/fixtures/PROVENANCE.md` still does not ship.** 7A-3 owns the
   fixture globs; this package adds only `recursive-include tests *.py`, as
   instructed. The job's assertion is deliberately about `*.py` only.

4. **The `sdist-install` job builds the sdist twice** — once by the job, and
   once more inside `test_v8_b1_pyproject_and_sdist_contents`. That is the
   shipped test's behaviour, not the job's.

5. **The `--strict` claims step still exits 1** until G6. It is advisory, as
   before; the job treats it as such.

6. **7A-3 and 7A-4 are not started here.** They will use the jobs this
   package adds.

---

## Rollback

Revert the commit and delete the `sdist-install` job from
`.github/workflows/ci-cpu.yml`; the `MANIFEST.in` line can be removed
independently. Nothing else in the repository changes, so the rollback cannot
affect the build, the GPU CI, or any other package's evidence. The evidence
bundle is additive.

## Claims changed

None. No public claim was added, removed or re-qualified. This package adds CI
plumbing, one packaging rule, and the evidence that the shipped harness is
installable and runnable.
