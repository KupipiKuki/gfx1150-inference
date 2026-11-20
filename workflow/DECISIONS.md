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

## DEC-009 — Temporary auditor model waiver (WAIVER-001)

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

## DEC-010 — Model-class coverage: support first, then low-tier tests on all

- **Date:** 2026-11-15
- **Context:** HO-STRATA-001 found the pinned build supports only `qwen4exp`
  (Qwen3.8-Flash-Next) and `qwen35moe` (Qwen3.6-35B-A3B). The owner wants
  low-tier tests on **all** model classes, not Qwen-only.
- **Decision:** after HO-001 is SIGNED, run **HO-006** (read-only support
  investigation: Qwen3-30B-A3B, Mixtral 8x7B, DeepSeek-V2-Lite/MoE-16B), add
  support for the cheapest family first, then run low-tier tests on every
  supported class. No class is declared supported before its low-tier test.
  HO-STRATA-002/003/004 are blocked on HO-006.
- **Consequences:** the test-bed plan changes from immediate runs to
  support-first; the end targets (8x22B, DeepSeek v2/V4) share the path with
  their small representatives; a class that needs a new kernel/attention path is
  a large deviation and may be descoped by the architect. The route decision
  (HO-005) uses the low-tier results.
- **Affected:** DEC-003, `STATUS.md` 002–005, HO-006,
  `planning/strata-engine/11-model-support-investigation.md`.

## DEC-011 — Large-model feasibility track (DeepSeek V4 Flash, MiniMax M3.1 Flash)

- **Date:** 2026-11-15
- **Context:** the owner wants to investigate support for two large MoEs:
  DeepSeek V4 Flash and MiniMax M3.1 Flash. Both are far beyond the small
  family representatives in HO-006.
- **Decision:** add **HO-STRATA-007** as a separate **north-star feasibility
  track** after HO-006. No implementation commitment: capacity, architecture
  gap, and effort/risk first. It does not block the small-model low-tier tests.
- **Preliminary facts (external; verify):** V4 Flash 284B/13B, 1M context, MIT,
  Q4 ~167 GB; V4.1 Flash 552B backbone/8–16B active; MiniMax M3.1 Flash
  428B/23B, 1M, 2-bit ~143.9 GB. Both exceed the gfx1150's 92 GB at usable
  quants; a gfx1100 host with 128–256 GB RAM + SSD and new
  attention/quantization paths is required. The 780M/MI25 are out.
- **Consequences:** HO-006 remains the near-term path; HO-007 may change the
  Route 2 vs Route 3 decision; no support/performance claim until a measured
  low-tier run on the target host.
- **Affected:** DEC-003, DEC-010, `STATUS.md` HO-005/HO-007,
  `planning/strata-engine/12-large-model-support-investigation.md`.

## DEC-012 — Large-model track is investigative; a hybrid join is a candidate

- **Date:** 2026-11-15
- **Context:** the owner wants the DeepSeek V4 Flash / MiniMax M3.1 Flash work
  to remain **purely investigative**. A hybrid path joining the
  `gfx-inference` and Strata branches may be the outcome, rather than adding
  the models to Strata or building a new engine.
- **Decision:** no branch merge and no implementation now. HO-007 compares
  three routes: **A** add to Strata, **B** an independent large-model engine,
  **C** a hybrid joining the gfx-inference evidence/capability substrate with
  the Strata MoE engine. The 780M dense continuation remains separate for now.
  No merge before HO-007 and an owner decision.
- **Constraints:** the MoE engine must not import the per-layer Python boundary
  or the all-or-nothing residency model; one claims ledger/evidence trail across
  dense and MoE; MIT/attribution preserved; the hybrid is a shared substrate
  with a hard engine boundary, not one engine.
- **Consequences:** HO-005 becomes a three-way decision; DEC-001's split is a
  current boundary, not permanent; the large-model work has no implementation
  commitment.
- **Affected:** DEC-001, DEC-011, `planning/strata-engine/10` and `12`,
  HO-005/HO-007.

## DEC-013 — Subagent model is fixed at child-session launch

- **Date:** 2026-11-15
- **Context:** the HO-001 QAQC review ran on `opencode-go/deepseek-v4.1-flash`
  even though the QAQC agent was assigned Gemini at 19:42; the child session
  started at ~19:30. The OpenCode usage shows no Argon. The QAQC report itself
  flags this as finding F9.
- **Finding:** a subagent’s model is fixed when its child session starts; a
  mid-run agent-file change does not affect a running child. The architect can
  also override the model per `subagent` call, which defeats the file.
- **Decision:** assign role models before launching; do not launch a role while
  its model is `PENDING`; after a model change, reload the config or start a
  fresh session; the architect must not pass a `model` override. The HO-001
  QAQC review is a **setup exception**, not an independent QAQC; re-run it on
  Gemini before the audit. The audit cannot cite the DeepSeek QAQC as
  independent.
- **Consequences:** the QAQC re-review is a new child session on Gemini; the
  model usage must show Argon; the auditor reviews after that. The architect
  prompt gets a “no model override / no review while PENDING” rule when the
  active agent is free.
- **Affected:** `MODEL_POLICY.md`, QAQC handoff/report, HO-001,
  `SESSION_KICKOFF.md`, architect prompt (when free).

## DEC-014 — Owner audit uses Mistral 4

- **Date:** 2026-11-15
- **Context:** the owner will perform the final independent audit of HO-001
  with **Mistral 4** after the workflow cycle.
- **Decision:** the owner audit model is Mistral 4; it is outside the five role
  models and must be independent of them (not DeepSeek/Argon/Claude/GPT). The
  audit is a fresh, read-only session; it records the model, version, date and
  verdict in the owner audit record and in `OT-STRATA-001`.
- **Consequences:** the final audit is a different family from the coder
  (DeepSeek), QAQC (Argon/Gemini), auditor (DeepSeek) and architect (DeepSeek);
  no role model changes; the owner audit record is part of the evidence.
- **Affected:** `workflow/OWNER_AUDIT_CHECKLIST.md`, `OT-STRATA-001`.

## DEC-015 — HO-STRATA-001 merge is selective and deferred

- **Date:** 2026-11-16
- **Context:** HO-STRATA-001 is SIGNED. Its branch
  `wp/strata-001-gfx1150-build` is based on `a6166f7e` (the tip of
  `research/strata-memo`, **not** on `main`), local `main` is 41 commits behind
  `origin/main`, and three concurrent sessions committed on the branch during
  review. The audit (finding P1) counted four workstreams across 29 commits and
  82 files: the work package, a model-policy workstream (`MODEL_POLICY.md`,
  `model_policy.json`, `check_model_policy.py`, `.opencode/agents/*`,
  `ENGINEERING_WORKFLOW.md`, `README.md`, `SESSION_KICKOFF.md`), a planning
  workstream (`planning/strata-engine/10…12`, `OWNER_AUDIT_CHECKLIST.md`), and
  research. Merging the branch wholesale would put a **PENDING** model policy on
  `main` and would fast-forward 69 commits of unrelated work.
- **Options:** (a) fast-forward `main` to the branch; (b) merge the branch
  wholesale; (c) selective merge after the branch stops moving; (d) sign and
  defer the merge until the concurrent sessions settle.
- **Decision:** (d) then (c). The handoff is `DONE` and reviewable on its branch
  now; the merge happens once the branch is quiet, and it takes **only**:
  `workflow/evidence/HO-STRATA-001/**` (all 20 files **from one commit**, so
  `hashes.txt` stays true), `HO-STRATA-001.md`, `HO-STRATA-001-QAQC.md`,
  `HO-STRATA-001-APPROVAL.md`, `RW-HO-STRATA-001-1.md`, the QAQC report, the
  audit report, and the `.gitignore` evidence-log negation (DEC-008).
  `DECISIONS.md`, `STATUS.md` and `OT-STRATA-001.md` are shared and are taken
  hunk by hunk. Everything else on the branch is another workstream's and is
  merged (or not) on its own terms.
- **Consequences:** no fast-forward, ever; `290922d` is not rewritten; the
  evidence stays byte-identical to what QAQC and the auditor verified; the
  PENDING model policy cannot reach `main` through this handoff.
- **Affected:** HO-STRATA-001, HO-STRATA-002…006, `STATUS.md`.

## DEC-016 — Owner holds the support-first path: DEC-003 stays, 002–004 blocked

- **Date:** 2026-11-16
- **Context:** HO-STRATA-001 SIGNED with the measured family list
  (`qwen4exp` = Qwen3.8-Flash-Next, `qwen35moe` = Qwen3.6-35B-A3B) and the
  finding that Mixtral 8x7B, Qwen3-30B-A3B and DeepSeek are **not implemented**
  at the pin. DEC-010 (written while 001 was in review) proposed support-first:
  investigate (HO-006), implement the cheapest family, then low-tier tests, with
  HO-STRATA-002/003/004 blocked on HO-006. HO-006 was made `READY`.
  The owner was asked two questions and answered:
  1. **Do not launch HO-006 now** — "wait for my owner decisions first" (the
     OT-STRATA-001 decisions 2–5: packs, timebox).
  2. **Keep DEC-003 unchanged and block** — do not amend the three test beds,
     do not substitute the two supported Qwen families.
- **Options:** accept DEC-010 support-first; replace the beds with the supported
  Qwen families; keep DEC-003 and block. The owner chose **keep and block**.
- **Decision:**
  - **DEC-003 stands as written.** The three beds (Mixtral 8x7B,
    Qwen3-30B-A3B, DeepSeek-V2-Lite/MoE-16B) remain the cross-family test.
  - **HO-STRATA-002/003/004 → `BLOCKED`**, not "deferred on 006". They unblock
    only when (a) the family is implemented in a Strata build we can run on
    `gfx1150`, and (b) the owner has answered decisions 2–4 for the pack.
    A family-support implementation is a **deviation** and needs the owner's
    written go-ahead; nothing is forked or patched before that.
  - **HO-STRATA-006 → `DEFERRED`** (was READY). It is not cancelled: it stays
    the cheapest first step whenever the owner reopens support work. No coder is
    launched on it now.
  - **DEC-010 is superseded** on its sequence (006 → implement → low-tier):
    its premise (owner wants support work now) is not what the owner decided.
    The low-tier test definition in `planning/strata-engine/11` §2 is kept as a
    definition, not as an active plan.
  - **No new technical work starts** until the owner's OT decisions 2–5 are
    recorded by the auditor. The only open work is bookkeeping and the pending
    model-policy application.
- **Consequences:** the project pauses with 001 DONE and everything else blocked
  by an owner decision, which is honest rather than busy. The gfx1150 build
  baseline, the support surface and the engine boundary are established and
  reproducible; the next measured number requires either a supported family run
  (`qwen35moe` fits this host, ≈20–21 GiB at Q4) or an owner-approved support
  deviation.
- **Affected:** DEC-003, DEC-010, DEC-015; HO-STRATA-002…006; `STATUS.md`;
  `OT-STRATA-001.md`.

## DEC-017 — Owner accepts the build/support package; authorizes the qwen35moe low-tier test

- **Date:** 2026-11-16
- **Context:** the Mistral 4 independent audit accepted HO-STRATA-001 (build,
  support surface, engine boundary); the owner-facing cross-family criteria 3–4
  remain blocked by DEC-016 because the requested families are unimplemented at
  the pin. The supported `qwen35moe` family (Qwen3.6-35B-A3B) is the one real
  low-tier run available on gfx1150.
- **Decision:**
  - **Accept HO-STRATA-001** as the build/support package (criteria 1, 2, 5).
  - **Keep DEC-003 and HO-STRATA-002/003/004 `BLOCKED`** (no substitution).
  - **Keep HO-STRATA-006 `DEFERRED`** (read-only support investigation).
  - **Authorize HO-STRATA-007** — a single low-tier `qwen35moe` run on gfx1150:
    smallest practical quant, 512–2,048 context, 16–32 tokens, one fixed
    prompt, temperature 0; no performance/support claim.
  - **Merge HO-001 selectively later** (DEC-015); the test is its own
    work-package branch.
- **Consequences:** one real generation result without reopening family
  support; HO-005 (Route 2 vs Route 3) can use it; the cross-family beds remain
  blocked; the coder/QAQC/auditor models are set (architect remains the session
  model).
- **Affected:** OT-STRATA-001, `STATUS.md`, HO-STRATA-007, DEC-003, DEC-016.

## DEC-018 — QAQC write boundary vs the state-transition duty

- **Date:** 2026-11-16
- **Context:** `ENGINEERING_WORKFLOW.md` §4 makes QAQC read-only outside
  `workflow/reports/qaqc/`, while §6 gives QAQC the `QAQC_REVIEW → AUDIT_REVIEW`
  transition. The HO-007 QAQC run therefore wrote only its report and embedded
  the `QAQC_TO_AUDITOR` record in it; the coder-to-QAQC handoff still read
  `PROPOSED` (audit finding A-1).
- **Decision:**
  - The **QAQC report** is the authoritative record of the QAQC verdict and of
    the `QAQC_REVIEW → AUDIT_REVIEW` transition; the embedded
    `QAQC_TO_AUDITOR` block is sufficient.
  - The **architect mirrors** the state field and the QAQC signature line in
    the handoff file, attributing it to the QAQC report; QAQC does not edit
    handoffs, source, tests, docs, or configuration.
  - A separate `HO-*-AUDIT.md` file is optional, not required.
- **Consequences:** the write boundary stays intact and the handoff record no
  longer contradicts the report; future QAQC runs use this pattern.
- **Affected:** `ENGINEERING_WORKFLOW.md` §4/§6 interpretation,
  `HO-STRATA-007-QAQC.md`, `templates/QAQC_REPORT.md`.

## DEC-019 — Owner accepts HO-STRATA-007 without a second independent audit

- **Date:** 2026-11-16
- **Context:** the owner performed the Mistral 4 independent audit for HO-001
  (grade A). For HO-007 the owner judged that the workflow chain — coder (Kimi) →
  independent QAQC on Gemini/Argon → auditor on DeepSeek (WAIVED) → architect
  signoff, with 5 independent reproductions of the output — executed cleanly,
  and declined a second owner audit.
- **Decision:** HO-STRATA-007 is **accepted** on the workflow evidence. No new
  Mistral 4 audit is produced for this handoff; the owner-audit record notes the
  omission and its reason. HO-001's Mistral 4 audit stands as the independent
  check of the process itself.
- **Consequences:** HO-007 is `DONE` and eligible for merge; the evidence chain
  is unchanged; a future handoff can still request an owner audit. This is an
  acceptance decision, not a change to the audit requirement in the contract.
- **Affected:** `OT-STRATA-001`, `STATUS.md`, `OWNER_AUDIT_CHECKLIST.md`,
  `MERGE_PLAN.md`.

## DEC-020 — HO-005 is narrowed to "confirm Route 2 + define the Route 3 triggers"

- **Date:** 2026-11-17
- **Context:** the original HO-005 asked for a three-way Route 1/2/3 comparison
  and depended on HO-STRATA-006, which the owner held under DEC-016. The first
  low-tier run (HO-007) is now signed and merged, so two of the three inputs
  exist; the third can never arrive while the hold stands, and a comparison that
  cannot cost the fork is not a comparison.
- **Decision (owner):** narrow HO-005. It **confirms Route 2** and writes the
  **measurable triggers** that would reopen Route 3. Route 3 stays **deferred,
  not rejected**. No HO-006, no fork work, no new measurements.
- **Why this is not a formality:** the pinned overlay currently carries **zero
  patches** — HO-001 and HO-007 both ran with a clean Strata checkout; the cost
  of Route 2 today is an environment contract plus a pin.
- **Consequences:** the decision is recorded as DEC-021 after the evidence pack
  is assembled; the trigger table is the reversal record; HO-006 remains held;
  the decision document is a documentation work package, so QAQC/audit are
  recorded as `N/A — no code, no measurement` and the architect verifies the
  citations at the gate.
- **Affected:** HO-STRATA-005, `STATUS.md`, DEC-002, DEC-010, DEC-016.

## DEC-021 — Route 2 confirmed; Route 3 deferred with five triggers

- **Date:** 2026-11-17
- **Context:** HO-STRATA-005 (narrowed by DEC-020) assembled the recorded evidence
  from HO-001 and HO-007. The pinned Strata build at `baf16363` configures,
  builds, starts headlessly and runs one low-tier `qwen35moe` generation with
  **zero source patches**; the cost of the current route is two environment
  variables, an opt-in hipBLASLt table, and the `--native` invocation.
  Evidence: `workflow/evidence/HO-STRATA-005/route-decision.md` and its
  31-row citation map.
- **Options:**
  - Route 2 — pinned patch overlay (DEC-002), confirmed by this decision.
  - Route 3 — fork + P0–P9; not costed, because DEC-016 holds HO-006 and a
    comparison without the fork's price is not a comparison.
  - Status quo — rejected implicitly: the engine already works on gfx1150.
- **Decision:**
  1. **Confirm Route 2** as the delivery route for gfx1150.
  2. **Adopt five triggers** that reopen Route 3, each measurable:
     - **T1** a requested family needs an engine path the pin lacks and cannot be
       expressed as a localized patch (structural, not configuration, failure);
     - **T2** the patch set exceeds **5 files or 300 inserted lines** against the
       pin (working threshold, not a measured bound);
     - **T3** rebase conflicts on **2 of 3** consecutive pin updates, or the pin is
       abandoned upstream;
     - **T4** a second hardware class (gfx1100, gfx900/MI25, gfx1201) enters the
       critical path;
     - **T5** the deliverable becomes an independent, machine-gated engine with its
       own API/CLI contract.
  3. **Route 3 is deferred, not rejected.** T1/T2/T3 are architect decisions;
     T4/T5 need an owner scope decision through the auditor.
- **Reversal cost:** the patch inventory (currently zero) must be rebased and
  re-validated on the forked tree; the gfx1150 baseline from HO-001/HO-007 does
  not expire, but post-confirmation patches would be unproven on Route 3.
- **Consequences:** no fork work, no P0–P9, no new measurement; HO-006 stays
  deferred (DEC-016) and HO-002/003/004 stay blocked; T1 firing is what would
  start the support-investigation conversation, not this decision.
- **Affected:** HO-STRATA-005 (`DONE`), `STATUS.md`, DEC-002, DEC-010, DEC-016.

## DEC-022 — Architect model assigned (DeepSeek V4 Pro, max reasoning)

- **Date:** 2026-11-17
- **Context:** MODEL_POLICY R6 requires an explicit model for all five roles; the
  architect was the only role still unset, so `check_model_policy.py --strict`
  reported `PENDING` and exited 2. DEC-006 fixes the architect's family as
  DeepSeek; `opencode-go/deepseek-v4-pro` is available with `high`/`max`
  variants.
- **Decision:** architect = `opencode-go/deepseek-v4-pro#max`, recorded in
  `.opencode/agents/architect.md`. Family `deepseek`, exclusive to the architect
  (R1); no other role may use it (R7: variants do not count as different).
- **Consequences:**
  - `check_model_policy.py --strict` now exits **0** with `RESULT: WAIVED` — the
    remaining exception is WAIVER-001 (auditor also on `deepseek`), which is a
    disclosed exception, **not** a PASS.
  - The change takes effect in the **next** architect session: a subagent's or
    agent's model is fixed when the session starts (DEC-013), and the policy
    forbids editing an active agent mid-use. This session continues on the
    session model.
  - Family coverage is now: architect `deepseek`, coder-primary `kimi`,
    coder-secondary `qwen3.8`, QAQC `gemini`, auditor `deepseek` (waived).
- **Affected:** `.opencode/agents/architect.md`, `workflow/MODEL_POLICY.md`,
  WAIVER-001, DEC-006, DEC-013.

## DEC-023 — The architect stays on V4 Pro; heavy drafting goes to a coder

- **Date:** 2026-11-17
- **Context:** with the architect assigned (DEC-022), the owner proposed starting
  the architect on DeepSeek V4 Pro to review the package outline, then handing
  long work sections to Flash, on the grounds that Flash "is only temporarily
  fulfilling another role".
- **Analysis:**
  - Family-wise this is allowed: both are `deepseek`, and the policy separates by
    family (R7). No R1 breach.
  - But Flash **is** the auditor (WAIVER-001). Using it for architect work means
    the same model writes a document and audits it — collapsing the overlap from
    "same family" to "same model", which is exactly what the waiver bounds. The
    compensating layer above QAQC would become the owner audit alone.
  - The cost case is negligible: a 50k-in/10k-out section is ≈$0.053 on V4 Pro
    and ≈$0.014 on Flash, about 4¢ per section.
  - The mechanism already exists: HO-005 ran as architect-contract →
    coder-assembled evidence → architect-verified signature.
- **Decision:** the **architect seat stays on `opencode-go/deepseek-v4-pro#max`**.
  Long documents are delegated **by role, not by model**: `coder-secondary`
  (Qwen) for pure assembly, `coder-primary` (Kimi) when drafting needs
  reasoning; the architect writes the handoff, verifies, and signs. The
  architect's model is not downgraded for cost or latency; if latency is a
  problem, the work is split into smaller handoffs.
- **Consequences:** the auditor's model never authors what it reviews; the model
  policy needs no new waiver; the drafting path is a normal handoff with its own
  evidence and guard rails. WAIVER-001 is unchanged.
- **Affected:** `MODEL_POLICY.md` §3 (drafting rule), DEC-022, WAIVER-001,
  HO-STRATA-005 (the precedent).

## DEC-024 — Hash immutable artifacts; pin mutable shared files by commit

- **Date:** 2026-11-18
- **Context:** HO-STRATA-005's `hashes.txt` listed two files that live on `main`
  and change: `workflow/DECISIONS.md` and
  `workflow/evidence/HO-STRATA-007/manifest.md`. After DEC-022/023 and the
  HO-007 model-path PR landed, `sha256sum -c` reported both `FAILED` — the
  decision's evidence rotted without anything in the decision changing.
- **Decision:** `hashes.txt` covers **immutable** files only (the handoff's own
  documents, raw run outputs, signed approvals). Mutable shared inputs are
  **pinned by commit**: the base SHA the work was assembled from, with
  `git show <sha>:<path> | sha256sum` and the resulting digest recorded in
  `hashes-notes.txt`.
- **Why:** a working-tree hash of a file that others append to is not a proof of
  stability, it is a delayed failure. A commit pin is immutable and verifiable
  with one command.
- **Consequences:** no periodic rehashing of evidence for unrelated commits; the
  `evidence-bundle` skill now states the rule; HO-005 applies it and verifies
  16/16 hashed files.
- **Affected:** `evidence-bundle` skill, HO-STRATA-005 evidence,
  `HANDOFF_CONTRACT.md` §7 interpretation.

## DEC-025 — Next phase prepared: model inventory + a bounded family probe

- **Date:** 2026-11-18
- **Context:** the owner downloaded the alternate (smaller) quants — Mixtral 8x7B
  Q3_K_M (18.96 GiB) and DeepSeek-MoE-16B Q4_K_M (10.10 GiB) — and asked to
  prepare the next development phase. Both files are intact (SHA256 matches the
  LFS objects). The signed engine lists only `qwen4exp qwen35moe`.
- **Decision:**
  1. Register every pack in `workflow/MODELS.md` with size, SHA256, GGUF arch and
     support status, so evidence bundles cite one source instead of restating
     paths.
  2. Prepare **HO-STRATA-008**, a bounded probe: one load-and-generate attempt per
     family on the signed binary, classified as REFUSED,
     LOADED-UNSUPPORTED, or FAILED-OTHER, with raw output. No source change, no
     flag tuning, no support work.
  3. **Implementation stays held (DEC-016).** The probe is evidence for DEC-021
     trigger T1; it does not authorize family support, a fork, or HO-006.
- **Why a probe and not a test:** the Mixtral GGUF reports arch `llama`. If the
  engine has a generic llama path, it could load and emit plausible text — a
  silent wrong-path success that looks like support. The probe distinguishes that
  from a clean refusal before anyone invests in support work.
- **Consequences:** the next phase has a concrete first step with a defined
  stopping point; the hold remains until the result is reviewed and the owner
  decides whether T1 fired.
- **Affected:** `workflow/MODELS.md`, HO-STRATA-008, `STATUS.md`, DEC-016,
  DEC-021.

## DEC-026 — Family probe accepted: the refusal is a loader contract (PLE), not a family string

- **Date:** 2026-11-18
- **Context:** HO-STRATA-008 probed the signed build with Mixtral 8x7B Q3_K_M
  (`llama`) and DeepSeek-MoE-16B Q4_K_M (`deepseek`). Both attempts were
  **REFUSED** before allocation with
  `--native requires --ple-gguf … no shard … holds per_layer_token_embd.weight`
  (`generate.cpp:4810-4823`). The first attempts hit `unknown argument: --n`
  because `--n` belongs to the `qwen35` path; `RW-008-1` corrected the flag.
- **Finding:** the generic native loader is **PLE-mandatory**. PLE is a model
  architecture component, not a user-supplied file, so `--ple-gguf` cannot be
  used to force these families; `--no-ple` is a diagnostic ablation that is
  itself refused. No silent dense fallback occurred — the engine refuses before
  allocating, which is the safer failure mode.
- **Decision:** accept the probe as **T1 evidence**. The build cannot load
  non-PLE families. Whether support is a localized patch or a new model class is
  **not** settled by this probe and belongs to a scoped investigation.
- **Consequences:** HO-006 stays **held** (DEC-016). The owner now has a precise
  question for it: *what does a non-PLE model class require, and is it a patch or
  a fork?* That question — not "which families exist" — is what T1 turns on.
- **Affected:** HO-STRATA-008 (`DONE`), `workflow/MODELS.md`, DEC-016, DEC-021.
- 
## DEC-027 — Family-support test plan prepared; execution waits on the owner

- **Date:** 2026-11-18
- **Context:** DEC-026 established that the engine cannot load non-PLE families
  (Mixtral `llama`, DeepSeek `deepseek`). The owner asked for a test plan to add
  model capabilities. The plan is
  `planning/strata-engine/13-family-support-test-plan.md`.
- **Decision:** adopt the plan as the working annex for family work. Its shape:
  reference-oracle first (llama.cpp pinned), then recognition → geometry → load →
  layer parity → token parity → baseline → review, with exact-token gates and a
  regression gate that re-runs the HO-007 command bit-for-bit.
- **Order:** Mixtral 8x7B first (downloaded, simplest routing, hardest dispatch),
  then DeepSeek-MoE-16B, then Qwen3-30B-A3B if a pack is fetched.
- **Status:** **prepared, not authorized.** DEC-016 still holds family work.
  The owner chooses: lift for S0 only (oracle + harness), lift for Mixtral
  S0–S7, or keep the hold and treat the plan as a costed annex.
- **Consequences:** a costed estimate exists (5–7 days per family, stated as an
  estimate with its basis); the qwen baselines are protected by A6; no
  performance claim is introduced.
- **Affected:** `planning/strata-engine/13`, DEC-016, DEC-021, `STATUS.md`.

## DEC-031 — Three-model set fixed: qwen35moe, deepseek, olmoe

- **Date:** 2026-11-19
- **Context:** Mixtral 8x7B was retired as a target (DEC-029): the TheBloke pack is
  the 2023 per-expert layout and no modern stacked pack exists, so it cannot serve
  as an oracle. The owner asked for a three-model set and a replacement family.
- **Decision:** the three test families are:
  1. **Qwen3.6-35B-A3B** (`qwen35moe`) — measured, HO-007;
  2. **DeepSeek-MoE-16B** (`deepseek`) — oracle ready (S0);
  3. **OLMoE-1B-7B-Instruct** (`olmoe`) — chosen as the third.
- **Why OLMoE:** it is the only candidate that adds a structural axis the other
  two lack — 64 experts, top-8, **no shared expert**, and a 50k tokenizer — for a
  ~4 GiB download. Its size also makes S4/S5 parity iterations seconds rather than
  minutes, and those stages are where the cost sits.
- **Rejected:** Qwen3-30B-A3B (`qwen3moe`) — repeats qwen35moe's shape without
  shared experts and costs an 18.6 GB download; Mistral 7B (dense) — outside the
  MoE thesis and uses the arch string just retired.
- **Consequences:** an OLMoE oracle extension (S0b) is authorized under this
  decision; **S1 and later remain held** under DEC-016. `qwen4exp` stays a
  supported, unmeasured fourth point.
- **Affected:** `planning/strata-engine/13` §5, `workflow/MODELS.md`,
  HO-STRATA-011, DEC-016, DEC-029.

## DEC-032 — S0b accepted; AC-3 amended for a fail-closed tokenizer refusal

- **Date:** 2026-11-19
- **Context:** HO-STRATA-011 (S0b) extended the oracle to OLMoE. Its tokenizer
  cannot be exercised at the pin: `tools/strata_tokenizer.py:104-112` knows only
  `qwen35` and `deepseek*`, and the pack declares `tokenizer.ggml.pre = olmo`, so
  the tool exits 1 with `UnknownPreTokenizer('olmo')` rather than mis-tokenize.
- **Decision:** for S0b, AC-3 is satisfied by **either** tokenizer parity **or** a
  recorded engine refusal with its reason. The oracle uses llama.cpp token IDs
  until an `olmo` pre-tokenizer exists. This is an architect amendment to a
  criterion, recorded here — not a coder reclassifying a failure.
- **Why accept:** the engine's refusal is the safe behaviour ("running it with the
  wrong rule would change what it reads"); the oracle's value — a fixed reference
  for S4/S5 — does not depend on engine-side tokenization; and the gap is now
  documented instead of discovered later.
- **Consequences:** OLMoE needs **two** things, not one: a tokenizer pre-tokenizer
  rule (small patch) and a family path (large). That sharpens DEC-021 **T1**:
  the missing capability is tokenization *and* model class, not routing alone.
  S1 remains held (DEC-016).
- **Affected:** HO-STRATA-011 (`DONE`), `planning/strata-engine/13` §5,
  DEC-016, DEC-021, DEC-031.
