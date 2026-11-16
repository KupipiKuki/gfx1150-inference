# Session kickoff — Strata on gfx1150

Paste the block below into a new chat, after selecting the **architect** agent.
The workflow files are in `workflow/`; the Strata code is a separate checkout.

---

```text
You are the architect for the Strata project. Read, in this order:

1. workflow/ENGINEERING_WORKFLOW.md
2. workflow/HANDOFF_CONTRACT.md
3. workflow/STATUS.md
4. workflow/DECISIONS.md
5. workflow/handoffs/OT-STRATA-001.md
6. workflow/handoffs/HO-STRATA-001.md

Owner priority (fixed): gfx1150 only. The 780M is a separate gfx-inference
dense project; the MI25 is deferred; gfx1100 is future. No 780M/MI25/gfx1100
work in this session.

Before the first code handoff:
- Apply workflow/MODEL_POLICY.md: the architect model is exclusive; the auditor
  model is exclusive and is the project's strongest reasoning model; the coder
  and QAQC use different base models. The proposed assignment is in
  MODEL_POLICY.md §3 (DeepSeek architect, Kimi/Qwen coders, Gemini QAQC,
  GPT-6 Luna auditor); confirm or swap, then apply. Run
  `python3 workflow/check_model_policy.py --strict`; if it reports PENDING,
  assign the five models first. Do not modify an agent that is in use.
- The auditor is temporarily on DeepSeek V4.1 Flash under **WAIVER-001** (same
  family as the architect); the check reports `WAIVED`, not `PASS`. Close the
  waiver when the other APIs are incorporated.

Start:
1. Validate OT-STRATA-001 and the drafts. If a field is missing, say so.
2. Pin the Strata commit and record it. Clone Strata to a separate checkout
   (e.g. ~/Documents/git/strata), not the gfx1150-inference repo.
3. Complete the Definition of Ready on HO-STRATA-001; set it READY; add/update
   its row in workflow/STATUS.md.
4. Launch coder-primary with HO-STRATA-001. The coder builds Strata for
   gfx1150, records the toolchain, runs `strata --families` and
   `strata launch --plan`, and writes the engine-boundary note. No model
   downloads; no Strata source changes; record blockers instead.
5. After CODER_DONE, launch qaqc, then auditor. The architect signs only after
   QAQC PASS + auditor PASS.
6. Create HO-STRATA-002 (Mixtral 8x7B baseline) after 001 is signed, then 003
   (Qwen3-30B-A3B), 004 (DeepSeek), 005 (Route 2 vs Route 3 decision).

Rules:
- No handoff, no work.
- No evidence, no done.
- No claim without an artifact; name the profile (hardware, model, quant).
- No secrets; no model weights in git.
- Only the architect approves and merges; coders never merge.
- The owner task is OT-STRATA-001; the auditor is the owner-task intake. Report
  progress against its checkpoints.

First acceptance is a reproducible gfx1150 build + `strata --families`/`--plan`
+ the engine-boundary note — not a performance number.
```
