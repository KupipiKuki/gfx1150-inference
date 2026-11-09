# G6 / 7F — evidence & release bundle: notes, provenance, findings

Branch `wp/7F-evidence-release`, base `vibe/phase7-220201` at `2d48efe`
(authorization commit; work-package brief at document top). Coder: Mistral
Vibe, acting as the 7F coder per `PHASE7_7F_EVIDENCE_RELEASE_BRIEF.md`.
This file is the coder's report; the auditor's signoff is **not** part of
this file (see the contract README).

## Header status

**7F-1 is BLOCKED (owner action).** No self-hosted runner is registered;
`ci-gpu.yml` keeps `continue-on-error` per the brief's own fallback
("If the runner is unavailable: stop and record the blocker; do not claim
G6"). Owner steps + ready-to-apply diff: `gpu-runner.md`. Everything else
(7F-2 .. 7F-5) shipped with evidence below — but per the brief, **G6
cannot be claimed until 7F-1 lands**, so this is a *candidate* bundle for
the auditor, with the explicit blocker recorded.

## What was delivered

| Package | Result | Evidence |
|---|---|---|
| 7F-1 required GPU CI | **BLOCKED** (runner not registered; no branch-protection rights) | `gpu-runner.md` |
| 7F-2 real-GGUF goldens | **NOT PASSED** (honest record: exact until near-tie forks; tokenizer divergence flagged). Not weakened; no claim promoted | `golden/` |
| 7F-3 benchmark harness + baseline + gate | **DONE**: `scripts/bench/`, ≥20-iteration medians/p95, checked-in synthetic baseline, 15%-ratio regression gate, real 7B lane recorded | `bench/` |
| 7F-4 `--stats`/`--json` telemetry | **DONE**: prompt-safe `gfx1150-stats/1`, documented schema, hipEvent per-projection ms, variance + leak checks | `telemetry/`, `tests/test_telemetry*.py` |
| 7F-5 release-blocking claims gate | **DONE**: baseline **empty (0 bytes)**, `--strict` blocking in CI, non-empty baseline itself fails strict, 16 green canaries (4 new), ledger/docs diff recorded | `claims/`, `audit/claims_baseline.txt`, `.github/workflows/ci-cpu.yml` |

## Measured results (7F-3), gfx1150 host (Ryzen AI 9 HX 370 / Radeon 890M,
AMDGPU ROCm (HIP 7.16.26385-0000000), kernel 7.0.0-42, Python 3.14.10,
NumPy 2.5.4)

* **Synthetic lane** (deterministic 2-layer Q4_K_M fixture, 64-token
  prefill + 16 decode tokens, 20 measured iterations after 2 warm-ups;
  `scripts/bench/baseline-synthetic.json`):
  prefill median **29,808 tok/s** (p95 32,540), decode median **1,050
  tok/s** (p95 1,066), per-projection kernel medians 0.009–0.013 ms.
  Run-to-run medians (run1 vs run2): ≤4% (decode −2.1%, gate kernel
  +1.8%, q kernel +3.8%).
* **Real 7B lane** (Mistral-7B-Instruct-v0.2 Q4_K_M, sha256
  `3e0039fd…ccf9`, 72-token prefill + 16 decode, 20+2 iterations): prefill
  median **18.63 tok/s** (p95 18.74), decode median **2.67 tok/s** (p95
  2.68); per-projection kernel medians: down 0.86 ms, gate 1.07 ms, up
  1.04 ms, q 0.32 ms, o 0.28 ms, k 0.16 ms, v 0.08 ms. Disk reads 0 and
  0 major faults during iterations (model residency auto→pin: but note
  `io.disk_read_bytes_delta` is measured per iteration after warm-up, so
  the page-cache-warm state is what is measured — recorded, not assumed).
  Rerun (`bench/mistral-7b-run2-rerun.json`): decode +1.2%, prefill −8.7%,
  kernels within ±8% — all inside the 15% gate ratio.
* These numbers are the honest record for the docs' "performance targets":
  the historical figures (983.4 tok/s, 1.12 TFLOPS, 0.50/2.76 ms) are now
  qualified UNVERIFIED in place, and the plan points at this evidence.
  No throughput claim was added to the public docs.

## 7F-2 goldens: outcome, tolerance, and honesty

Three comparisons (details in `golden/README.md`): engine vs pinned
llama.cpp `7d7f0287`, TinyLlama-1.1B-Chat Q4_K_M (two prompts) and Q6_K
(one prompt). Result identical in shape: greedy token chains match
**exactly** for many steps, then fork at a step whose top-1 margin
(0.008–0.164 in ours / 0.06–0.16 in the reference) is *below* the
cross-implementation FP16-vs-F32 noise measured on the matching steps
(0.3–0.9 logits). After the fork the logits live on different states and
differ by 10–30 (meaningless).

The acceptance criterion was "token IDs match exactly". **They do not
match exactly over 16 steps.** The golden FAILs and the consequences are
applied: no real-Q4_K_M/Q6_K claim promoted (claim 6 stays PARTIAL with
the newly-qualified README wording; claim 5 keeps its G0 synthetic
VERIFIED scope), and the README release-scope paragraph states the
measured outcome. The tolerance statement
(`LOGITS_MAX_ABS_DIFF = 0.5`) is the pre-registered bound on the
matching-state noise; one matching step (q4km-prompt1 step 1) already
exceeds it (0.89), which is recorded as a tolerance failure in the
verdicts rather than quietly widened.

## Findings flagged for the auditor (not fixed in 7F)

1. **Tokenizer divergence on a real SentencePiece vocab (7B/G2 scope).**
   `tokenizer.encode()` of the plain-text prompts does not match llama.cpp
   on the real TinyLlama vocab ("jumps" → 432,17204 vs llama.cpp
   12500,29879; one such divergence per prompt). G2's own corpus passed;
   the golden runner feeds the reference tokenization to both sides so
   states match, and records the divergence. Re-opening 7B requires a
   written auditor finding, per the brief.
2. **Near-tie fork sensitivity** (see above): an exact-token golden
   between two real implementations with different numeric precision can
   only be defined over decisive-margin steps. Spec decision deferred to
   the auditor; recorded in `golden/README.md`.
3. **7E trace latch is process-global**
   (`layer_trace_enabled()` reads `GFX1150_STREAM_TRACE` once per process).
   Telemetry per-kernel ms therefore requires the env var to be set before
   the process's first layer forward — always true for the CLI
   (fresh process) and asserted by running the GPU telemetry test in a
   subprocess (`tests/test_telemetry_gpu.py`). Changing the latch would
   touch `src/kernels/**` (not in 7F's allowed files).

## Non-goals honored

No kernel math, tokenizer, model-family, or 7D-policy code was touched.
`src/inference.py` carries telemetry plumbing only (`--stats`/`--json`,
`perf_counter` counters, stderr tap, sysfs/GTT sampler; generation
behavior unchanged — `generate_ids`/`generate` untouched, verified by the
525-test CPU lane and 45-test GPU lane green).

## Reproducing from a clean clone

```bash
git clone <repo> && cd gfx1150-inference
cmake -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build -j
python3 -m pytest -m "not gpu" -q
python3 -m pytest -m gpu -q                       # on the gfx1150 host
python3 scripts/qa/check_claims.py --strict        # needs the empty baseline
test ! -s audit/claims_baseline.txt
python3 scripts/qa/canary_claims.py
python3 scripts/bench/run.py --model synthetic --json > mine.json
python3 scripts/bench/regress.py scripts/bench/baseline-synthetic.json mine.json
```

The clean-clone re-verification (fresh tree, fresh build, both lanes +
goldens + bench) is in `clean-clone/`. Real GGUFs are not committed; see
`golden/README.md` for hashes and acquisition commands.

## Rework log (2026-11-08, PHASE7_7F_REWORK_BRIEF.md — five blockers)

| Blocker | Disposition |
|---|---|
| 7F-1 required GPU CI | **still BLOCKED** (owner action; `gpu-runner.md` unchanged) |
| 7F-2 SPM tokenizer uses BPE ranks | **FIXED** — `src/tokenizer.py`: `use_ranks = bool(self.merge_ranks) and self._uses_gpt2`. Regression tests: `test_spm_vocab_with_merges_array_ignores_bpe_ranks` + the GPT-2-ranks guard (`tests/test_goldens_tokenizer.py`, 353 passed). Engine tokenization now reference-exact on all three real prompts (31/31, 35/35, 31/31 — `rework-tokenizer-evidence.txt`) |
| 7F-3 golden acceptance criterion | **adjudicated as pre-registered** — `scripts/qa/real_gguf_golden.py` now records `strict_16_step` (kept FAIL) + `decisive_margin` (threshold 1.0 both sides, stop at first indecisive step, INCONCLUSIVE when 0 compared). Reruns with `--engine-prompt-ids`: Q6_K **PASS** (2 decisive steps exact), both Q4_K_M prompts **INCONCLUSIVE** (step 0 already near-tied). Logits are diagnostics; bounds unchanged |
| 7F-4 sdist lane red | **FIXED** — `MANIFEST.in` ships `scripts/bench *.py *.json`; locally rebuilt sdist: extracted-tree lane **523 passed, 49 deselected**; new CI assertion checks every local module a shipped test imports |
| 7F-5 release-scope wording | **FIXED** — README L132 narrowed (synthetic-hardware kernel verification for Q4_0/Q4_K/Q8_0, explicit "no real-GGUF golden"; real-GGUF result stated with the measured outcomes); ledger row 31 inventories the claim (`Verified release scope` literal, qualified in place); row 5 typo fixed; stale lane counts fixed (45 GPU / 525 CPU); `regress.py` docstring now matches the checked-in `scripts/bench/baseline-7b.json` (7B lane is now gateable; rerun PASSes it) |

Rerun battery at the rework tip: CPU lane 527 passed / GPU lane 45 passed /
cpu_only OK (both modes) / strict claims PASS (baseline still 0 bytes) /
canaries 16/16 / bench synthetic gate PASS / bench 7B gate PASS
(`rework-run.log`, `clean-clone/` re-verified).
