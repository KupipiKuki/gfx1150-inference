# C2b–C2f — watchdog, units, installer, workflow, contract (landed 2026-11-14)

This package implements the rest of the runner/CI rebuild after C2a. It is the
code the runner/workflow interaction depends on; C2g (PAT deployment, drills
D1–D8, ruleset restore) remains owner-pending because it needs root and GitHub
admin.

## What landed

| WP | File | Purpose |
|---|---|---|
| C2b | `scripts/ci/ensure_runner_registered.sh` | watchdog orchestrator: run the doctor, act on the verdict, repair once, verify, transition alerts |
| C2b | `tests/test_runner_watchdog.py` | 19 CPU-lane cases driven by a fake doctor + PATH shims |
| C2c | `scripts/ci/gfx1150-runner-watchdog.{service,timer}` | `After=network-online.target time-sync.target`, `OnBootSec=5min`, `AccuracySec=30s`, no `OnFailure`, `TimeoutStartSec=240` |
| C2c | `scripts/ci/gfx1150-runner-watchdog-alert.service` | transition-alert hook (journal line) |
| C2c | `scripts/ci/gfx1150-runner-watchdog.logrotate` | bounded `/var/log/ensure-runner.log` |
| C2d | `scripts/ci/install_runner_watchdog.sh` | `--apply` / `--check` (sha256 drift) / `--uninstall`; installs the manifest the installed doctor uses for L6 |
| C2d | `tests/test_install_runner_watchdog.py` | 8 CPU-lane cases, including D7 (drift → apply → OK) |
| C2e | `.github/workflows/ci-gpu.yml` | `permissions: contents: read`, concurrency per ref, fork guard, preflight, `pip freeze` artifact, cron `0 5 * * *` |
| C2f | `tests/test_ci_contract.py` | 10 CPU-lane contract assertions + 5 mutation checks + static guards |
| C2b | `scripts/ci/runner_doctor.sh` | `JOB_IN_FLIGHT` (state order 4), `generated_at` in JSON, manifest-aware L6 drift |
| C2b | `scripts/ci/runner.env` | `DOCTOR_INSTALLED`, `DRIFT_MANIFEST`, `STATE_FILE`, `ALERT_UNIT`, `DOCTOR_TIMEOUT_SECS`, `REPAIR_VERIFY_*` |

## The decision the watchdog makes

The watchdog no longer greps the diag log. It consumes `runner_doctor.sh
--json` and maps the verdict:

| Verdict | Exit | Action |
|---|---|---|
| `HEALTHY` / `JOB_IN_FLIGHT` / `STARTING` | 0 | nothing |
| `CLOCK_SKEW` | 2 | alert once; **repair forbidden** |
| `OFFLINE` | 1 | repair once (cooldown, worker guard), verify, exit 0/1 |
| `MISCONFIGURED` + `LABELS_MISMATCH`/`REGISTRATION_NOT_VISIBLE` | 3 | re-register with the spec labels |
| `MISCONFIGURED` (anything else) | 3 | alert once; owner action |

This is the structural fix for the false "registration deleted" episodes: a
clock-skew rejection can no longer reach the repair path.

## Regressions proven

- **skew never repairs:** `CLOCK_SKEW` → exit 2, no curl, no restart.
- **mtime poison** stays a doctor test; the watchdog sees `HEALTHY` and does
  nothing.
- **job in flight:** doctor returns `HEALTHY`/`JOB_IN_FLIGHT`; a second guard
  in the watchdog defers even if the doctor races.
- **cooldown:** a second offline tick makes no new attempt and no second alert.
- **PAT safety:** the PAT is only in a 0600 `-K` config file; the static test
  and the runtime test both prove it is absent from argv and the log.
- **alert dedup:** healthy → broken → broken → healthy produces exactly one
  `ALERT:` and one `RECOVERED:` line.
- **drift:** `install --check` is `OK` after `--apply`, `DRIFT` after a manual
  edit, `OK` again after `--apply`.
- **workflow mutations:** a wrong label, a renamed job, a push trigger, a
  missing fork guard and a too-early cron each fail the corresponding check.

## Live state (pre-deploy, honest)

`scripts/ci/install_runner_watchdog.sh --check` exits `1` on the host right
now, and that is correct:

```text
script     /usr/local/sbin/gfx1150-runner-watchdog              MISSING
script     /usr/local/sbin/gfx1150-runner-doctor                MISSING
spec       /etc/gfx1150-runner/runner.env                       MISSING
unit       .../gfx1150-runner-watchdog.service                  DRIFT
unit       .../gfx1150-runner-watchdog.timer                    DRIFT
unit       .../gfx1150-runner-watchdog-alert.service            DRIFT
logrotate  /etc/logrotate.d/gfx1150-runner-watchdog             MISSING
manifest   /etc/gfx1150-runner/watchdog.sha256                  MISSING
unit       gfx1150-runner-watchdog.timer                        NOT ENABLED
PAT        /etc/gfx1150-runner/runner.pat                       MISSING
RESULT: DRIFT
```

The doctor still says `HEALTHY` (exit 0): the runner itself is fine; the
self-repair layer is the part that is not deployed. The installer refuses
`--apply` without the PAT, so this cannot be "fixed" from the repository alone.

## Verification

```text
21 passed  tests/test_runner_doctor.py
19 passed  tests/test_runner_watchdog.py
10 passed  tests/test_ci_contract.py
 8 passed  tests/test_install_runner_watchdog.py
617 passed pytest -m "not gpu"
45 passed  pytest -m gpu
PASS       check_claims.py --strict (baseline 0 bytes)
16/16      canary_claims.py
```

## Not in this package (C2g, owner)

- Deploy `/etc/gfx1150-runner/runner.pat` (0600, root).
- `sudo scripts/ci/install_runner_watchdog.sh --apply`.
- Drills D1–D8 (stop, delete+repair, skew, label removal, busy guard, PAT
  rotation, drift, alert dedup), each with an evidence file.
- Restore `GPU correctness (self-hosted gfx1150)` in ruleset `26990297`.
- Close `audit/G6_ENFORCEMENT_WAIVER_2026-11-13.md`.

## Evidence

- `doctor-c2b-f-2026-11-14.txt` — live human + JSON doctor output.
- `installer-check-2026-11-14.txt` — pre-deploy `--check` (expected DRIFT).
- `c2b-f-tests-2026-11-14.log` — targeted suites, CPU, GPU, claims, canaries.
