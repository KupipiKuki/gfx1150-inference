# 7G-C2 — Runner & CI Rebuild Plan (redeveloped 2026-11-14)

**Status:** COMPLETE — C2a–C2g landed and exercised by D1–D8; G7-C signed
2026-11-15 ([`audit/G7_C_SIGNOFF_2026-11-15.md`](audit/G7_C_SIGNOFF_2026-11-15.md)).
Supersedes the C2 implementation approach in `PHASE7_7G_CLOSURE_BRIEF.md` §C2.
**Gate:** G7-C (last gate of this project).
**Branch:** `wp/7G-C-closure`.
**Roles:** Owner (host admin + GitHub admin) · Coder · QAQC · Auditor.
**Companion:** `audit/AUDIT_7G_C_2026-11-14.md` (blockers and addenda),
`audit/G6_ENFORCEMENT_WAIVER_2026-11-13.md` (restore condition).

---

## 0. Why this document exists

C2 has consumed hours of troubleshooting across five incidents in five days,
and each incident was diagnosed *after* the fact, from a different log, with a
different ad-hoc command. The code was not the only problem:

| # | Incident | What we believed | What was true | Cost |
|---|---|---|---|---|
| 1 | Required GPU check queued for days | "GitHub deleted the registration" | Host clock jumped **+5 h** at boot (RTC in local time); the runner rejected its own token as "not valid until…" and reported it as *registration deleted* | Days of blocked PRs |
| 2 | Dispatched job never started | "The runner is online" | The runner's `rocm` label was missing; `runs-on: [self-hosted, gfx1150, rocm]` matched nothing | ~1 h |
| 3 | Watchdog said "offline" for a healthy runner | "The health check is fine" | It picked the newest `_diag` log **by mtime**; the clock jump reordered mtimes | Repeated alerts |
| 4 | Watchdog re-registered/alerted every 5 min | "The cooldown protects us" | The health check itself was wrong, so every tick took the repair path | Noise, near-churn |
| 5 | A manual re-registration "fixed" it, then it broke again | "Re-register and move on" | Re-registering *inside* a skewed clock window fails the same way; the cause was never fixed | Repeat cycles |

**The systemic cause:** the runner has **no single source of truth**, **no
layered diagnosis**, and **no contract test** tying the workflow to the runner
configuration. Health is inferred from proxies (a startup-only log marker, a
file mtime, a service state) that each break independently.

**This plan replaces inference with measurement.** Every claim below is a
command with a pass/fail rule. If a layer fails, the plan names the layer, the
command, the cause and the fix — before anyone opens a log file.

### How to use this document

- **Operator in a hurry:** §11 (decision table) and Appendix A.
- **Implementer:** §4–§9 (spec, doctor, health algorithm, watchdog, installer).
- **QAQC:** §10 (test tiers T1–T4) and §12 (work packages/acceptance).
- **Auditor:** §12–§14 (acceptance, evidence, gate exit).

---

## 1. Inventory — what exists today

### 1.1 Host and runner

| Item | Value | Source of truth today |
|---|---|---|
| Host | Linux Mint 22.3 (Ubuntu 24.04 base), systemd, x86_64 | `uname`, `/etc/os-release` |
| GPU | gfx1150 (Radeon 890M), ROCm/HIP 7.16 | `rocminfo` |
| Runner dir | `/home/kupipi/actions-runner` | `RUNNER_DIR` in scripts |
| Runner user | `kupipi` (in `render`, `video`) | service unit |
| Runner name | `gfx1150-host` | `.runner`, scripts |
| Labels | `gfx1150`, `rocm` (+ automatic `self-hosted`, `Linux`, `X64`) | **not stored locally** — server-side only |
| Runner group | `Default` (`poolName` in `.runner`) | GitHub UI |
| Agent id | 23 (as of 2026-11-14 22:00Z) | `.runner` |
| Work folder | `_work` | `.runner` |
| Service unit | `actions.runner.KupipiKuki-gfx1150-inference.gfx1150-host.service` | hardcoded in 3 places |
| Runner version | 2.338.2 | `_diag` logs |
| Boot window | ~03:38 UTC daily | journal |
| Timekeeping | RTC **now UTC**, chrony active, skew +8 s | `timedatectl`, `chronyc` |

**Labels are the fragile part:** they exist only on GitHub's side. Nothing in
the repository or on the host can read them without an authenticated API call.
A registration without `rocm` is invisible locally and queues every job
forever. This is why §7 adds a label assertion.

### 1.2 Watchdog (C2 as shipped)

| File | Purpose | Problem |
|---|---|---|
| `scripts/ci/ensure_runner_registered.sh` | health check + PAT repair | health from newest `_diag` **mtime**; no skew guard; no label check; no session-vs-deletion disambiguation |
| `scripts/ci/gfx1150-runner-watchdog.service` | oneshot, `OnFailure=alert` | alert fires on every failed tick |
| `scripts/ci/gfx1150-runner-watchdog.timer` | every 5 min, `OnBootSec=3min` | fires during the boot/clock window |
| `scripts/ci/gfx1150-runner-watchdog-alert.service` | appends one line to the log | no dedup, no recovery notice |
| `/etc/gfx1150-runner/runner.pat` | PAT | **absent** on the host; repair cannot run |

Live state measured 2026-11-14 22:00Z: timer `enabled`/`active`, PAT absent,
log 199 lines with **122 "offline"** lines, verdict wrong for a healthy runner.

### 1.3 Workflows

| Workflow | Triggers | Runner | Required? |
|---|---|---|---|
| `ci-cpu.yml` | `push` | `ubuntu-latest` | **yes** (`CPU Parser…`, `Sdist Install…`) |
| `ci-build.yml` | `push` | `ubuntu-24.04` | **yes** (`Clean-clone…`) |
| `ci-gpu.yml` | `pull_request`, `schedule 0 4 * * *`, `workflow_dispatch` | `[self-hosted, gfx1150, rocm]` | **waived** (was required at G6) |

Gaps in `ci-gpu.yml` today:

1. no `permissions:` block (default token is broader than needed);
2. no `concurrency:` group (a PR push + nightly can pile onto one runner);
3. no fork-PR guard (safe only while the repo is private);
4. `pip install` mutates the host interpreter every run and records no freeze;
5. no preflight step (a missing GPU/ROCm fails deep in the build with a
   misleading error);
6. the job name `GPU correctness (self-hosted gfx1150)` is a **required-check
   contract** but nothing tests that it still matches the ruleset;
7. the cron (04:00 UTC) has only ~22 min of margin after the measured ~03:38
   UTC boot;
8. no test asserts `runs-on` ⊆ runner labels — the exact failure of incident 2.

### 1.4 Tests today

| Suite | Count | What it proves |
|---|---|---|
| `pytest -m "not gpu"` | **561 passed**, 45 deselected | CPU/engine behavior |
| `pytest -m gpu` | **45 passed**, 527 deselected | HIP kernels on the host |
| `tests/test_runner_watchdog.py` | **11 passed** | scripted logic through PATH shims |
| sdist lane | 543 / 49 | shipped tree |
| `check_claims.py --strict` | PASS, baseline 0 bytes | claim discipline |
| `canary_claims.py` | 16/16 | checker canaries |

The watchdog tests are good but **model the old algorithm**:

- `test_health_check_does_not_use_a_moving_journal_window` asserts
  `"journalctl" not in body` — this forbids the journal-order fix;
- the health fixture is a `_diag` file with an old mtime — it does not model
  mtime *reordering*, the actual defect;
- nothing covers clock skew, label mismatch, session rejection, or alert dedup;
- the "live deletion-and-recovery" transcript is owner-pending.

---

## 2. Design principles

1. **One spec.** `scripts/ci/runner.env` is the only place name, labels, unit,
   user, paths, boot window and cron are declared. Scripts source it; tests
   read it; the workflow is cross-checked against it.
2. **One doctor.** `scripts/ci/runner_doctor.sh` answers "what is wrong?" in
   seven layers with stable exit codes. Nobody greps journals by hand.
3. **Current state, never proxies.** Health is decided from the *current
   service start*: process, unit state, and the diag log **of that start**
   selected by **filename timestamp**, never by mtime, never by a moving
   journal window.
4. **Clock before repair.** If the host is more than 60 s from GitHub, the
   runner cannot authenticate; repair is forbidden and the verdict is
   `CLOCK_SKEW`. Re-registering under skew is how incident 1 repeated.
5. **No repair under a job, no repair loop.** `Runner.Worker` present → skip;
   one attempt per 30 min; every attempt logged.
6. **Alerts are transitions, not ticks.** One alert when healthy→broken, one
   when broken→healthy. The 5-minute tick is silent while healthy.
7. **Contracts are tested.** Workflow `runs-on`, job name, cron-vs-boot, fork
   guard, skip-is-not-pass and permissions are asserted by a CPU test.
8. **Deploy is idempotent and drift-checked.** The installer reports when the
   installed copy differs from the repository.
9. **Evidence is a transcript, not a narrative.** Every drill records command,
   output, exit code, timestamp and verdict.

---

## 3. The layer model

`runner_doctor.sh` checks these layers in order and stops at the first hard
failure (later layers may be reported as `SKIP`).

| Layer | Question | Pass rule | Failure verdict |
|---|---|---|---|
| **L0 Time** | Is the clock usable? | `LocalRTC=no`, NTP synchronized, `abs(skew) ≤ 5 s` | `CLOCK_SKEW` (> 60 s) / `TIME_WARN` (5–60 s) |
| **L1 Service** | Is the unit running? | `ActiveState=active`, `SubState=running`, `NRestarts` stable | `SERVICE_DOWN` |
| **L2 Process** | Is the listener alive? | `pgrep -u $USER -f 'Runner\.Listener'` | `LISTENER_DEAD` |
| **L3 Session** | Is *this* session registered and listening? | current-start diag log has `Listening for Jobs` and no later rejection | `REGISTRATION_DELETED` / `SESSION_SKEW` / `STARTING` / `NOT_LISTENING` |
| **L4 Routing** | Can GitHub send jobs here? | agent visible to the repo, labels ⊇ spec labels, group grants access | `LABELS_MISMATCH` / `REGISTRATION_NOT_VISIBLE` |
| **L5 Contract** | Do the repo and runner agree? | workflow `runs-on` ⊆ labels, job name = required check, cron after boot, guard present | `CONTRACT_MISMATCH` |
| **L6 Watchdog** | Can the system self-heal? | timer active, script installed and not drifted, PAT present/valid, cooldown sane | `WATCHDOG_DEGRADED` (warn) |

Exit codes (stable contract, used by CI and drills):

| Code | Meaning | Repair allowed? |
|---|---|---|
| `0` | HEALTHY (warnings allowed) | — |
| `1` | OFFLINE (repairable: service/listener/registration) | yes |
| `2` | CLOCK_SKEW (fix time first) | **no** |
| `3` | MISCONFIGURED / INDETERMINATE (labels, group, PAT, contract, network) | owner action |

`--check` is read-only and never repairs. `--repair` delegates to
`ensure_runner_registered.sh` after the same L0–L3 decision.

---

## 4. The spec — `scripts/ci/runner.env`

Shell-sourceable (no YAML dependency, no duplication with systemd).

```bash
# scripts/ci/runner.env — single source of truth for the gfx1150 runner.
# Sourced by scripts/ci/*.sh and read by tests/test_ci_contract.py.

REPO_URL="https://github.com/KupipiKuki/gfx1150-inference"
REPO_SLUG="KupipiKuki/gfx1150-inference"

RUNNER_NAME="gfx1150-host"
RUNNER_DIR="/home/kupipi/actions-runner"
RUNNER_USER="kupipi"
RUNNER_LABELS="gfx1150,rocm"          # must be a superset of ci-gpu.yml runs-on
RUNNER_WORK="_work"

SERVICE_UNIT="actions.runner.KupipiKuki-gfx1150-inference.gfx1150-host.service"
PAT_FILE="/etc/gfx1150-runner/runner.pat"
PAT_OWNER="root"
PAT_MODE="600"

LISTEN_MARKER="Listening for Jobs"
DELETED_MARKER="registration has been deleted"
SKEW_MARKER="not valid until"

BOOT_WINDOW_UTC="03:38"               # measured; nightly cron must clear it
NIGHTLY_CRON_UTC="05:00"              # owner decision (was 04:00)
STARTUP_GRACE_SECS="180"              # no marker yet, service younger than this = STARTING
COOLDOWN_SECS="1800"
SKEW_WARN_SECS="5"
SKEW_FAIL_SECS="60"

REQUIRED_GPU_CHECK="GPU correctness (self-hosted gfx1150)"
```

**Rule:** no script may hardcode any of these values. A test asserts the
workflow's `runs-on` list equals `RUNNER_LABELS` plus the automatic labels, and
that the job `name:` equals `REQUIRED_GPU_CHECK`.

---

## 5. The doctor — `scripts/ci/runner_doctor.sh`

### 5.1 Interface

```text
Usage: runner_doctor.sh [--check|--repair] [--json] [--quiet] [--no-network]

  --check       read-only (default); exit code reports the verdict
  --repair      run the repair path when the verdict is repairable
  --json        machine-readable output (one object, stable keys)
  --quiet       one line: VERDICT + primary cause
  --no-network  skip L0 skew and L4 API checks (offline diagnosis)
```

Exit codes per §3. Root is required for `--repair`; `--check` works unprivileged
(it degrades L6 to `UNKNOWN` rather than failing).

### 5.2 Output (human)

```text
gfx1150 runner doctor — 2026-11-14T23:10:00Z
  L0 timekeeping   PASS   rtc=utc  ntp=synchronized  skew=+8s
  L1 service       PASS   active/running since 21:38:50Z  restarts=0
  L2 process       PASS   Runner.Listener pid=16820 user=kupipi
  L3 session       PASS   log=Runner_20261114-213850-utc.log  listening  no rejection
  L4 routing       PASS   agent=23 labels=self-hosted,Linux,X64,gfx1150,rocm
  L5 contract      PASS   runs-on ⊆ labels  job=required  cron=05:00 > boot=03:38
  L6 watchdog      WARN   timer=active  installed=yes  drift=no  PAT=missing
VERDICT: HEALTHY (self-repair disabled: deploy /etc/gfx1150-runner/runner.pat)
```

`--json` emits the same data with keys `verdict`, `cause`, `layer`, `checks[]`,
`exit_code`, `generated_at`, so evidence files are diffable.

### 5.3 L0 — timekeeping (normative)

Helper contract used throughout: `pass LAYER msg` and `warn LAYER msg` record a
result and return; `fail LAYER msg EXITCODE` records the verdict and **exits
the doctor** with that code (the doctor stops at the first hard failure).
`--json` still prints the collected rows before exiting.

```bash
l0_time() {
  local localrtc ntp skew
  localrtc="$(timedatectl show -p LocalRTC --value 2>/dev/null || echo unknown)"
  ntp="$(timedatectl show -p NTPSynchronized --value 2>/dev/null || echo unknown)"
  [ "${localrtc}" = "no" ] || fail L0 "RTC is in local time: the clock jumps at boot" 2
  [ "${ntp}" = "yes" ]     || fail L0 "NTP is not synchronized" 2
  skew="$(github_skew_secs)" || { warn L0 "cannot reach GitHub"; return 0; }
  if [ "${skew}" -gt "${SKEW_FAIL_SECS}" ] || [ "${skew}" -lt "-${SKEW_FAIL_SECS}" ]; then
    fail L0 "CLOCK_SKEW: host is ${skew}s from GitHub; the runner cannot authenticate" 2
  fi
  [ "${skew}" -le "${SKEW_WARN_SECS}" ] && [ "${skew}" -ge "-${SKEW_WARN_SECS}" ] \
    || warn L0 "clock is ${skew}s from GitHub (warn > ${SKEW_WARN_SECS}s)"
  pass L0 "rtc=utc ntp=synchronized skew=${skew}s"
}

github_skew_secs() {
  local date_hdr
  date_hdr="$(curl -fsSI --max-time 10 https://api.github.com 2>/dev/null \
    | sed -n 's/^[Dd]ate: //p' | tr -d '\r')" || return 1
  [ -n "${date_hdr}" ] || return 1
  python3 - "${date_hdr}" <<'PY'
import email.utils, sys, time
print(round(time.time() - email.utils.parsedate_to_datetime(sys.argv[1]).timestamp()))
PY
}
```

### 5.4 L3 — the health algorithm (normative)

This is the fix for BLOCKER-7G-C-1 and -3. **Do not select the diag log by
mtime, and do not use a moving journal window.**

```bash
service_uptime_secs() {
  local start
  start="$(systemctl show -p ExecMainStartTimestamp --value "${SERVICE_UNIT}" 2>/dev/null)" || { echo 0; return; }
  [ -n "${start}" ] || { echo 0; return; }
  echo $(( $(date +%s) - $(date -d "${start}" +%s) ))
}

session_log() {
  # The runner writes a configuration log and a listener log about a second
  # apart on a restart. Only the listener log has "Listening for Jobs".
  # systemd records the service start between them, so a closest-timestamp tie
  # can select the configuration log and report a healthy runner as
  # NOT_LISTENING (D5 exposed this). Match by NAME, never by mtime: a clock
  # jump makes stale files look newer. Prefer a file at/after the service
  # start; fall back to the closest file within the 5 s granularity window.
  local start stamp f base fsec delta
  local after="" after_delta=999999 before="" before_delta=999999
  start="$(systemctl show -p ExecMainStartTimestamp --value "${SERVICE_UNIT}" 2>/dev/null)" || return 1
  [ -n "${start}" ] || return 1
  stamp="$(date -d "${start}" +%s 2>/dev/null)" || return 1   # local -> epoch; -u would parse it as UTC
  for f in "${RUNNER_DIR}"/_diag/Runner_*-utc.log; do
    [ -e "${f}" ] || continue
    base="${f##*/Runner_}"; base="${base%-utc.log}"
    fsec="$(date -u -d "${base:0:8} ${base:9:2}:${base:11:2}:${base:13:2}" +%s 2>/dev/null)" || continue
    [ "${fsec}" -ge "$(( stamp - 5 ))" ] || continue
    [ "${fsec}" -le "$(( stamp + 180 ))" ] || continue
    if [ "${fsec}" -ge "${stamp}" ]; then
      delta=$(( fsec - stamp ))
      if [ "${delta}" -lt "${after_delta}" ]; then after="${f}"; after_delta="${delta}"; fi
    else
      delta=$(( stamp - fsec ))
      if [ "${delta}" -lt "${before_delta}" ]; then before="${f}"; before_delta="${delta}"; fi
    fi
  done
  if [ -n "${after}" ]; then printf '%s\n' "${after}"; return 0; fi
  [ -n "${before}" ] || return 1
  printf '%s\n' "${before}"
}

l3_session() {
  local log uptime_s last_listen last_bad
  log="$(session_log)" || {
    uptime_s="$(service_uptime_secs)"
    if [ "${uptime_s}" -lt "${STARTUP_GRACE_SECS}" ]; then
      pass L3 "STARTING (service up ${uptime_s}s, no session log yet)"; return 0
    fi
    fail L3 "no diag log matches the current service start (${uptime_s}s up)" 1
  }
  # Append-only file: line order IS event order for this session.
  # `|| true`: grep exits 1 when a marker is absent; under `set -e` the
  # command substitution would otherwise abort the doctor.
  last_listen="$(grep -nF "${LISTEN_MARKER}" "${log}" | tail -1 | cut -d: -f1 || true)"
  last_bad="$(grep -nE "${DELETED_MARKER}|${SKEW_MARKER}" "${log}" | tail -1 | cut -d: -f1 || true)"

  if [ -z "${last_listen}" ]; then
    uptime_s="$(service_uptime_secs)"
    if [ "${uptime_s}" -lt "${STARTUP_GRACE_SECS}" ]; then
      pass L3 "STARTING (no listen marker yet, ${uptime_s}s up)"; return 0
    fi
    if grep -qF "${SKEW_MARKER}" "${log}"; then
      fail L3 "SESSION_SKEW: the runner rejected its token as not-yet-valid (host clock)" 2
    fi
    fail L3 "service is up but never listened (crash loop or rejected session)" 1
  fi
  if [ -n "${last_bad}" ] && [ "${last_bad}" -gt "${last_listen}" ]; then
    if grep -nF "${SKEW_MARKER}" "${log}" | awk -F: -v n="${last_bad}" '$1==n{found=1} END{exit !found}'; then
      fail L3 "SESSION_SKEW: token rejected as not-yet-valid after listening (host clock)" 2
    fi
    fail L3 "REGISTRATION_DELETED: GitHub rejected the registration after listening" 1
  fi
  pass L3 "log=${log##*/} listening, no later rejection"
}
```

**Why this is correct where the old check was not**

| Old check | Failure | New check |
|---|---|---|
| newest `_diag` by mtime | clock jump reorders mtimes → stale "deleted" log wins | match filename timestamp to `ExecMainStartTimestamp` |
| `journalctl --since -10min` | startup marker is 30 min old → 0 hits | read the current session's own log |
| `grep "registration has been deleted"` anywhere in the file | a *skew* rejection is misreported as deletion | compare line order and inspect `not valid until` |
| service active alone | a crash loop is "active" briefly | listener process + session marker |

### 5.5 L4 — routing and labels (normative)

```bash
l4_routing() {
  local json out rc=0
  json="$(curl -fsS --max-time 20 -K "${HDR_CFG}" \
    "https://api.github.com/repos/${REPO_SLUG}/actions/runners")" || {
      fail L4 "cannot list runners (PAT/network)" 3; return; }
  out="$(python3 - "${json}" "${RUNNER_NAME}" "${RUNNER_LABELS}" <<'PY'
import json, sys
data, name, want = json.loads(sys.argv[1]), sys.argv[2], sys.argv[3].split(",")
runners = data.get("runners", [])
me = next((r for r in runners if r.get("name") == name), None)
if me is None:
    print(f"REGISTRATION_NOT_VISIBLE: {name} is not available to this repo "
          f"(deleted or runner-group access)")
    sys.exit(3)
labels = {l["name"] for l in me.get("labels", [])}
missing = [l for l in want if l not in labels]
if missing:
    print(f"LABELS_MISMATCH: missing {missing}; labels={sorted(labels)}")
    sys.exit(3)
print(f"agent={me.get('id')} status={me.get('status')} labels={sorted(labels)}")
PY
)" || rc=$?
  if [ "${rc}" -ne 0 ]; then
    fail L4 "${out}" "${rc}"
  else
    pass L4 "${out}"
  fi
}
```

Notes:

- `GET /repos/{owner}/{repo}/actions/runners` returning the runner **is** the
  runner-group access check: a runner in a group that does not grant this repo
  never appears here.
- The PAT is passed via `-K` (a root-owned 0600 config file), never argv — the
  same rule as the repair path (BLOCKER-7G-C-2).
- If the PAT is missing, L4 is `SKIP`/`UNKNOWN` (warn), not a hard failure:
  the local runner may still be healthy.

### 5.6 L5 — workflow contract

Checks (all read-only, no network):

1. parse `runs-on` from `.github/workflows/ci-gpu.yml`; every label must be in
   `RUNNER_LABELS` or the automatic set `{self-hosted, Linux, X64}`;
2. the job `name:` equals `REQUIRED_GPU_CHECK`;
3. the cron time is at least 30 min after `BOOT_WINDOW_UTC`;
4. no `push:` trigger;
5. `permissions:` present with `contents: read`;
6. a fork-PR guard is present;
7. the junit "skip is not a pass" block is present.

These same checks live in `tests/test_ci_contract.py` (§10, T1) so a drift is
caught by the CPU lane, not only by the doctor.

The installed doctor runs from `/usr/local/sbin` and may not have the checkout.
`runner.env` therefore records `REPO_ROOT` (the checkout path), and L5 **warns**
rather than fails when the workflow file is absent: a missing read-only
cross-check must not turn a healthy runner into `MISCONFIGURED` and disable
self-repair. The CPU contract test remains authoritative.

### 5.7 L6 — watchdog health

- timer unit enabled **and** active;
- installed script sha256 equals the repository copy (drift);
- units installed and `daemon-reload` current;
- PAT file exists with `600:root` and matches `github_pat_*|ghp_*`;
- PAT expiry (from the `github-authentication-token-expiration` response
  header on `GET /user`) > 14 days, else warn;
- cooldown file sane;
- last log line age < 3× the timer period.

---

## 6. Health state machine

States and precedence (first match wins):

| Order | State | Condition | Exit | Repair |
|---|---|---|---|---|
| 1 | `CLOCK_SKEW` | `abs(skew) > 60 s` or RTC local / NTP off | 2 | **never** |
| 2 | `SERVICE_DOWN` | unit not `active/running` | 1 | yes |
| 3 | `LISTENER_DEAD` | no `Runner.Listener` | 1 | yes |
| 4 | `JOB_IN_FLIGHT` | `Runner.Worker` alive | 0 | defer |
| 5 | `STARTING` | service up < `STARTUP_GRACE_SECS`, no marker | 0 | defer |
| 6 | `SESSION_SKEW` | skew marker after last listen | 2 | **never** |
| 7 | `REGISTRATION_DELETED` | deletion marker after last listen | 1 | yes |
| 8 | `NOT_LISTENING` | no marker after grace | 1 | yes |
| 9 | `LABELS_MISMATCH` | API labels ⊉ spec | 3 | yes (re-register with labels) |
| 10 | `REGISTRATION_NOT_VISIBLE` | agent absent from repo list | 3 | yes (re-register) |
| 11 | `HEALTHY` | all above pass | 0 | — |

Transitions that must be tested: healthy→deleted→repaired→healthy;
healthy→skew→(time fixed)→healthy; deleted→job-in-flight→deferred→repaired;
labels-mismatch→repaired→job dispatches.

---

## 7. Watchdog redesign

### 7.1 Behaviour

```text
every 5 min (timer, OnBootSec=5min):
  doctor --check
    HEALTHY / STARTING / JOB_IN_FLIGHT -> exit 0, no output, no alert
    CLOCK_SKEW                        -> exit 2, alert once (transition)
    OFFLINE                           -> if cooldown: exit 1, no attempt
                                         else: record attempt, repair once,
                                               verify, exit 0/1
    MISCONFIGURED                     -> exit 3, alert once (owner action)
  alert only on state transition (healthy<->broken), plus one recovery line
```

### 7.2 Units

`gfx1150-runner-watchdog.service` (oneshot, root, `TimeoutStartSec=240`):

```ini
[Unit]
Description=gfx1150 runner watchdog (doctor + self-repair)
After=network-online.target time-sync.target
Wants=network-online.target
# No OnFailure: alerts are transition-based inside the script.

[Service]
Type=oneshot
User=root
ExecStart=/usr/local/sbin/gfx1150-runner-watchdog
TimeoutStartSec=240s
```

`gfx1150-runner-watchdog.timer`:

```ini
[Timer]
OnBootSec=5min
OnUnitActiveSec=5min
AccuracySec=30s
Persistent=true
```

`OnBootSec` moves from 3 to 5 min so the timer never fires inside the boot
window before NTP has settled.

### 7.3 Alert dedup

State file `/run/gfx1150-runner.state` (tmpfs, resets at boot) holds the last
verdict. The script calls `notify` only when `last != current`, and on recovery:

```bash
notify() {  # $1 = verdict, $2 = cause
  local last=""
  [ -r "${STATE_FILE}" ] && last="$(cat "${STATE_FILE}" 2>/dev/null || true)"
  printf '%s\n' "$1" >"${STATE_FILE}"
  [ "$1" = "${last}" ] && return 0
  if [ "$1" = "HEALTHY" ]; then
    log "RECOVERED: runner is healthy again (was ${last:-unknown})"
  else
    log "ALERT: runner ${1} — ${2}"
    systemctl start --no-block gfx1150-runner-watchdog-alert.service || true
  fi
}
```

### 7.4 Log rotation

Ship `scripts/ci/gfx1150-runner-watchdog.logrotate`:

```text
/var/log/ensure-runner.log {
    weekly
    rotate 4
    compress
    missingok
    notifempty
    create 0640 root root
}
```

The journal remains the primary record; the file is for evidence and grep.

---

## 8. Installer with drift detection

`scripts/ci/install_runner_watchdog.sh`:

```text
--apply      install script + units + logrotate, daemon-reload, enable timer
--check      verify installed == repository (sha256), units enabled/active
--uninstall  disable timer, remove units/script, keep the PAT and the log
```

`--check` output:

```text
script      /usr/local/sbin/gfx1150-runner-watchdog   OK (sha256 match)
unit        gfx1150-runner-watchdog.service           OK (enabled)
unit        gfx1150-runner-watchdog.timer             OK (enabled, active)
logrotate   /etc/logrotate.d/gfx1150-runner-watchdog  OK
PAT         /etc/gfx1150-runner/runner.pat            MISSING
```

The installer never reads or prints the PAT. It refuses `--apply` if the PAT is
missing, unless `--allow-no-pat` is given (for a dry run).

---

## 9. Workflow hardening (`ci-gpu.yml`)

Exact changes:

```yaml
permissions:
  contents: read

concurrency:
  group: gpu-lane-${{ github.ref }}
  cancel-in-progress: false

jobs:
  gpu-correctness:
    name: GPU correctness (self-hosted gfx1150)   # required-check contract
    runs-on: [self-hosted, gfx1150, rocm]
    timeout-minutes: 60
    # never run untrusted fork code on the host, even if the repo goes public
    if: >-
      github.event_name != 'pull_request' ||
      github.event.pull_request.head.repo.full_name == github.repository
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Preflight (fail fast, with a clear cause)
        run: |
          set -euo pipefail
          command -v python3 cmake hipcc git
          python3 -c "import numpy, pytest, pybind11; print('python deps ok')"
          rocminfo | grep -q gfx1150
          test -e /dev/kfd && compgen -G "/dev/dri/renderD*" >/dev/null
          python3 -VV

      - name: Install the documented test/build prerequisites
        run: |
          python3 -m pip install --upgrade pip \
            "numpy>=1.24.0" "setuptools>=64" wheel "pybind11>=2.12" pytest
          python3 -m pip freeze > pip-freeze.txt

      # ... configure / build / GPU lane / junit guard unchanged ...

      - name: Upload the GPU lane logs
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: gpu-lane-logs-${{ github.run_id }}
          path: |
            configure.log
            build.log
            gpu-lane.log
            gpu-lane.xml
            pip-freeze.txt
          if-no-files-found: warn
          retention-days: 14
```

Cron: move to `0 5 * * *` (owner decision; 04:00 leaves only ~22 min after the
measured 03:38 boot and GitHub can delay scheduled runs by several minutes).

Keep the host interpreter (do not switch to a venv in this gate): the G6
evidence was produced with the host pyenv Python 3.14.10 and must remain
reproducible. Record `pip freeze` as an artifact instead.

---

## 10. Test plan

Four tiers. T1 runs on every PR; T2 before/after every change; T3 in a
maintenance window; T4 at gate exit and on the nightly.

### T1 — simulation and contract (CPU lane, no host, no network)

`tests/test_runner_watchdog.py` (rewrite) drives `runner_doctor.sh` through
PATH shims for `systemctl`, `pgrep`, `journalctl`, `curl`, `runuser`, `date`.

| # | Case | Fixture | Expected |
|---|---|---|---|
| 1 | healthy, up 6 h | listen marker, no rejection | exit 0, no repair |
| 2 | **mtime poison** | stale file with future mtime + deleted marker; current file healthy | exit 0 (**regression for F3**) |
| 3 | deletion before listen | deleted line, then listen line | exit 0 |
| 4 | deletion after listen | listen line, then deleted line | exit 1, one repair |
| 5 | skew rejection | `not valid until` after listen | exit 2, **no repair** |
| 6 | skew guard | `github_skew_secs` shim = 3600 | exit 2, no repair |
| 7 | service down | `ActiveState=failed` | exit 1, repair |
| 8 | listener dead | pgrep fails | exit 1, repair |
| 9 | starting | service up 30 s, no log | exit 0, no repair |
| 10 | not listening | up 10 min, no marker | exit 1 |
| 11 | job in flight | `Runner.Worker` alive | exit 0, no repair |
| 12 | cooldown | second tick < 30 min | exit 1, no second attempt |
| 13 | labels mismatch | API labels without `rocm` | exit 3, re-register with spec labels |
| 14 | agent absent | API list without the name | exit 3 |
| 15 | PAT missing/perms/empty | file variants | exit 3, clear message |
| 16 | PAT not in argv | curl shim records argv | no `github_pat_`, no `Bearer` |
| 17 | registration token in argv | runuser shim | documented window only |
| 18 | timeouts | slow curl/config | bounded, exit 1 |
| 19 | log redaction | scan log | no PAT substring |
| 20 | alert dedup | healthy→broken→broken→healthy | 1 alert + 1 recovery |

`tests/test_ci_contract.py` (new, CPU lane, regex parsing — no PyYAML):

| # | Assertion |
|---|---|
| 1 | `runs-on` labels ⊆ `RUNNER_LABELS` ∪ `{self-hosted,Linux,X64}` |
| 2 | job `name:` == `REQUIRED_GPU_CHECK` |
| 3 | no `push:` trigger |
| 4 | cron ≥ boot + 30 min |
| 5 | `permissions: contents: read` present |
| 6 | `concurrency:` present |
| 7 | fork-PR guard present |
| 8 | junit skip-is-not-pass block present |
| 9 | `timeout-minutes` present |
| 10 | every script that needs config sources `runner.env` (no duplicated literals) |

Static guards to keep: PAT only via `-K`; no `--since` moving window; no
`ls -t` for health.

### T2 — host read-only (safe, any time)

```bash
cd /home/kupipi/Documents/git/gfx1150-inference
scripts/ci/runner_doctor.sh --check          # expect exit 0, VERDICT: HEALTHY
scripts/ci/runner_doctor.sh --json > /tmp/runner-doctor.json
scripts/ci/install_runner_watchdog.sh --check
```

Record the output under `audit/evidence/G7/7G-C/c2-runner/doctor-<date>.txt`.
A non-zero exit is the start of the decision table (§11), not a mystery.

### T3 — destructive drills (maintenance window, owner + coder)

Each drill: precondition → command → expected → cleanup → evidence file.

| ID | Drill | Command (abridged) | Expected |
|---|---|---|---|
| D1 | service stop | `sudo systemctl stop $UNIT` → doctor | `SERVICE_DOWN`, exit 1; `start` → HEALTHY |
| D2 | registration delete + self-repair | `gh api -X DELETE /repos/$SLUG/actions/runners/$ID`; wait ≤ 5 min | watchdog logs one repair; agent back with labels; doctor exit 0; **no PAT in `ps -eo args`** |
| D3 | skew (no host clock change) | `RUNNER_DOCTOR_FAKE_SKEW=3600 runner_doctor.sh --check` | exit 2, `CLOCK_SKEW`, no repair |
| D4 | label removal | `gh api -X DELETE .../labels/rocm`; doctor; repair | `LABELS_MISMATCH`, exit 3; repair restores labels |
| D5 | busy guard | dispatch a GPU job; run watchdog | `JOB_IN_FLIGHT`, no repair, exit 0 |
| D6 | PAT rotation | replace `runner.pat`, `--check-pat`, doctor | valid; repair works |
| D7 | drift | edit installed script; `install --check` | `DRIFT`; `--apply` restores |
| D8 | alert dedup | force 3 broken ticks | 1 alert line, not 3 |

Safety: D2 and D4 mutate the registration — run only when no PR is waiting on
the runner, and keep the PAT and a registration token ready for manual
recovery. D3 must **never** change the host clock.

### T4 — end-to-end CI

1. `gh workflow run "Self-Hosted GPU CI" --ref wp/7G-C-closure`.
2. Assert: conclusion `success`; runner name `gfx1150-host`; lane line
   `GPU lane: 45 passed, 0 skipped, ...`; `PASS: the GPU lane ran, with no skips`.
3. Cross-check on the host: newest `_diag/Worker_*.log` contains
   `Job result after all job steps finish: Succeeded`.
4. Restore the required check in ruleset `26990297`; confirm it appears green
   on a protected branch.
5. Red-team: a PR with a failing GPU test must be blocked (repeat of G6 proof).
6. Observe one nightly run after the cron change; record queue time (target
   < 10 min).

---

## 11. Troubleshooting decision table

| Symptom | Layer | First command | Cause | Fix |
|---|---|---|---|---|
| Job queued "Waiting for a runner", UI shows **Idle** | L4 | `runner_doctor.sh --check` | missing `rocm`/`gfx1150` label or group access | `--repair` (re-register with spec labels) |
| Job queued, UI shows **Offline**, process alive | L0/L3 | doctor | clock skew or stale session | fix time; `systemctl restart $UNIT` |
| Log: "registration has been deleted" | L0 first | doctor | **usually skew**, not deletion | if exit 2: fix clock, then re-register |
| Watchdog alerts every 5 min, runner works | L6 | doctor | health check wrong (mtime/window) | journal/session-log fix (C2b) |
| Watchdog repairs every 5 min | L6 | doctor + log | health check wrong or cooldown missing | same + cooldown |
| Nightly always queued | L5 | doctor | cron before boot | move cron after boot window |
| GPU lane fails at import | L5/host | preflight step | ROCm/PATH/extension | `preflight_gpu_runner.sh` |
| GPU lane "45 skipped" | — | junit guard | extension missing | **fail by design**; fix the build |
| Required check never appears | L5 | doctor | job renamed / ruleset drift | restore name + ruleset |
| Repair fails: "PAT file … not readable" | L6 | `install --check` | PAT not deployed | deploy PAT (owner) |
| Repair fails: 401/403 | L6 | `--check-pat` | PAT expired/scope | rotate PAT |
| `config.sh` fails | L3 | log tail | network/skew/token | doctor L0, then retry |
| Host rebooted, job queued | L1 | doctor | runner not yet up | wait; timer `OnBootSec=5min` |

---

## 12. Work packages (C2a–C2g)

One package per commit; each has its own acceptance and evidence. No package
merges before the auditor signs the gate.

### C2a — spec + doctor skeleton (read-only) — **LANDED 2026-11-14**

- Add `scripts/ci/runner.env`, `scripts/ci/runner_doctor.sh` (L0–L6, `--check`,
  `--json`, `--no-network`).
- No host mutation, no repair path.
- **Acceptance:** `--check` on the current host exits 0 or 2/3 with an accurate
  verdict; output matches §5.2; no secret in argv.

### C2b — health algorithm rewrite — **LANDED 2026-11-14**

- Replace the mtime/window check with §5.4 (`session_log`, `l3_session`),
  add the skew guard (§5.3) and the grace state.
- Update `tests/test_runner_watchdog.py` cases 1–12.
- **Acceptance:** the live host's healthy runner yields exit 0 while the
  mtime-poisoned fixture yields exit 0 too (both regressions); skew yields 2
  with no repair.

### C2c — watchdog hardening — **LANDED 2026-11-14**

- Transition-based alerts, state file, `OnBootSec=5min`, remove `OnFailure`,
  logrotate, cooldown preserved, job-in-flight preserved.
- **Acceptance:** D5, D8; no alert while healthy; one alert per outage.

### C2d — installer + drift — **LANDED 2026-11-14**

- `scripts/ci/install_runner_watchdog.sh` (`--apply/--check/--uninstall`).
- **Acceptance:** D7; `--check` reports `DRIFT` after a manual edit and `OK`
  after `--apply`.

### C2e — workflow hardening — **LANDED 2026-11-14**

- §9 changes (permissions, concurrency, fork guard, preflight, pip freeze,
  cron 05:00), keeping the job name and the junit guard.
- **Acceptance:** T4 steps 1–3 green; the required check name unchanged.

### C2f — contract tests — **LANDED 2026-11-14**

- `tests/test_ci_contract.py` (10 assertions) + static guards; update
  `EXPECTED_LANES` if a new test file is added.
- **Acceptance:** CPU lane green; injecting a wrong label or a renamed job
  makes the test fail (mutation check recorded).

### C2g — host drills + evidence + enforcement restore

- PAT deployed by the owner (`/etc/gfx1150-runner/runner.pat`, `600:root`).
- D1–D8 transcripts, doctor before/after, T4 run IDs.
- Restore `GPU correctness (self-hosted gfx1150)` in ruleset `26990297`.
- Close the enforcement waiver with the date and run ID.
- **Acceptance:** all drills pass; the required check is green on `main`; the
  waiver is closed.

---

## 13. Evidence contract

`audit/evidence/G7/7G-C/c2-runner/` must contain:

| File | Content |
|---|---|
| `runner-spec.txt` | `runner.env` as committed (sha256) |
| `doctor-before.txt` / `doctor-after.txt` | human output + exit code |
| `doctor.json` | `--json` output, diffable |
| `install-check.txt` | `install --check` before/after |
| `drill-D1…D8.txt` | command, output, exit code, timestamp, verdict |
| `pat-handling.txt` | `ps` snapshot during repair (no PAT), log scan (no PAT), token window documented |
| `labels.txt` | API JSON of the agent labels before/after a repair |
| `e2e-run.txt` | workflow run URL/ID, conclusion, lane line, worker log tail |
| `ruleset-restore.txt` | ruleset JSON showing the required check restored |
| `notes.md` | what changed, what was measured, what remains open |

---

## 14. Gate exit (C2 portion of G7-C)

- [x] `runner_doctor.sh --check` exits 0 on the healthy host, and exits 2 with
      no repair under simulated skew. (D3: `drill-D3-2026-11-15.txt`)
- [x] The mtime-poison regression (case 2) and the deletion-before-listen
      regression (case 3) pass. (`tests/test_runner_doctor.py`)
- [x] `tests/test_ci_contract.py` green; a deliberate label/job-name mutation
      fails it. (11 tests, 5 mutation checks)
- [x] PAT deployed, never in argv/logs; D2 repair transcript recorded.
      (`drill-D2-2026-11-15.txt`, D6 evidence)
- [x] D1–D8 pass; alert fires once per transition.
      (`drill-D{1..8}-2026-11-15.txt`)
- [x] `install --check` reports no drift. (D7: `DRIFT` → `--apply` → `OK`)
- [x] T4 green: dispatch on `main` run 43725517391; required check on the PR
      run 43728354793; red-team block (G6 PR #11).
- [ ] First nightly on the merged `main` — post-merge observation, tracked as
      a closure follow-up (not a merge blocker).
- [x] Enforcement waiver closed; ruleset `26990297` requires the GPU check
      again. (`audit/G6_ENFORCEMENT_WAIVER_2026-11-13.md` §Closure)
- [x] CPU 621, GPU 45, sdist lane green, strict claims (baseline 0 bytes),
      canaries 16/16 at the frozen candidate `582ff05`.
      (`final-verification-2026-11-15.log`)

---

## Appendix A — manual triage until the doctor lands

Paste this on the host; it reproduces L0–L4 without any new tooling:

```bash
S=actions.runner.KupipiKuki-gfx1150-inference.gfx1150-host.service
echo "== L0 time =="; timedatectl | grep -E 'System clock|RTC in local|NTP'
python3 - <<'PY'
import subprocess, email.utils, time
h=subprocess.run(["curl","-sI","https://api.github.com"],capture_output=True,text=True).stdout
d=[l.split(":",1)[1].strip() for l in h.splitlines() if l.lower().startswith("date:")]
print("skew:", round(time.time()-email.utils.parsedate_to_datetime(d[0]).timestamp()), "s" if d else "unknown")
PY
echo "== L1/L2 =="; systemctl show "$S" -p ActiveState -p SubState -p ExecMainStartTimestamp --value
pgrep -u kupipi -af 'Runner\.Listener'
echo "== L3 session (current start only) =="
start=$(systemctl show "$S" -p ExecMainStartTimestamp --value)
echo "service start: $start"
ls -lt --time-style=long-iso ~/actions-runner/_diag/Runner_*.log | head -3
echo "(match the filename to the start time, NOT the mtime)"
echo "== L6 watchdog =="; systemctl is-enabled gfx1150-runner-watchdog.timer; tail -3 /var/log/ensure-runner.log
```

**Rule of thumb:** if the runner is `active/running` with a live
`Runner.Listener` but jobs queue, the problem is **never** the process — it is
time (L0), labels/group (L4), or a stale session (L3 restart). Do not
re-register before checking L0.
