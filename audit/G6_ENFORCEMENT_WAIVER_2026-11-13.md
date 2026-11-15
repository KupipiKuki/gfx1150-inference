# Enforcement waiver — required GPU status check (2026-11-13)

**Auditor:** DeepSeek V4.1 Flash (primary auditor)
**Date:** 2026-11-13
**Status:** **CLOSED (2026-11-15)** — the required check is restored in ruleset
`26990297`; see §Closure. The waiver was temporary and time-boxed; it is now a
historical record, not an active deviation.
**Affects:** ruleset `26990297` (`release-gates`) on `main` and
`vibe/phase7-220201`.
**Related:** `audit/G6_SIGNOFF_2026-11-12.md`, `audit/AUDIT_7F_CI_STATUS_2026-11-11.md` (G6-QF-2), `PHASE7_7G_RESIDENCY_AND_FOLLOWUP_PLAN.md` (closure item C2).

---

## 1. What is waived

The **required** status check `GPU correctness (self-hosted gfx1150)` is
temporarily removed from the ruleset's required list. The other three
requirements stay in force:

- `CPU Parser, Tokenizer, Sampler & Packaging Suite`
- `Sdist Install (CPU-only path, GFX1150_SKIP_CMAKE=1)`
- `Clean-clone documented build (G0 C-1)`

The `Self-Hosted GPU CI` **workflow is not disabled**: it still triggers on
`pull_request`, the nightly schedule and `workflow_dispatch`, and it will run
and report whenever a runner is online. Only its *blocking* power is suspended.

## 2. Why

1. **The blocker is GitHub-side infrastructure, not the code.** The runner's
   server-side registration for `agentId 21` has been deleted **four times in
   four days with no local action** — the local `.runner`/`.credentials` are
   unchanged since 2026-11-09 20:37, so nothing on this host removed it:

   | session | outcome |
   |---|---|
   | Nov 10 01:38 | listening (ok) |
   | Nov 11 03:40, 08:35 | registration deleted |
   | Nov 12 01:09, 03:03, 22:50, 23:33 | listening (ok) — PR #10 and the red-team jobs ran |
   | Nov 13 03:38, Nov 14 03:42 | registration deleted |

   Each deletion leaves the required check **permanently queued**, which blocks
   every PR to the protected branches. Re-registering by hand fixes one
   occurrence; it does not fix the class (closure item **C2**: PAT-based
   self-repair + a watchdog that alerts when the registration is missing).
2. **The risk that motivated the hard requirement does not apply here.** The
   reason to require a self-hosted lane on a *public* repository is that fork
   PRs would otherwise execute untrusted code on the runner host. This
   repository is **private**: no untrusted fork PR can reach the runner, so the
   enforcement's safety value is currently nil while its blocking cost is
   every PR.
3. **Nothing about the signed evidence changes.** The green GPU run
   (`43129386477`, 45 passed / 0 skipped), the red-team block (PR #11) and the
   ruleset record all stand as history.

## 3. What is **not** waived

- The G6 **evidence** (goldens, benchmarks, telemetry, claims gate) and the
  release claim set.
- The other three required checks, the strict claims gate
  (`check_claims.py --strict`, empty baseline), and the CI lanes themselves.
- The **release scope**: no 70B/8-hour/throughput claim, no real-GGUF exact
  golden claim — unchanged.

## 4. Effect on the G6 signoff

`audit/G6_SIGNOFF_2026-11-12.md` lists "the GPU job is **required**, not
`continue-on-error`" as a G6 exit criterion, and the red-team proof
demonstrates that enforcement. With this waiver that property is
**suspended, not revoked**: the signoff continues to describe the state that
existed at signing time, and this waiver is the record of the temporary
deviation. The release remains valid; the *ongoing* enforcement is reduced.

## 5. Interim control

Until the requirement is restored, the GPU lane is still run on this host
before each merge to `main` — `PYTHONPATH=build python3 -m pytest -m gpu -q`
(**45 passed** at the current tip) — and the result is recorded in the merge
note. This is an audit trail, not a substitute for CI enforcement.

## 6. Restore condition (C2)

Restore `GPU correctness (self-hosted gfx1150)` to the required list when:

1. **C2 lands** — the runner can repair its own registration (repo-admin PAT →
   `POST /repos/{owner}/{repo}/actions/runners/registration-token` →
   `config.sh --replace`, token stored root-readable only) and a watchdog
   alerts when the registration is missing; **and**
2. a green GPU run on the protected branch is observed; **and**
3. this waiver is closed with the restoration date and the run ID.

Until then the deviation is open and visible.

---

**Signed:** DeepSeek V4.1 Flash, primary auditor — 2026-11-13.

---

## 7G-C addendum (2026-11-14) — waiver remains accurate at closure

Closure item **C2 landed in code** on `wp/7G-C-closure`: the self-repair
script (`scripts/ci/ensure_runner_registered.sh`), the systemd watchdog units
(`scripts/ci/gfx1150-runner-watchdog.{service,timer}`), and the nightly cron
moved to 04:00 UTC (after the host's ~03:38 UTC boot window). The enforcement
**requirement is still suspended**: restoring it needs the conditions in §6
above — the owner's PAT deployed at `/etc/gfx1150-runner/runner.pat` (outside
the repository), the watchdog timer enabled, and the *simulated*
deletion-and-recovery transcript recorded
(`audit/evidence/G7/7G-C/c2-runner/`). **C4 is decided and recorded
(2026-11-13, `audit/evidence/G7/7G-C/notes.md` §C4): no push trigger is
added** — `ci-gpu.yml` keeps its `pull_request` / `schedule` /
`workflow_dispatch` triggers and stays advisory while this waiver is in
force. The waiver is a process exception only: the G0–G6 evidence, the claim
set and the release scope are untouched.

---

## Closure (2026-11-15)

**The waiver is closed. `GPU correctness (self-hosted gfx1150)` is required
again in ruleset `26990297` (`release-gates`).**

The §6 conditions are met:

1. **C2 lands.** C2a–C2f are implemented on `wp/7G-C-closure` and the live drill
   matrix D1–D8 is recorded in `audit/evidence/G7/7G-C/c2-runner/`. The drills
   found and fixed two real bugs: `config.sh --replace` refused an
   already-configured local runner (`c4a82a6`), and the L3 session selector
   could pick the config log over the listener log (`192bdb8`). The sdist now
   ships the runner/CI fixtures (`582ff05`).
2. **A green GPU run on the protected branch is observed.** Manual
   `workflow_dispatch` on `main`, run
   [43725517391](https://github.com/KupipiKuki/gfx1150-inference/actions/runs/43725517391):
   `GPU lane: 45 passed, 0 skipped, 0 failed, 0 errors, 45 collected` and
   `PASS: the GPU lane ran, with no skips`.
3. **The requirement is restored and green on the PR.** Ruleset `26990297`
   requires the check again; the PR GPU run
   [43728354793](https://github.com/KupipiKuki/gfx1150-inference/actions/runs/43728354793)
   is green. The PR is mergeable with all required checks.

The §5 interim control (a local `pytest -m gpu` before merge) remains a useful
pre-merge check, but it no longer substitutes for enforcement: the required
check is blocking again.

The first nightly on the merged `main` (cron `0 5 * * *`) is a **post-merge
observation**, not a condition of this closure; its queue time will be recorded
when it runs.

**Closed by:** DeepSeek V4.1 Flash, primary auditor — 2026-11-15.

