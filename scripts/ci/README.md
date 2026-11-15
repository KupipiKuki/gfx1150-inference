# Runner watchdog — operations reference

**Authoritative design and rollout:** [`PHASE7_7G_C2_RUNNER_REBUILD_PLAN.md`](../../PHASE7_7G_C2_RUNNER_REBUILD_PLAN.md).
This directory holds the current C2 implementation; the rebuild plan
supersedes its health algorithm and adds the doctor, installer and contract
tests.

## Diagnose first

Run the doctor; it answers L0–L6 with a stable exit code:

```bash
cd /home/kupipi/Documents/git/gfx1150-inference
scripts/ci/runner_doctor.sh --check          # 0 healthy, 1 offline, 2 clock, 3 misconfigured
scripts/ci/runner_doctor.sh --check --json   # machine-readable
scripts/ci/runner_doctor.sh --check --no-network   # offline diagnosis
```

Do **not** re-register the runner before checking the clock and the labels —
those were the actual causes of every "registration deleted" episode on this
host. The doctor checks them in order:

1. **L0 clock** — `timedatectl` (RTC must be UTC, NTP synchronized) and skew
   vs GitHub's `Date:` header. Skew > 60 s makes the runner reject its own
   token and *report it as a deleted registration*.
2. **L4 labels** — the agent must carry `gfx1150` **and** `rocm`; a missing
   label queues every job forever while the runner looks idle.
3. **L3 session** — a restart with a correct clock fixes a stale session.

## Files

| File | Purpose |
|---|---|
| `runner.env` | single source of truth for name, labels, unit, user, paths, thresholds |
| `runner_doctor.sh` | read-only layered diagnosis (L0–L6) with stable exit codes |
| `ensure_runner_registered.sh` | watchdog: run the doctor, repair only when the verdict allows it, verify, alert on transitions |
| `install_runner_watchdog.sh` | install / verify (sha256 drift) / uninstall the watchdog, doctor, spec, units and logrotate |
| `gfx1150-runner-watchdog.service` | oneshot systemd unit (root), `TimeoutStartSec=240` |
| `gfx1150-runner-watchdog.timer` | every 5 minutes, `OnBootSec=5min`, `AccuracySec=30s` |
| `gfx1150-runner-watchdog-alert.service` | transition-alert hook (journal line; extend for paging) |
| `gfx1150-runner-watchdog.logrotate` | keeps `/var/log/ensure-runner.log` bounded |

## Deployment (root, on the gfx1150 host)

The installer is the only supported deployment path; it installs the script,
the doctor, the spec, the units and logrotate, reloads systemd and enables the
timer.

```bash
# 1. the PAT (repo admin, Administration: write), outside the repository
sudo install -d -m 0700 -o root -g root /etc/gfx1150-runner
sudo install -m 0600 -o root -g root /dev/stdin /etc/gfx1150-runner/runner.pat
sudo stat -c '%a:%U' /etc/gfx1150-runner/runner.pat      # expect 600:root

# 2. install (refuses without the PAT; --allow-no-pat stages without it)
sudo scripts/ci/install_runner_watchdog.sh --apply

# 3. verify
sudo scripts/ci/install_runner_watchdog.sh --check       # exit 0 = no drift
sudo scripts/ci/runner_doctor.sh --check                 # exit 0 = healthy
```

`--check` compares every installed file with the repository by sha256 and
reports `MISSING`/`DRIFT`/`OK` plus the timer and PAT state. It exits `1` on
drift or a missing file.

## Verify and operate

```bash
scripts/ci/runner_doctor.sh --check            # 0 healthy, 1 offline, 2 clock, 3 misconfigured
sudo /usr/local/sbin/gfx1150-runner-watchdog --check   # same, verify-only
sudo journalctl -u gfx1150-runner-watchdog.service -n 20 --no-pager
sudo tail -20 /var/log/ensure-runner.log
```

The watchdog runs the doctor on every tick and acts on the verdict:

| Verdict | Exit | Watchdog action |
|---|---|---|
| `HEALTHY` / `JOB_IN_FLIGHT` / `STARTING` | 0 | nothing (a job in flight defers repair) |
| `CLOCK_SKEW` | 2 | alert once; **repair forbidden** — fix timekeeping |
| `OFFLINE` (`SERVICE_DOWN`, `LISTENER_DEAD`, `REGISTRATION_DELETED`, `NOT_LISTENING`) | 1 | repair once, verify, exit 0/1 |
| `MISCONFIGURED` (`LABELS_MISMATCH`, `REGISTRATION_NOT_VISIBLE`) | 3 | re-register with the spec labels, verify |
| `MISCONFIGURED` (anything else) | 3 | alert once; owner action |

Alerts are transition-based (`/run/gfx1150-runner.state`): one alert when the
runner becomes broken, one recovery line when it is healthy again — never one
per tick. Repairs never run under a live `Runner.Worker` and are rate-limited
to one per 30 minutes (`/run/ensure-runner.last-repair`).

If the timer is active but the service fails with `runner.env not found` or
`workflow ... not available`, the install is partial (the spec was not
installed). Re-run `sudo scripts/ci/install_runner_watchdog.sh --apply`
(add `--allow-no-pat` to stage without the PAT); the installer writes the spec
and the drift manifest that the installed doctor reads.

## Uninstall

```bash
sudo scripts/ci/install_runner_watchdog.sh --uninstall   # keeps the PAT and the log
```

## Secret handling

The PAT reaches `curl` through a root-owned, mode-0600 `--config` file
(`-K`), never argv; it is unset after use and never logged. The one-time
registration token is passed to `config.sh --token` as the runner user, so it
is visible in `/proc/<pid>/cmdline` for roughly one second — single-use,
short-lived, registration-only, and documented rather than hidden.
