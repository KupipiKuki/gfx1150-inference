# 7G-C (C2) — runner-registration watchdog (deploy on the gfx1150 host)

The units below deploy `scripts/ci/ensure_runner_registered.sh` as a
root-owned systemd timer. Status: **authored, deployment pending** — the
owner must create the repo-admin PAT (`Administration: write`) before the
units will repair anything; see `audit/evidence/G7/7G-C/c2-runner/`.

## One-time setup (root, on the gfx1150 host)

```bash
# 1. the PAT, outside the repository, root-readable only
install -d -m 0700 -o root -g root /etc/gfx1150-runner
# paste the PAT (Administration: write, repo admin):
install -m 0600 -o root -g root /dev/stdin /etc/gfx1150-runner/runner.pat

# 2. the script, root-owned
install -m 0755 -o root -g root \
  /home/kupipi/Documents/git/gfx1150-inference/scripts/ci/ensure_runner_registered.sh \
  /usr/local/sbin/ensure_runner_registered.sh

# 3. the units
install -m 0644 -o root -g root /home/kupipi/Documents/git/gfx1150-inference/scripts/ci/gfx1150-runner-watchdog.service /etc/systemd/system/
install -m 0644 -o root -g root /home/kupipi/Documents/git/gfx1150-inference/scripts/ci/gfx1150-runner-watchdog-alert.service /etc/systemd/system/
install -m 0644 -o root -g root /home/kupipi/Documents/git/gfx1150-inference/scripts/ci/gfx1150-runner-watchdog.timer  /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now gfx1150-runner-watchdog.timer
```

## Watchdog behaviour

* every 5 minutes: `ensure_runner_registered.sh`;
* healthy → exit 0, one log line, nothing else;
* offline → re-register with a fresh registration token, restart the service,
  verify it is listening again;
* a repair is never attempted while a `Runner.Worker` process exists (a job
  is in flight), and attempts are rate-limited to one per 30-minute cooldown
  (see `REMEDIATION-2026-11-14.md`);
* still offline after the repair → exit non-zero with the log line
  `RUNNER-REGISTRATION-OFFLINE` (`OnFailure` target), so the outage is
  visible before it queues a required check.

The verify-only mode (`--check`) exits non-zero when the runner is offline
without repairing anything; that is what the evidence transcript uses.

Secret handling (post-remediation, matching the script's header): the PAT
never enters the repository, the logs, a workflow file, the service
environment, **or argv** — it travels to `curl` through a root-owned, 0600
temp config file passed via `--config`, which keeps `Authorization` out of
`/proc/<pid>/cmdline`. The one-time registration token **does** appear
transiently in the argv of `runuser`/`config.sh` (readable by any local user
for roughly one second); it is single-use, short-lived and grants only runner
registration — documented and accepted as low severity.
