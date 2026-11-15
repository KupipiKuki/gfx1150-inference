---
name: Scope deviation
description: Raise and decide a deviation or scope-drift request with the architect, without silent scope expansion
---

# Scope deviation

Use when the work needs a change outside the handoff scope, or a technical
blocker makes the written scope impossible. Template:
`workflow/templates/DEVIATION_REQUEST.md`; file:
`workflow/handoffs/DR-<HO-ID>-<n>.md`.

## Raise (any role)

1. **Stop.** Do not make the out-of-scope change.
2. Write the deviation request:
   - original scope;
   - proposed change (files/areas/behavior);
   - reason the original cannot be met;
   - impact: cost, schedule, risk, evidence/claims, dependencies;
   - at least two options with pros/cons and a recommendation.
3. Set the state `DEVIATION`; notify the architect.

## Decide (architect)

1. Review the options and the evidence impact.
2. **APPROVE** or **REJECT**; do not leave it implicit.
3. Record the decision in `workflow/DECISIONS.md` with an ID, context, options,
   decision, consequences, and affected handoffs.
4. Update the handoff's scope, acceptance criteria, evidence, and timebox
   before work resumes.
5. If the change affects the owner's task, update the `OWNER_TASK` through the
   auditor.

## Resume

- The coder resumes only after the handoff is updated and `READY`.
- The reviewer checks the new scope, not the old one.
- Silent scope drift is a process failure; the auditor flags it.

## Rule

A deviation is a decision record, not a chat agreement. If it is not in
`DECISIONS.md`, it did not happen.
