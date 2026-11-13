# 7F-3 — benchmark harness, baselines, regression gate (G6 evidence)

## Harness

* `scripts/bench/run.py` — single file; `--model synthetic` (deterministic
  Q4_K_M 2-layer fixture, needs no weights) or `--model /real.gguf`.
  Workload fixed: `BENCH_PROMPT` (or `SYNTHETIC_PROMPT_IDS`), `temperature=0`,
  `seed`, `stop_on_eos=False`, `max-new-tokens 16`; ≥20 measured
  iterations after 2 warm-ups (default 20; the harness refuses fewer).
  Timing: `perf_counter` for E2E + the 7E hipEvent trace
  (`GFX1150_STREAM_TRACE=1`, parsed from the engine's own stderr via the
  7F-4 `_StderrTap`) for per-projection kernel windows — the same hipEvent
  source the telemetry uses (consistency requirement, brief 7F-4).
* `scripts/bench/aggregate.py` — pure aggregation + the gate rules
  (CPU-importable; unit-tested in `tests/test_bench_gate.py`).
* `scripts/bench/regress.py` — the release gate CLI.
* `scripts/bench/baseline-synthetic.json` — **checked-in baseline**
  (synthetic lane, gfx1150 host, 2026-11-08).

## Regression gate rule (agreed ratio, stated)

`check_regression()` fails when, on the **same GPU, same model sha256,
same workload label**, with ≥20 measured iterations in both files:

* the median of `prefill_tok_per_s` / `decode_tok_per_s` /
  `total_tok_per_s` in the result is below `0.85×` the baseline
  (i.e. a regression larger than **15%**), or
* a per-projection kernel-time median exceeds `1.15×` the baseline.

**Why 15%:** measured cross-run variance of the medians on this host is
≤9% (7B prefill, run1 vs run2) and ≤4% (synthetic lane) — driven by
page-cache residency, GTT pressure and APU thermal/power limits — while
a real regression (added sync, broken kernel path, eviction bug) moves
medians by multiples of that. 15% tolerates host noise and nothing bigger
(`bench/mistral-7b-run2-rerun.json` is the measured proof the gate passes
on an unchanged codebase).

## Real-model lane (7B-class, this host)

Baseline artifacts (not checked into `scripts/bench/` because the model
is external; the payloads record its sha256):

* `mistral-7b-run1.json` — Mistral-7B-Instruct-v0.2 Q4_K_M,
  sha256 `3e0039fd0273fcbebb49228943b17831aadd55cbcbf56f0af00499be2040ccf9`,
  acquisition: `wget https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/resolve/main/mistral-7b-instruct-v0.2.Q4_K_M.gguf`
* `mistral-7b-run2-rerun.json` — same lane, second run (variance probe).

Medians (20 iterations): prefill 18.63 tok/s, decode 2.67 tok/s. These are
single-host numbers for the exact recorded GPU/ROCm state; no 70B
extrapolation, no 780M port numbers (none measured — Phase 8 is
stretch-scope). The 7B lane numbers are recorded per the brief
("Measure the real paths the docs describe (7B-class on this host)").

Reproduce:

```bash
python scripts/bench/run.py --model synthetic --json > mine.json
python scripts/bench/regress.py scripts/bench/baseline-synthetic.json mine.json
# exit 0 = PASS, 1 = REGRESSION, 2 = comparison error
python scripts/bench/run.py --model /path/mistral-7b-instruct-v0.2.Q4_K_M.gguf --json > real.json
```
