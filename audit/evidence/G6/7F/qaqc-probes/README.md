# 7F QAQC probes — what an independent reviewer should re-run

These probes run *outside* the checked-in test suite; each is one command
from the repo root (fresh clone instructions in `../notes.md`).

| Probe | Command | Expected |
|---|---|---|
| Clean-clone CPU lane | `python -m pytest -m "not gpu" -q` | 525 passed (log: `../clean-clone/cpu-lane.log`) |
| Clean-clone GPU lane | `python -m pytest -m gpu -q` | 45 passed (`../clean-clone/gpu-lane.log`) |
| Strict claims gate | `python scripts/qa/check_claims.py --strict` | PASS: 0 unqualified occurrences; baseline-empty enforced |
| Canaries | `python scripts/qa/canary_claims.py` | all 16 detected |
| Bench reproduces | `python scripts/bench/run.py --model synthetic --json > mine.json && python scripts/bench/regress.py scripts/bench/baseline-synthetic.json mine.json` | PASS within 15% (ran on the clean clone: `../clean-clone/bench-regress.log`) |
| Golden from clean clone | `python scripts/qa/real_gguf_golden.py --model <tinyllama> --prompt-file ../golden/prompt1.txt --steps 16 --ref-prefix <ref>/ref --out-dir out [--engine-prompt-ids]` | original criterion: exit 1 with the recorded near-tie fork; **rework criterion** (`--engine-prompt-ids`): Q6_K exit 0 (decisive PASS), Q4_K_M exit 1 (INCONCLUSIVE, recorded) — see `../golden/README.md` |
| Telemetry prompt-leak | the `--json` run in `../telemetry/schema.md`, grep the payload for prompt words | absent; recorded in `../telemetry/variance-and-leak-check.txt` |

`golden_ref.cpp` here is the pinned-llama.cpp reference program source
(see `../golden/README.md` for the exact commit, build line, and model
hashes).
