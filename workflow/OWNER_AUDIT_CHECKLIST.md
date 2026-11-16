# Owner independent audit checklist

Use **after the workflow’s own cycle** (QAQC PASS → auditor PASS → architect
SIGNED) and **before owner acceptance/merge**. The owner is independent of the
coder, QAQC, auditor and architect; this is the final check on the evidence.

## Owner audit record

| Field | Value |
|---|---|
| Auditor | Owner (independent of the workflow roles) |
| Model/tool | **Mistral 4** |
| Date | 2026-11-16 |
| Handoff/commit | HO-STRATA-001 @ `76034a0`; independent report `95c4cec` |
| Verdict | **ACCEPT (build/support portion)** |
| Notes | Grade A; 8/8 HO criteria; 19/19 hashes; cross-family criteria 3–4 remain blocked (DEC-016); qwen35moe low-tier authorized (HO-007/DEC-017). |

**HO-STRATA-007:** accepted without a second owner audit (DEC-019). The workflow
chain executed cleanly (independent QAQC on Gemini/Argon; auditor PASS under
WAIVER-001; architect SIGNED) and the output reproduced five times. No Mistral 4
record is produced for this handoff; HO-001's audit remains the independent
check of the process. The earlier HO-001 record above is unaffected.

The owner audit is a **fresh, read-only session**: it may write only this record
and the owner verdict in `OT-STRATA-001`.

## 1. Contract and scope

- [ ] Handoff state is `SIGNED`/`DONE`; the signature is the architect’s.
- [ ] Scope and out-of-scope are explicit; no silent drift.
- [ ] Definition of Ready and Done are marked.
- [ ] Every acceptance criterion has a command/check and a matching evidence
      row.
- [ ] Guard rails were respected (files, dependencies, commands, claims).
- [ ] One work package per branch; no merge before signoff.

## 2. Evidence

- [ ] `workflow/evidence/<ID>/manifest.md` is complete.
- [ ] Commands are copy-paste reproducible; cwd/env/versions recorded.
- [ ] Outputs are raw; failures/skips kept verbatim.
- [ ] Hashes match the artifacts; model/prompt/data hashes recorded.
- [ ] No secrets, tokens, PATs, or private data.
- [ ] No model weights in git.
- [ ] Re-run the acceptance commands yourself and compare; do not trust the
      summary.

## 3. Model separation

- [ ] QAQC report names its model; it ran on the assigned family (Gemini/Argon
      for HO-001’s re-run).
- [ ] Auditor model is recorded; WAIVER-001/DEC-009 is in force and reported as
      `WAIVED`, not `PASS`.
- [ ] Architect/coder models are set; no role shares a family except an
      approved waiver.
- [ ] The OpenCode usage UI shows the expected model for each role; no silent
      session-model fallback.
- [ ] No per-call `model` override was used by the architect.
- [ ] The owner audit model is recorded (**Mistral 4**) and is independent of
      the coder, QAQC, auditor and architect; it is not one of the role models.

## 4. Rework

- [ ] The rework handoff names the failed criterion and the exact evidence.
- [ ] QAQC returned findings/rework, **not code edits**; the coder made the
      fix.
- [ ] The coder fixed only the failed scope; no expansion.
- [ ] QAQC re-verified the fix; the report records the re-check.
- [ ] A second failure on the same criterion escalated.

## 5. Claims and findings

- [ ] No performance, support or quality claim without an artifact.
- [ ] The profile is named (hardware, model, quant, workload).
- [ ] The family finding is recorded: the pinned build supports **qwen4exp**
      (Qwen3.8-Flash-Next) and **qwen35moe** (Qwen3.6-35B-A3B) only; Mixtral /
      Qwen3-30B-A3B / DeepSeek are unsupported.
- [ ] The “no model loaded” limit is stated where applicable.

## 6. Checkouts and repository

- [ ] Workflow repo: branch/commit named; evidence tracked (log negation rule).
- [ ] Strata checkout: pinned SHA recorded; `git status --porcelain` empty
      (read-only, DEC-008).
- [ ] No source edits in the investigation/build handoff unless a deviation
      allowed them.

## 7. Decisions and status

- [ ] DEC IDs are unique; DEC-009 (auditor waiver), DEC-010 (support-first),
      DEC-012 (hybrid investigation), DEC-013 (launch rule) are present.
- [ ] No duplicate DEC-007.
- [ ] `STATUS.md` matches the handoff state and evidence links.
- [ ] `OT-STRATA-001` checkpoints are current.

## 8. Verdict

- [ ] **ACCEPT** or **REJECT**, with the evidence and the date.
- [ ] Record the owner verdict in `OT-STRATA-001`.
- [ ] Any deviation/waiver has an owner and an expiry.

---

## HO-STRATA-001 specifics

- **Setup exception:** the QAQC review ran on the session model (DeepSeek V4.1
  Flash) before the QAQC assignment; it found AC-4 FAIL and the rework.
- **Required before audit:** a **new QAQC child session on Gemini/Argon** after
  the model assignment and a reload/fresh session; the audit cannot cite the
  DeepSeek QAQC as independent.
- **Rework:** `RW-HO-STRATA-001-1` fixed the family mapping and tuning-gate
  citations; QAQC must re-verify.
- **Build result:** gfx1150 HIP build exit 0; `--families` = `qwen4exp
  qwen35moe`; no model loaded; AC-5 refusal recorded verbatim.
- **Model policy:** auditor DeepSeek under WAIVER-001/DEC-009; QAQC Gemini;
  architect/coders pending (the coder used the session model as a setup
  exception).
- **Branches:** workflow repo `wp/strata-001-gfx1150-build`; Strata pinned
  `baf16363...` read-only.
