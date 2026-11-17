# QAQC report — <HO-ID>

| Field | Value |
|---|---|
| **Handoff** | HO-<project>-<nnn> |
| **Reviewer** | QAQC |
| **Date (UTC)** | |
| **Verdict** | PASS / FAIL |
| **Scope reviewed** | <files/diff/commit> |

## 1. Acceptance criteria re-run

| # | Criterion | Command | Observed | Pass? |
|---|---|---|---|---|
| 1 | | | | |

## 2. Diff and guard-rail review

- [ ] Diff is within scope; no unrelated files.
- [ ] No new dependencies without approval.
- [ ] No secrets/tokens in the diff, logs, or evidence.
- [ ] Tests are meaningful; no skips hidden as passes.
- [ ] Evidence matches the commands that were run.

## 3. Findings (severity order)

| # | Severity | Finding | File:line / evidence | Required action |
|---|---|---|---|---|
| 1 | Blocker/Major/Minor | | | |

## 4. Verdict and next state

- **PASS** → `AUDIT_REVIEW`; attach this report and the evidence path.
- **FAIL** → `REWORK`; create `RW-<HO-ID>-<n>` with the failed criteria.

## 5. Statement

I did not modify code, tests, docs, or configuration. This report is the only
artifact I wrote.
