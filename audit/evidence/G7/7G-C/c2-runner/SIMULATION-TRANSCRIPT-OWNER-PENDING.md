# C2 — simulated deletion-and-recovery transcript: OWNER-PENDING

**Status: BLOCKED (owner-pending), reason recorded per brief §7.**

The brief's C2 acceptance requires a *live* simulated failure on the real
runner: stop `actions.runner.KupipiKuki-gfx1150-inference.gfx1150-host.service`,
delete the server-side registration through the API, run
`ensure_runner_registered.sh`, and confirm the runner comes back **by itself**.

That simulation needs the repo-admin **PAT** (`Administration: write`) stored
at `/etc/gfx1150-runner/runner.pat`, root-owned. Per the C4/C2 decisions the
PAT is created and installed **by the owner only** — the coder must not handle
the credential or receive it in any form. The PAT was therefore not present on
the host at bundle-assembly time and the live simulation could not run.

## What was verified without the PAT (functional, this host, 2026-11-13)

**Historical note (2026-11-14):** the checks below exercised the *pre-remediation*
health check the audit rejected (BLOCKER-7G-C-1): "online path" meant
"`Listening for Jobs` inside a 10-minute journal window", which misjudges a
long-up healthy runner. The fix, its discipline and the new scripted check
(`tests/test_runner_watchdog.py`) are recorded in
`REMEDIATION-2026-11-14.md`; the live re-run required below must use the
fixed script.

Both code paths of `scripts/ci/ensure_runner_registered.sh` were exercised
with fake `systemctl`/`journalctl` on `PATH` (no PAT involved — the repair
path exits before the API call when the PAT file is absent, check mode reports
the offline state):

* **offline path:** service inactive + `_diag` shows no `Listening for Jobs`
  → the script reports `RUNNER-REGISTRATION-OFFLINE` and exits non-zero
  (alert contract exercised); with a PAT file present it reaches the
  registration-token step and fails cleanly (exit 2, no token or PAT echoed)
  when the PAT is a placeholder;
* **online path:** service active + `Listening for Jobs` in the log →
  exit 0, single `runner healthy` line, all manipulations skipped.

Tests/CI contract: the nightly cron in `.github/workflows/ci-gpu.yml` was
moved 03:00 → 04:00 UTC (below), and the runner-host acceptance procedure is
documented in `scripts/ci/README.md` (steps 1–4 there are exactly the
deletion-and-recovery simulation the owner runs once the PAT exists).

## The transcript that closes this item (owner, after PAT install)

```bash
systemctl stop actions.runner.KupipiKuki-gfx1150-inference.gfx1150-host.service
# delete the registration via the API with the PAT (Administration: write)
sudo /usr/local/sbin/ensure_runner_registered.sh
# expect: fresh registration token, config.sh --replace --unattended,
#         service restarted, 'Listening for Jobs' back — no human action
# and the watchdog timer pings RUNNER-REGISTRATION-OFFLINE while it was out
```

Record the output in this directory as `simulated-transcript.log` (the PAT and
the one-time registration token must not appear; the script already refuses
to echo either).

## Open item carried in `notes.md`

- [ ] owner: create PAT, run the unit steps in `README.md`, run the simulation
      above, attach `simulated-transcript.log`;
- [ ] owner: `systemctl enable --now gfx1150-runner-watchdog.timer`;
- after both land, the G6 enforcement waiver can be lifted (its own §addendum
  records the same dependency).
