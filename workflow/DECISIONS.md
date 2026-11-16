# Decision log

Dated decisions with ID, context, options, decision, consequences and affected
handoffs. Only the architect decides; the auditor reviews. A decision not in
this file did not happen.

## DEC-001 — Split the 780M out of Strata

- **Date:** 2026-11-15
- **Context:** the 780M has 32 GB unified RAM; the Strata end targets need
  gfx1150's 92 GB (or gfx1100 + RAM/SSD). The dense engine and Strata have
  different abstractions and evidence.
- **Options:** keep the 780M in Strata; split it; drop it.
- **Decision:** split. The 780M is a full `gfx-inference` dense continuation
  (Phase 8); Strata is gfx1150-only for now.
- **Consequences:** separate branch/evidence; no Strata 780M claims; the 780M
  may later consume a small Strata model if it fits.
- **Affected:** `00`–`05`, `08`, `09`, `10`; agent scope.

## DEC-002 — Route 2 before Route 3

- **Date:** 2026-11-15
- **Context:** the audit showed the P0–P9 fork framework front-loads work for
  four hardware classes before validating Strata on the hardware we own.
- **Options:** Route 1 (current engine), Route 2 (modify Strata directly),
  Route 3 (fork + P0–P9).
- **Decision:** Route 2, as a pinned patch overlay; upstream PRs optional.
  Route 3 is the escalation annex.
- **Consequences:** gfx1150 Stage 1 spike first; P0–P9 only on an escalation
  trigger.
- **Affected:** `07`, `08`, `03`.

## DEC-003 — Three gfx1150 test beds

- **Date:** 2026-11-15
- **Context:** Strata's design center is Qwen, Mistral and DeepSeek.
- **Options:** one model; one per family; the full end targets.
- **Decision:** one small MoE per family: Mixtral 8x7B, Qwen3-30B-A3B,
  DeepSeek-V2-Lite or DeepSeek-MoE-16B. End targets stay on gfx1150/gfx1100.
- **Consequences:** model-family support work is exercised early; the
  architecture-adjacent test is preferred (8x7B → 8x22B, V2-Lite → v2).
- **Affected:** `09`, `08`.

## DEC-004 — MI25 deferred

- **Date:** 2026-11-15
- **Context:** five MI25 cards owned, but the OCuLink adapters and a hardware
  build are not ready; gfx900 is not in current ROCm.
- **Options:** start the feasibility now; defer; drop.
- **Decision:** defer. `06-mi25-feasibility.md` is the plan for when one card is
  physically usable; it never blocks Strata.
- **Consequences:** no MI25 work in P0–P9; no MI25 claims.
- **Affected:** `06`, `08`, `03` S0.

## DEC-005 — Handoff-contract workflow adopted

- **Date:** 2026-11-15
- **Context:** the previous project had road bumps from implicit scope and
  late evidence.
- **Options:** ad-hoc chat; a formal handoff contract; a full ticketing system.
- **Decision:** adopt this handoff-contract workflow and the OpenCode role
  agents/skills.
- **Consequences:** no handoff, no work; no evidence, no done; the auditor is
  the owner-task intake; the architect is the final approver.
- **Affected:** `workflow/`, `.opencode/agents`, `.opencode/skills`.

## DEC-006 — Role-model exclusivity

- **Date:** 2026-11-15
- **Context:** a model that serves two roles can approve or review its own work.
  The role prompts separate duties, but the model configuration must too.
- **Options:** allow shared models; require distinct models only for coder/QAQC;
  full role-model exclusivity.
- **Decision:** full role-model exclusivity.
  - The **architect model** is exclusive to the architect; it cannot take any
    other role.
  - The **auditor model** is exclusive to the auditor and is the project's
    strongest reasoning model.
  - The **architect and auditor are barred from all other roles**.
  - The **coder and QAQC must use different base models**; variants
    (`#high`/`#max`) of the same base do not count as different.
  - Each role gets an explicit `model` once the active agent is free; until
    then the policy is **PENDING**.
- **Enforcement:** `workflow/check_model_policy.py --strict`.
- **Status:** adopted; application pending (the active agent must not be
  modified while in use).
- **Affected:** `.opencode/agents/*`, `workflow/MODEL_POLICY.md`,
  `workflow/check_model_policy.py`, `workflow/README.md`.

## DEC-007 — Pin Strata to a commit (`baf16363`)

- **Date:** 2026-11-15
- **Context:** HO-STRATA-001 needs a base commit before READY; OT-STRATA-001
  decision 1 asks for "latest `main`" vs a pinned release/tag, and the owner's
  session directive is "pin the Strata commit and record it". Strata `main` moves
  often (7350 tracked files, frequent release manifests), so an unpinned base
  makes every later baseline unreproducible.
- **Options:** (a) follow `origin/main` tip; (b) pin the tip at kickoff; (c) pin a
  release tag (`rc/0.1.30`); (d) pin the community-validated engine `e8ca9af`.
- **Decision:** (b) pin `origin/main` at kickoff:
  `baf16363b4403ef0ed4f538f5d5ed11c43fb9535`
  (`2026-11-15 20:46:59 +0100`, "release manifest: the Control 0.1.60.1 packages
  of the 0.2.14.1 update"). Clone at `/home/kupipi/Documents/git/strata`,
  provenance in `workflow/evidence/HO-STRATA-001/artifacts/pinned-commit.txt`.
  No release tag is newer, and `e8ca9af` is a 0.1.40.2-era engine from the
  community report — kept as prior art, not as the base.
- **Consequences:**
  - Every handoff 001–005 names this SHA; a later bump is a new decision.
  - Baselines in 002–004 are reproducible against it, including the
    `tools/hip/gfx1150-hipblaslt-100401.txt` table
    (SHA256 `aee2867c096887cccaef8bc04a9ef10adec43da58421edfdaaec04a61ec5549c`).
  - The Strata tree is read-only for HO-STRATA-001: no source edits, so the
    build is judged against upstream as-is (Route 2 patches come later, under
    HO-STRATA-005 and a deviation).
- **Affected:** HO-STRATA-001 … HO-STRATA-005.

## DEC-008 — Two checkouts: evidence in the workflow repo, Strata read-only

- **Date:** 2026-11-15
- **Context:** the HO-STRATA-001 draft named one work-package branch but two
  repositories, and its guard rail ("do not touch the `gfx1150-inference` repo")
  contradicted its own evidence path (`workflow/evidence/HO-STRATA-001/`).
- **Options:** (a) evidence inside the Strata checkout; (b) evidence in the
  workflow repo with the Strata checkout read-only; (c) evidence in both.
- **Decision:** (b). The work-package branch
  `wp/<project>-<HO-ID>-<slug>` lives in `gfx1150-inference` and carries only
  `workflow/evidence/<ID>/**` plus the handoff file. The Strata checkout
  (`/home/kupipi/Documents/git/strata`) is a pinned, read-only input: no branch,
  no commit, `git status --porcelain` empty at CODER_DONE.
- **Consequences:** one branch per handoff still holds; the pinned SHA stays
  meaningful; a needed Strata source change becomes a blocker/deviation, not an
  edit; QAQC can re-run the build from a clean tree. Evidence logs are tracked by
  an explicit negation in `.gitignore` (`!workflow/evidence/**/*.log`) instead of
  `git add -f`, so the contract's `commands.log` is versioned by rule.
- **Affected:** HO-STRATA-001 … HO-STRATA-005.

## DEC-007 — Temporary auditor model waiver (WAIVER-001)

- **Date:** 2026-11-15
- **Context:** the owner's other APIs are not incorporated yet; the auditor is
  temporarily set to `opencode-go/deepseek-v4.1-flash`.
- **Decision:** accept the R2/R5 violation under **WAIVER-001**. The auditor
  shares the DeepSeek family with the architect until the auditor moves to a
  different family (target: `opencode-go/gpt-6-luna#max`).
- **Risk:** correlated blind spots between the architect and auditor. The
  architect's final review and the owner are the compensating checks; QAQC and
  the evidence bundle are unchanged.
- **Expiry:** when the other APIs are incorporated and the auditor moves to a
  different family. Then remove the waiver from
  `workflow/model_policy.json`, rerun `check_model_policy.py --strict` (must
  return PASS), and record the change.
- **Affected:** `.opencode/agents/auditor.md`, `workflow/MODEL_POLICY.md`,
  `workflow/model_policy.json`, `workflow/check_model_policy.py`.
