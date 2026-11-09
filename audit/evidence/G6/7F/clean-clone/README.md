# G6 / 7F clean-clone verification

Two rounds: the **original candidate** (`a4887d4`)
and the **rework** (`b3920d2`, `PHASE7_7F_REWORK_BRIEF.md`). Both: fresh
clone of the commit into `/tmp`, fresh `cmake` configure + build on the
gfx1150 host, every required check run from that tree alone (the pinned
llama.cpp reference artifacts and real GGUFs live outside the repo — see
`../golden/README.md` — and are referenced by absolute path).

## Rework run at `b3920d2` (2026-11-08)

| Check | Exit | Log / artifact |
|---|---|---|
| `cmake` configure + build | 0 | — |
| `python -m pytest -m "not gpu" -q` | 0 (527 passed) | `cpu-lane.log` |
| `python -m pytest -m gpu -q` | 0 (45 passed) | `gpu-lane.log` |
| `tests/test_cpu_only.py` / `-O` | 0 / 0 | `cpuonly.log` |
| `check_claims.py --strict` | 0 (PASS, baseline 0 bytes) | `claims-strict.log` |
| `canary_claims.py` | 0 (16/16) | `canaries.log` |
| golden Q6_K rerun (`--engine-prompt-ids`, decisive-margin) | **0 — decisive PASS** (2 steps exact; strict16 FAIL kept in the verdict) | `golden-rework-cleanclone.json` |
| sdist build → extract → `pytest -m "not gpu and not slow" -q` | 0 (523 passed, 49 deselected) | `../rework-run.log` (tail) |

## Original candidate run at `a4887d4` (kept for the record)

| Check | Exit |
|---|---|
| CPU lane | 0 (525 passed) — `cpu-lane.log` was refreshed by the rework run; the original log is preserved in git history at `0554e07` |
| GPU lane | 0 (45 passed) — same |
| strict claims | 0 |
| canaries | 16/16 |
| bench synthetic + regress gate | 0 (PASS within 15%; `bench-synthetic.json`) |
| golden Q4_K_M p1 (pre-amendment criterion) | 1 — the recorded honest strict FAIL (bit-identical to the bundle verdict) |

The rework golden reruns for all three prompts (decisive-margin criterion)
are `../golden/verdict-rework-*.json`; the battery summary is
`../rework-run.log`.
