---
name: Handoff contract
description: Create, validate, accept, and transition an engineering handoff (HO) with a firm Definition of Ready and Done
---

# Handoff contract

Use before creating or accepting any handoff. The normative contract is
`workflow/HANDOFF_CONTRACT.md`; the template is
`workflow/templates/HANDOFF.md`.

## Create (sender)

1. Choose the type: `ARCHITECT_TO_CODER`, `CODER_TO_QAQC`,
   `QAQC_TO_AUDITOR`, `AUDITOR_TO_ARCHITECT`.
2. Copy `templates/HANDOFF.md` to `workflow/handoffs/HO-<project>-<nnn>.md`.
3. Fill every required field:
   - ID, type, from/to, title, work package, branch/base commit.
   - Scope and **out-of-scope**.
   - Inputs (paths/hashes).
   - Numbered, measurable acceptance criteria with a command/check.
   - Evidence requirements (manifest, commands, artifacts, hashes).
   - Guard rails (files, dependencies, commands, claims).
   - Dependencies, priority/timebox.
4. Mark the Definition of Ready. If any item is open, the state stays
   `PROPOSED`; do not send it.
5. Set `READY` and add a row to `workflow/STATUS.md`.

## Accept (receiver)

1. Read the handoff file, not a chat summary.
2. Validate the DoR. If a field is missing or a criterion is untestable, set
   `NEEDS_INFO` with the exact missing fields and **do not start**.
3. If the work needs a change outside the guard rails, raise a `DEVIATION`
   (see the `scope-deviation` skill); do not expand scope.
4. Set `IN_PROGRESS` and log the acceptance.

## Transition

- Coder: `IN_PROGRESS` → `CODER_DONE` only when the DoD is satisfied and the
  evidence manifest is complete.
- QAQC: `CODER_DONE` → `QAQC_REVIEW` → `AUDIT_REVIEW` (PASS) or `REWORK` (FAIL).
- Auditor: `AUDIT_REVIEW` → `ARCHITECT_APPROVAL` (PASS) or `REWORK` (FAIL).
- Architect: `ARCHITECT_APPROVAL` → `DONE` (SIGNED) or `REWORK` (REJECTED).

Only the named role makes its transition. Do not self-approve.

## Reject an incomplete handoff

Write `NEEDS_INFO` in the state and the log, list the missing fields, and return
it to the sender. No work starts on `NEEDS_INFO`.
