# AUDIT 7F (G6) — Evidence & release gates

**Auditor:** DeepSeek V4.1 Flash (primary auditor)
**Date:** 2026-11-08
**Gate:** G6 (Phase 7F evidence & release)
**Target:** `wp/7F-evidence-release` @ `baa3e87` (work `a4887d4`; evidence `0554e07`; QAQC `baa3e87`; base `2d48efe`)
**Brief:** `PHASE7_7F_EVIDENCE_RELEASE_BRIEF.md`; **contract:** `audit/evidence/G6/7F/README.md`
**QAQC:** `audit/QAQC_7F_2026-11-08.md`

---

## 1. Verdict

**G6: NOT SIGNED — rework required.**

The 7F work is substantial and much of it is honest and well-evidenced:
the benchmark harness/baseline/gate (7F-3), prompt-safe telemetry (7F-4), and
the release-blocking strict claims gate (7F-5) all pass independent
reproduction. The coder also recorded the 7F-2 near-tie golden failure honestly
and did not weaken it.

However, five blockers remain:

1. **7F-1 is not done** — the self-hosted GPU runner is not registered and
   `ci-gpu.yml` still has `continue-on-error: true` (owner action).
2. **A real SentencePiece tokenizer regression** — real llama-family GGUFs that
   ship both `model="llama"` and a `merges` array are segmented with the BPE
   rank comparator instead of the SPM score comparator. The engine tokenizes
   the committed prompts differently from llama.cpp on the real TinyLlama
   vocabulary. This is a 7B/G2 regression and a release blocker.
3. **7F-2's acceptance criterion is not met** — exact token IDs do not match
   over 16 steps (14/16, 3/16, 4/16), and the pre-fork logits already violate
   the pre-registered 0.5 tolerance (one sample at 0.89). The near-tie
   explanation is plausible, but the gate as written is not satisfied; a
   pre-registered decisive-margin criterion (or a narrower release scope) is
   required.
4. **The branch CI is red** — the sdist-install lane fails on `baa3e87`
   because `tests/test_bench_gate.py` imports `scripts/bench/aggregate.py` and
   `MANIFEST.in` does not ship `scripts/`.
5. **The release-scope claim overstates the evidence** — README L132 says the
   release scope has "real-GGUF/hardware evidence", but the only real-GGUF
   runs are Q4_K_M/Q6_K and they do not pass an exact golden; the Q4_0/Q4_K/
   Q8_0 release-scope types have synthetic GGUFs only.

The QAQC report recommends accepting 7F-2 and holding G6 only on 7F-1. This
audit does not: the tokenizer regression and the sdist CI are coder-fixable
defects the QAQC missed, and 7F-2 is a recorded FAIL, not an acceptance.

---

## 2. Blockers

### BLOCKER-7F-1 (High, process) — required GPU CI not in place

`ci-gpu.yml` still carries `continue-on-error: true` at the job level, and no
self-hosted runner exists on the gfx1150 host (QAQC verified; the file is
unchanged). The local GPU lane is green (45 passed), but the gate requires the
job to be **required** and green on the real runner, with a demonstrated red
block. This is an owner/repo-admin action; the coder did the right thing by
not weakening or prematurely tightening it.

**Evidence:** `.github/workflows/ci-gpu.yml` lines 30–35;
`audit/evidence/G6/7F/gpu-runner.md`.

### BLOCKER-7F-2 (High, code/G2) — SPM tokenizer uses BPE ranks when a GGUF ships `merges`

`src/tokenizer.py::_greedy_merge_symbols` selects the comparator with

```python
use_ranks = bool(self.merge_ranks)
```

The real TinyLlama Q4_K_M/Q6_K GGUFs have `tokenizer.ggml.model = "llama"`
(SentencePiece), **and** a 61,249-entry `tokenizer.ggml.merges` array, **and**
`tokenizer.ggml.scores` present but all zero. The SPM path therefore uses the
BPE merge ranks. llama.cpp's `llm_tokenizer_spm_session` ignores `merges` for
SPM and, with all-zero scores, merges leftmost-first.

Auditor reproduction (real GGUF, committed prompts):

| surface | engine | llama.cpp |
|---|---|---|
| `jumps` | `▁j` (432) + `umps` (17204) | `▁jump` (12500) + `s` (29879) |
| `sources` | `▁sources` (8974) | `▁sou` (3669) + `rc` (2214) + `es` (267) |
| `quoting` | `▁qu` (439) + `oting` (11427) | `▁quot` (13911) + `ing` (292) |

All three committed prompts mismatch the reference tokenization. The 7F-2
golden runner feeds the **reference** prompt IDs to the engine by default, so
it isolated the model comparison and masked this defect. The real CLI path
(`engine.tokenizer.encode(prompt)`) was wrong on a real llama-family GGUF.

**Fix verified by the auditor:**

```python
use_ranks = bool(self.merge_ranks) and self._uses_gpt2
```

With that one-line change: `tests/test_goldens_tokenizer.py` **351 passed**,
the CPU lane **525 passed**, and the engine's prompt token IDs match the
reference exactly on Q4_K_M prompt1 (31/31), Q4_K_M prompt2 (35/35), and Q6_K
prompt1 (31/31). The end-to-end golden with `--engine-prompt-ids` then reports
`prompt_token_ids_match=true` and still forks at the step-14 near-tie.

**Evidence:** `audit/evidence/G6/7F/audit-probes/tokenizer-spm-merges.md` and
`golden-q4km-prompt1-engine-tokenizer-fixed.json`; `src/tokenizer.py` line 210.

**This reopens 7B for a narrow fix** (the SPM/BPE comparator selection only) —
not a general tokenizer rewrite. Add a regression fixture whose vocabulary has
`model="llama"`, zero scores, and a non-empty `merges` array.

### BLOCKER-7F-3 (High, gate/spec) — 7F-2 exact-token golden does not pass

The three real-GGUF comparisons match only 14/16, 3/16, and 4/16 greedy
steps. The forks occur at top-1 margins 0.031/0.156, 0.008/0.059, and
0.164/0.113, below the measured ~0.3–0.9 FP16-vs-F32 pre-fork noise. The
pre-fork logits also exceed the pre-registered `LOGITS_MAX_ABS_DIFF = 0.5`
(one sample 0.89). The coder recorded this as a FAIL and did not widen the
tolerance, which is correct.

**Auditor adjudication:** the exact 16-step token criterion is not achievable
between the FP16 engine and llama.cpp's CPU path at near-tie steps. The gate
may be amended, but only with a **pre-registered** criterion, and the strict
16-step result must remain recorded as a FAIL:

- Compare greedy token IDs exactly for every step whose **top-1 margin on both
  sides is ≥ 1.0 logit** (above the observed 0.9 noise); stop at the first
  step below the threshold and report it as the decisive-margin fork.
- Keep the logits check as a diagnostic with an explicit, pre-registered bound
  (do not silently widen 0.5); if the bound is changed, record the amendment
  and justify it from the measured matching-state noise.
- Re-run all three goldens with `--engine-prompt-ids` **after** the tokenizer
  fix, and record both the strict result and the decisive-margin result.

If this amendment is not accepted, 7F-2 stays **BLOCKED** and the release
cannot claim real-GGUF support for the affected types.

**Evidence:** `audit/evidence/G6/7F/golden/README.md` and
`verdict-*.json`; `audit/QAQC_7F_2026-11-08.md` `QAQC-7F-2`.

### BLOCKER-7F-4 (High, CI/packaging) — sdist lane red

`wp/7F-evidence-release` @ `baa3e87` has CPU-Only Verification & Regression CI
run `42549525288` **failure**: job `128941746885` (Sdist Install), step
**"Run the shipped CPU lane in the extracted sdist tree"**.

`tests/test_bench_gate.py` (CPU lane) imports
`scripts/bench/aggregate.py`; `MANIFEST.in` ships `tests/*.py`,
`tests/fixtures/*`, `src/kernels`, `src/python_bindings`, but **not
`scripts/`**. Reproduced locally:

```
ERROR collecting tests/test_bench_gate.py
ModuleNotFoundError: No module named 'aggregate'
```

**Fix verified by the auditor:** add

```
recursive-include scripts/bench *.py *.json
```

to `MANIFEST.in`; rebuild the sdist and run the exact lane →
**521 passed, 49 deselected**.

**Evidence:** `audit/evidence/G6/7F/audit-probes/sdist-packaging.md`; CI run
`42549525288`.

### BLOCKER-7F-5 (Medium/High, claims) — release-scope wording overstates the evidence

README L132 says:

> **Verified release scope:** text-only **llama-family `Q4_0` / `Q4_K` /
> `Q8_0`** GGUFs (real-GGUF/hardware evidence).

The only real-GGUF runs in the bundle are Q4_K_M/Q6_K (TinyLlama), and they do
not pass the exact golden. Q4_0/Q4_K/Q8_0 have synthetic GGUFs on the hardware
lanes only. The same README's compatibility matrix (L148) correctly says
"synthetic GGUFs". The parenthetical "(real-GGUF/hardware evidence)" must be
narrowed, and the release-scope claim should be inventoried in
`audit/CLAIMS_LEDGER.md` so the strict gate covers it (it currently does not).

**Required wording direction:** separate "synthetic-GGUF hardware-verified
kernels" from "real-GGUF exact goldens not yet achieved"; do not imply a
real-GGUF waterfall for Q4_0/Q4_K/Q8_0.

---

## 3. What passed (independent reproduction)

| Check | Result |
|---|---|
| CPU lane | **525 passed / 45 deselected** |
| GPU lane (local gfx1150) | **45 passed / 525 deselected** |
| `test_cpu_only.py` / `-O` | **OK / OK** |
| Claims default | **PASS**, 0 baselined |
| Claims `--strict` | **PASS**, 0 unqualified; baseline **0 bytes** |
| Canaries | **16/16** |
| Benchmark gate | `regress.py` PASS vs the checked-in baseline; 20 iterations, 15% ratio, like-for-like schema/GPU/model checks |
| Benchmark evidence | synthetic 29,808 prefill / 1,050 decode tok/s; real Mistral-7B Q4_K_M 18.63→17.01 prefill, 2.67→2.70 decode across reruns (inside 15%); page-cache-warm state recorded honestly |
| Telemetry | `gfx1150-stats/1` schema; counters-only payload; QAQC marker absent from payload and stderr; variance recorded |
| Golden artifacts | pinned llama.cpp `7d7f0287`, model hashes, token files, verdicts, logits hashes committed; strict FAIL recorded honestly |
| Scope | 7F diff limited to allowed paths; no kernel math/tokenizer/model/7D changes (the tokenizer defect is pre-existing, not introduced by 7F) |
| Clean-clone CI | run `42549525230` **success** |
| CPU parser/strict-gate job | run `42549525288` job `128941746615` **success** |

---

## 4. Non-blocking notes

- **7E trace latch is process-global** (`GFX1150_STREAM_TRACE` read once);
  telemetry per-kernel ms requires the env var before the first layer forward.
  Documented; fixing it would touch `src/kernels/**` and is out of 7F scope.
- **Real 7B benchmark is not gated** — only the synthetic baseline is checked
  in; the 7B lane is recorded evidence. `regress.py`'s docstring references a
  nonexistent `audit/evidence/G6/7F/bench/baseline-7b.json`; fix the docstring
  or add the baseline.
- **Stale prose counts:** `audit/evidence/G6/7F/notes.md` says "39 passed /
  532-test CPU lane / 41-test GPU lane"; the current logs are **45 / 525**.
- **Ledger typo:** row 5 says "ran a real a real-GGUF Q6_K file".
- **Golden tolerance:** `LOGITS_MAX_ABS_DIFF = 0.5` is violated by one
  matching-state sample (0.89). Keep the failure recorded; if the criterion is
  amended, do it explicitly (see BLOCKER-7F-3).

---

## 5. Gate impact

- **G6:** **NOT SIGNED.** 7F stays in rework; do not merge
  `wp/7F-evidence-release`.
- **7F-1:** owner action; G6 cannot close until the runner is registered, the
  job is required, and a red-suite block is demonstrated.
- **7B:** reopened narrowly for the SPM/BPE comparator fix
  (BLOCKER-7F-2). Do not reopen the rest of 7B.
- **Release:** no real-GGUF exact-token, 70B, 8-hour, or throughput claim is
  added; the release-scope wording must be narrowed (BLOCKER-7F-5).
- **CI:** must be green on the rework tip, including the sdist lane.

---

## 6. Sign-off

**7F decision: NOT SIGNED — rework required.** The benchmark, telemetry, and
claims-gate work is accepted as evidenced. The tokenizer regression, the 7F-2
gate/spec gap, the sdist packaging failure, the release-scope wording, and the
owner-blocked GPU runner prevent G6 closure.

**Signed:** DeepSeek V4.1 Flash, primary auditor — 2026-11-08.
