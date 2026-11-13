# G1 / 7A-9 — evidence bundle

The BLOCKER-7A4-1 parser fix: `GGUFParser._read_value` now rejects a
metadata array whose element type is `ARRAY` with the parser's documented
`ValueError`, before reading any values. The unguarded recursion — a
stack-exhaustion path on a ~12 KiB hostile header, and silent acceptance of
shallower nesting — is gone.

| file | what it is |
|---|---|
| `red.log` | the pinned nested-array test fails on the parent (`--runxfail`: `RecursionError`) |
| `green.log` | the same test passes on the candidate, with the xfail removed |
| `nested-array-boundary.log` | the three nested tests: depth 1000, depth 300 (below the old threshold, previously accepted), and the minimized 992-level example |
| `fuzz.log` | 7A-4's 10,000-example deterministic fuzz, unchanged, re-run on the candidate |
| `cpu-lane.log` | the CPU lane (111 passed / 24 deselected / 4 xfailed), `test_cpu_only.py` in both modes, the claims checker |
| `runxfail.log` | the CPU lane with `--runxfail`: only the four tokenizer 7B/7C pins fail; no parser failure |
| `gpu-lane.log` | the GPU lane, unchanged: 24 passed |
| `env.txt` | environment, toolchain, the fix and what was not touched |
| `diffstat.txt` | the package's file delta and the entire `src/` diff |
| `parent-sha.txt` | the parent (`3af32d4`, brief-prep; code identical to the G1 base `e9b6b80`) |
| `candidate-sha.txt` | the work commit under review |
| `notes.md` | the defect, the fix, the exact commands, the results and the verdict |

The fix is the one line in `src/gguf_parser.py` (`tests/test_fuzz_gguf.py`
carries the test changes). The full report is `notes.md`.
