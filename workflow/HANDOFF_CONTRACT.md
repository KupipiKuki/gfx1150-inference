# Handoff contract (normative)

**Version:** 1.0 · 2026-11-15
**Status:** binding for every work package in this project.
**How to read:** MUST / MUST NOT / SHOULD are normative. A handoff that does not
meet the MUST clauses is not `READY`.

---

## 1. The handoff is the unit of work

A handoff is a file at `workflow/handoffs/<ID>.md`, created from
`templates/HANDOFF.md`. Chat messages, issue comments and verbal agreements are
**not** handoffs. If it is not in the file, it is not in scope.

**ID format:** `HO-<project>-<nnn>` (zero-padded), e.g. `HO-STRATA-007`.
Rework: `RW-<HO-ID>-<n>`. Deviation: `DR-<HO-ID>-<n>`. Owner task:
`OT-<project>-<nnn>`.

## 2. Handoff types

| Type | From → To | Purpose |
|---|---|---|
| `ARCHITECT_TO_CODER` | Architect → Primary/Secondary Coder | implement a work package |
| `CODER_TO_QAQC` | Coder → QAQC | request independent review |
| `QAQC_TO_AUDITOR` | QAQC → Auditor | pass/fail report and evidence |
| `AUDITOR_TO_ARCHITECT` | Auditor → Architect | audit verdict and final-review request |
| `OWNER_TASK` | Owner → Auditor | owner intent, instructions, evidence, oversight |
| `REWORK` | Reviewer → Coder | fix a failed criterion |
| `DEVIATION` | Any → Architect | scope/technical change decision |

## 3. Required fields (MUST)

Every handoff MUST contain:

1. **ID**, **type**, **state**, **created/updated** (UTC), **author**.
2. **From** and **to** roles (named, not "the team").
3. **Title** (one line) and **work package** (ID/slug).
4. **Branch** and **base commit** (SHA); the repository and path.
5. **Scope** — what is included, with files/areas.
6. **Out of scope** — what is explicitly excluded.
7. **Inputs** — specs, designs, prior handoffs, decisions, model/data hashes.
8. **Acceptance criteria** — numbered, measurable, each with a command or a
   check; no "looks good".
9. **Evidence required** — commands, outputs, artifacts, hashes; where they go.
10. **Guard rails** — files not to touch, dependencies not to add, commands not
    to run, claims not to make.
11. **Dependencies / blockers** — with owner and expected resolution.
12. **Priority and timebox** — P0/P1/P2 and the target date/hours.
13. **Definition of Ready** — the checklist in §5, marked.
14. **Definition of Done** — the checklist in §6, marked.
15. **Signatures** — sender and receiver (role + date).

If a field is genuinely not applicable, write `N/A — <reason>`; do not omit it.

## 4. Acceptance criteria

Each criterion MUST be:

- **Specific** — one behavior or artifact.
- **Measurable** — a command, a test, a diff, a file, a hash, or a count.
- **Reproducible** — the receiver can run it without asking.
- **Bounded** — it does not require a different environment or model.

The coder MUST NOT invent criteria. If a criterion is ambiguous, the handoff
returns `NEEDS_INFO` to the architect.

## 5. Definition of Ready (DoR) — the ready gate

The architect MUST mark every item before the state becomes `READY`:

- [ ] ID, type, from/to, title, work package present.
- [ ] Branch and base commit exist and are named.
- [ ] Scope and out-of-scope are explicit.
- [ ] Inputs are linked and available (paths/hashes).
- [ ] Every acceptance criterion has a command or check.
- [ ] Evidence requirements are explicit and runnable.
- [ ] Guard rails are explicit.
- [ ] Dependencies are resolved or named with an owner.
- [ ] Priority/timebox is set.
- [ ] No unresolved `NEEDS_INFO` from the receiver.

The receiver MUST reject an incomplete handoff with `NEEDS_INFO` and the exact
missing fields; the receiver MUST NOT start work.

## 6. Definition of Done (DoD) — the coder gate

The coder MUST mark every item before `CODER_DONE`:

- [ ] Code/tests/docs are committed on the work-package branch.
- [ ] The branch is based on the named base commit; the diff is in scope.
- [ ] Every acceptance criterion was run; the raw output is in the evidence
      manifest.
- [ ] Tests pass; failures/skips are recorded verbatim with the reason.
- [ ] No new dependency, file, or command outside the guard rails.
- [ ] No secrets, tokens, PATs, or private data in the repo/logs.
- [ ] The evidence manifest is complete (`templates/EVIDENCE_MANIFEST.md`).
- [ ] The handoff is updated to `CODER_DONE` and the QAQC handoff is created.

## 7. Evidence contract

Every handoff MUST have `workflow/evidence/<ID>/` containing:

- `manifest.md` — the filled `EVIDENCE_MANIFEST` template.
- `commands.log` — the exact commands, cwd, env, and exit codes.
- `test-output.txt` — raw output; failures kept verbatim.
- `artifacts/` — logs, JSON, screenshots, reports.
- `hashes.txt` — SHA256 of the model, prompt, dataset, and key artifacts.

Rules:

- Commands MUST be copy-paste reproducible; include the working directory,
  Python/ROCm/compiler versions, and any environment variables that matter.
- Outputs MUST be raw; do not paraphrase a failure.
- A claim ("works", "faster", "supported") MUST cite the command and the output.
- Secrets MUST be redacted; a token in the evidence is a failed handoff.
- One profile per claim: hardware, model family, quantization, workload.

## 8. Reviewer contracts

### QAQC

- Reviews the handoff and the evidence; runs the acceptance commands itself.
- Checks the diff against scope and guard rails.
- Writes `workflow/reports/qaqc/<ID>-qaqc.md` (template).
- Returns PASS (to auditor) or FAIL (to coder via `REWORK`).
- MUST NOT modify code, tests, docs, or configuration.

### Auditor

- Reviews the coder's and QAQC's work and evidence.
- Verifies the claims, the guard rails, the scope, and the evidence manifest.
- Writes `workflow/reports/audit/<ID>-audit.md` (template).
- Returns PASS (to architect) or FAIL (to coder/QAQC via `REWORK`).
- MUST NOT modify code, tests, docs, or configuration.
- For owner tasks, is the single intake: writes the `OWNER_TASK`, detailed
  instructions, evidence requirements, and progress oversight.

### Architect

- Reviews the audit and the evidence; checks the acceptance criteria and scope.
- Signs `templates/ARCHITECT_APPROVAL.md` to move to `DONE`.
- Decides deviations and records them in `DECISIONS.md`.
- Merges only after QAQC PASS + auditor PASS + architect SIGNED.

## 9. Rework contract

A rework handoff MUST contain:

- Original HO ID and the failed criterion/criteria.
- The exact evidence that failed (command, output, line, hash).
- The required fix and the guard rails (fix only this; no scope expansion).
- The evidence required to prove the fix.
- A new `RW-<HO-ID>-<n>` ID and the reviewer who will re-check.

The coder MUST acknowledge within 4 working hours; a second failure on the same
criterion escalates to the architect.

## 10. Deviation contract

A deviation request MUST contain:

- Original scope and the proposed change.
- Reason and the problem it solves.
- Cost, risk, and schedule impact.
- Evidence/claims impact (what must be re-measured).
- Options (at least two) and a recommendation.

Only the architect decides. The decision is recorded in `DECISIONS.md`, and the
handoff's scope/criteria/evidence are updated before work continues. Silent
scope drift is a process failure; the auditor MUST flag it.

## 11. Owner-task contract

The owner's work enters through the auditor only. The `OWNER_TASK` MUST contain:

- Owner intent in the owner's words.
- Scope and out-of-scope.
- Decisions the owner must make (with options and a recommendation).
- **Detailed instructions** for the technical roles.
- **Evidence requirements** (what will prove completion to the owner).
- Progress checkpoints and who reports.
- Acceptance criteria and the owner's final approval.
- Links to the architect handoffs and the evidence.

The auditor assigns the work through the architect's handoffs, tracks the
status, and reports to the owner. The owner's acceptance is recorded in the
`OWNER_TASK`.

## 12. Template index

| Template | Use |
|---|---|
| `templates/HANDOFF.md` | any handoff type |
| `templates/REWORK.md` | rework request |
| `templates/QAQC_REPORT.md` | QAQC review |
| `templates/AUDIT_REPORT.md` | audit review |
| `templates/OWNER_TASK.md` | owner task intake |
| `templates/EVIDENCE_MANIFEST.md` | evidence bundle |
| `templates/ARCHITECT_APPROVAL.md` | final approval |
| `templates/DEVIATION_REQUEST.md` | scope/technical change |

## 13. Rejection and appeal

- `NEEDS_INFO` is a valid state; the handoff returns to the sender with the
  exact missing fields.
- A disputed PASS/FAIL goes to the auditor; a disputed audit goes to the
  architect; a disputed scope goes to the owner through the auditor.
- The record is the file, not the chat.

---

**Effective:** 2026-11-15. Changes to this contract require an architect
decision recorded in `DECISIONS.md` and an auditor review.
