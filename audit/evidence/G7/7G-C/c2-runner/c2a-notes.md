# C2a — spec + read-only doctor (landed 2026-11-14)

## What landed

| File | Purpose |
|---|---|
| `scripts/ci/runner.env` | single source of truth: repo, runner name/user/dir/labels, unit, PAT path, markers, boot window, cron, thresholds, required check name |
| `scripts/ci/runner_doctor.sh` | read-only layered diagnosis L0–L6, `--check`/`--json`/`--quiet`/`--no-network`, stable exit codes 0/1/2/3 |
| `tests/test_runner_doctor.py` | 19 CPU-lane tests: healthy, mtime-poison, deletion before/after listen, skew vs deletion, service/listener down, STARTING grace, L4 labels/group, JSON/quiet, static guards |
| `tests/test_harness_contract.py` | the new module is classified `cpu` in `EXPECTED_LANES` |

## Live result (this host)

```text
L0 PASS  rtc=utc ntp=synchronized skew=5s
L1 PASS  active/running since Sat 2026-11-14 16:38:50 EST
L2 PASS  Runner.Listener pid=16820 user=kupipi
L3 PASS  log=Runner_20261114-213850-utc.log listening, no later rejection
L4 WARN  PAT missing; labels/group not verifiable (owner action)
L5 PASS  runs-on is covered by the runner labels
L5 PASS  job name matches the required check
L5 WARN  cron 0 4 * * * leaves 22 min after boot 03:38 (want >= 30)
L5 PASS  no push trigger
L5 WARN  missing permissions / concurrency / fork guard (C2e)
L5 PASS  junit skip-is-not-pass guard present
L6 WARN  timer disabled; installed watchdog DRIFTED; PAT missing
L6 PASS  watchdog log updated 332s ago
VERDICT: HEALTHY (8 warning(s))
```

Exit 0. The warnings are the *known, planned* C2c–C2e items, not surprises.

## Regressions proven

- **mtime poison (BLOCKER-7G-C-3):** a stale `_diag` file with a future
  mtime and a deletion marker does not make the healthy current session
  offline — the doctor selects by filename timestamp.
- **skew vs deletion (root cause, audit §3b):** a `not valid until` rejection
  after listening is `SESSION_SKEW`, exit 2, repair forbidden — not
  `REGISTRATION_DELETED`.
- **deletion before listen:** a deletion line followed by a successful listen
  is healthy (line order, not mere presence).
- **PAT out of argv:** the doctor sends the header through `-K` (a 0600
  config file); the static test forbids `-H "Authorization: Bearer …"`.

## Not in this package (by design)

- `--repair` (C2b/C2c): the doctor refuses it with exit 3.
- Watchdog unit changes, transition alerts, installer, drift `--apply` (C2c/C2d).
- Workflow changes and contract tests (C2e/C2f).
- PAT deployment and the live drills D1–D8 (C2g, owner).

## Evidence

- `doctor-c2a-2026-11-14.txt` — live human + JSON output, exit codes.
- `c2a-tests-2026-11-14.log` — 19 doctor tests, CPU 583, GPU 45, strict claims,
  canaries.
