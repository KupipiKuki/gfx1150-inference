# Session handoff — 2026-11-27 (after HO-016 / S5, parked at CODER_DONE)

**Paste this file into a new session with the `architect` agent selected.**
Reading order: this file → `STATUS.md` → `DECISIONS.md` (this session:
DEC-047, 048, 049, 050) → `HO-STRATA-016.md` `CODER_TO_QAQC`.

---

## 1. Where the project is

```text
main                 8abcb3b  (HO-015 merged; this session's bookkeeping merged)
work branch          wp/strata-016-deepseek-s5  @ 6adab78   (open, not merged)
Strata branch        strata-016-deepseek-s5     @ 3c2f89555
signed binary        build-hip/strata  d58ee239…  (never rebuilt)
f32 oracle pack      /tmp/opencode/deepseek-moe-16b-f32.gguf  8cd778a7…
llama.cpp            /tmp/opencode/llama-ref @ 78e05298…  (build, build-tools)
S5 logits dumps      /tmp/opencode/HO-STRATA-016-dumps/  (12 × 6.55 MB, digests on record)
```

**S4 is complete and merged** (#29, #31). **S5 is built, measured and
`CODER_DONE` — it has not been independently reviewed**, because the QAQC seat's
model disappeared (DEC-049/050). No PASS is recorded for S5; the support claim is
**not** in force.

## 2. What S5 measured (unverified by QAQC — treat as the coder's claim)

| Item | Value |
|---|---|
| Token gate | **0/48 mismatches** (3 prompts × 16 greedy tokens), engine = Q4_K = f32 oracle |
| KL (gated, DEC-047) | mean 6.42e-07 / 2.94e-09 / 1.19e-08 nats; max step 5.99e-06 — ceiling 1e-2 / 1e-1 |
| Context curves | engine‖Q4_K up to 2.35e-02 mean; Q4_K‖f32 up to 3.17e-02 (quantization gap dominates, as DEC-047 predicted) |
| Flip | `--families` → `qwen4exp qwen35moe deepseek` (engine build) · `qwen4exp qwen35moe` (signed) · refusal still fires without the engine |
| Bundle | `check_bundle --strict` PASS (73 checks), 44 hashes, 20 pin rows, fixed point |

**Why this matters:** the token gate is the only test that exercises the engine's
*own* trajectory (its K/V and residual accumulation). Teacher forcing — which
proved S4b — deliberately cannot see that (audit A15).

## 3. Decisions in force (this session)

| DEC | Meaning |
|---|---|
| **047** | KL is an **absolute ceiling** against the exact-f32 model (mean ≤1e-2, step ≤1e-1), not a ratio to a floor — a same-binary floor cannot exist for two different arithmetics (the DEC-044 mistake one level up). Tokens remain the gate. |
| **048** | What "the family runs" means: dispatch without `--parity-run` + `--families`/`model_family_runs` scoped **compile-time** so a build without the engine still refuses honestly. |
| **049** | Provider migration: `opencode-go` no longer serves kimi / deepseek-v4-pro / gemini-argon; `alibaba-token-plan` does. S5's coder ran on `alibaba-token-plan/qwen3.8-flash` as a **disclosed substitution**; closure = migrate `coder-primary` to `alibaba-token-plan/kimi-k2.7-code` before S6. |
| **050** | **S5 parks at `CODER_DONE`**: QAQC unavailable, owner declined every substitute. Resume when the Gemini seat returns. |

## 4. The immediate next task

**QAQC review of HO-STRATA-016** at `6adab78`, with the brief already drafted (it
is in this session's history; reconstruct it from `CODER_TO_QAQC` if needed). Then
audit → signoff → merge. The three things QAQC must judge:

1. Is the **support claim** earned by the token gate rather than by the KL numbers?
2. Does DEC-047's absolute ceiling let a bad engine through where the q36 ratio
   would not? (Argue both sides and rule.)
3. Is the **compile-time flip** honest for a build without the engine? (Prove the
   refusal still fires.)

If `gemini-4-argon` is still unavailable, **ask the owner** — do not substitute
silently (DEC-050).

## 5. Open items after S5

1. **S6/S7 (HO-STRATA-017)**: baseline + GTT/`dmesg` envelope + the HO-007
   regression bit-identical; QAQC → audit → sign. Not written.
2. **Coder seat closure** (DEC-049): migrate `coder-primary` to
   `alibaba-token-plan/kimi-k2.7-code`, commit the agent file, update
   `MODEL_POLICY.md` §3, `check_model_policy.py --strict`.
3. **Auditor/architect seats**: both are absent from `opencode-go`'s current
   listing. They are being served in this session. If either fails to launch, that
   is an **owner escalation** — a substitute for the auditor breaks the
   independence the workflow rests on.
4. Carried, still open: HO-011's two unlisted artifacts (keep `--all` red, do not
   tune the tool); HO-010 B-1/B-2/B-4; the S5 audit carries (A15 → the token gate
   is now implemented; A12 verdict-consistency now covers every claim).
5. **OLMoE (HO-STRATA-018)** needs two things, not one (DEC-032): an `olmo`
   pre-tokenizer **and** a family path. Owner scope decision required.

## 6. Budget notes

- This session: S4b finished and merged, S5 built and parked, one coder-seat and
  one QAQC-seat outage. Cost was concentrated in **evidence assembly**, again — the
  coder ran out of steps twice at exactly the packaging step, and a prior
  `check_bundle.py` PASS coexisted with a gate artifact that was a traceback.
- **Durable lesson (now recorded):** `check_bundle.py` checks *packaging*, not
  whether an artifact proves what the manifest says. Three S4b reworks and one S5
  gate artifact were found only by a reviewer reading files. A future HO could add
  a content-level check — the bundle's own `verdict-consistency` idea, generalised.
- Cheapest order from here: QAQC → audit → sign → merge; then S6.

## 7. First message (copy-paste)

```text
Resume the Strata project. Read workflow/SESSION_HANDOFF_2026-11-27.md, then
STATUS.md and DECISIONS.md (DEC-047/048/049/050). Verify: signed binary d58ee239…,
check_bundle --all red only on HO-011, reference server optional. If the QAQC seat
(gemini-4-argon) is available, run QAQC on HO-STRATA-016 @ 6adab78; if not, ask me
before substituting. Do not treat S5 as passed until QAQC and audit report.
```
