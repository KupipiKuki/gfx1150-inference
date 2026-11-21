# Session kickoff — Strata on gfx1150

**Current handoff: [`SESSION_HANDOFF_2026-11-22.md`](SESSION_HANDOFF_2026-11-22.md).**
Start there; this file is only the pointer and the paste block.

The original 2026-11-15 kickoff (project start, HO-001 READY) is superseded — see
the git history of this file if it is ever needed.

## State in one line

Strata builds and runs `qwen35moe` on gfx1150 (measured), the `deepseek` family is
recognised and refused by name with its geometry and 363-tensor inventory in place
(S1–S3, PR open), and all three test families have a pinned llama.cpp oracle. S4
(the DeepSeek forward pass) is the next step and is **not** authorised.

## Paste this into a new session, after selecting the **architect** agent

```text
Resume the Strata project. Read workflow/SESSION_HANDOFF_2026-11-22.md, then
workflow/STATUS.md and workflow/DECISIONS.md, then workflow/MODEL_POLICY.md.
We are merging the HO-012 PR and deciding the QAQC seat before anything else.
Do not start S4 until I authorize it.
```
