# HO-STRATA-005 — confirm Route 2 and define the Route 3 triggers

| Field | Value |
|---|---|
| **ID** | HO-STRATA-005 |
| **Type** | ARCHITECT_TO_CODER (evidence pack) → architect decision |
| **State** | **READY** — DoR met (§8) |
| **Created / updated (UTC)** | 2026-11-17 |
| **From → To** | Architect → Primary Coder (`coder-primary`), decision by Architect |
| **Work package** | `strata-005-route-decision` |
| **Branch / base commit** | `wp/strata-005-route-decision` / `8c1a291` (`main` after PR #15/#16) |
| **Priority / timebox** | P1 · 4 working hours |
| **Owner task** | OT-STRATA-001 (narrowed by the owner’s 2026-11-17 decision, DEC-020) |

## 1. Why this handoff changed shape

The original HO-005 asked for a three-way comparison (Route 1 vs 2 vs 3) and
depended on HO-STRATA-006 (the cross-family support matrix). The owner held
HO-006 under DEC-016, and DEC-010’s support-first plan is paused, so the fork
side of that comparison can never be costed with the evidence available.

The owner therefore narrowed the handoff (2026-11-17): **confirm Route 2 and
write down the conditions that would reverse it**. Route 3 is **deferred, not
rejected**; the trigger table is the record of what would reopen it. No fork
work and no support matrix are in scope.

What makes this a real decision rather than a formality: the pinned overlay
currently contains **zero patches** (HO-001 and HO-007 both ran with
`git status --porcelain` empty on the Strata checkout). The cost of Route 2 today
is an environment contract plus a pin, not a maintained patch set — so the
triggers must describe when a patch set becomes unavoidable, not assert that it
already is.

## 2. Scope (in)

- A one-page decision document at
  `workflow/evidence/HO-STRATA-005/route-decision.md`.
- The **current cost of Route 2**, enumerated from HO-001 and HO-007: the two
  environment requirements, the opt-in hipBLASLt table, the `--native` path,
  and the explicit count of Strata source patches (zero).
- A **trigger table** for Route 3: each trigger measurable, each with the check
  that evaluates it and the handoff that would own the response.
- The **reversal cost**: what is lost if Route 2 is confirmed and a trigger fires
  late.
- A citation map: every factual sentence → HO ID + evidence file (+ line where
  practical).

## 3. Out of scope

- Building, evaluating, or costing Route 3; any fork work; any P0–P9 activity.
- HO-STRATA-006 and any cross-family support investigation (DEC-016 hold).
- New measurements, builds, model runs, or downloads. This consumes recorded
  evidence only.
- Any performance, throughput, quality or support claim.
- 780M, MI25, gfx1100, gfx1151, gfx1201.
- Editing the merged evidence bundles or the signed handoffs.

## 4. Inputs (all available)

| Input | Path | State |
|---|---|---|
| HO-001 approval + evidence | `workflow/handoffs/HO-STRATA-001-APPROVAL.md`, `workflow/evidence/HO-STRATA-001/` | SIGNED, merged |
| HO-007 approval + evidence | `workflow/handoffs/HO-STRATA-007-APPROVAL.md`, `workflow/evidence/HO-STRATA-007/` | SIGNED, merged |
| Engine boundary note | `workflow/evidence/HO-STRATA-001/artifacts/engine-boundary.md` | merged |
| HIPBLASLt tuning finding | `workflow/evidence/HO-STRATA-001/artifacts/tuning-table.md` | merged |
| Route decision + holds | `workflow/DECISIONS.md` — DEC-002, DEC-010, DEC-016, DEC-017, DEC-019 | adopted |
| Roadmap route section | `planning/strata-engine/08-roadmap-decision.md` §4–§5 | merged |

## 5. Acceptance criteria

| # | Criterion | Check |
|---|---|---|
| 1 | Route 2 confirmed with its **current** cost enumerated: the two environment requirements, the opt-in table, the `--native` path, and **zero** source patches | document review against HO-001/007 evidence |
| 2 | Every factual sentence cites an HO ID + evidence file; the citation map covers every claim | `grep -o 'HO-STRATA-[0-9]*' …` count matches the citation map rows; spot-check each row resolves |
| 3 | **Five** Route 3 triggers, each measurable, each with the check that evaluates it and the owning handoff | table has 5 rows, none of the form “it gets expensive” |
| 4 | Reversal cost stated: what is lost if Route 2 is confirmed and a trigger fires late | document review |
| 5 | No new measurement, build, model run, or download in the work | `git diff --name-status` touches only the evidence directory + handoff + STATUS |
| 6 | Decision recorded in `DECISIONS.md` as **DEC-021** with context, options, decision, consequences, reversal conditions | DEC-021 present, dated, cross-linked |
| 7 | No performance/support/quality claim; one profile per cited number | grep for claim language; each number carries its profile |

### Trigger set to evaluate (the coder may refine the wording, not the substance)

| # | Trigger | Check | Owner if fired |
|---|---|---|---|
| T1 | A requested family needs an engine path the pin lacks (new attention, kernel, or quant type) and the change cannot be expressed as a localized patch | the family’s low-tier test fails with a structural error, not a configuration error | Architect → HO-006 |
| T2 | The patch set grows past a small bound (threshold set in the decision, e.g. >5 files or >300 lines) | `git diff --stat` against the pin | Architect |
| T3 | Rebasing the overlay against upstream conflicts on 2 of 3 consecutive pin updates, or the pin is abandoned upstream | rebase log per pin bump | Architect |
| T4 | A second hardware class (gfx1100, gfx900/MI25) enters the critical path | OT-STRATA-001 scope change | Owner via Auditor |
| T5 | The deliverable becomes an independent, machine-gated engine with its own API/CLI contract | scope decision in `DECISIONS.md` | Owner |

## 6. Evidence required

`workflow/evidence/HO-STRATA-005/`:

- `route-decision.md` — the one-page decision (≤2 pages), with the trigger table.
- `citation-map.md` — claim → HO ID → evidence file (→ line), one row per claim.
- `commands.log` — the `grep`/`git` commands used to build and check the map, with cwd and exit codes.
- `hashes.txt` — SHA256 of the two files above and of the inputs consumed (HO-001/007 approvals and the cited evidence files).
- No new measurements; no model weights.

## 7. Guard rails

- No code, no fork, no patch, no build, no model run, no download.
- No edits to merged evidence bundles, signed handoffs, or QAQC/audit reports.
- No claim beyond what HO-001 and HO-007 recorded; no cross-profile transfer.
- No reinstatement of HO-006; the route decision does not unblock the held test beds.
- No silent scope growth from “confirm + triggers” back to “three-way comparison”.

## 8. Definition of Ready — **MET**

- [x] ID, type, from/to, title, work package present
- [x] Branch and base commit named (`wp/strata-005-route-decision` / `8c1a291`)
- [x] Scope and out-of-scope explicit
- [x] Inputs linked and available (no HO-006 dependency)
- [x] Every acceptance criterion has a command or check
- [x] Evidence requirements explicit and runnable
- [x] Guard rails explicit
- [x] Dependencies resolved (none open)
- [x] Priority/timebox set (P1, 4 hours)
- [x] No unresolved `NEEDS_INFO`

## 9. Definition of Done

- [ ] Route 2’s current cost enumerated and cited
- [ ] Five measurable triggers + checks + owners
- [ ] Reversal cost stated
- [ ] Citation map complete; every row resolves
- [ ] No new measurement; diff is documentation only
- [ ] Decision recorded in `DECISIONS.md`
- [ ] Handoff `DONE` after architect sign-off

## 10. Roles

- **Coder:** assembles the document and the citation map, runs the checks, commits
  on the work-package branch.
- **QAQC / Auditor:** `N/A — no code, no measurement, no artifact claim.` The
  decision’s integrity rests on citations, which the architect verifies at the
  gate against the merged evidence; a QAQC re-run would only re-read the same
  files. Recorded here rather than left blank.
- **Architect:** verifies the citations, writes the `DECISIONS.md` entry, signs.

## 11. Signatures

| Role | Name/agent | Date | Decision |
|---|---|---|---|
| Sender (Architect) | architect | 2026-11-17 | READY (narrowed per owner decision) |
| Receiver (Coder) | `coder-primary` | | |

## 12. Log

- 2026-11-16 Architect: created `PROPOSED`; blocked on HO-006 and a first
  low-tier run.
- 2026-11-17 Architect: HO-007 signed and merged; HO-006 held (DEC-016). Owner
  narrowed the handoff to “confirm Route 2 + triggers” (DEC-020 scope note);
  state `READY`; branch created; HO-006 dependency removed.
