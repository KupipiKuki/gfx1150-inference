# QAQC rework review — Phase 7F (Gate G6) after the five blockers

> **Scope:** adversarial QAQC of branch `wp/7F-evidence-release` at tip `d5f2947`
> (rework work commit `b3920d2`, rework evidence `d5f2947`; auditor base `baa3e87` /
> rework brief `PHASE7_7F_REWORK_BRIEF.md`; audit `audit/AUDIT_7F_DEEP_2026-11-08.md`).
> **This review changed no code or evidence:** it adds only this report.
> **Method:** full battery re-run on the real gfx1150 host (Radeon 890M, ROCm
> 10.1.0); each blocker re-verified independently — mutation test of the tokenizer
> fix, direct tokenizer probe on the real TinyLlama GGUFs (sha256-verified),
> full re-run of all three real-GGUF goldens against a freshly regenerated
> pinned-llama.cpp reference, fabricated-input probes of the decisive-margin
> compare logic, sdist rebuild + extracted-tree lane, claims-gate mutation probe.
> **Status legend:** VERIFIED = independently reproduced · NOTE = non-blocking ·
> OPEN = not closed.

---

## 1. Re-run results at tip `d5f2947` (this review, 2026-11-10)

| Check | Result |
|---|---|
| `pytest -m "not gpu" -q` (CPU lane) | VERIFIED — **527 passed, 45 deselected** (exit 0) |
| `pytest -m gpu -q` (real gfx1150 host) | VERIFIED — **45 passed, 527 deselected** (exit 0) |
| `tests/test_goldens_tokenizer.py -q` | VERIFIED — **353 passed** |
| `tests/test_cpu_only.py` / `-O` | VERIFIED — OK / OK (exit 0 both) |
| `check_claims.py` / `--strict` | VERIFIED — PASS exit 0 / PASS exit 0 (0 unqualified, 0 baselined) |
| `canary_claims.py` | VERIFIED — 16/16, exit 0 |
| `audit/claims_baseline.txt` | VERIFIED — 0 bytes |
| sdist build → extract → `pytest -m "not gpu and not slow" -q` | VERIFIED — **523 passed, 49 deselected** (exit 0); sdist contains `scripts/bench/{aggregate,regress,run}.py` + both baselines |
| bench synthetic run → `regress.py` vs `baseline-synthetic.json` | VERIFIED — PASS exit 0 (within 15%) |
| committed 7B rerun → `regress.py` vs new `scripts/bench/baseline-7b.json` | VERIFIED — PASS exit 0 |
| real-GGUF goldens (all three, `--engine-prompt-ids`, fresh pinned-llama.cpp refs) | VERIFIED — bit-identical tokens and identical verdicts to the committed `verdict-rework-*.json` (see §2, BLOCKER-7F-3) |
| real TinyLlama GGUF sha256 vs `golden/README.md` table | VERIFIED — Q4_K_M `9fecc3b3…76a0`, Q6_K `9fb2be7c…cb6d`, Mistral-7B `3e0039fd…ccf9` all match |
| pinned llama.cpp | VERIFIED — `/home/kupipi/goldens7f/llamacpp/repo` @ `7d7f0287530bc8981690f361d8c1627dbae1c99a` |
| rework diff scope `a48d6f1..d5f2947` | VERIFIED — only `src/tokenizer.py` + `tests/test_goldens_tokenizer.py` under `src/`/`tests/` for code; no `src/kernels`, `src/model_spec.py`, `src/inference.py`, telemetry, or claims-gate changes; workflows: only `ci-cpu.yml` (+15 lines, the sdist assertion) |
| branch CI at the rework tip | NOTE — not re-queried: no PR exists for `wp/7F-evidence-release` and the available connector exposes only PR check-runs (PR #8 tracks base `2d48efe`, all green there). The previously red sdist lane was instead reproduced locally green (§2, BLOCKER-7F-4) |

---

## 2. Blocker-by-blocker verification

### BLOCKER-7F-1 (required GPU CI) — OPEN (owner action, correctly not coder-fixed)

`ci-gpu.yml` is unchanged by the rework and still carries
`continue-on-error: true` at the job level; no self-hosted runner is
registered on the gfx1150 host (`audit/evidence/G6/7F/gpu-runner.md` documents
the owner steps and the connector limitation). The local GPU lane is green
(45 passed, this review), but per the G6 contract it does not count until the
runner is registered, the job is required, and a red-suite block is
demonstrated. Nothing was weakened to work around it — correct per the brief's
stop rule. **G6 cannot close until this lands; it is the only remaining
blocker.**

### BLOCKER-7F-2 (SPM tokenizer used BPE ranks) — VERIFIED FIXED

- `src/tokenizer.py:216` now reads exactly
  `use_ranks = bool(self.merge_ranks) and self._uses_gpt2` — the auditor's
  prescribed one-line fix, with an explanatory comment.
- **Mutation test:** running the new regression tests against the pre-fix
  `tokenizer.py` (from `a48d6f1`) fails
  `test_spm_vocab_with_merges_array_ignores_bpe_ranks` with the defective
  segmentation; `test_gpt2_vocab_still_uses_merge_ranks` passes both ways
  (guard against over-correction). At the tip: 353 passed.
- **Real-GGUF probe (this review):** both TinyLlama files have
  `tokenizer.ggml.model="llama"`, 61,249 `merges`, all-zero `scores`,
  `_uses_gpt2=False`. Engine segmentation now matches the audit's llama.cpp
  reference column exactly: `jumps` → `[1, 12500, 29879]` (`▁jump`+`s`),
  `sources` → `[1, 3669, 2214, 267]` (`▁sou`+`rc`+`es`),
  `quoting` → `[1, 13911, 292]` (`▁quot`+`ing`). All three committed prompts:
  engine token IDs == reference token IDs (31/31, 35/35, 31/31).
- **End-to-end:** all three goldens re-run with `--engine-prompt-ids` record
  `prompt_tokenization_engine_matches_reference=true`; my token files are
  byte-identical to the committed `ours-rework-*.tokens.txt`.
- The narrow 7B reopen was honored: no other `src/` file changed.

### BLOCKER-7F-3 (7F-2 acceptance criterion) — VERIFIED implemented as pre-registered

- `scripts/qa/real_gguf_golden.py` implements exactly the rework-brief §3
  amendment: `DECISIVE_MARGIN_THRESHOLD = 1.0`, top-1 margin required ≥ 1.0 on
  **both** sides, walk stops at the first indecisive step, 0 compared steps →
  `INCONCLUSIVE` (never a pass); the strict 16-step result is kept verbatim
  under `strict_16_step`; logits/probs are recorded as diagnostics with the
  bounds **unchanged** (`LOGITS_MAX_ABS_DIFF = 0.5`, `PROBS_MAX_ABS_DIFF =
  0.02`) and no longer gate `pass`; `pass` = prompt IDs match AND decisive
  PASS.
- **Independent reproduction (this review):** regenerated the reference with
  `golden_ref` from the pinned llama.cpp (`7d7f0287…`) — ref tokens
  bit-identical to the committed `ref-*.tokens.txt`, ref logits sha256
  `2ac130e9…` matches the committed table. Then re-ran all three engine
  goldens with `--engine-prompt-ids`. Every verdict matches the committed
  `verdict-rework-*.json`:

  | Run | strict 16-step | decisive-margin | committed == mine |
  |---|---|---|---|
  | Q4_K_M prompt1 | FAIL, fork step 14 (margins 0.031/0.156) | INCONCLUSIVE — step 0 indecisive (ref margin 0.950 < 1.0), 0 compared | yes, tokens identical |
  | Q4_K_M prompt2 | FAIL, fork step 3 (0.008/0.059) | INCONCLUSIVE — step 0 indecisive (0.781/0.749), 0 compared | yes, tokens identical |
  | Q6_K prompt1 | FAIL, fork step 4 (0.164/0.113) | PASS — steps 0–1 decisive (margins ≥ 1.21/1.21 and 1.94/1.79) and token-exact; stops at indecisive step 2 | yes, tokens identical |

- I recomputed the decisive walk from the per-step margins in the verdicts
  (matches), and probed the compare logic with fabricated inputs: mismatch at
  a decisive step → FAIL; all-decisive match → PASS; indecisive at step 0 on
  one side only → INCONCLUSIVE with `pass=false`; prompt-ID mismatch →
  `pass=false` even when decisive passes. All branches behave as specified.
- Pre-fork logits noise reproduced: max abs diff 0.71 (Q6_K), **0.89**
  (Q4_K_M p1 — the audit's 0.89 sample), 0.92 (Q4_K_M p2) pre-fork; post-fork
  10–32 (different states, meaningless) — consistent with the README.
- Honesty preserved: the pre-rework verdicts still record
  `prompt_tokenization_engine_matches_reference: false`; the rework README
  keeps the original result verbatim below the rework result.
- **NOTE (QAQC-7F-R1, non-blocking):** in default mode (without
  `--engine-prompt-ids`) the verdict field
  `prompt_tokenization_engine_matches_reference` is computed from the *fed*
  prompt IDs (`meta["prompt_ids"] == ref_prompt`), which is trivially true in
  default mode, and the explicit `prompt_ids_match_reference` boolean was
  dropped from the verdict. The raw `prompt_ids_engine` is still recorded, so
  a divergence is recoverable, and post-fix engine==ref on the real vocab —
  but recommend keying that field off `prompt_ids_engine` (as in engine mode)
  so a future tokenizer regression cannot be masked in default mode.

### BLOCKER-7F-4 (sdist lane red) — VERIFIED FIXED

- `MANIFEST.in` adds `recursive-include scripts/bench *.py *.json`.
- Rebuilt the sdist at the tip: contains `scripts/bench/aggregate.py`,
  `regress.py`, `run.py`, `baseline-synthetic.json`, `baseline-7b.json`, and
  `tests/test_bench_gate.py`. Extracted-tree lane (the exact previously red CI
  step): **523 passed, 49 deselected**, exit 0 — matching the coder's
  `rework-run.log`.
- New guard in `ci-cpu.yml` (the only workflow change): after listing
  `sdist-contents.txt`, the job fails if any of `scripts/bench/aggregate.py`,
  `regress.py`, `baseline-synthetic.json`, `baseline-7b.json` is absent from
  the archive. The grep pattern (`^[^/]+/<path>$`) is correct against
  `tar -tzf` output. Shipped tests import only `aggregate` from that
  directory (`tests/test_bench_gate.py`), so the list covers the import
  closure.

### BLOCKER-7F-5 (release-scope wording overstated) — VERIFIED FIXED

- README L132 now states the release scope as llama-family kernel paths
  **synthetic-hardware-verified** (`Q4_0`/`Q4_K`/`Q8_0` on the gfx1150 lanes),
  explicitly "**not a real-GGUF golden**", and states the real-GGUF result with
  its measured outcomes (tokenizer reference-exact after the BLOCKER-7F-2 fix;
  strict 16-step FAIL recorded; decisive-margin Q6_K PASS / Q4_K_M
  INCONCLUSIVE; **no exact 16-step golden claim**). README L10 carries the same
  PARTIAL qualification. This is exactly the required wording direction.
- `audit/CLAIMS_LEDGER.md` row 31 inventories the `Verified release scope`
  literal (PARTIAL, qualified at README.md:132). **Mutation probe (this
  review):** appending an unqualified `Verified release scope` sentence to a
  scratch copy of README makes `check_claims.py --strict` exit 1 (detected);
  the clean tree exits 0. Rows 5/6 updated with the rework outcomes; the row-5
  "ran a real a real-GGUF" typo is fixed.
- `scripts/bench/baseline-7b.json` is checked in (model sha256 + acquisition
  command recorded in `bench/README.md`; the local model file's sha256 matches),
  and the `regress.py` docstring now points at the checked-in file — the
  nonexistent-path reference is gone. The committed 7B rerun passes the new
  baseline (exit 0, this review).
- Gate state at the tip (this review): default PASS (0 baselined), `--strict`
  PASS exit 0, canaries 16/16, baseline 0 bytes.

---

## 3. Findings

| ID | Status | Finding |
|---|---|---|
| QAQC-7F-R1 | NOTE | `real_gguf_golden.py` default mode: `prompt_tokenization_engine_matches_reference` is computed from the fed IDs (trivially true without `--engine-prompt-ids`) and `prompt_ids_match_reference` is no longer in the verdict; `prompt_ids_engine` is still recorded. Recommend keying the field off `prompt_ids_engine`. Non-blocking — post-fix the engine matches the reference on the real vocab, and all rework runs used `--engine-prompt-ids` |
| QAQC-7F-R2 | NOTE | Stale prose counts remain in two evidence files: `audit/evidence/G6/7F/notes.md` L104 and `audit/evidence/G6/7F/qaqc-probes/README.md` still say "525 passed" for the CPU lane (actual at the rework tip: **527**; the rework log in notes.md states 527 correctly), and `gpu-runner.md` says "39 passed" for the local GPU lane (actual: **45**). Same stale-count class the audit flagged; cosmetic, does not affect any gate |
| QAQC-7F-R3 | NOTE | Branch CI at the rework tip `d5f2947` could not be re-queried through the available connector (no PR for `wp/7F-evidence-release`; PR #8 check-runs track the base). The previously red sdist job was reproduced locally green; the new static assertion guards the class. The auditor may want to confirm a push-run at the tip |
| QAQC-7F-R4 | NOTE | 7E trace latch still process-global (`GFX1150_STREAM_TRACE` read once) — unchanged, documented, out of 7F scope |
| QAQC-7F-R5 | NOTE | Untracked local dirs `7c/` and `build-ptds/` pre-exist; not part of the branch |

No OPEN defects in the coder's rework. BLOCKER-7F-1 is OPEN by design (owner
action) and is the only remaining G6 blocker.

---

## 4. Verdict recommendation

**Blockers 7F-2, 7F-3, 7F-4, 7F-5: closed** — each independently reproduced by
this review (mutation-tested tokenizer fix reference-exact on the real GGUFs;
all three goldens re-run against a fresh pinned-llama.cpp reference with
bit-identical artifacts and verdicts matching the pre-registered
decisive-margin amendment, strict FAIL kept; sdist extracted-tree lane green
523/49 with a new CI guard; release-scope wording narrowed and enforced by
`--strict` with ledger row 31, proven by a mutation probe).

**BLOCKER-7F-1 remains OPEN** (owner: register the self-hosted runner, make
`GPU correctness (self-hosted gfx1150)` required, demonstrate a red block).
Per the brief's stop rule, G6 cannot be signed until it lands.

**Recommendation to the auditor:** hold G6 open **only** on 7F-1. On the
7F-2 gate outcome under the amended criterion: Q6_K decisive PASS (2 steps
token-exact above the 1.0-logit threshold), both Q4_K_M prompts INCONCLUSIVE
(step 0 already below threshold on one side — honestly recorded, never counted
as pass), strict 16-step FAIL recorded verbatim in all three verdicts. The
claims wording makes no exact-golden claim, so it does not depend on that
adjudication; whether INCONCLUSIVE on Q4_K_M is acceptable for the release
scope is the auditor's call at re-review.

**QAQC:** independent re-run on the real gfx1150 host, 2026-11-10.
