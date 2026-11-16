# Architect approval — <HO-ID>

| Field | Value |
|---|---|
| **Handoff** | HO-<project>-<nnn> |
| **Architect** | |
| **Date (UTC)** | |
| **Decision** | SIGNED / REJECTED |
| **Merge commit** | `<sha>` (after signoff) |

## 1. Criteria trace

| # | Criterion | Evidence | QAQC | Audit | Architect |
|---|---|---|---|---|---|
| 1 | | | PASS/FAIL | PASS/FAIL | PASS/FAIL |

## 2. Gate evidence

- [ ] QAQC report: `workflow/reports/qaqc/<HO-ID>-qaqc.md` — PASS
- [ ] Audit report: `workflow/reports/audit/<HO-ID>-audit.md` — PASS
- [ ] Evidence manifest complete.
- [ ] Scope matches the handoff; no drift.
- [ ] Guard rails respected.
- [ ] No secrets; no unsupported claims.

## 3. Conditions / follow-ups

- <condition, owner, due date>

## 4. Decision

- **SIGNED** → state `DONE`; merge authorized; record the merge commit and the
  evidence directory.
- **REJECTED** → state `REWORK`; create `RW-<HO-ID>-<n>` with the failed
  criteria.

| Role | Signature | Date |
|---|---|---|
| Architect | | |
