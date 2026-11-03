# G1 / 7A-8 follow-up — CI condition QF-1

**Package:** 7A-8 follow-up (condition C-7A8-1; merge checklist C-7A8-2 recorded for G1)
**Branch:** `wp/7A-8-followup`
**Base:** `cb4655c` (the independent audit commit on `wp/7A-8-build-entrypoint`; content candidate `9c04912`)
**Audit trace:** `audit/AUDIT_7A-8_BUILD_ENTRYPOINT_DEEP_2026-11-02.md` §3 (QF-1, QF-2, the ROCm-cost observation)
**red/green:** **applies** — the RED is the CI job's own first run (it failed at the
configure smoke test with `No module named pytest`), the GREEN is the second run of
the same workflow after the fix. `ci-run.log` holds both.

The build fix itself is **not** touched. This package is CI and merge bookkeeping.

---

## C-7A8-1 (QF-1) — make `ci-build.yml` runnable

### The defect

The job installed `numpy`, `setuptools`, `wheel` and `pybind11`, then ran
`python -m pytest tests/test_build_configure.py -v`. `actions/setup-python` does not
ship pytest, so the job died with `No module named pytest` before it ever reached
the smoke test. The build fix was never reached either — but the configure and the
build had already succeeded by then, so the defect was confined to the test step.

### The fix

One word, in the prerequisites step:

```yaml
python -m pip install --upgrade pip \
  "numpy>=1.24.0" "setuptools>=64" wheel "pybind11>=2.12" pytest
```

Plus a run-log step, which the brief allows ("one word plus any needed run-log
step"): the configure step now tees to `configure.log` under `set -o pipefail`, and
a following step publishes the lines that matter to the job summary. A green run is
therefore self-evidencing — the summary carries

```
### Configure (documented command, no ambient pybind11_DIR)

-- pybind11 CMake package: /opt/hostedtoolcache/Python/3.12.*/lib/python3.12/site-packages/pybind11/share/cmake/pybind11
-- Configuring done
```

which is the proof that pybind11 was discovered from the interpreter rather than
from an ambient `pybind11_DIR`.

`set -o pipefail` is explicit because GitHub's default bash step is `bash -e {0}`,
which does **not** set `pipefail`: without it, `cmake ... | tee configure.log`
would report success even when cmake failed.

### The two CI runs

Both on `wp/7A-8-followup`; the full API view is in `ci-run.log`.

| | RED | GREEN |
|---|---|---|
| run | [41544981963](https://github.com/KupipiKuki/gfx1150-inference/actions/runs/41544981963) | [41545742018](https://github.com/KupipiKuki/gfx1150-inference/actions/runs/41545742018) |
| head sha | `33fc5f98` (the prep commit) | `683a0f70` (this follow-up) |
| conclusion | **failure** | **success** |
| failing step | 9. *Run the configure smoke test* → failure | — |
| skipped after the failure | 10. Build the sdist · 11. Install the sdist in a clean venv | — |

Every other step was green in both runs, including *Install the ROCm development
packages*, *Configure the project (the documented command)* and *Build the HIP
extension*. So the ROCm apt repository, the package name and the documented
configure command all work on the hosted runner — the only thing broken was the
missing pytest.

`qf1-local-repro.log` reproduces the failure text locally with the job's exact
prerequisites (a fresh virtualenv with numpy, setuptools, wheel and pybind11, and
no pytest), and shows the same virtualenv passing once pytest is installed.

**On the excerpt.** The raw log download is `GET /repos/{owner}/{repo}/actions/runs/{id}/logs`,
which answers **HTTP 403** without an API token, and there is no token in this
environment. What is recorded is the API's own view of the run: the conclusion,
every step's conclusion, and the check-run annotations (including
`Process completed with exit code 1` for the failing step). `capture-run.py` in this
directory regenerates it.

The runs also surface one advisory annotation, unchanged by this fix:
`actions/checkout@v4` and `actions/setup-python@v5` target Node.js 20 and are forced
onto Node.js 24. That is a deprecation notice, not a failure; bumping the action
versions is a separate, low-risk change that belongs with the next CI edit.

## C-7A8-2 (QF-2) — merge checklist for G1 (recorded, not executed here)

This is the merge owner's step, not a change to this branch. The 7A-8 README
additions shift the 7A-6 ledger's README references by **+19**, and the 7A-6
checker reports the shift as **drift warnings** — designed behaviour, not a
failure.

At the 7A-8 merge into `vibe/phase7-220201`:

| what | from | to |
|---|---|---|
| claims 8, 9 (qualified site) | `README.md:111` | `README.md:130` |
| claims 10, 11, 12 (sites) | `README.md:110,111` | `README.md:129,130` |
| claim 21 (qualified site) | `README.md:104` | `README.md:123` |
| ID 3 locator block | `L85–L89` | `L98–L102` |

Then:

1. refresh the nine README scope references and the ID-3 prose;
2. re-run `python3 scripts/qa/check_claims.py`;
3. require **zero drift warnings** (0 stale-scope, 0 findings).

The `id3_claim_removed` canary is line-independent and survives the shift, so the
C-1 fix does not need re-doing at merge time.

The numbers above are the auditor's throw-away merge simulation
(`AUDIT_7A-8_BUILD_ENTRYPOINT_DEEP_2026-11-02.md` §3, QF-2). They are recorded
here as a checklist; **they are not executed on this branch**, and the merge owner
should recompute them from the actual merge rather than trusting this table.

## Observation — the ROCm install cost

`ci-build.yml` installs ROCm from AMD's stable apt repository on every push and
pull request. The two runs above measure the cost precisely (`ci-run.log` carries
every step's duration):

| step | RED run | GREEN run |
|---|---|---|
| *Install the ROCm development packages* | **6:46** | **4:49** |
| everything else (11 steps) | 1:04 | 1:07 |
| job wall clock | 7:50 | 5:56 |

So the ROCm install is 83-87 % of the job, and everything the acceptance is about
- the configure, the build, the smoke test, the sdist install - costs under a
minute in total.

This is **not** a 7A-8 condition. The auditor's G1 ruling is open: accept it for
now, or narrow the hosted job to the configure-only check and move the full build
to the self-hosted gfx1150 runner (7A-7's `ci-gpu.yml`, 7F-1's runner). The
follow-up's recommendation is the second option — the hosted job then proves the
*C-1 fix* (the configure succeeds on a clean tree), which is what the acceptance
is about, while the build and the GPU tests run where a gfx1150 exists — but the
decision is the auditor's and is recorded for G1 rather than taken here.

## What was verified

| check | result |
|---|---|
| `ci-build.yml` prerequisites include pytest | yes — `... "pybind11>=2.12" pytest` |
| the smoke test runs locally with pytest installed | `python -m pytest tests/test_build_configure.py -v` → 3 passed |
| one green `ci-build.yml` run recorded | run [41545742018](https://github.com/KupipiKuki/gfx1150-inference/actions/runs/41545742018), conclusion `success`, every step green |
| the CI job's own RED recorded | run [41544981963](https://github.com/KupipiKuki/gfx1150-inference/actions/runs/41544981963), conclusion `failure` at the smoke-test step |
| ROCm apt install and package name on the hosted runner | both steps green in both runs |
| the documented configure command on the hosted runner | green in both runs |
| the build, the sdist and the full sdist install on the hosted runner | green in the GREEN run |
| no build-fix, CMake, README, tests, source, packaging, ledger or 7A-6 change | confirmed by the diffstat |
| `audit/CLAIMS_LEDGER.md`, `audit/claims_baseline.txt` | present on this branch (it forks from `4bcffeb`) and untouched |
| `scripts/qa/**`, the 7A-6 evidence | not present on this branch — 7A-8 forks from `4bcffeb`, in parallel with 7A-6 — and not added |

## Files touched

| file | change |
|---|---|
| `.github/workflows/ci-build.yml` | `pytest` added to the prerequisites; the configure step tees to `configure.log` under `set -o pipefail`; a new step publishes the configure excerpt to the job summary |
| `audit/evidence/G1/7A-8-followup/**` | this bundle: `ci-run.log`, `qf1-local-repro.log`, `capture-run.py`, `notes.md` |

Nothing else. `CMakeLists.txt`, `README.md`, `tests/**`, `src/`, `setup.py`,
`pyproject.toml`, `MANIFEST.in`, the claims ledger and the baseline are all
untouched, as the brief requires. (`scripts/qa/**` and the 7A-6 evidence are not
on this branch at all — 7A-8 forks from `4bcffeb`, in parallel with 7A-6 — so
they are untouched by construction; that is also why the claims checker could not
be run as an extra check on this branch.)

## Limitations and follow-ups

1. **The raw CI log could not be archived.** The download endpoint needs an API
   token (HTTP 403 unauthenticated) and none is available here. The recorded
   excerpt is the API's step table and annotations. If a reviewer wants the raw
   text, the run URL is in `ci-run.log` and is readable in a browser.
2. **The `actions/checkout@v4` / `actions/setup-python@v5` Node.js 20
   deprecation** is visible as an annotation on both runs. It is advisory, but the
   action versions should be bumped with the next CI edit.
3. **The ROCm install cost is unresolved** — see the observation above; it is a
   G1 ruling, not a 7A-8 condition.
4. **QF-2 is recorded, not executed.** The merge owner recomputes the line
   numbers from the actual merge.

## Rollback

Revert the commit. The only functional change is the workflow file; the evidence
bundle is additive. Reverting restores the prep commit's workflow exactly, i.e.
the job that fails at the smoke test.
