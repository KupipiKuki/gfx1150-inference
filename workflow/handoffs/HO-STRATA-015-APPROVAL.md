# Architect approval — HO-STRATA-015

| Field | Value |
|---|---|
| **Handoff** | HO-STRATA-015 (DeepSeek **S4b**: MoE blocks 1–27, layer parity) |
| **Architect** | `architect` (`opencode-go/deepseek-v4-pro#max`) |
| **Date (UTC)** | 2026-11-26 |
| **Decision** | **SIGNED** |
| **Merge commit** | via `merge/*` PR with a merge commit (DEC-040) |
| **Evidence** | `workflow/evidence/HO-STRATA-015/` (54 checks, 34/34 hashes, 11 pin rows) · `reports/qaqc/HO-STRATA-015-qaqc.md` · `reports/audit/HO-STRATA-015-audit.md` · `DR-HO-STRATA-015-1.md` · `RW-HO-STRATA-015-1/2/3.md` |

## 1. Criteria trace

| # | Criterion | Evidence | QAQC | Audit | Architect |
|---|---|---|---|---|---|
| AC-1 | build; signed binary + oracle untouched | `d58ee239…`, `a4c56b9d…` | PASS | PASS | PASS |
| AC-2 | refusal verbatim; `--families` unchanged | `artifacts/refusal.txt`, `families.txt` | PASS | PASS | PASS |
| AC-3 | `--parity-run` gating incl. supported models (F2) | three cases + unit test | PASS | PASS | PASS |
| AC-4 | dump `1,187,840` B, N=28 | `compare_layers.py --slots 28 --shape-only` | PASS | PASS | PASS |
| **AC-5b** | **teacher-forced layer parity, 108 then 112 cells, ≤ 5e-3** | `artifacts/ac5.log`: max **1.569942e-04** at `(4,3)`, median 3.2e-05 | PASS | PASS (reproduced; mutation-tested) | **PASS** |
| AC-5b-info | free-running reported, not gated | `ac5b_free.log`, `llama-ref-moe.md`, `router-margin-19-1.txt` | PASS | PASS | PASS |
| AC-6 | determinism | byte-identical dumps | PASS | PASS | PASS |
| AC-7 | Qwen 32 IDs + both tests | `11751 … 10919`; 39 checks | PASS | PASS | PASS |
| AC-8 | memory + dequant spot-check | 23.124 / 45.970 GiB; max diff `0.0` | PASS | PASS | PASS |
| AC-9 | geometry assertions | 11 fields `ok` | PASS | PASS | PASS |
| AC-10 | patch applies; T2 measured | `0003-s4b-moe.patch` on `baf16363`+`0001`+`0002`; cumulative 14 files / +1,656 / −31 | PASS | PASS (within DEC-043) | PASS |
| AC-11 | evidence gate | `check_bundle --strict` PASS (54) | PASS | PASS | PASS (re-ran) |
| AC-12 | carried criteria implemented | A1–A4, A6–A8; `B6-pins` 11 rows | PASS | PASS | PASS |

## 2. What the gate did this time

Two gate changes were made after measurements, and both survived adversarial review:

- **DEC-044** (S4a) changed the *reference* because the signed Q4_K oracle's
  matmuls quantise activations (q8_K), making it lossy at ~1e-1. The exact-f32
  reference then exposed a real RoPE bug.
- **DEC-046** (S4b) changed *what is compared*, because a free-running comparison
  at layer 19 crossed a router tie whose margin (**3.36e-6** prob / **7.95e-5**
  logit) is *tighter than the 7.12e-5 of inherited drift*; the observed drift moves
  the 33↔40 gap by **1.3845e-4 = 1.74×** the margin. Teacher forcing isolates layer
  arithmetic from that drift.

The audit's decisive check was not reproduction but **mutation**: re-introducing
top-6 renormalisation fails at cell `(1,0)` with max **6.16e-1**, and dropping the
shared-expert branch fails with **7.52e-1**. The gate is sharp — it is not a
softened gate that happens to pass.

## 3. What is claimed, and what is not

**Claimed:** the engine computes the DeepSeek-MoE-16B forward pass for all 28
blocks, and each block reproduces the exact-arithmetic reference within 5e-3 given
the reference's own input (**max 1.569942e-04**, 31.8× inside the bound).

**Not claimed:** that the family runs. `model_family_runs()` is still `false`, the
named refusal and `--families` (`qwen4exp qwen35moe`) are unchanged, the parity
path is reachable only through `--parity-run`, and no performance or support
statement exists in the bundle, the handoff or the commit messages. Cross-position
state (the engine's own K/V and residual accumulation) is **not** proven by teacher
forcing — that is S5's job, and A15 makes it blocking.

## 4. Conditions / follow-ups (binding on HO-STRATA-016 / S5)

| # | Severity | Condition |
|---|---|---|
| **A15** | **Major** | S5 must be a **blocking end-to-end token gate**: 3 prompts × 16 greedy tokens vs the Q4_K oracle, zero mismatches, KL ≤ 1.5× the measured floor. Teacher forcing cannot see cross-position state; only this gate can. |
| **A12** | Major (carry) | S5's verdict-consistency check must cover **every** artifact cited as PASS (HO-015's covers 4/12 and is partly vacuous). |
| **A14** | Minor | Record the engine-side input assertion, and assert block-0 inputs against `token_embd` rather than self-comparing. |
| **A18** | Minor | State the subtraction convention for the gap (`40−33` vs `33−40`) — the magnitude and direction are right, only the label is unstated. |
| A10, A11, A13, A16 | Minor | Hygiene: environment row, AC-8 host/GTT wording, stale labels, committed inputs for any generator. |

The three reworks (**RW-1** self-containment, **RW-2** wrong-trajectory margins,
**RW-3** a drift artifact wrong by 902×) are closed. Each was an **evidence**
defect found by review, not an engineering defect — the same class this project has
fought since HO-008, and the reason `check_bundle.py` exists. It is worth recording
that the tool would not have caught any of the three: it checks packaging, not
whether an artifact proves what the manifest says. A12 is the beginning of a fix;
the durable lesson is that a reviewer must read the artifacts, not just verify their
hashes.

## 5. Decision

- **SIGNED** → state `DONE`. Merge per DEC-040 via a `merge/*` PR with a merge commit.
- **Next:** **HO-STRATA-016 (S5)** — exact token parity and KL, which is also the
  only handoff that may flip `model_family_runs()`; then HO-STRATA-017 (S6/S7:
  baseline, envelope, HO-007 regression, signoff).

| Role | Signature | Date |
|---|---|---|
| Architect | `architect` (`opencode-go/deepseek-v4-pro#max`) — **SIGNED** | 2026-11-26 |
