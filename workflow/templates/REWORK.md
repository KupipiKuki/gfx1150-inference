# RW-<HO-ID>-<n> — rework request

| Field | Value |
|---|---|
| **Rework ID** | RW-<HO-ID>-<n> |
| **Original handoff** | HO-<project>-<nnn> |
| **From → To** | <QAQC / Auditor / Architect> → <Coder> |
| **State** | REWORK |
| **Created (UTC)** | <date> |
| **Reviewer** | <role> |

## 1. Failed criterion/criteria

| # | Criterion | Evidence (command + output/line) |
|---|---|---|
| 1 | | |

## 2. Required fix

- <the minimal change that satisfies the criterion>
- <files/areas allowed>
- <do not expand scope>

## 3. Evidence required to prove the fix

- <command(s) and expected output>
- <artifacts/hashes>

## 4. Guard rails

- Fix only the failed criterion; no unrelated changes.
- No new dependencies without approval.
- Re-run the full acceptance set, not only the failed item.
- Update `workflow/evidence/<HO-ID>/` with the new run.

## 5. Acknowledgment

| Role | Date | Note |
|---|---|---|
| Coder | | |

**Escalation:** a second failure on the same criterion goes to the architect.
