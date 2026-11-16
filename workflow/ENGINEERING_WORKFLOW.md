# Engineering workflow — handoff contract v1

**Status:** adopted for the next project (and reusable).
**Source of truth:** this file + `HANDOFF_CONTRACT.md` + the templates.
**OpenCode mapping:** `.opencode/agents/*` (roles) and `.opencode/skills/*`
(procedures). The agents are the roles; the skills are the procedures they load.

---

## 1. Purpose

Make every piece of work a **handoff with a contract**: a named sender, a named
receiver, a measurable definition of done, required evidence, and a state
machine. No work starts from a chat message. No work moves forward without the
evidence the next role needs.

This is the response to the previous project's road bumps: implicit scope,
review after the fact, evidence assembled at the end, and rework discovered at
the gate.

## 2. Roles and authority

| Role | Owns | May | May not |
|---|---|---|---|
| **Architect** | Project implementation, handoffs, final approval, deviation and scope-drift decisions | Write handoffs, set acceptance/evidence, approve or reject, decide deviations, merge after signoff | Approve without QAQC + audit reports; silently expand scope |
| **Primary Coder** | Implementation of assigned work packages | Edit code/tests/docs in scope, run builds/tests, commit to the work-package branch, produce evidence | Change scope, merge, push to `main`, invent acceptance criteria, add dependencies without approval |
| **Secondary Coder** | Low-priority coding tasks | Same as primary, for low-priority handoffs | Same as primary; no high-priority scope |
| **QAQC** | Independent review per the architect handoff | Run the acceptance commands, inspect diffs/evidence, write QAQC reports, assign rework per auditor/architect handoff | Modify code/docs/tests; merge; approve a release; hide a failed test |
| **Auditor** | Review of coder and QAQC work; rework before architect final review; **owner-task intake and oversight** | Verify evidence, assign rework, write audit reports, receive owner tasks, write detailed instructions/evidence requirements, track progress | Modify code/docs/tests; final-approve; merge |
| **Owner** | Scope, budget, priorities, final product acceptance | Set direction, approve scope/budget, accept the final result | Bypass the auditor's owner-task intake; approve without the evidence |

**Authority rule:** the architect is accountable for delivery; the auditor is
accountable for the integrity of the evidence and the review. Neither can do
the other's job. The owner decides *what* and *why*; the architect decides
*how*; the auditor decides whether the *evidence* supports the claim.

**Model separation (DEC-006).** The architect's model is exclusive to the
architect; the auditor's model is exclusive to the auditor and is the project's
strongest reasoning model; the coder and QAQC MUST use different base models
(variants of the same base do not count). The architect and auditor are barred
from every other role. See `MODEL_POLICY.md`; enforce with
`python3 workflow/check_model_policy.py --strict` once the models are assigned.
The policy is **PENDING** until the active agent is free.

## 3. RACI

| Activity | Architect | Primary Coder | Secondary Coder | QAQC | Auditor | Owner |
|---|---|---|---|---|---|---|
| Scope / priorities | C | I | I | I | C | **A/R** |
| Work-package handoff | **A/R** | I | I | I | C | I |
| Implementation | A | **R** | **R** (low priority) | I | I | I |
| Acceptance criteria | **A/R** | C | C | C | C | I |
| QAQC review | A | C | C | **R** | C | I |
| Audit review | C | C | C | C | **A/R** | I |
| Rework assignment | C | R | R | C | **A/R** | I |
| Final approval | **A/R** | I | I | C | C | C |
| Deviation / scope drift | **A/R** | R (raise) | R (raise) | C | C | C |
| Owner-task intake | C | I | I | I | **A/R** | C |
| Merge | **A/R** | I | I | C | C | I |

## 4. Artifacts and layout

```text
workflow/
  ENGINEERING_WORKFLOW.md      this file
  HANDOFF_CONTRACT.md          normative contract
  STATUS.md                    live status board (one row per handoff)
  DECISIONS.md                 deviation/scope decisions
  handoffs/                    HO-*.md (one file per handoff)
  evidence/                    HO-*/ manifest, logs, artifacts, hashes
  templates/                   HANDOFF, REWORK, QAQC_REPORT, AUDIT_REPORT,
                               OWNER_TASK, EVIDENCE_MANIFEST,
                               ARCHITECT_APPROVAL, DEVIATION_REQUEST
  reports/qaqc/                QAQC reports (only QAQC writes here)
  reports/audit/               audit reports (only Auditor writes here)
```

- A handoff is a **file**, not a chat message. The file is the contract.
- The evidence directory is named by the handoff ID.
- Only the owning role writes its report directory; QAQC and Auditor are
  read-only everywhere else.

## 5. The handoff is the unit of work

Every handoff has an ID: `HO-<project>-<nnn>` (e.g., `HO-STRATA-007`). It moves
through the state machine below. A handoff that is not `READY` is not work.

The full contract (required fields, definition of ready/done, validation,
rejection) is in [`HANDOFF_CONTRACT.md`](HANDOFF_CONTRACT.md). The short form:

- **Sender** and **receiver** are named roles, not "the team."
- **Scope** is explicit; **out of scope** is explicit.
- **Acceptance criteria** are measurable and testable.
- **Evidence** is specified before work starts, not after.
- **Guard rails** are explicit (files, dependencies, commands, claims).
- **Definition of Ready (DoR)** must be satisfied before `READY`.
- **Definition of Done (DoD)** must be satisfied before `DONE`.

## 6. State machine

```text
PROPOSED
  -> READY            (architect: DoR satisfied)
  -> IN_PROGRESS      (coder: accepted)
  -> CODER_DONE       (coder: DoD + evidence)
  -> QAQC_REVIEW      (qaqc: started)
  -> AUDIT_REVIEW     (qaqc: PASS, report attached)
  -> ARCHITECT_APPROVAL (auditor: PASS, report attached)
  -> DONE             (architect: final approval)
```

Side states:

- `NEEDS_INFO` — receiver rejects an incomplete handoff; returns to sender.
- `REWORK` — QAQC/auditor/architect sends a rework handoff to the coder.
- `BLOCKED` — coder/QAQC/auditor cannot proceed; names the blocker and owner.
- `DEVIATION` — scope/technical change under architect decision.
- `DEFERRED` / `CANCELLED` — architect decides; recorded in `DECISIONS.md`.

**Transitions are role-exclusive:**

| Transition | Only |
|---|---|
| PROPOSED → READY | Architect |
| READY → IN_PROGRESS | Coder |
| IN_PROGRESS → CODER_DONE | Coder |
| CODER_DONE → QAQC_REVIEW | QAQC |
| QAQC_REVIEW → AUDIT_REVIEW | QAQC (PASS) |
| QAQC_REVIEW → REWORK | QAQC (FAIL) |
| AUDIT_REVIEW → ARCHITECT_APPROVAL | Auditor (PASS) |
| AUDIT_REVIEW → REWORK | Auditor (FAIL) |
| ARCHITECT_APPROVAL → DONE | Architect (SIGNED) |
| ARCHITECT_APPROVAL → REWORK | Architect (REJECTED) |
| Any → DEVIATION | Architect (or receiver raises) |
| Any → BLOCKED | Receiver or reviewer |
| Any → DEFERRED/CANCELLED | Architect |

## 7. Gates

1. **Ready gate:** the handoff passes the DoR checklist. No code before READY.
2. **Coder gate:** the coder's evidence manifest is complete; the code is
   committed on the work-package branch; the acceptance commands were run.
3. **QAQC gate:** the QAQC report reproduces the acceptance commands, checks the
   diff, and records PASS/FAIL with findings. No code changes.
4. **Audit gate:** the auditor verifies the evidence, the QAQC report, the
   claims, and the guard rails; PASS or REWORK.
5. **Architect gate:** the architect checks the criteria, the evidence, the
   audit, and the scope; SIGNED or REJECTED. Only then merge.

## 8. Evidence rules

Every handoff has an evidence manifest (`templates/EVIDENCE_MANIFEST.md`):

- **Commands** are copy-paste reproducible, with working directory and env.
- **Outputs** are raw; failures are kept verbatim, not paraphrased.
- **Artifacts** have a path and a SHA256; models/prompts/datasets have hashes.
- **Environment** records OS, kernel, driver, compiler, runtime, and versions.
- **No secrets**: redact PATs/tokens/keys; never commit them.
- **No claim without an artifact**: "works", "faster", "supported" require the
  command and the output that show it.
- **One profile per claim**: name the hardware, model family, quantization and
  workload; a result on one profile does not transfer to another.

## 9. Branch, commit, merge

- One work package per branch: `wp/<project>-<HO-ID>-<slug>`.
- Commit subject: `<HO-ID>: <summary>`; body: what/why/evidence/limits.
- The coder may commit and push the **work-package branch**.
- The coder **must not** merge or push to `main`.
- The architect merges only after QAQC PASS, auditor PASS, and architect SIGNED.
- Force-push is forbidden on shared branches; rewrite only your own work-package
  branch, and say so in the handoff.
- The merge commit references the HO ID and the evidence directory.

## 10. Rework loop

Rework is a **new handoff**, not a chat correction:

1. The reviewer writes `RW-<HO-ID>-<n>.md` with the failed criterion, the
   exact evidence, and the required fix.
2. The coder accepts, fixes only the failed scope, and attaches new evidence.
3. The handoff returns to the same reviewer; no silent scope expansion.
4. A second failure on the same criterion escalates to the architect.

## 11. Deviation and scope drift

- The coder/reviewer **raises** a `DEVIATION_REQUEST`; only the architect
  decides.
- The request names the original scope, the proposed change, the reason, the
  cost/risk, and the evidence impact.
- The architect records the decision in `DECISIONS.md` and updates the handoff
  (scope, criteria, evidence) before work continues.
- Silent scope drift is a process failure; the auditor flags it.

## 12. Owner tasks

The owner does **not** hand work directly to a coder. The flow is:

```text
Owner -> Auditor (intake) -> Architect (plan/handoff) -> Coder/QAQC -> Auditor -> Owner (accept)
```

The auditor is the single intake for owner tasks:

- Writes the `OWNER_TASK` with the owner's intent, scope, decisions needed,
  **detailed instructions**, **evidence requirements**, checkpoints, and
  acceptance criteria.
- Assigns the technical work through the architect's handoffs.
- Oversees progress, verifies the evidence, and reports status to the owner.
- Records the owner's final acceptance or rejection.

The owner may talk to the architect for context, but the **task of record** is
the auditor's `OWNER_TASK`.

## 13. Status and decisions

- `STATUS.md`: one row per handoff — ID, title, state, owner, branch, next
  action, blocker, evidence link. The architect/auditor keep it current.
- `DECISIONS.md`: dated decisions with ID, context, options, decision,
  consequences, and the handoffs affected.
- A handoff without a status row is invisible; add it when it becomes READY.

## 14. Review timeboxes (defaults)

| Step | Target |
|---|---|
| QAQC review | 1 working day after CODER_DONE |
| Auditor review | 1 working day after QAQC PASS |
| Architect approval | 1 working day after audit PASS |
| Rework acknowledgement | 4 working hours |
| Blocked escalation | 4 working hours to the architect |
| Scope drift | immediately to the architect |

The owner can override per project; record overrides in `DECISIONS.md`.

## 15. Hard rules

1. No handoff, no work.
2. No evidence, no done.
3. No QAQC PASS, no audit.
4. No audit PASS, no architect approval.
5. No architect approval, no merge.
6. No silent scope change.
7. No claim without an artifact.
8. No secrets in the repo, logs, or handoffs.
9. One work package per branch; one branch per handoff.
10. The auditor is the owner-task intake; the architect is the final approver.

## 16. OpenCode mapping

- **Roles** are agents: `architect` (primary), `coder-primary`,
  `coder-secondary`, `qaqc`, `auditor` (subagents).
- **Procedures** are skills: `handoff-contract`, `evidence-bundle`,
  `rework-loop`, `owner-task-intake`, `scope-deviation`.
- The architect launches the subagents with a handoff file; the subagents load
  the matching skill and follow the contract.
- The user can ask the architect to start a work package; the architect writes
  the handoff, then launches the coder. The auditor is launched for review, and
  for owner tasks.
- The default agent is set in `opencode.json`; the agent definitions are in
  `.opencode/agents/`.
