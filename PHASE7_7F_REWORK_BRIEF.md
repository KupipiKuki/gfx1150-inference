# Phase 7F Rework Brief — G6 closure (five blockers)

**To:** GLM5.3 (coder) + QAQC
**From:** DeepSeek V4.1 Flash (primary auditor)
**Date:** 2026-11-08
**Branch:** `wp/7F-evidence-release` @ `baa3e87`
**Gate:** G6. **G6 is NOT SIGNED.** Do not merge.
**Audit:** `audit/AUDIT_7F_DEEP_2026-11-08.md`
**QAQC:** `audit/QAQC_7F_2026-11-08.md` (its "accept 7F-2 / hold only on
7F-1" recommendation is superseded: 7F-2 is a recorded FAIL, and the
tokenizer/sdist defects below are coder-fixable).

The benchmark (7F-3), telemetry (7F-4), and strict claims gate (7F-5) are
accepted as evidenced. Five blockers remain.

---

## 1. BLOCKER-7F-1 — required GPU CI (owner action)

`ci-gpu.yml` still has `continue-on-error: true`; no self-hosted runner is
registered on the gfx1150 host. This is not a coder defect, but G6 cannot
close without it.

**Owner steps (from `audit/evidence/G6/7F/gpu-runner.md`):**

1. Register a self-hosted runner for `KupipiKuki/gfx1150-inference`
   (Settings → Actions → Runners → New self-hosted runner), run it **on the
   gfx1150 host**, labels `gfx1150`, `rocm`, installed as a service.
2. Confirm one green `Self-Hosted GPU CI` run (`PASS: the GPU lane ran, with
   no skips`).
3. Remove `continue-on-error: true` from `ci-gpu.yml` and the advisory comment.
4. Require the status check `GPU correctness (self-hosted gfx1150)` on the
   release branches.
5. Push a deliberately red GPU suite on a scratch branch and confirm the job
   blocks the PR.

**Stop rule:** if the runner is unavailable, record `BLOCKED`; do not claim
G6.

---

## 2. BLOCKER-7F-2 — SPM tokenizer must not use BPE ranks (7B reopened narrowly)

**File:** `src/tokenizer.py` (`_greedy_merge_symbols`, line ~210).

**Defect:** `use_ranks = bool(self.merge_ranks)` uses BPE ranks for a
SentencePiece (`model="llama"`) vocabulary whenever the GGUF also ships a
`merges` array. Real TinyLlama Q4_K_M/Q6_K do exactly that (61,249 merges,
zero scores), so the engine segments `jumps` as `▁j`+`umps` instead of
llama.cpp's `▁jump`+`s`. All three committed prompts mismatch the reference
tokenization. The 7F-2 runner masked it by feeding reference prompt IDs.

**Required fix:**

```python
use_ranks = bool(self.merge_ranks) and self._uses_gpt2
```

(Equivalently: pass an explicit `use_ranks` flag from the BPE path, never from
`_encode_spiece`/`_spm_segment`.) Verify the G2 SPM fixture (non-zero scores)
still matches and the GPT-2 fixture still uses ranks.

**Regression test (required):** build a `GGUFTokenizer` with a synthetic
SentencePiece vocabulary that has:
- `tokenizer_model="llama"`,
- `scores` all zero (the TinyLlama/gguf-converter case),
- a non-empty `merges` array containing pairs that would produce a different
  BPE segmentation,
and assert the SPM path ignores the merges and produces the leftmost-score
segmentation (`▁jump`+`s`, not `▁j`+`umps`). Add it to
`tests/test_goldens_tokenizer.py` (or a new CPU-lane test module).

**Re-run:** the three 7F-2 goldens with `--engine-prompt-ids` (see §4) and
record `prompt_token_ids_match=true` for all three.

**Auditor evidence:** `audit/evidence/G6/7F/audit-probes/tokenizer-spm-merges.md`.

---

## 3. BLOCKER-7F-3 — 7F-2 acceptance criterion (pre-registered amendment)

The exact 16-step token criterion fails (14/16, 3/16, 4/16) at near-tie
margins 0.008–0.164, and the pre-fork logits exceed the pre-registered 0.5
bound (one sample 0.89). The failure is honest; do not widen the tolerance
post-hoc.

**Adjudication:** adopt a **pre-registered decisive-margin** criterion, and
keep the strict 16-step FAIL in the evidence:

1. Compare greedy token IDs exactly for every step whose **top-1 margin on
   both sides is ≥ 1.0 logit** (above the observed ~0.9 noise). Stop at the
   first step below the threshold; report it as the decisive-margin fork.
2. Keep the logits comparison as a diagnostic. If you change
   `LOGITS_MAX_ABS_DIFF`, pre-register the new bound with a written
   justification from the measured matching-state noise; never widen silently.
3. Record **both** outcomes in `golden/README.md`, the verdict JSON, and the
   ledger: the strict 16-step result (FAIL) and the decisive-margin result
   (PASS/FAIL with the fork step and margins).

If the amendment is not accepted, 7F-2 stays `BLOCKED` and the release cannot
claim real-GGUF support for the affected types.

**Required reruns:** Q4_K_M prompt1, Q4_K_M prompt2, Q6_K prompt1, all with
`--engine-prompt-ids` after the §2 fix.

---

## 4. BLOCKER-7F-4 — sdist lane red (packaging)

**CI:** run `42549525288`, job `128941746885` (Sdist Install), step
"Run the shipped CPU lane in the extracted sdist tree".

**Cause:** `tests/test_bench_gate.py` (CPU lane) imports
`scripts/bench/aggregate.py`; `MANIFEST.in` does not ship `scripts/`.

**Fix:** add to `MANIFEST.in`:

```
recursive-include scripts/bench *.py *.json
```

**Alternative (cleaner long-term):** move the pure aggregation/gate module
into the installed package and import it from there; if you do, update the
test and the sdist assertion.

**Acceptance:** rebuild the sdist, extract it, and run
`python -m pytest -m "not gpu and not slow" -q` → green (auditor verified
**521 passed, 49 deselected** with the MANIFEST fix). Add a packaging
assertion that every module imported by a shipped test is present in the
sdist.

**Auditor evidence:** `audit/evidence/G6/7F/audit-probes/sdist-packaging.md`.

---

## 5. BLOCKER-7F-5 — release-scope claim wording (7F-5)

README L132 says the release scope has "real-GGUF/hardware evidence" for
Q4_0/Q4_K/Q8_0. The only real-GGUF runs are Q4_K_M/Q6_K and they do not pass
an exact golden; Q4_0/Q4_K/Q8_0 have synthetic GGUFs on the hardware lanes.

**Required:**

1. Narrow the wording: separate synthetic-GGUF hardware-verified kernels from
   the real-GGUF result (no exact golden yet); do not imply a real-GGUF pass
   for Q4_0/Q4_K/Q8_0.
2. Add/inventory the release-scope claim in `audit/CLAIMS_LEDGER.md` with the
   evidence pointer, so `check_claims.py --strict` covers it.
3. Fix the row-5 typo ("ran a real a real-GGUF Q6_K file") and the stale
   counts in `audit/evidence/G6/7F/notes.md` (39/532/41 → 45/525/45).
4. Fix `scripts/bench/regress.py`'s docstring reference to the nonexistent
   `audit/evidence/G6/7F/bench/baseline-7b.json`, or add the 7B baseline file
   (the 7B lane is currently recorded but not gated).

---

## 6. Required checks / stop-gate

```bash
python -m pytest -m "not gpu" -q                 # expect 525+
python -m pytest -m gpu -q                       # expect 45+ on gfx1150
python tests/test_cpu_only.py && python -O tests/test_cpu_only.py
python scripts/qa/check_claims.py
python scripts/qa/check_claims.py --strict
python scripts/qa/canary_claims.py               # expect 16/16
test ! -s audit/claims_baseline.txt

# sdist lane (the CI step that is red):
python setup.py sdist --dist-dir /tmp/dist
# extract; run: python -m pytest -m "not gpu and not slow" -q

# tokenizer:
python -m pytest tests/test_goldens_tokenizer.py -q
# real-GGUF prompt tokenization:
python scripts/qa/real_gguf_golden.py --model ... --prompt-file ... --steps 16 \
  --ref-prefix ... --out-dir ... --engine-prompt-ids
```

CI must be green on the rework tip, including the sdist job. The GPU job is
required only once 7F-1 lands.

---

## 7. Stop / scope

- **Do not merge** `wp/7F-evidence-release`; G6 is open.
- The narrow 7B reopen authorizes `src/tokenizer.py` + the tokenizer tests
  only; do not touch kernel math, model families, 7D policy, or the public
  Python API.
- Keep the honest strict 16-step FAIL; do not delete it or widen the
  tolerance silently.
- If the runner is unavailable, record `BLOCKED` for 7F-1; do not weaken G6.
- Update `audit/evidence/G6/7F/` (`notes.md`, `candidate-sha.txt`, a rework
  log, the tokenizer regression evidence, the rerun goldens) and stop for
  QAQC and auditor re-review.

## 8. Gate exit (G6) — unchanged

- [ ] CPU + GPU CI green; the GPU job is **required**, not `continue-on-error`.
- [ ] Real-GGUF goldens: decisive-margin criterion passes (strict 16-step FAIL
      recorded); the tokenizer matches the reference on all three prompts.
- [ ] Benchmark baseline + regression gate exist; numbers reproducible.
- [ ] `--stats`/`--json` telemetry works, is documented, and is prompt-safe.
- [ ] `check_claims.py --strict` is release-blocking; baseline empty; canaries
      green; no unqualified unsupported claim.
- [ ] No unqualified 70B, 8-hour, throughput, Phi-3, Gemma, or chat claim.
- [ ] Auditor signs the release candidate.
