# G1 / 7A-8 follow-up — evidence bundle

Condition C-7A8-1 (QF-1): make `ci-build.yml` runnable, and record one green run.

| file | what it is |
|---|---|
| `notes.md` | what was done, the two CI runs, the QF-2 merge checklist for G1, and the ROCm-cost measurement |
| `ci-run.log` | the GitHub Actions API's view of the RED run (41544981963) and the GREEN run (41545742018): conclusion, every step's conclusion and duration, check-run annotations |
| `qf1-local-repro.log` | the `No module named pytest` failure reproduced locally with the job's exact pre-fix prerequisites |
| `capture-run.py` | regenerates `ci-run.log` from the Actions API |
| `env.txt` | environment and the two run identifiers |
| `diffstat.txt` | the package's file delta and the scope check |
| `parent-sha.txt` | the base of the follow-up branch (the 7A-8 audit commit) |
| `candidate-sha.txt` | the follow-up's fix commit (the workflow change) |

The raw CI log needs an authenticated API call (`GET .../actions/runs/{id}/logs`
answers HTTP 403 without a token), so the recorded excerpt is the API's step
table and annotations rather than the log text.
