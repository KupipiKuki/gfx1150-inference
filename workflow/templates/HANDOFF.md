# HO-<project>-<nnn> — <title>

| Field | Value |
|---|---|
| **ID** | HO-<project>-<nnn> |
| **Type** | ARCHITECT_TO_CODER / CODER_TO_QAQC / QAQC_TO_AUDITOR / AUDITOR_TO_ARCHITECT |
| **State** | PROPOSED |
| **Created / updated (UTC)** | <date> / <date> |
| **From → To** | <role> → <role> |
| **Work package** | <slug> |
| **Branch / base commit** | `wp/<project>-<HO-ID>-<slug>` / `<sha>` |
| **Priority / timebox** | P0/P1/P2 · <date or hours> |

## 1. Scope (in)

- <what to do, with files/areas>

## 2. Out of scope

- <explicit exclusions; no silent expansion>

## 3. Inputs

| Input | Path / hash | Status |
|---|---|---|
| spec / design | | |
| prior handoff | | |
| model / data | | |

## 4. Acceptance criteria

| # | Criterion | Command / check | Expected |
|---|---|---|---|
| 1 | | | |
| 2 | | | |

## 5. Evidence required

- `workflow/evidence/<ID>/manifest.md`
- `commands.log`, `test-output.txt`, `artifacts/`, `hashes.txt`
- <specific artifacts>

## 6. Guard rails

- Do not touch: <files/areas>
- Do not add dependencies without architect approval.
- Do not change acceptance criteria or scope.
- Do not merge or push to `main`.
- No performance/claims without the evidence commands.
- No secrets in the repo, logs, or handoff.

## 7. Dependencies / blockers

| Dependency | Owner | Status | Needed by |
|---|---|---|---|
| | | | |

## 8. Definition of Ready

- [ ] ID/type/from/to/title/work package present
- [ ] Branch and base commit named
- [ ] Scope and out-of-scope explicit
- [ ] Inputs linked and available
- [ ] Every criterion has a command/check
- [ ] Evidence requirements runnable
- [ ] Guard rails explicit
- [ ] Dependencies resolved or owned
- [ ] Priority/timebox set
- [ ] No open `NEEDS_INFO`

## 9. Definition of Done

- [ ] Code/tests/docs committed on the branch
- [ ] Every criterion run; raw output in the manifest
- [ ] Tests pass; failures/skips recorded verbatim
- [ ] No out-of-scope edits or new dependencies
- [ ] No secrets
- [ ] Evidence manifest complete
- [ ] Handoff updated; next handoff created

## 10. Signatures

| Role | Name/agent | Date | Decision |
|---|---|---|---|
| Sender | | | |
| Receiver | | | |

## 11. Log

- <UTC> <role>: <state change / note>
