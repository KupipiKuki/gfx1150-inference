# AUDIT 7F REWORK (G6) — blockers 7F-2..7F-5 closed; 7F-1 remains

**Auditor:** DeepSeek V4.1 Flash (primary auditor)
**Date:** 2026-11-09
**Gate:** G6 (Phase 7F evidence & release)
**Target:** `wp/7F-evidence-release` @ `d5f2947` (rework work `b3920d2`; QAQC `d909a64`; audit base `a48d6f1`; original base `2d48efe`)
**Prior audit:** `audit/AUDIT_7F_DEEP_2026-11-08.md` (five blockers)
**Rework brief:** `PHASE7_7F_REWORK_BRIEF.md`
**QAQC:** `audit/QAQC_7F_REWORK_2026-11-10.md`

---

## 1. Verdict

**G6: NOT SIGNED — only BLOCKER-7F-1 remains.**

The coder's rework closes blockers 7F-2, 7F-3, 7F-4, and 7F-5. Each was
independently reproduced by this audit. The only remaining gate blocker is
**7F-1**: the self-hosted GPU runner is not registered and
`ci-gpu.yml` still carries `continue-on-error: true`. That is an owner action;
G6 cannot be signed until it lands and is red-teamed.

| Blocker | Status |
|---|---|
| 7F-1 required GPU CI | **OPEN** (owner action) |
| 7F-2 SPM tokenizer used BPE ranks | **CLOSED** |
| 7F-3 7F-2 golden acceptance criterion | **CLOSED** (pre-registered decisive-margin amendment accepted) |
| 7F-4 sdist lane red | **CLOSED** |
| 7F-5 release-scope wording | **CLOSED** |

---

## 2. Independent verification (2026-11-09)

| Check | Result |
|---|---|
| CPU lane | **527 passed / 45 deselected** |
| GPU lane (local gfx1150) | **45 passed / 527 deselected** |
| `tests/test_goldens_tokenizer.py` | **353 passed** |
| `test_cpu_only.py` / `-O` | **OK / OK** |
| Claims default / `--strict` | **PASS / PASS** (0 baselined, 0 unqualified) |
| Canaries | **16/16** |
| `audit/claims_baseline.txt` | **0 bytes** |
| sdist → extract → `pytest -m "not gpu and not slow"` | **523 passed / 49 deselected**; the archive contains `scripts/bench/{aggregate,regress,run}.py` + both baselines |
| CI at `d5f2947` | CPU-Only **success** (`42557609184`, incl. the previously red sdist job) and Clean-Clone **success** (`42557609198`) |
| Bench regression | synthetic baseline PASS; 7B baseline PASS against the committed rerun |

### 7F-2 — tokenizer fix (CLOSED)

`src/tokenizer.py` now has `use_ranks = bool(self.merge_ranks) and self._uses_gpt2`.
On the real TinyLlama Q4_K_M/Q6_K files (sha256-verified), the SPM path ignores
the 61,249-entry `merges` array and matches llama.cpp exactly on all three
committed prompts: **31/31, 35/35, 31/31** token IDs. The new regression tests
fail against the pre-fix file and pass at the tip. The narrow 7B reopen was
honored (only `src/tokenizer.py` + the tokenizer tests changed).

### 7F-3 — decisive-margin amendment (CLOSED)

`scripts/qa/real_gguf_golden.py` implements the pre-registered rule:
`DECISIVE_MARGIN_THRESHOLD = 1.0`, top-1 margin ≥ 1.0 on **both** sides, walk
stops at the first indecisive step, 0 compared → `INCONCLUSIVE` (never pass),
strict 16-step result recorded separately, logits/probs unchanged as
diagnostics. Auditor re-run with `--engine-prompt-ids`:

| Run | Strict 16-step | Decisive-margin |
|---|---|---|
| Q4_K_M prompt1 | FAIL, fork step 14 | INCONCLUSIVE (step 0: 1.086/0.950; 0 compared) |
| Q4_K_M prompt2 | FAIL, fork step 3 | INCONCLUSIVE (step 0: 0.781/0.749; 0 compared) |
| Q6_K prompt1 | FAIL, fork step 4 | **PASS** (steps 0–1 decisive, token-exact; stops at step 2) |

My verdicts match the committed `verdict-rework-*.json`. The strict FAIL is
retained; no exact 16-step claim is made.

### 7F-4 — sdist packaging (CLOSED)

`MANIFEST.in` ships `scripts/bench` and the CI job now asserts the four
required files are in the archive. Local sdist lane **523/49**; CI sdist job
**success** at `d5f2947`.

### 7F-5 — release-scope wording (CLOSED)

README L132 now separates **synthetic-hardware-verified** kernel paths
(`Q4_0`/`Q4_K`/`Q8_0`) from the real-GGUF result, states that no real
Q4_0/Q4_K/Q8_0 file has been compared, records the tokenizer-exact real runs,
the strict FAIL, and the decisive-margin outcome (Q6_K PASS; Q4_K_M
INCONCLUSIVE), and makes **no exact real-GGUF golden claim**. Ledger row 31
inventories the `Verified release scope` literal. Auditor mutation probe:
appending an unqualified `Verified release scope` line to README makes
`--strict` exit 1 with claim 31; the clean tree exits 0.

---

## 3. Adjudication: Q4_K_M INCONCLUSIVE

The amended criterion leaves both Q4_K_M prompts **INCONCLUSIVE** because the
first step is already below the 1.0 decisive-margin threshold. I accept this
for G6, for these reasons:

- the release scope is narrowed to **synthetic-hardware** verification and
  explicitly disclaims a real-GGUF golden; no Q4_K_M claim is promoted
  (row 6 stays PARTIAL, qualified in place);
- Q6_K provides a decisive-margin **PASS** (2 steps) and the strict Q4_K_M p1
  chain matches 14/16 tokens before a near-tie fork (margins 0.031/0.156),
  which is consistent with a correct model path plus FP16-vs-F32 noise;
- the strict FAIL is recorded verbatim; the tolerance was not widened; the
  amendment was pre-registered before the rerun.

**Quality note (not a G6 blocker):** a 2-step decisive pass is thin. A future
work package (7G or a 7F-6 evidence extension) should add prompts whose first
steps are decisive, or require a minimum number of decisive steps, so the
real-GGUF evidence is stronger.

---

## 4. Non-blocking findings

- **QAQC-7F-R1 / AUD-7F-R6 (low):** in default mode (without
  `--engine-prompt-ids`), `prompt_tokenization_engine_matches_reference` is
  computed from the *fed* IDs and is trivially true; `prompt_ids_engine` is
  still recorded. Key it off `prompt_ids_engine` so a future tokenizer
  regression cannot be masked in default mode. All rework goldens used engine
  mode, so the gate evidence is valid.
- **AUD-7F-R7 (low):** `strict_16_step.result` is token-only; if a future run
  matched tokens but failed the original logits/probs bounds, it would report
  PASS. Include the logits/probs gates in the strict result (or rename the
  field) so "strict" means the original criterion.
- **AUD-7F-R8 (cosmetic):** `audit/evidence/G6/7F/notes.md` still has the
  pre-rework header ("7F-2 NOT PASSED") and stale counts (39 GPU / 525 CPU;
  actual 45 / 527); `qaqc-probes/README.md` also has stale counts. The
  rework golden README is correct. Clean up before signoff.
- **AUD-7F-R9 (cosmetic):** the QAQC rework report is dated 2026-11-10 (one
  day after this audit); likely a date typo.
- **AUD-7F-R10 (note):** the GPT-2 guard test asserts the `_uses_gpt2` flag and
  rank presence rather than an end-to-end tokenization difference; the
  existing GPT-2 goldens pin the behavior, so this is acceptable but weak.
- **AUD-7F-R11 (note):** the 7E trace latch remains process-global; unchanged,
  documented, out of 7F scope.

---

## 5. Gate impact

- **G6:** **NOT SIGNED.** 7F-2..7F-5 are closed; **7F-1 is the sole gate
  blocker**. Do not merge `wp/7F-evidence-release` until 7F-1 lands.
- **7F-1:** owner/repo-admin action — register the self-hosted `gfx1150,rocm`
  runner, remove `continue-on-error`, require the `GPU correctness
  (self-hosted gfx1150)` check, and demonstrate a red-suite block.
- **Release:** the scope is synthetic-hardware verified; no real-GGUF exact
  golden, no 70B/8-hour/throughput claim. Q6_K has a decisive-margin pass;
  Q4_K_M is PARTIAL/INCONCLUSIVE and qualified.
- **After 7F-1:** the auditor verifies the required GPU run and the red-suite
  block, then signs G6.

---

## 6. Sign-off

**7F rework decision: blockers 7F-2..7F-5 CLOSED; G6 remains OPEN on 7F-1
only.** The tokenizer fix, decisive-margin amendment, sdist packaging, and
release-scope/claims wording are accepted as independently verified.

**Signed:** DeepSeek V4.1 Flash, primary auditor — 2026-11-09.
