# Runner watchdog — operations reference

**Authoritative design and rollout:** [`PHASE7_7G_C2_RUNNER_REBUILD_PLAN.md`](../../PHASE7_7G_C2_RUNNER_REBUILD_PLAN.md).
This directory holds the current C2 implementation; the rebuild plan
supersedes its health algorithm and adds the doctor, installer and contract
tests.

## Diagnose first

Do **not** re-register the runner before checking the clock and the labels —
those were the actual causes of every "registration deleted" episode on this
host.

```bash
# until scripts/ci/runner_doctor.sh lands (C2a), use the plan's Appendix A:
cd /home/kupipi/Documents/git/gfx1150-inference
sed -n '/## Appendix A/,/Rule of thumb/p' PHASE7_7G_C2_RUNNER_REBUILD_PLAN.md
```

Order of suspicion:

1. **L0 clock** — `timedatectl` (RTC must be UTC, NTP synchronized) and skew
   vs GitHub's `Date:` header. Skew > 60 s makes the runner reject its own
   token and *report it as a deleted registration*.
2. **L4 labels** — the agent must carry `gfx1150` **and** `rocm`; a missing
   label queues every job forever while the runner looks idle.
3. **L3 session** — a restart with a correct clock fixes a stale session.

## Files

| File | Purpose |
|---|---|
| `ensure_runner_registered.sh` | health check + PAT-based re-registration |
| `gfx1150-runner-watchdog.service` | oneshot systemd unit (root) |
| `gfx1150-runner-watchdog.timer` | every 5 minutes, after boot |
| `gfx1150-runner-watchdog-alert.service` | visible alert line |

## Deployment (root, on the gfx1150 host)

```bash
# 1. the PAT (repo admin, Administration: write), outside the repository
install -d -m 0700 -o root -g root /etc/gfx1150-runner
install -m 0600 -o root -g root /dev/stdin /etc/gfx1150-runner/runner.pat
stat -c '%a:%U' /etc/gfx1150-runner/runner.pat      # expect 600:root

# 2. the script and units
install -m 0755 -o root -g root scripts/ci/ensure_runner_registered.sh \
  /usr/local/sbin/ensure_runner_registered.sh
install -m 0644 -o root -g root scripts/ci/gfx1150-runner-watchdog.service \
  /etc/systemd/system/
install -m 0644 -o root -g root scripts/ci/gfx1150-runner-watchdog.timer \
  /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now gfx1150-runner-watchdog.timer
```

## Verify

```bash
sudo /usr/local/sbin/ensure_runner_registered.sh --check   # exit 0 = healthy
sudo journalctl -u gfx1150-runner-watchdog.service -n 20 --no-pager
sudo tail -20 /var/log/ensure-runner.log
```

`--check` is read-only: it never re-registers. The timer runs the same script
without `--check`, which repairs only when the runner is offline, never while
a job is in flight, and at most once per 30 minutes.

## Secret handling

The PAT reaches `curl` through a root-owned, mode-0600 `--config` file
(`-K`), never argv; it is unset after use and never logged. The one-time
registration token is passed to `config.sh --token` as the runner user, so it
is visible in `/proc/<pid>/cmdline` for roughly one second — single-use,
short-lived, registration-only, and documented rather than hidden.
