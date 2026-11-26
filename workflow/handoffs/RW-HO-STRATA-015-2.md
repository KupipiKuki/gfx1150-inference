# RW-HO-STRATA-015-2 — evidence-only rework: the margin in the bundle must be the one on the gate's trajectory

| Field | Value |
|---|---|
| **ID** | RW-HO-STRATA-015-2 |
| **Original handoff** | HO-STRATA-015 (S4b) |
| **Issued by** | Architect, on audit finding **A9** (`workflow/reports/audit/HO-STRATA-015-audit.md`) |
| **To** | `coder-primary` |
| **Date (UTC)** | 2026-11-26 |
| **State** | ISSUED |
| **Scope** | evidence only — **no code, no gate value, no bound, no reference, no prompt, no cells** |

## 1. The failed criterion

The audit's verdict is **REWORK, evidence-only**: the gate passes and the gate
change is justified, but the **bundle still explains it with the wrong numbers**.

`manifest.md:76` and `artifacts/llama-ref-moe.md:69-70` quote the router margin as
**2.80e-4 probability / 6.62e-3 logit** against 6.8e-5…7.12e-5 of drift. Those
values come from `ffn_inp-19` of the **Q4_K_M oracle**. The gate's trajectory is
the **exact-f32** reference, where the margin is **3.36e-6 probability /
7.95e-5 logit** (oracle) and **1.74e-6 / 4.10e-5** (engine) — i.e. **tighter than
the drift**, which is exactly what makes the flip predicted rather than tolerated.

As written, a reader of the bundle alone would conclude the flip is *not*
explained by a near-tie, and would have to distrust the deviation. DEC-046's
erratum ordered this correction; it was applied to the decision log, the handoff
and the DR by the architect, but **not to the bundle's own files**.

## 2. Required fix (this and nothing else)

1. **`artifacts/llama-ref-moe.md:69-70`** — replace the Q4_K margins with the
   exact-f32 ones (`3.36e-6` prob / `7.95e-5` logit), and say which trajectory they
   belong to; keep the Q4_K value only if labelled as the shipped pack's
   trajectory, if you still need it for context.
2. **`manifest.md:76`** — same correction, with one sentence naming the audit's
   third measurement: the observed drift moves the 33↔40 logit gap by
   **+1.385e-4, 1.74× the margin**, and even with identical input the engine's own
   f32 arithmetic moves expert 40's logit by `3.84e-5` — so the swap is inside the
   arithmetic noise, not a defect.
3. **Add `artifacts/router-margin-19-1.txt`**: the recomputation on the exact-f32
   trajectory (top-7 probabilities, both top-6 sets, the 6th/7th margins, the drift
   at that cell) with the command that produced it, committed and hashed, so the
   number in the prose has an artifact.
4. **Rehash**, rebuild `test-output.txt` after the final capture (DEC-041 §2),
   re-run `check_bundle.py workflow/evidence/HO-STRATA-015 --strict` → PASS,
   re-run the verdict-consistency check, `git status --porcelain` clean.
5. Append a log line to `HO-STRATA-015.md` §11 referencing RW-2.

## 3. Evidence required to close

- `artifacts/router-margin-19-1.txt` with its command.
- The corrected lines quoted from both files (paste them).
- `check_bundle --strict` verdict and count, the hash count, and the verdict-consistency result.
- Commit SHA on `wp/strata-015-deepseek-s4b`.

## 4. Guard rails

Do not touch `src/**`, the Strata tree, `teacher_outputs.bin`, the gate value
`1.569942e-04`, the 5e-3 bound, the reference dump, the prompt, the positions, the
cell counts, the free-running informational report, `DECISIONS.md`, or the
audit/QAQC reports. If the exact-f32 margin you recompute disagrees with the
auditor's `3.36e-6 / 7.95e-5`, **stop and report the discrepancy** rather than
editing the prose to match.
