---
name: Owner task intake
description: "Auditor-only intake for owner requests: detailed instructions, evidence requirements, checkpoints, and owner acceptance"
---

# Owner task intake

Use when the **owner** asks for work. The auditor is the single intake; the
owner does not hand work directly to a coder. Template:
`workflow/templates/OWNER_TASK.md`; file:
`workflow/handoffs/OT-<project>-<nnn>.md`.

## Intake

1. Quote the owner's intent in the owner's words; do not paraphrase it away.
2. Write the scope and the out-of-scope.
3. List the decisions the owner must make, with options and a recommendation.
4. Write **detailed instructions** for each technical role:
   - Architect: plan, handoff IDs, acceptance/evidence.
   - Primary/Secondary coder: what to implement.
   - QAQC: what to verify.
   - Auditor: what to audit, which checkpoints.
5. Write the **evidence requirements**: the commands, artifacts, hashes,
   environment, and limits that will prove completion to the owner.
6. Set progress checkpoints (plan, implementation, QAQC, audit, owner
   acceptance) with owners and dates.
7. Write owner-facing acceptance criteria.
8. Assign the technical work through the architect's handoffs; do not implement.

## Oversight

- Track each checkpoint; report status to the owner at the agreed cadence.
- Verify that the architect's handoffs and the evidence match the owner task.
- If the scope changes, raise a deviation; do not silently alter the owner task.
- Record the owner's acceptance or rejection in the owner task.

## Hard rules

- The owner does not bypass the auditor's intake.
- The auditor does not implement or approve the final result.
- No owner task without evidence requirements.
- No "done" without the owner's acceptance.
