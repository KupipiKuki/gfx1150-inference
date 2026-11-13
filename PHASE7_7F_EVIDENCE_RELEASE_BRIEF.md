# Phase 7F Coder Brief — Evidence & Release Gates (Gate G6)

**To:** GLM5.3 (coder)
**From:** DeepSeek V4.1 Flash (primary auditor)
**Date:** 2026-11-08
**Branch:** `wp/7F-evidence-release`
**Base:** `vibe/phase7-220201` at `08698f4` (the merge of the G5-signed 7E work;
confirm with `git log -1 --oneline`; do not start from an older SHA)
**Gate:** G6. **7F is authorized after G5 signed and merged (2026-11-08).**
**Prior gates:** G0–G5 signed. Do not reopen 7A/7B/7C/7D/7E without a written
auditor finding.

---

## 0. Read first

1. `PHASE7_IMPLEMENTATION_HANDOFF.md` §7F and `audit/CLAIMS_LEDGER.md`
   (all `UNVERIFIED` / `NOT YET` rows).
2. `IMPLEMENTATION_PLAN.md` 7F row, release wording (lines ~255–265), and the
   G6 release statement.
3. `scripts/qa/check_claims.py`, `scripts/qa/canary_claims.py`,
   `audit/claims_baseline.txt`.
4. `.github/workflows/ci-gpu.yml` (currently `continue-on-error`), `ci-cpu.yml`,
   `ci-build.yml`.
5. `src/inference.py` (CLI / generation loop), `tests/conftest.py` and the
   existing golden/benchmark fixtures.

**Current gap:** GPU CI is still `continue-on-error`; there is **no real-GGUF
golden run**, **no checked-in benchmark baseline**, **no telemetry contract**,
and `check_claims.py --strict` is still advisory with a non-empty baseline.
The 70B, 8-hour, and throughput claims remain unverified; 7F must either produce
the evidence or keep those claims qualified/absent.

---

## 1. Objective and non-goals

**Objective (G6):** produce release-grade evidence and make it enforceable:

- a **required** self-hosted gfx1150 GPU CI job (no `continue-on-error`);
- real GGUF golden token/logit evidence against llama.cpp;
- a reproducible benchmark harness with a checked-in baseline and a regression
  gate;
- `--stats` / `--json` telemetry that is reproducible and prompt-safe;
- a **release-blocking** strict claims gate with an empty baseline and a
  ledger-vs-docs diff.

**Non-goals (do not bundle):**
- New model families, tokenizer changes, kernel math, 7D memory-policy changes,
  flash attention, GQA sharing, batching, or 7G polish.
- Any claim the evidence does not support: **no 70B "without OOM"**, **no
  8-hour endurance**, **no throughput number** until 7F-3 artifacts exist.
- Changing the public Python API semantics; 7F-4 may add CLI flags and a stats
  object, but generation behavior must stay identical.

---

## 2. Allowed files

- `tests/**` — new golden/benchmark/telemetry tests and fixtures; do not weaken
  existing tests.
- `scripts/bench/**` (new), `scripts/qa/**` — benchmark harness, claims tooling,
  and release checklist helpers.
- `.github/workflows/**` — make GPU CI required after the runner is registered;
  no unrelated workflow rewrites.
- `src/inference.py` — **only** `--stats` / `--json` telemetry plumbing and
  `perf_counter` instrumentation; no generation/sampling logic changes.
- `README.md`, `IMPLEMENTATION_PLAN.md`, docs — verified-scope wording only.
- `audit/CLAIMS_LEDGER.md` — update statuses/evidence pointers with the 7F
  artifacts; do not silently promote unverified rows.
- `audit/evidence/G6/7F/**` — the evidence bundle (contract:
  `audit/evidence/G6/7F/README.md`).

**Forbidden:** tokenizer/model-family/7D policy changes; kernel math; 7G;
deleting or weakening tests; unqualified public claims; force-pushing shared
branches.

---

## 3. Work packages

### 7F-1 — Required self-hosted GPU CI

- Register the self-hosted gfx1150 runner with labels `gfx1150`, `rocm`
  (**owner action**; the coder cannot create the runner).
- Once a green run exists, remove `continue-on-error` from `ci-gpu.yml` and make
  `pytest -m gpu` required on PR + nightly; retain logs/artifacts.
- Branch protection must require the GPU job (owner/repo-admin action).

**Acceptance:** a real-runner GPU run is green with no `continue-on-error`;
the job blocks a deliberately red GPU suite; logs/artifacts retained.
**If the runner is unavailable:** stop and record the blocker; do not claim G6.

### 7F-2 — Real GGUF goldens (Q4_K_M / Q6_K)

- Fixed prompt, `temperature=0`, fixed seed; run the real GGUF on gfx1150 and a
  pinned llama.cpp build on the same prompt.
- Compare **token IDs exactly** and logits within a **stated tolerance**
  (document the tolerance and why).
- Commit artifacts: model identity/hash, llama.cpp commit, commands, token IDs,
  logits hashes or a small tolerance-checked excerpt, and the environment.
- Phi-3/Gemma remain synthetic-only unless real goldens are produced here;
  Qwen2 stays `NOT YET` unless separately authorized and evidenced.

**Acceptance:** token IDs match exactly; logits within the stated tolerance;
artifacts are reproducible from a clean clone + documented model acquisition.
Do not commit multi-GB weights; record hashes and an acquisition command.

### 7F-3 — Benchmark harness and regression gate

- Warm-up, `hipEvent` timing, **≥20 iterations**, median and p95, hardware
  (gfx1150), ROCm/HIP version, model hash, prompt/seq length, and date.
- Check in a baseline file under `scripts/bench/` (or evidence) and add a
  regression gate: fail when a metric exceeds an **agreed ratio** (state it).
- Measure the real paths the docs describe (7B-class on this host). Do not
  extrapolate to 70B/780M; record any 780M numbers separately.

**Acceptance:** reproducible numbers from a clean clone; baseline file; a
documented CI gate or manual release gate; no unqualified throughput claim.

### 7F-4 — Telemetry (`--stats` / `--json`)

- Emit bytes read, major faults, GTT peak, per-kernel ms, and tok/s; use
  `perf_counter` consistently.
- Keep logs prompt-safe: no prompt text or token content in stats output.
- Document the schema and how to reproduce it.

**Acceptance:** metrics reproducible within a stated variance; schema documented;
no prompt leakage; CUDA/HIP event timings consistent with the benchmark harness.

### 7F-5 — Release-blocking claims gate

- `check_claims.py --strict` runs in CI and the release checklist; make it
  **blocking**.
- **Empty** `audit/claims_baseline.txt` at G6.
- Diff `audit/CLAIMS_LEDGER.md` against `README.md` / `IMPLEMENTATION_PLAN.md`
  and include the diff in release evidence.
- Every `VERIFIED` row has an existing evidence path; every `UNVERIFIED`/`NOT
  YET` row is absent or qualified in public docs.
- Keep the canaries green and add canaries for: an unqualified throughput claim,
  an unqualified 70B/8-hour claim, and a `VERIFIED` row with a missing path.

**Acceptance:** strict mode passes with an empty baseline; injected canaries
fail as expected; ledger/docs diff is part of the release evidence.

---

## 4. Required checks

```bash
python -m pytest -m "not gpu" -q
python -m pytest -m gpu -q
python tests/test_cpu_only.py && python -O tests/test_cpu_only.py
python scripts/qa/check_claims.py
python scripts/qa/check_claims.py --strict
python scripts/qa/canary_claims.py
test ! -s audit/claims_baseline.txt
python scripts/bench/run.py --model <fixture> --json > bench.json
git diff "$(git merge-base HEAD origin/vibe/phase7-220201)" -- \
  audit/CLAIMS_LEDGER.md README.md IMPLEMENTATION_PLAN.md
```

A GPU lane result only counts from the **self-hosted real runner** once 7F-1
lands; local GPU runs are supporting evidence, not the G6 gate.

---

## 5. QAQC adversarial checks

- Re-run the golden and benchmark from a clean clone; verify artifact hashes and
  that token IDs are compared exactly, not "close enough".
- Rerun the benchmark and confirm the reported variance; check warm-up and p95.
- Confirm the GPU CI job is required (no `continue-on-error`) and fails a red
  GPU suite.
- Confirm telemetry has no prompt/token leakage.
- Inject an `UNVERIFIED` canary into `README.md`; confirm 7F-5 fails.
- Inject a `VERIFIED` ledger row with a missing evidence path; confirm it fails.
- Delete/blank the baseline; confirm strict mode expects it empty (not a skip).
- Confirm no unqualified 70B / 8-hour / throughput / Phi-3 / Gemma / chat claim
  remains.

---

## 6. Stop / scope

- Do not start 7G.
- Do not claim G6 until the GPU runner is required and green, real-GGUF goldens
  pass, the benchmark baseline exists, telemetry is documented, and the strict
  claims gate is release-blocking with an empty baseline.
- If a prerequisite is unavailable (runner registration, real GGUF files,
  llama.cpp reference), stop and record the blocker in the evidence bundle;
  mark the affected package `BLOCKED` rather than weakening the gate.
- Keep the branch `wp/7F-evidence-release`; one work package per gate; do not
  merge before the auditor signs G6.

## 7. Gate exit (G6)

- [ ] CPU + GPU CI green; the GPU job is **required**, not `continue-on-error`.
- [ ] Real-GGUF golden token/logit artifacts pass (or the affected model family
      stays explicitly `NOT YET`).
- [ ] Benchmark baseline + regression gate exist; numbers reproducible.
- [ ] `--stats` / `--json` telemetry works, is documented, and is prompt-safe.
- [ ] `check_claims.py --strict` is release-blocking; baseline empty; canaries
      green; ledger/docs diff clean.
- [ ] No unqualified 70B, 8-hour, throughput, Phi-3, Gemma, or chat claim.
- [ ] Auditor signs the release candidate.
