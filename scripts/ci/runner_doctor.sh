#!/usr/bin/env bash
# C2a — gfx1150 runner doctor: one read-only, layered diagnosis.
#
# Replaces ad-hoc journal grepping. Layers, in order:
#
#   L0 time       RTC in UTC, NTP synchronized, skew vs GitHub <= 60 s
#   L1 service    the systemd unit is active/running
#   L2 process    a Runner.Listener process of the runner user is alive
#   L3 session    the diag log OF THE CURRENT SERVICE START is listening and
#                 was not rejected afterwards (never by mtime, never by a
#                 moving journal window: this host's clock jumps reorder both)
#   L4 routing    the agent is visible to the repo and carries the spec labels
#                 (GET /repos/.../actions/runners; PAT via a 0600 --config file)
#   L5 contract   ci-gpu.yml agrees with the runner spec (runs-on, job name,
#                 cron after boot, no push trigger, hardening items)
#   L6 watchdog   timer, installed script (drift), PAT, log freshness
#
# Exit codes (stable contract):
#   0 HEALTHY          warnings allowed
#   1 OFFLINE          repairable (service/listener/registration)
#   2 CLOCK_SKEW       fix timekeeping first; repair must NOT run
#   3 MISCONFIGURED    labels/group/PAT/contract; owner action
#
# This is the read-only C2a skeleton: it never repairs. C2b adds --repair.
#
# Usage: runner_doctor.sh [--check] [--json] [--quiet] [--no-network]
#
# Test hook: RUNNER_DOCTOR_FAKE_SKEW=<seconds> overrides the network skew so
# the clock-skew drill (D3) never has to change the host clock.

set -uo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=runner.env
. "${SCRIPT_DIR}/runner.env"

REPO_ROOT="${REPO_ROOT:-$(cd -- "${SCRIPT_DIR}/../.." && pwd)}"
WORKFLOW="${REPO_ROOT}/.github/workflows/ci-gpu.yml"

JSON=0
QUIET=0
NO_NETWORK=0
WARN_COUNT=0

usage() {
  cat <<'EOF'
Usage: runner_doctor.sh [--check] [--json] [--quiet] [--no-network]

  --check       read-only diagnosis (default)
  --json        machine-readable output
  --quiet       print only the verdict line
  --no-network  skip L0 skew and L4 routing (offline diagnosis)

Exit: 0 healthy, 1 offline, 2 clock skew, 3 misconfigured.
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --check) : ;;
    --json) JSON=1 ;;
    --quiet) QUIET=1 ;;
    --no-network) NO_NETWORK=1 ;;
    --repair)
      printf 'runner_doctor: --repair is added by C2b; this build is read-only\n' >&2
      exit 3
      ;;
    -h|--help) usage; exit 0 ;;
    *)
      printf 'runner_doctor: unknown option: %s\n' "$1" >&2
      usage >&2
      exit 3
      ;;
  esac
  shift
done

ROWS_FILE="$(mktemp "${TMPDIR:-/tmp}/runner-doctor-rows.XXXXXX")"
HDR_FILE=""
cleanup() {
  rm -f "${ROWS_FILE}"
  [ -n "${HDR_FILE}" ] && rm -f "${HDR_FILE}"
}
trap cleanup EXIT

record() { printf '%s|%s|%s\n' "$1" "$2" "$3" >>"${ROWS_FILE}"; }
pass() { record "$1" PASS "$2"; }
warn() { record "$1" WARN "$2"; WARN_COUNT=$((WARN_COUNT + 1)); }
skip() { record "$1" SKIP "$2"; }

verdict_for() {
  case "$1" in
    1) printf 'OFFLINE' ;;
    2) printf 'CLOCK_SKEW' ;;
    3) printf 'MISCONFIGURED' ;;
    *) printf 'UNHEALTHY' ;;
  esac
}

emit_json() {
  python3 - "${ROWS_FILE}" "$1" "$2" "$3" "${WARN_COUNT}" <<'PY'
import json
import sys

rows_path, verdict, cause, code, warnings = sys.argv[1:6]
checks = []
with open(rows_path, encoding="utf-8") as fh:
    for line in fh:
        line = line.rstrip("\n")
        if not line:
            continue
        layer, status, message = line.split("|", 2)
        checks.append({"layer": layer, "status": status, "message": message})
print(json.dumps({
    "verdict": verdict,
    "cause": cause,
    "exit_code": int(code),
    "warnings": int(warnings),
    "checks": checks,
}, indent=2))
PY
}

finish() {
  local verdict="$1" cause="$2" code="$3"
  if [ "${JSON}" = 1 ]; then
    emit_json "${verdict}" "${cause}" "${code}"
  elif [ "${QUIET}" = 1 ]; then
    printf 'VERDICT: %s' "${verdict}"
    [ -n "${cause}" ] && printf ' - %s' "${cause}"
    printf '\n'
  else
    printf 'gfx1150 runner doctor - %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    while IFS='|' read -r layer status msg; do
      [ -n "${layer}" ] || continue
      printf '  %-3s %-5s %s\n' "${layer}" "${status}" "${msg}"
    done <"${ROWS_FILE}"
    printf 'VERDICT: %s' "${verdict}"
    [ -n "${cause}" ] && printf ' - %s' "${cause}"
    [ "${WARN_COUNT}" -gt 0 ] && printf ' (%d warning(s))' "${WARN_COUNT}"
    printf '\n'
  fi
  exit "${code}"
}

fail() {
  record "$1" FAIL "$2"
  finish "$(verdict_for "$3")" "$2" "$3"
}

# ---------------------------------------------------------------- L0 time --

github_skew_secs() {
  local date_hdr
  date_hdr="$(curl -fsSI --max-time 10 https://api.github.com 2>/dev/null \
    | sed -n 's/^[Dd]ate: //p' | tr -d '\r')"
  [ -n "${date_hdr}" ] || return 1
  python3 - "${date_hdr}" <<'PY'
import email.utils
import sys
import time

print(round(time.time() - email.utils.parsedate_to_datetime(sys.argv[1]).timestamp()))
PY
}

layer_l0() {
  local localrtc ntp skew abs_skew
  localrtc=""
  ntp=""
  if command -v timedatectl >/dev/null 2>&1; then
    localrtc="$(timedatectl show -p LocalRTC --value 2>/dev/null || true)"
    ntp="$(timedatectl show -p NTPSynchronized --value 2>/dev/null || true)"
  fi
  if [ -n "${localrtc}" ] && [ "${localrtc}" != "no" ]; then
    fail L0 "RTC is in local time (LocalRTC=${localrtc}); run 'timedatectl set-local-rtc 0'" 2
  fi
  if [ -n "${ntp}" ] && [ "${ntp}" != "yes" ]; then
    fail L0 "NTP is not synchronized (NTPSynchronized=${ntp}); the runner cannot authenticate reliably" 2
  fi
  if [ -n "${RUNNER_DOCTOR_FAKE_SKEW:-}" ]; then
    skew="${RUNNER_DOCTOR_FAKE_SKEW}"
  elif [ "${NO_NETWORK}" = 1 ]; then
    warn L0 "skew not checked (--no-network)"
    return 0
  else
    skew="$(github_skew_secs)" || {
      warn L0 "cannot reach api.github.com; skew unknown"
      return 0
    }
  fi
  skew="${skew#+}"
  case "${skew}" in
    ''|*[!0-9-]*)
      warn L0 "unparseable skew '${skew}'"
      return 0
      ;;
  esac
  abs_skew=$((skew < 0 ? -skew : skew))
  if [ "${abs_skew}" -gt "${SKEW_FAIL_SECS}" ]; then
    fail L0 "CLOCK_SKEW: host is ${skew}s from GitHub (limit ${SKEW_FAIL_SECS}s); fix timekeeping first" 2
  fi
  if [ "${abs_skew}" -gt "${SKEW_WARN_SECS}" ]; then
    warn L0 "clock is ${skew}s from GitHub (warn > ${SKEW_WARN_SECS}s)"
  else
    pass L0 "rtc=utc ntp=synchronized skew=${skew}s"
  fi
}

# ------------------------------------------------------------- L1 service --

layer_l1() {
  local state sub start restarts
  state="$(systemctl show "${SERVICE_UNIT}" -p ActiveState --value 2>/dev/null || true)"
  sub="$(systemctl show "${SERVICE_UNIT}" -p SubState --value 2>/dev/null || true)"
  start="$(systemctl show "${SERVICE_UNIT}" -p ExecMainStartTimestamp --value 2>/dev/null || true)"
  restarts="$(systemctl show "${SERVICE_UNIT}" -p NRestarts --value 2>/dev/null || true)"
  if [ -z "${state}" ]; then
    fail L1 "unit ${SERVICE_UNIT} not found (is the runner installed?)" 1
  fi
  if [ "${state}" != "active" ] || [ "${sub}" != "running" ]; then
    fail L1 "SERVICE_DOWN: service is ${state:-unknown}/${sub:-unknown}, not active/running" 1
  fi
  if [ -n "${restarts}" ] && [ "${restarts}" -gt 0 ] 2>/dev/null; then
    warn L1 "service has restarted ${restarts} time(s) since start"
  fi
  pass L1 "active/running since ${start:-unknown}"
}

# ------------------------------------------------------------- L2 process --

layer_l2() {
  local pids first
  pids="$(pgrep -u "${RUNNER_USER}" -f 'Runner\.Listener' 2>/dev/null | tr '\n' ' ' || true)"
  if [ -z "${pids// /}" ]; then
    fail L2 "LISTENER_DEAD: no Runner.Listener process for user ${RUNNER_USER}" 1
  fi
  first="${pids%% *}"
  pass L2 "Runner.Listener pid=${first} user=${RUNNER_USER}"
}

# ------------------------------------------------------------- L3 session --

service_uptime_secs() {
  local start
  start="$(systemctl show "${SERVICE_UNIT}" -p ExecMainStartTimestamp --value 2>/dev/null || true)"
  [ -n "${start}" ] || { printf '0\n'; return 0; }
  printf '%s\n' "$(( $(date +%s) - $(date -d "${start}" +%s 2>/dev/null || date +%s) ))"
}

session_log() {
  # The runner names each diag file with its own start time
  # (Runner_YYYYMMDD-HHMMSS-utc.log). systemd records the same start time.
  # Match by NAME, never by mtime: this host's clock jumps reorder mtimes.
  # Only a file at/after the service start (minus 5 s of granularity) can
  # belong to this session.
  local start stamp f base fsec delta best="" best_delta=999999
  start="$(systemctl show "${SERVICE_UNIT}" -p ExecMainStartTimestamp --value 2>/dev/null || true)"
  [ -n "${start}" ] || return 1
  stamp="$(date -d "${start}" +%s 2>/dev/null)" || return 1
  for f in "${RUNNER_DIR}"/_diag/Runner_*-utc.log; do
    [ -e "${f}" ] || continue
    base="${f##*/Runner_}"
    base="${base%-utc.log}"
    fsec="$(date -u -d "${base:0:8} ${base:9:2}:${base:11:2}:${base:13:2}" +%s 2>/dev/null)" || continue
    [ "${fsec}" -ge "$((stamp - 5))" ] || continue
    [ "${fsec}" -le "$((stamp + 180))" ] || continue
    delta=$((fsec - stamp))
    [ "${delta}" -lt 0 ] && delta=$(( -delta ))
    if [ "${delta}" -lt "${best_delta}" ]; then
      best="${f}"
      best_delta="${delta}"
    fi
  done
  [ -n "${best}" ] || return 1
  printf '%s\n' "${best}"
}

layer_l3() {
  local log uptime_s last_listen last_bad
  log="$(session_log)" || {
    uptime_s="$(service_uptime_secs)"
    if [ "${uptime_s}" -lt "${STARTUP_GRACE_SECS}" ]; then
      pass L3 "STARTING (service up ${uptime_s}s, no session log yet)"
      return 0
    fi
    fail L3 "NOT_LISTENING: no diag log matches the current service start (${uptime_s}s up)" 1
  }
  # The diag file is append-only: line order is event order for this session.
  # `|| true` keeps grep's exit 1 (marker absent) from aborting under -u.
  last_listen="$(grep -nF "${LISTEN_MARKER}" "${log}" | tail -1 | cut -d: -f1 || true)"
  last_bad="$(grep -nE "${DELETED_MARKER}|${SKEW_MARKER}" "${log}" | tail -1 | cut -d: -f1 || true)"

  if [ -z "${last_listen}" ]; then
    uptime_s="$(service_uptime_secs)"
    if [ "${uptime_s}" -lt "${STARTUP_GRACE_SECS}" ]; then
      pass L3 "STARTING (no listen marker yet, ${uptime_s}s up)"
      return 0
    fi
    if grep -qF "${SKEW_MARKER}" "${log}"; then
      fail L3 "SESSION_SKEW: the runner rejected its token as not-yet-valid (host clock)" 2
    fi
    fail L3 "NOT_LISTENING: service is up but never listened (crash loop or rejected session)" 1
  fi

  if [ -n "${last_bad}" ] && [ "${last_bad}" -gt "${last_listen}" ]; then
    if grep -nF "${SKEW_MARKER}" "${log}" | awk -F: -v n="${last_bad}" '$1 == n { found = 1 } END { exit !found }'; then
      fail L3 "SESSION_SKEW: token rejected as not-yet-valid after listening (host clock)" 2
    fi
    fail L3 "REGISTRATION_DELETED: GitHub rejected the registration after listening" 1
  fi
  pass L3 "log=${log##*/} listening, no later rejection"
}

# ------------------------------------------------------------- L4 routing --

layer_l4() {
  local pat_value hdr rc=0 json out
  if [ ! -e "${PAT_FILE}" ]; then
    warn L4 "PAT ${PAT_FILE} missing; labels/group not verifiable (owner action)"
    return 0
  fi
  if [ ! -r "${PAT_FILE}" ]; then
    warn L4 "PAT ${PAT_FILE} not readable by this user; run as root to verify labels"
    return 0
  fi
  pat_value="$(tr -d '\r\n' <"${PAT_FILE}")"
  case "${pat_value}" in
    github_pat_*|ghp_*) ;;
    "") warn L4 "PAT file is empty; labels/group not verifiable"; return 0 ;;
    *) warn L4 "PAT file does not look like a GitHub PAT; labels/group not verifiable"; return 0 ;;
  esac
  HDR_FILE="$(mktemp "${TMPDIR:-/tmp}/.runner-doctor-hdr.XXXXXX")"
  chmod 600 "${HDR_FILE}"
  printf 'header = "Authorization: Bearer %s"\n' "${pat_value}" >"${HDR_FILE}"
  unset pat_value
  json="$(curl -fsS --max-time 20 -K "${HDR_FILE}" \
    "https://api.github.com/repos/${REPO_SLUG}/actions/runners?per_page=100" 2>/dev/null)" || rc=$?
  rm -f "${HDR_FILE}"
  HDR_FILE=""
  if [ "${rc}" -ne 0 ]; then
    fail L4 "cannot list runners (PAT scope or network); expected Administration: write" 3
  fi
  out="$(python3 - "${json}" "${RUNNER_NAME}" "${RUNNER_LABELS}" <<'PY'
import json
import sys

data, name, want_csv = json.loads(sys.argv[1]), sys.argv[2], sys.argv[3]
want = [x.strip() for x in want_csv.split(",") if x.strip()]
runners = data.get("runners", [])
me = next((r for r in runners if r.get("name") == name), None)
if me is None:
    print(f"REGISTRATION_NOT_VISIBLE: {name} is not available to this repo "
          f"(deleted or runner-group access)")
    sys.exit(3)
labels = {label["name"] for label in me.get("labels", [])}
missing = [label for label in want if label not in labels]
if missing:
    print(f"LABELS_MISMATCH: missing {missing}; labels={sorted(labels)}")
    sys.exit(3)
print(f"agent={me.get('id')} status={me.get('status')} labels={sorted(labels)}")
PY
)" || rc=$?
  if [ "${rc}" -ne 0 ]; then
    fail L4 "${out}" "${rc}"
  fi
  case "${out}" in
    *"status=offline"*)
      warn L4 "${out} (GitHub reports offline: stale session?)"
      ;;
    *)
      pass L4 "${out}"
      ;;
  esac
}

# ------------------------------------------------------------ L5 contract --

layer_l5() {
  if [ ! -r "${WORKFLOW}" ]; then
    fail L5 "workflow ${WORKFLOW} is missing or unreadable" 3
  fi
  while IFS='|' read -r status msg; do
    [ -n "${status}" ] || continue
    case "${status}" in
      PASS) pass L5 "${msg}" ;;
      WARN) warn L5 "${msg}" ;;
      FAIL) fail L5 "${msg}" 3 ;;
      *) warn L5 "${msg}" ;;
    esac
  done < <(python3 - "${WORKFLOW}" "${RUNNER_LABELS}" "${REQUIRED_GPU_CHECK}" \
    "${BOOT_WINDOW_UTC}" "${CRON_MARGIN_MIN}" <<'PY'
import re
import sys

path, labels_csv, required_name, boot, margin_want = sys.argv[1:6]
try:
    text = open(path, encoding="utf-8").read()
except OSError as exc:
    print(f"FAIL|cannot read {path}: {exc}")
    raise SystemExit(0)

automatic = {"self-hosted", "Linux", "X64"}
want = {x.strip() for x in labels_csv.split(",") if x.strip()} | automatic

match = re.search(r"^\s*runs-on:\s*\[(.*?)\]\s*$", text, re.M)
if not match:
    print("FAIL|no runs-on list found in ci-gpu.yml")
else:
    got = {x.strip().strip("'\"") for x in match.group(1).split(",") if x.strip()}
    missing = sorted(got - want)
    if missing:
        print(f"FAIL|runs-on labels not on the runner: {missing}")
    else:
        print(f"PASS|runs-on {sorted(got)} is covered by the runner labels")

match = re.search(r"^\s{4}name:\s*(.+?)\s*$", text, re.M)
if not match:
    print("FAIL|no job name found")
elif match.group(1) != required_name:
    print(f"FAIL|job name '{match.group(1)}' != required check '{required_name}'")
else:
    print("PASS|job name matches the required check")

match = re.search(r"cron:\s*[\"']([^\"']+)[\"']", text)
if not match:
    print("WARN|no cron schedule found")
else:
    fields = match.group(1).split()
    try:
        cron_min = int(fields[1]) * 60 + int(fields[0])
        boot_h, boot_m = (int(x) for x in boot.split(":"))
        boot_min = boot_h * 60 + boot_m
        margin = (cron_min - boot_min) % (24 * 60)
    except (IndexError, ValueError):
        print(f"WARN|cannot parse cron '{match.group(1)}'")
    else:
        if margin < int(margin_want):
            print(f"WARN|cron {match.group(1)} leaves {margin} min after boot {boot} "
                  f"(want >= {margin_want})")
        else:
            print(f"PASS|cron {match.group(1)} clears boot {boot} by {margin} min")

if re.search(r"^\s{2}push:", text, re.M):
    print("FAIL|ci-gpu.yml has a push trigger (C4 decided: not allowed)")
else:
    print("PASS|no push trigger")

if re.search(r"^permissions:\s*$", text, re.M):
    print("PASS|permissions block present")
else:
    print("WARN|missing permissions: contents: read (C2e)")

if re.search(r"^concurrency:\s*$", text, re.M):
    print("PASS|concurrency group present")
else:
    print("WARN|missing concurrency group (C2e)")

if "head.repo.full_name" in text:
    print("PASS|fork-PR guard present")
else:
    print("WARN|no fork-PR guard (C2e)")

if "skip is not a pass" in text:
    print("PASS|junit skip-is-not-pass guard present")
else:
    print("FAIL|junit skip-is-not-pass guard missing")
PY
  )
}

# ------------------------------------------------------------ L6 watchdog --

layer_l6() {
  local enabled active installed sha_repo sha_inst perms now mtime age
  enabled="$(systemctl is-enabled "${WATCHDOG_TIMER}" 2>/dev/null || true)"
  active="$(systemctl is-active "${WATCHDOG_TIMER}" 2>/dev/null || true)"
  if [ "${enabled}" = "enabled" ] && [ "${active}" = "active" ]; then
    pass L6 "timer ${WATCHDOG_TIMER} enabled and active"
  elif [ "${enabled}" = "enabled" ]; then
    warn L6 "timer ${WATCHDOG_TIMER} enabled but ${active:-inactive}"
  else
    warn L6 "timer ${WATCHDOG_TIMER} is ${enabled:-absent}: self-repair disabled"
  fi

  installed=""
  for candidate in "${WATCHDOG_INSTALLED}" "${WATCHDOG_LEGACY_INSTALLED}"; do
    if [ -e "${candidate}" ]; then
      installed="${candidate}"
      break
    fi
  done
  if [ -z "${installed}" ]; then
    warn L6 "watchdog script not installed (C2d installer)"
  else
    sha_repo="$(sha256sum "${SCRIPT_DIR}/ensure_runner_registered.sh" 2>/dev/null | cut -d' ' -f1)"
    sha_inst="$(sha256sum "${installed}" 2>/dev/null | cut -d' ' -f1)"
    if [ -n "${sha_repo}" ] && [ "${sha_repo}" = "${sha_inst}" ]; then
      pass L6 "installed watchdog matches the repository"
    else
      warn L6 "installed watchdog DRIFTED from the repository (${installed})"
    fi
  fi

  if [ -e "${PAT_FILE}" ]; then
    perms="$(stat -c '%a:%U' "${PAT_FILE}" 2>/dev/null || true)"
    if [ "${perms}" = "${PAT_MODE}:${PAT_OWNER}" ]; then
      pass L6 "PAT ${PAT_FILE} is ${perms}"
    else
      warn L6 "PAT ${PAT_FILE} is ${perms:-unknown}, expected ${PAT_MODE}:${PAT_OWNER}"
    fi
    if [ ! -r "${PAT_FILE}" ]; then
      warn L6 "PAT present but not readable by this user; run as root to verify content"
    else
      case "$(tr -d '\r\n' <"${PAT_FILE}")" in
        github_pat_*|ghp_*) pass L6 "PAT content looks valid" ;;
        "") warn L6 "PAT file is empty" ;;
        *) warn L6 "PAT content does not look like a GitHub PAT" ;;
      esac
    fi
  else
    warn L6 "PAT ${PAT_FILE} missing: self-repair cannot run (owner action)"
  fi

  if [ -r "${WATCHDOG_LOG}" ]; then
    now="$(date +%s)"
    mtime="$(stat -c %Y "${WATCHDOG_LOG}" 2>/dev/null || printf '%s' "${now}")"
    age=$((now - mtime))
    if [ "${age}" -gt 900 ]; then
      warn L6 "watchdog log has not been written for ${age}s (timer stuck or disabled)"
    else
      pass L6 "watchdog log updated ${age}s ago"
    fi
  else
    warn L6 "watchdog log ${WATCHDOG_LOG} not readable"
  fi
}

layer_l0
layer_l1
layer_l2
layer_l3
if [ "${NO_NETWORK}" = 1 ]; then
  skip L4 "network checks skipped (--no-network)"
else
  layer_l4
fi
layer_l5
layer_l6
finish HEALTHY "" 0
