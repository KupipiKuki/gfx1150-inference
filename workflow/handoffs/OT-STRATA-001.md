# OT-STRATA-001 — start the Strata project on gfx1150

| Field | Value |
|---|---|
| **Owner task** | OT-STRATA-001 |
| **Received by** | Auditor (single intake) |
| **Date (UTC)** | 2026-11-15 |
| **State** | INTAKE |
| **Owner intent (quoted)** | “Start the Strata project on the current gfx1150 host; prove upstream Strata builds and runs on the APU; establish one small-MoE baseline per family; decide Route 2 vs Route 3. The 780M is a separate gfx-inference dense project; the MI25 is deferred; gfx1100 is future.” |
| **Priority** | P0 |

## 1. Scope

**In scope (gfx1150 only)**

- Pin the Strata commit and record the toolchain.
- Build Strata for `gfx1150`; record setup/CMake friction and tuning-table match.
- `strata --families` / `--plan`; record supported/unsupported model families.
- Inspect the engine boundary (can it run without `apps/`/`serve/`?).
- One small-MoE baseline per family: Mixtral 8x7B, Qwen3-30B-A3B, DeepSeek
  (V2-Lite or MoE-16B).
- Route 2 vs Route 3 decision with evidence.

**Out of scope**

- The 780M (separate `gfx-inference` dense project), MI25 (deferred), gfx1100
  (future).
- Performance/support claims beyond the measured baselines.
- The P0–P9 capability framework (escalation annex).
- Product/app work (`apps/`, `serve/`) unless it is needed to run the engine.

## 2. Decisions the owner must make

| # | Decision | Options | Recommendation | Owner choice |
|---|---|---|---|---|
| 1 | Strata commit | latest `main` vs a pinned release/tag | pin a commit and record it | |
| 2 | Mixtral pack | Mixtral 8x7B Q4_K_M | start here (8x22B-adjacent) | |
| 3 | Qwen pack | Qwen3-30B-A3B Q4_K_M vs Qwen1.5-MoE-A2.7B | Qwen3-30B-A3B, fallback A2.7B | |
| 4 | DeepSeek pack | DeepSeek-V2-Lite vs DeepSeek-MoE-16B | V2-Lite if supported, else MoE-16B | |
| 5 | Timebox | 1–2 days for the build spike | 1 day build + 1 day first run | |

## 3. Detailed instructions

- **Architect:** write `HO-STRATA-001` (build + support + engine boundary),
  then `HO-STRATA-002` (Mixtral), `HO-STRATA-003` (Qwen), `HO-STRATA-004`
  (DeepSeek), and `HO-STRATA-005` (Route 2 vs Route 3 decision). Validate the
  DoR; set READY; launch `coder-primary`; then `qaqc` and `auditor`.
- **Primary coder:** execute each HO on its work-package branch in the Strata
  checkout; produce the evidence manifest; do not modify Strata source in 001
  — record build blockers instead.
- **QAQC:** re-run the build/commands and the baselines; check the evidence and
  guard rails.
- **Auditor:** verify the evidence, the claims, and the scope; write audit
  reports; track this owner task and report to the owner.

## 4. Evidence requirements

- `workflow/evidence/HO-STRATA-001/`: pinned SHA, `rocminfo`, `hipcc --version`,
  kernel/`linux-firmware`, CMake/build log, `strata --families`, `--plan`,
  tuning-table match, engine-boundary note.
- `HO-STRATA-002/003/004`: one baseline table per family — model hash/quant,
  flags, prompt/decode tok/s, GTT/RAM, `dmesg`, limits; no cross-family claim.
- `HO-STRATA-005`: a one-page Route 2 vs Route 3 recommendation with the
  evidence that supports it.
- No secrets; no model weights in git; hashes only.

## 5. Progress checkpoints

| Checkpoint | Owner | Status |
|---|---|---|
| Model policy applied (`check_model_policy --strict`) | Architect | pending |
| Build spike (001) | Architect/Coder | pending |
| Mixtral baseline (002) | Coder/QAQC | pending |
| Qwen baseline (003) | Coder/QAQC | pending |
| DeepSeek baseline (004) | Coder/QAQC | pending |
| Route decision (005) | Architect | pending |
| Owner acceptance | Owner | pending |

## 6. Acceptance criteria (owner-facing)

1. A reproducible gfx1150 build with the exact toolchain recorded.
2. `strata --families`/`--plan` output and the engine-boundary note.
3. One measured baseline per family, with the model hash and the limits.
4. A Route 2 vs Route 3 decision recorded in `DECISIONS.md`.
5. The evidence bundle is complete; no unsupported claims.

## 7. Owner acceptance

| Decision | Date | Note |
|---|---|---|
| pending | | |

---

## 8. Auditor status — 2026-11-16 (UTC)

> Appended by the **Auditor** as owner-task intake and oversight. Status only. §1–§7 above
> (owner intent, scope, decisions, instructions, evidence requirements, acceptance) are unchanged.

**Checkpoint 1 — Build spike (001): done, pending architect sign-off.**
HO-STRATA-001 is at `AUDIT_REVIEW` with a QAQC **PASS** (re-check after `RW-HO-STRATA-001-1`) and an
auditor **PASS**. Audit report:
`workflow/reports/audit/HO-STRATA-001-audit.md`; evidence:
`workflow/evidence/HO-STRATA-001/`. The auditor re-derived every load-bearing claim in this session
against the pinned checkout — the 19 bundle hashes, the tuning-table and binary SHA256s, the Strata
pin and its clean porcelain, `hipblasLtGetVersion = 100401` (probe rebuilt), `--families` =
`qwen4exp qwen35moe` and `--geometry` = `flash_next` (both exit 0), the `gemm.cu:322` gate, and the
family↔GGUF mapping. Owner-facing acceptance criteria **1, 2 and 5** are satisfied by this handoff.
Criteria **3** (one baseline per family) and **4** (Route 2 vs Route 3) are not met and are not in
this handoff's scope.

**Checkpoint 1a — Model policy applied (`--strict`): still pending.**
`python3 workflow/check_model_policy.py --strict` exits **2** with `PENDING: 3 role(s) have no
explicit model: architect, coder-primary, coder-secondary` (QAQC = `gemini-4-argon`, auditor =
`deepseek-v4.1-flash`). This audit therefore runs under **DEC-009 / WAIVER-001** and is a `WAIVED`,
not `PASS`, row on `workflow/OWNER_AUDIT_CHECKLIST.md`. `DEC-014` assigns the owner's independent
final audit to **Mistral 4**; that is a separate, later checkpoint and is the compensating check for
the auditor/architect model-family overlap.

**Checkpoints 2–5 (002 Mixtral / 003 Qwen / 004 DeepSeek / 005 Route decision): untouched and
blocked** — see the scope question below, and `DEC-010`.

### 8.1 Open owner decisions

| # | Decision | Status | Why it is still open |
|---|---|---|---|
| 2 | Mixtral 8x7B Q4_K_M pack | **open** | The family is not implemented at the pin (§8.2). The choice now depends on whether the owner wants support added first. |
| 3 | Qwen3-30B-A3B Q4_K_M vs Qwen1.5-MoE-A2.7B | **open, options partly obsolete** | Qwen3-30B-A3B is not an implemented family at the pin. The *supported* Qwen MoE is `qwen35moe` = **Qwen3.6-35B-A3B**, which is **not** Qwen3-30B-A3B. |
| 4 | DeepSeek-V2-Lite vs DeepSeek-MoE-16B | **open** | DeepSeek is a *retired* family the Control refuses (`strata_control/retired.py:19`, `strata_control/runtime.py:561`), not an engine family. |
| 5 | Timebox (1–2 days for the build spike) | **open, and partly consumed** | Checkpoint 1 used the 1-day build-spike budget. The owner should confirm the remaining budget for 006 and the baselines. |
| 1 | Strata commit pin | **answered by the architect, needs owner ratification** | Pinned `baf16363b4403ef0ed4f538f5d5ed11c43fb9535` at kickoff (`DEC-007`), with provenance in the evidence bundle. |

### 8.2 The scope question the evidence created

Your intent in §1 asks for "one small-MoE baseline per family: **Mixtral 8x7B, Qwen3-30B-A3B,
DeepSeek**". The 001 evidence shows that at the pinned commit **none of the three is an implemented
engine family**:

- `strata --families` reports the GGUF architectures this build runs: `qwen4exp qwen35moe`
  (= Qwen3.8-Flash-Next and Qwen3.6-35B-A3B), compiled in at
  `src/program/generate.cpp:3566-3574`.
- `grep -rni 'mixtral' src/ include/ strata_control/` → exit 1 (no match);
  `grep -rni 'qwen3moe\|30b-a3b' …` → exit 1 (no match); DeepSeek is retired and refused by the
  Control.
- The family the upstream gfx1150 community bench measured — Qwen3.8-Flash-Next — **is** supported
  (as `qwen4exp`), so the bench prior art is usable.

This is already routed, and the routing is consistent with your "low-tier tests on all model classes"
direction: **`DEC-010`** puts a read-only support investigation (**HO-006**) first, then adds the
cheapest family, then runs low-tier tests on every supported class — with **HO-002/003/004 blocked
on HO-006**. What the record still lacks is *your* amendment to §1, because §1 as written cannot be
executed. The choices, for the owner (not for the architect):

1. **Accept `DEC-010` support-first** and re-point decisions 2–4 from "which pack" to "which family
   do we add support for first" (recommended — it keeps your all-classes goal and costs one
   read-only handoff before any download).
2. **Descope §1** to a Qwen3.8-Flash-Next baseline (supported today) plus a Qwen3.6-35B-A3B
   baseline, and drop Mixtral/Qwen3-30B-A3B/DeepSeek from the immediate plan.
3. **Hold 002–005** until support is added for the three named families — a much larger, open-ended
   effort that `DEC-010` explicitly does not commit to.

Nothing is downloaded, installed or run while this is unanswered. **Status: awaiting the owner.**

