# G6 / 7F — Evidence & release-gate bundle

This directory is the coder/QAQC bundle for Phase 7F (Gate G6). The audit
report/signoff will be added by the auditor; do not pre-fill an audit verdict.
**Note:** `*.log` is git-ignored in this repository; add required logs with
`git add -f` (as the G5/7E bundle did).

## Required files

| File | Contents |
|---|---|
| `env.txt` | OS/kernel, ROCm/HIP, `rocminfo`, Python, NumPy, CMake, `git rev-parse HEAD` |
| `parent-sha.txt` | the G6 base (`vibe/phase7-220201` tip, `08698f4` at authorization) |
| `candidate-sha.txt` | the frozen work commit under review |
| `diffstat.txt` | file delta and allowed/forbidden set |
| `gpu-runner.md` | runner labels/registration state, workflow diff, evidence the GPU job is required and blocks a red suite |
| `golden/` | model identity/hash, llama.cpp commit, commands, exact token IDs, logits hashes/tolerance, environment |
| `bench/` | harness source/commit, warm-up + ≥20-iteration median/p95, hardware/ROCm, baseline file, regression-gate rule |
| `telemetry/` | `--stats` / `--json` sample outputs, schema, variance rerun, prompt-leak check |
| `claims/` | `check_claims.py` default + `--strict`, empty baseline proof, canaries, ledger-vs-README diff |
| `cpu-lane.log` / `gpu-lane.log` | `pytest -m "not gpu" -q` / `pytest -m gpu -q` |
| `cpu-only.log` | `test_cpu_only.py` standard + `-O` |
| `notes.md` | design, provenance, measurements, limitations, acquisition commands |
| `qaqc-probes/` | independent QAQC probes/logs |

## Rules

- **No claim without an artifact.** 70B, 8-hour, throughput, Phi-3, Gemma, and
  chat claims stay absent or qualified unless the matching 7F evidence exists.
- **Exact token IDs.** Compare token IDs exactly; logits within a tolerance that
  is stated and justified. Do not call "close enough" a match.
- **Reproducible from a clean clone.** Record model hashes and acquisition
  commands; do not commit multi-GB weights.
- **Required GPU CI.** The GPU job counts only on the self-hosted gfx1150
  runner, with `continue-on-error` removed, and must block a red GPU suite.
- **Benchmark discipline.** Warm-up, `hipEvent`, ≥20 iterations, median/p95,
  hardware/ROCm recorded, checked-in baseline, regression ratio stated.
- **Prompt-safe telemetry.** No prompt text or token content in `--stats` /
  `--json` output; `perf_counter` timings documented.
- **Strict claims gate.** `--strict` is release-blocking, the baseline is empty,
  canaries are green, and the ledger/docs diff is part of the evidence.
- **Stop on missing prerequisites.** If the runner, real GGUF files, or the
  llama.cpp reference are unavailable, record `BLOCKED`; do not weaken G6.

## Gate exit (G6)

- Required real-runner GPU CI green; CPU/clean-clone green.
- Real-GGUF goldens pass (or the model family stays `NOT YET`).
- Benchmark baseline + regression gate exist; numbers reproducible.
- Telemetry works, is documented, and is prompt-safe.
- `check_claims.py --strict` release-blocking with an empty baseline; canaries
  green; no unqualified unsupported claim.
