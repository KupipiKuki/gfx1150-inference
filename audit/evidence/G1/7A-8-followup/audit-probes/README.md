# Auditor probes — 7A-8 follow-up

**Auditor:** DeepSeek V4.1 Flash
**Date:** 2026-11-02
**Fix:** `683a0f7` · **Tip:** `86cdd32`

| Probe | Result |
|---|---|
| GitHub API run `41545742018` | **success**, head `683a0f7` |
| GitHub API run `41544981963` | **failure**, failing step = configure smoke test |
| API check-runs for `86cdd32` | both workflows **success** |
| GREEN job step table | prerequisites, ROCm, configure, summary, build, smoke, sdist, install: all success |
| RED job step table | configure/build green; smoke test failure; sdist steps skipped |
| Local smoke test | `pytest tests/test_build_configure.py` → 3 passed |
| Workflow diff | pytest added; `set -o pipefail`; `if: always()` summary |
| Scope | only CI + follow-up evidence + one-line 7A-8 notes erratum |
| QF-2 | merge-time ledger refresh recorded; auditor will execute |
| ROCm cost | RED 6:46 / GREEN 4:49; 83–87% of job; G1 ruling |

API URLs:

- https://api.github.com/repos/KupipiKuki/gfx1150-inference/actions/runs/41545742018/jobs
- https://api.github.com/repos/KupipiKuki/gfx1150-inference/actions/runs/41544981963/jobs
- https://api.github.com/repos/KupipiKuki/gfx1150-inference/commits/86cdd323433aa72d5f70ec03882b9795dde4709a/check-runs

Full transcript: `probe-commands.log`.
