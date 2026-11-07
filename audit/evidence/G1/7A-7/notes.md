# G1 / 7A-7 — GPU CI scaffold

**Package:** 7A-7 (G1 item: GPU CI workflow + the skip-is-not-a-pass guard)
**Branch:** `wp/7A-7-gpu-ci`
**Base:** `vibe/phase7-220201` @ `a873a9c` (includes Mistral's PASS verification and
all merged 7A packages, including 7A-8's build fix)
**red/green:** **N/A (CI-only)** — no GitHub Actions runner is registered, so the
workflow was **not** executed by Actions. It was validated mechanically
(`yaml-validation.log`) and its steps were executed **verbatim on this gfx1150
host** — the same hardware the runner will provide (`gpu-lane.log`). The guard
itself has a red/green pair (`skip-guard.log`), because a skip-is-not-a-pass rule
is only worth anything if it is shown to fail.

---

## What was added

`.github/workflows/ci-gpu.yml` — one job, `gpu-correctness`, on
`runs-on: [self-hosted, gfx1150, rocm]`, triggered on `pull_request`, a nightly
`schedule` (03:00 UTC) and `workflow_dispatch`.

| step | what it does |
|---|---|
| Checkout repository | `actions/checkout@v4` |
| Install the documented test/build prerequisites | host `python3 -m pip install numpy setuptools wheel pybind11 pytest` — no ROCm pip package; the ROCm toolchain comes from the runner image |
| Configure the project (the documented command) | `rm -rf build` then `env -u pybind11_DIR cmake -B build -DCMAKE_BUILD_TYPE=Release` — the README-documented command, with 7A-8's discovery fix, and no cache from an earlier run on the runner |
| Build the HIP extension | `cmake --build build -j` |
| Run the GPU lane (a skip is not a pass) | `PYTHONPATH=build:src python3 -m pytest -m gpu -v -rs --junitxml=gpu-lane.xml`, then the no-skip guard |
| Upload the GPU lane logs | `actions/upload-artifact@v4`, `if: always()`, so the logs survive a failing lane |

## The skip-is-not-a-pass guard (C-7A1-6 / QF-5)

This is the point of the package. The GPU lane is **all-or-nothing**: if the HIP
extension is not importable, `tests/conftest.py`'s `matmul_module` fixture turns
every `gpu`-marked test into a **skip**, and **pytest exits 0**. A workflow that
trusted the exit code would report a green build whose extension was never
produced. That is exactly the failure the G1 audit recorded as C-7A1-6.

So the step does not trust the exit code. It parses the junit report and
requires: **at least one test collected**, **at least one passed**, **zero
skipped**, and no failures or errors.

The brief offers a grep-based pattern; this uses the junit report instead, for
two reasons:

* The junit report carries the counts as data, so the guard can report *how
  many* tests were skipped and stays robust to prose/report-format changes.
  (The brief's grep pattern was tested against both real lane outputs and
  behaves correctly there; this is a robustness/precision choice, not a
  demonstrated false positive.)
* The counts are exact, so the guard states *how many* were skipped rather than
  only that the text appeared.

`skip-guard.log` is the red/green pair for the guard, with the guard extracted
**verbatim from the parsed workflow** (so it is exactly what the shell runs on the
runner, not a re-typed copy):

| case | result |
|---|---|
| the real lane on gfx1150 | 18 passed / 0 skipped → **exit 0** |
| the extension not importable | pytest exits **0**, guard says `FAIL: the GPU lane reported no passing test` → **exit 1** |
| 3 passed + 1 skipped | `FAIL: the GPU lane skipped 1 test(s) -- a skip is not a pass` → **exit 1** |
| nothing collected | `FAIL: the GPU lane collected no tests` → **exit 1** |

## The gate state: not a G1 pass

`continue-on-error: true` is set, because **no self-hosted runner is
registered**: there is no runner directory on this host and no runner service, so
the job would simply queue forever. The workflow says so in its header comment,
and names the tracking:

* https://github.com/KupipiKuki/gfx1150-inference/pull/8 — the open Phase 7 gates tracker;
* handoff work package **7F-1**, which registers the runner with the labels
  `gfx1150` and `rocm` and then removes `continue-on-error` so the lane is
  required on PR and nightly.

**A note on the recorded SHA.** The branch's first push of this package recorded
`candidate-sha.txt` as the commit that *recorded* the SHA rather than the work
commit it stands for. That is corrected in a later commit on the same branch, so
that the published history is not rewritten: `candidate-sha.txt` names the work
commit (`955fa04`, the commit that adds the workflow and this bundle), and
`diffstat.txt` is computed from it, so both figures are exact.

**This package does not claim GPU CI is enforced.** The lane is designed and its
steps are verified on the target hardware, but until the runner exists the job is
queued, not green, and it must not be counted as a G1 pass.

## Validation

`yaml-validation.log` is the output of `validate-workflow.py` (committed next to
it), which checks the brief's section-3 requirements one by one: the runner
labels, the triggers, `continue-on-error`, a timeout, the documented configure
command, the build, `pytest -m gpu`, that the lane is checked for skips and not
only for an exit code, that at least one test must pass, that the artifact upload
exists and runs on failure, that no secret is referenced, and that the tracking
issue is named. **20/20 checks pass.**

The workflow's steps were then executed verbatim on this host, from a clean
checkout, in the order the workflow runs them (`configure.log`, `build.log`,
`gpu-lane.log`):

```
configure: -- pybind11 CMake package: .../site-packages/pybind11/share/cmake/pybind11
           -- Configuring done
build:     [100%] Built target matmul_module
lane:      18 passed, 43 deselected in 1.71s        (0 skipped)
```

So the *commands* are proven correct on gfx1150; what is unproven is the
*Actions plumbing* (runner registration, artifact upload), which cannot be
exercised without the runner.

## Two deliberate deviations, both stated

1. **The guard parses junit XML instead of grepping the output** (above). The
   brief allows adjusting the pattern; the intent — at least one passed, zero
   skipped, fail on failed/error — is met exactly, and `skip-guard.log` shows
   each clause firing.
2. **The configure step removes `build/` first.** The brief asks for a clean
   checkout and no pre-existing cache; on a self-hosted runner the workspace
   persists between runs, so a stale `build/` (and a stale
   `matmul_module.so`) could make a broken build look green. `rm -rf build` makes
   the run hermetic. This is also why the lane's `PYTHONPATH` points at the
   freshly built extension.

## What was verified

| check | result |
|---|---|
| workflow exists, valid YAML, `runs-on: [self-hosted, gfx1150, rocm]` | yes — `yaml-validation.log`, 20/20 checks |
| the build uses the documented clean-clone path (no `pybind11_DIR`) | yes — `env -u pybind11_DIR cmake -B build -DCMAKE_BUILD_TYPE=Release`, executed and green |
| the GPU step fails on any skip and on any failure | yes — `skip-guard.log`, three red cases and one green |
| `18 passed / 0 skipped` on gfx1150 | yes — `gpu-lane.log` |
| artifacts upload | `actions/upload-artifact@v4`, `if: always()` |
| `continue-on-error: true` with a tracked runner issue | yes — PR #8 and 7F-1 are named in the workflow header |
| no `src/`, tests, CMake, packaging, ledger, baseline or docs outside the allowed set | confirmed by the diffstat |
| the workflow executed by GitHub Actions | **no** — no runner is registered; validated mechanically and run verbatim on the gfx1150 host instead |

## Limitations and follow-ups

1. **The workflow has never run in Actions.** The runner does not exist. Until
   7F-1 registers it, the job is queued, and the artifact upload path is
   unexercised.
2. **The runner image must provide ROCm and a pip-installable Python.** The
   prerequisites step installs into the host Python; on a distribution whose
   Python is PEP 668 "externally managed", `pip install` fails and the step
   fails loudly rather than silently. Provisioning the runner with a
   pip-installable interpreter (a venv or a pyenv build) is part of 7F-1.
3. **The lane's expected size is asserted as "at least one passed, zero
   skipped", not as an exact count.** The brief says the exact count may change
   only with an approved test addition; asserting an exact 18 would make an
   approved addition look like a failure. The count is *reported* in the log
   (`GPU lane: 18 passed, ...`) so a change is visible.
4. **The nightly schedule assumes the runner is registered**; until then the
   nightly trigger also queues.
5. **The ROCm install cost question is untouched.** It belongs to 7A-8's
   hosted job, not to this self-hosted one: the runner image provides ROCm, so
   there is no per-run download here.

## Rollback

Revert the commit and delete `.github/workflows/ci-gpu.yml`. Nothing else in the
repository changes, so the rollback cannot affect the CPU CI, the build, or any
package's evidence. The evidence bundle is additive.

## Claims changed

None. No public claim was added, removed or re-qualified. This package adds CI
plumbing and the evidence that a skipped GPU lane cannot be mistaken for a pass.
