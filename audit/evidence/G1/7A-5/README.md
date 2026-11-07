# G1 / 7A-5 — evidence bundle

CPU pytest CI job + sdist-install CI job, and the **C-7A1-5** fix
(`tests/conftest.py` missing from the sdist).

| file | what it is |
|---|---|
| `notes.md` | what was added, the red/green, the finding that shaped the job, the 7A-2 closeout, and the stated deviations |
| `sdist-contents.log` | the sdist contents before and after the `MANIFEST.in` fix, and why the defect survived (distutils' default is a `tests/test*.py` filename glob) |
| `sdist-install.log` | the whole `sdist-install` job, executed twice — RED (parent `MANIFEST.in`) and GREEN — with every step script and every exit code |
| `cpu-lane.log` | the whole `cpu-smoke` job, executed step by step, plus the 7A-2 closeout (12/12 normal and `-O`) |
| `ci-run.log` | the GitHub Actions run: URLs, job names, conclusions |
| `env.txt` | environment, toolchain, and the two properties of the rehearsal host that differ from the CI runner |
| `diffstat.txt` | the package's file delta and the scope check |
| `parent-sha.txt` | the branch base (`180fc2d`) |
| `candidate-sha.txt` | the work commit under review |
| `rehearse-workflow.py` | executes a workflow job's `run:` scripts verbatim, as the runner would |
| `verify-pytest-config.py` | verifies 7A-1's pytest configuration (declared + behavioural), the 7A-2 closeout |

The workflow was **not** executed by GitHub Actions from this host: the branch
is a feature branch, so the two jobs were executed here from the *parsed*
workflow, each step's `run:` script extracted exactly as the runner sees it.
`ci-run.log` records the actual CI run for the pushed branch.
