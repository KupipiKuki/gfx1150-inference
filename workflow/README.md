# Engineering workflow — quickstart

A handoff-contract workflow for solo/agent teams. It turns every piece of work
into a named contract with measurable acceptance, required evidence, and a
role-exclusive state machine.

## Read

1. [`ENGINEERING_WORKFLOW.md`](ENGINEERING_WORKFLOW.md) — roles, authority,
   RACI, states, gates, branches, owner tasks.
2. [`HANDOFF_CONTRACT.md`](HANDOFF_CONTRACT.md) — the normative contract.
3. [`STATUS.md`](STATUS.md) — the live board.
4. [`DECISIONS.md`](DECISIONS.md) — deviation/scope decisions.
5. [`templates/`](templates/) — copy these; do not invent formats.

## The loop

```text
Architect writes HO-...  ->  Coder implements + evidence  ->  QAQC review
        ^                                                        |
        |                                                        v
Architect signs  <-  Auditor review  <-  QAQC PASS + report
        |
        v
      merge
```

- **No handoff, no work.**
- **No evidence, no done.**
- **No QAQC PASS, no audit.**
- **No audit PASS, no architect approval.**
- **No architect approval, no merge.**

## Roles

| Role | Agent | Writes | Cannot |
|---|---|---|---|
| Architect | `architect` | handoffs, approvals, decisions, status | approve without QAQC + audit |
| Primary coder | `coder-primary` | code/tests/docs in scope, evidence | change scope, merge, push to main |
| Secondary coder | `coder-secondary` | low-priority code, evidence | P0/P1 work, merge |
| QAQC | `qaqc` | QAQC reports, rework requests | modify code/tests/docs |
| Auditor | `auditor` | audit reports, rework, owner tasks | modify code/tests/docs, final-approve |

## OpenCode

- Agents: `.opencode/agents/{architect,coder-primary,coder-secondary,qaqc,auditor}.md`.
- Skills: `.opencode/skills/{handoff-contract,evidence-bundle,rework-loop,owner-task-intake,scope-deviation}/SKILL.md`.
- Default agent: `architect` (`.opencode/opencode.json`).
- To use: ask the architect for a work package; it writes the handoff and
  launches the coder/QAQC/auditor. For owner tasks, talk to the auditor.

## Owner tasks

The owner talks to the **auditor**, who writes `OT-...` with detailed
instructions, evidence requirements, checkpoints and acceptance, assigns the
work through the architect, and oversees progress. The owner accepts the final
result.

## First handoff to write

`HO-STRATA-001 — gfx1150 Stage 1 spike`: build upstream Strata for gfx1150,
record the toolchain/friction, run the three test beds (Mixtral 8x7B,
Qwen3-30B-A3B, DeepSeek), and record a baseline per family. The architect
writes it; the coder executes; QAQC/auditor review; the architect signs.

## Reuse in the next repo

Copy `workflow/` and `.opencode/` to the new repository root. Keep the
`workflow/` history; do not copy the old evidence unless it is an input.
