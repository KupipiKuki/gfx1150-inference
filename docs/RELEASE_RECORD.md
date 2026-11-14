# RELEASE RECORD — gfx1150-inference (final state)

**Date:** 2026-11-14 (7G-C closure package)
**Branch of record:** `main` (7G-C merged after the auditor signs G7-C)
**Gate history:** G0 → G1 → G2 → G3 → G4 → G5 → G6 signed; **G7-C** is the
closing gate. Signoffs live in `audit/G*_SIGNOFF_*.md`; per-gate work in
`audit/evidence/G*/`.

---

## 1. What this project is

A **dense-LLM SSD-offloaded inference engine for one specific AMD APU**
(Radeon 890M / `gfx1150`, unified memory, no discrete VRAM), built as an
**evidence-discipline project**: every public capability claim is rowed in
`audit/CLAIMS_LEDGER.md` with a reproducible evidence pointer, machine-checked
by `scripts/qa/check_claims.py --strict` against an **empty** ratchet baseline
and protected by mutation canaries (`scripts/qa/canary_claims.py`).

What it does, measured (`docs/CAPABILITIES.md` is the authoritative numbers):

- streams quantized weights (F16, `Q4_0`, `Q4_K`/`Q4_K_M`, `Q6_K`, `Q8_0`)
  from NVMe via `mmap` with best-effort page-cache management
  (`posix_fadvise(DONTNEED)` + PTE drop), with a measured residency policy
  (`auto`/`pin`/`stream`, 7D);
- runs llama-family dense models end-to-end on the gfx1150 GPU (HIP kernels;
  kernels hardware-verified on synthetic GGUFs, G0) and `phi3`/`gemma` on the
  Python spec-driven path (synthetic-fixture verified, 7C);
- tokenizes llama-family GGUF vocabularies (SentencePiece and byte-level BPE)
  reference-faithfully against pinned llama.cpp goldens + a 310-case
  differential corpus (G2), with `qwen2` as a metadata/bias regression target
  only;
- budgets everything it allocates: weights (measured budget from GTT sysfs ∩
  `MemAvailable` ∩ cgroup, minus KV/activations/margin), the device-resident
  KV pool (same sources), and — since 7G-C/C6 — the CPU-offloaded KV pool by
  **host RAM** and the mmap-backed KV pool by host RAM **and** free disk,
  with explicit refusals instead of OOMs (7D-3 + 7G-C);
- carries a prompt-safe telemetry surface (`gfx1150-stats/1`): per-run SSD
  bytes, faults, GTT peak, per-projection kernel medians — never prompt text,
  token IDs, or completions (7F-4);
- since 7G-C/C5, accepts multi-KB research prompts via `--prompt-file` or
  `--prompt -` (stdin) with clean one-line errors on bad input.

## 2. The real-GGUF golden record (stated honestly)

Real TinyLlama-1.1B-Chat `Q4_K_M`/`Q6_K` runs against pinned llama.cpp on the
gfx1150 GPU: **tokenization reference-exact on every prompt**; greedy chains
token-identical through every decisive step and forking only at FP16-noise
near-ties, so **no exact 16-step golden is claimed** — the strict result is
**FAIL, recorded verbatim on every run**. The 7G-C re-adjudication
(`audit/evidence/G7/7G-C/c3-golden/`, pre-registered walk refinement +
minimum-2-decisive-steps rule) records decisive comparisons passing on 4 of
5 prompts; one Q4_K_M prompt stays INCONCLUSIVE. Nothing was widened to make
a test pass; PARTIAL is the strongest flavor status (ledger rows 5, 6, 31).

## 3. What it explicitly does **not** do

- No MoE / expert routing, grouped GEMM, or expert cache.
- No CPU-side compute: layers are always computed on the GPU.
- No speculative decoding (MTP / n-gram / prompt-lookup drafting).
- No 70B real-GGUF claim (the 70B path exists but was never run) and no
  "without OOM" 70B guarantee (ledger ID 18).
- No 8-hour endurance measurement (ledger ID 19).
- No chat-template end-to-end verification for any family.
- No discrete-VRAM target; the verification host is an APU.
- No real-GGUF exact golden for any flavor (see §2).
- The GPU CI lane is **advisory under the waiver** in force at closure
  (`audit/G6_ENFORCEMENT_WAIVER_2026-11-13.md`): the no-push-trigger decision
  stands (`audit/evidence/G7/7G-C/notes.md` §C4) and the *requirement* is
  restored when the runner self-repair (C2) is deployed.

## 4. Gate history (one line each)

| Gate | Scope | Signoff |
|---|---|---|
| G0 | build/CLI baseline, kernel + CPU suites, sdist install | `audit/G0_SIGNOFF…` / evidence `G0/7.0-baseline/` |
| G1 | tokenization architecture (SPM + BPE) | `audit/AUDIT…G1` / evidence `G2/7B/` |
| G2 | tokenizer goldens vs llama.cpp (7B) | `audit/AUDIT_7B_*` |
| G3 | model families: `phi3`/`gemma` synthetic verification | `audit/AUDIT_7C_*` / evidence `G3/7C/` |
| G4 | memory honesty: residency policy, eviction, KV hardening | `audit/AUDIT_7D_*` / evidence `G4/7D/` |
| G5 | stream topology, copy/compute overlap, per-projection telemetry | `audit/AUDIT_7E_*` / evidence `G5/7E/` |
| G6 | release evidence: real-GGUF goldens, benchmarks, claims gate, CI | `audit/G6_SIGNOFF_2026-11-12.md` (+ §the four G6-QF carry-forwards) |
| G7-C | closure package (this record) | pending: auditor signature |

## 5. The four G6 carry-forwards and their closure

| ID | Defect | Closure |
|---|---|---|
| G6-QF-1 (C1) | residency-probe flake on the GitHub-hosted runner (`assert 0 > 0`, warm page cache) | fixed: fixture `flush`+`fsync` before the probe; `MADV_PAGEOUT` failure now falls back to a `MADV_DONTNEED` PTE drop (unit-tested). No skip path was needed; no 7D claim or evidence changed. `audit/evidence/G7/7G-C/c1-residency-probe.log` |
| G6-QF-2 (C2) | server-side runner registration deleted four times in four days; required GPU check queued forever | code complete: PAT-based self-repair `scripts/ci/ensure_runner_registered.sh` + systemd watchdog units; nightly cron moved 03:00→04:00 UTC (after the ~03:38 boot). **Deployment pending** (needs the owner's PAT at `/etc/gfx1150-runner/runner.pat` + root); the simulated deletion-and-recovery transcript is recorded as owner-pending in `audit/evidence/G7/7G-C/c2-runner/` |
| G6-QF-3 (C3) | two mixed k-quant goldens INCONCLUSIVE (0 decisive steps compared) | closed by measurement: two pre-registered forced-completion prompts + the pre-registered decisive-walk refinement and minimum-2-decisive-steps rule; re-adjudication recorded with margins (4 of 5 prompts decisive PASS; prompt2 honestly INCONCLUSIVE); strict FAILs verbatim; no exact-golden claim. `audit/evidence/G7/7G-C/c3-golden/` |
| G6-QF-4 (C4) | enforcement of the required GPU check (no push trigger) | **decided, 2026-11-13: no push trigger.** Recorded in `audit/evidence/G7/7G-C/notes.md` §C4; the waiver text carries the restoration condition (C2 deployment) |

## 6. Deferral note — 7G-1/7G-2/7G-3

**Deferred, not dropped.** The bounded-weight-residency feature (7G-1), the
host-side compute/CPU-offload thesis (7G-2), and the speculative-decoding
work (7G-3) belong to the **next project**, seeded as milestones M0–M6 in
`docs/NEXT_PROJECT_SEED.md` (7G-1 → M3, 7G-2 → M4/M6 per its table; the ADR
on hardware target and model class is M0). They were **not** started on this
repository, per the 2026-11-13 owner decision recorded in
`PHASE7_7G_RESIDENCY_AND_FOLLOWUP_PLAN.md` §7G-C.

## 7. Pointers

- Capability document (what it can do, with measured numbers):
  `docs/CAPABILITIES.md`
- Next project (Strata-class: MoE, CPU compute, speculation, discrete-VRAM
  target): `docs/NEXT_PROJECT_SEED.md`
- Claim record + gate: `audit/CLAIMS_LEDGER.md`, `scripts/qa/check_claims.py --strict`
- Final-state label: `docs/STATUS.md`

*gfx1150-inference — closed as a dense APU inference engine with an evidence
discipline.*
