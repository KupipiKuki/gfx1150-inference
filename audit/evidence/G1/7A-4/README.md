# G1 / 7A-4 — evidence bundle

Deterministic fuzz for the GGUF header parser: 10,000 examples per test,
`derandomize=True`, `database=None`.

**The fuzz found a real parser defect: `BLOCKER.md` (BLOCKER-7A4-1).** A
metadata array whose element type is `ARRAY` makes the parser recurse until
the interpreter's stack is exhausted, so a hostile header of about 12 KiB
raises `RecursionError` instead of the documented `ValueError`. It is pinned in
the test suite as a strict xfail, and `src/` is not touched here.

| file | what it is |
|---|---|
| `BLOCKER.md` | the defect report: the minimized example, the threshold, the impact and the proposed fix |
| `notes.md` | what was added, the mutation coverage, the CI wiring and the verdict |
| `fuzz.log` | the fuzz run with the hypothesis statistics, and what the fuzz exercises |
| `fuzz-rerun.log` | the second run and the diff: the two runs differ only in their timings |
| `measure-fuzz-coverage.py` | reproduces the mutation-class and outcome counts in `fuzz.log` |
| `cpu-lane.log` | the CPU lane (with the fuzz), `test_cpu_only.py` in both modes, the claims checker |
| `gpu-lane.log` | the GPU lane (unchanged: 24 passed) |
| `sdist-install.log` | the sdist-install job rehearsed locally, with the new `hypothesis` dependency and the `slow` deselection |
| `ci-run.log` | the GitHub Actions run: URLs, job names, conclusions |
| `env.txt` | environment, toolchain, and the fuzz settings |
| `diffstat.txt` | the package's file delta and the scope check |
| `parent-sha.txt` | the branch base (`758e500`) |
| `candidate-sha.txt` | the work commit under review |

The fuzz itself is `tests/test_fuzz_gguf.py`.
