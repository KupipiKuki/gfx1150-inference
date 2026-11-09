# G6 / 7F clean-clone verification

Fresh clone of the work commit (`../candidate-sha.txt`, `a4887d4`) into
`/tmp`, fresh `cmake` configure + build, then every required check run
from that tree (`2026-11-08`). The pinned-llama.cpp reference artifacts
and real GGUFs live outside the repo (see `../golden/README.md`), so the
golden re-run used them by absolute path; everything else is from the
clone alone.

| Check | Exit | Log / artifact |
|---|---|---|
| `cmake -B build` configure + build | 0 | (not kept; summary in notes below) |
| `python -m pytest -m "not gpu" -q` | 0 (525 passed) | `cpu-lane.log` |
| `python -m pytest -m gpu -q` | 0 (45 passed) | `gpu-lane.log` |
| `python scripts/qa/check_claims.py --strict` | 0 (PASS, 0 unqualified) | `claims-strict.log` |
| `python scripts/qa/canary_claims.py` | 0 (16/16) | `canaries.log` |
| `test ! -s audit/claims_baseline.txt` | 0 (0 bytes) | — |
| `python scripts/bench/run.py --model synthetic --json` | 0 | `bench-synthetic.json` |
| `python scripts/bench/regress.py baseline-synthetic.json result` | 0 (PASS within 15%) | `bench-regress.log` |
| `python scripts/qa/real_gguf_golden.py ...` (Q4_K_M prompt 1) | **1 — the recorded honest FAIL** | `golden-q4km-cleanclone.json` |

The clean-clone golden is **bit-identical** to the bundle verdict
(`per_step_summary` equal; first fork at step 14, the same near-tie), so
the golden outcome and its tolerance analysis reproduce from a clean
clone with the documented acquisition commands.
