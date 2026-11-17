---
name: Rework loop
description: Issue and consume a rework handoff when an acceptance criterion fails, without expanding scope
---

# Rework loop

Use when QAQC, the auditor, or the architect fails an acceptance criterion.
Template: `workflow/templates/REWORK.md`.

## Issue (reviewer)

1. Create `workflow/handoffs/RW-<HO-ID>-<n>.md`.
2. Name the original HO and the exact failed criterion/criteria.
3. Quote the evidence that failed: command, output, line, hash.
4. State the **minimal** required fix and the files/areas allowed.
5. State the evidence required to prove the fix.
6. Do not add new scope; if the fix needs a scope change, raise a deviation
   instead.
7. Set the state `REWORK`; the coder acknowledges within 4 working hours.

## Consume (coder)

1. Read the rework file, not a chat summary.
2. Fix only the failed criterion; no unrelated changes.
3. Re-run the **full** acceptance set, not only the failed item.
4. Update `workflow/evidence/<HO-ID>/` with the new run.
5. Return the handoff to the same reviewer; do not self-approve.

## Close

- The reviewer re-checks and records PASS/FAIL.
- A second failure on the same criterion escalates to the architect.
- Rework history stays in the handoff log; do not delete it.
