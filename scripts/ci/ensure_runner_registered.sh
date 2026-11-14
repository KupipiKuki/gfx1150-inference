#!/usr/bin/env bash
# 7G-C (C2) — self-hosted runner registration self-repair (G6-QF-2).
#
# The runner's server-side registration is deleted server-side (observed four
# times in four days, no local action): the local `.runner`/`.credentials`
# stay stale, the service exits with "the runner registration has been deleted
# from the server", and the required GPU check queues forever.
#
# This script runs ON the gfx1150 host as root (systemd timer, every 5
# minutes) and repairs the registration without human action:
#
#   1. Is the runner healthy? Health is decided from the CURRENT state only:
#      the service is active+running, a Runner.Listener process of the runner
#      user is alive, and the newest _diag/Runner_*.log shows that the runner
#      is listening AND that its registration was not deleted (a restart on
#      the same start refreshes nothing there: a deleted registration stays
#      visible in that log until config.sh rewrites it).
#      -> healthy, exit 0 and do nothing.
#      A RUNNING RUNNER IS NEVER "OFFLINE" BECAUSE IT HAS BEEN UP A WHILE:
#      no moving journal window is used for the startup-only
#      "Listening for Jobs" marker (audit BLOCKER-7G-C-1).
#   2. Otherwise obtain a fresh registration token with the repo-admin PAT
#      (Administration: write), stored OUTSIDE the repository:
#        /etc/gfx1150-runner/runner.pat   (mode 0600, owner root)
#      via POST /repos/{owner}/{repo}/actions/runners/registration-token.
#   3. Re-run config.sh --replace --unattended with the existing name/labels.
#   4. Restart the service.
#
# Secret handling. The PAT is never written to a log, a file in the
# repository, a workflow, the service environment, or echoed, and it NEVER
# appears in argv: it is written to a root-owned 0600 temp curl config file
# and handed to curl via --config, which keeps the Authorization header out
# of /proc/<pid>/cmdline (audit BLOCKER-7G-C-2).
# The one-time registration token is a different matter: it is passed to
# config.sh as a single argument of a process run AS THE RUNNER USER (via
# runuser -u), so it appears transiently in /proc/<pid>/cmdline and there is
# readable by any local user for roughly the one second config.sh needs. It
# is single-use, short-lived and grants only runner registration, which is
# accepted as low severity — this is documented here, not hidden.
#
# Repair discipline (audit BLOCKER-7G-C-1): a repair is never attempted
# while a Runner.Worker process exists (a job is in flight), and attempts
# are rate-limited to one per cooldown period (default 30 minutes, recorded
# on tmpfs at /run/ensure-runner.last-repair) so a persistent failure cannot
# loop the 5-minute timer. Every attempt is logged and failures exit
# non-zero.
#
# Watchdog contract: exit 0 = healthy or repaired; non-zero = the runner is
# NOT online after the repair attempt (the OnFailure alert + the log line
# "RUNNER-REGISTRATION-OFFLINE" make the outage visible before it blocks a
# PR).
#
# Usage: sudo scripts/ci/ensure_runner_registered.sh [--check]
#   --check  verify-only (no repair); exit 0 healthy / 1 offline.

set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/KupipiKuki/gfx1150-inference}"
RUNNER_DIR="${RUNNER_DIR:-/home/kupipi/actions-runner}"
RUNNER_NAME="${RUNNER_NAME:-gfx1150-host}"
RUNNER_LABELS="${RUNNER_LABELS:-gfx1150,rocm}"
SERVICE_UNIT="${SERVICE_UNIT:-actions.runner.KupipiKuki-gfx1150-inference.gfx1150-host.service}"
SERVICE_USER="${SERVICE_USER:-kupipi}"
PAT_FILE="${PAT_FILE:-/etc/gfx1150-runner/runner.pat}"
PAT_OWNER="${PAT_OWNER:-root}"
LISTEN_MARKER="Listening for Jobs"
LOG_TAG="ensure-runner"
LOG_FILE="${LOG_FILE:-/var/log/${LOG_TAG}.log}"
CURL_CONNECT_TIMEOUT_SECS="${CURL_CONNECT_TIMEOUT_SECS:-10}"
CURL_MAX_TIME_SECS="${CURL_MAX_TIME_SECS:-60}"
CONFIG_TIMEOUT_SECS="${CONFIG_TIMEOUT_SECS:-120}"
RESTART_TIMEOUT_SECS="${RESTART_TIMEOUT_SECS:-30}"

log() {
  local line
  line="$(printf '%s %s' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*")"
  printf '%s\n' "${line}" >&2
  # best-effort persistent log; never fatal (non-root --check runs)
  { printf '%s\n' "${line}" >>"${LOG_FILE}" ; } 2>/dev/null || true
}

die() { log "RUNNER-REGISTRATION-OFFLINE: $*"; exit 1; }

CHECK_ONLY=0
[ "${1:-}" = "--check" ] && CHECK_ONLY=1

runner_online() {
  systemctl is-active --quiet "${SERVICE_UNIT}" || return 1
  # The service must be genuinely active/running (not activating or
  # crash-looping), not merely "not failed". The output is captured before
  # grepping: grep -q over a live pipe under pipefail races the writer
  # (early exit can SIGPIPE it) and would make health flaky.
  local svc_state
  svc_state="$(systemctl show "${SERVICE_UNIT}" -p ActiveState -p SubState --value 2>/dev/null || true)"
  grep -q '^active$' <<<"${svc_state}" || return 1
  # The listener process of the *current* service start must be alive.
  pgrep -u "${SERVICE_USER}" -f 'Runner\.Listener' >/dev/null || return 1
  # And the newest diag log of the current start must show a live,
  # non-deleted registration. "Listening for Jobs" is a startup-only
  # marker: it is judged from the newest diag file, never from a moving
  # journal window of the last N minutes (a runner that has been up for
  # 30 minutes is still healthy — see audit BLOCKER-7G-C-1).
  local newest
  # `|| true` guards the ls|head against the same SIGPIPE race.
  newest="$(ls -t "${RUNNER_DIR}"/_diag/Runner_*.log 2>/dev/null | head -1 || true)"
  [ -n "${newest}" ] || return 1
  grep -q "${LISTEN_MARKER}" "${newest}" || return 1
  ! grep -q "registration has been deleted" "${newest}" || return 1
  return 0
}

if runner_online; then
  log "runner ${RUNNER_NAME} is online (service active, listening for jobs)"
  exit 0
fi

_svc_state="$(systemctl is-active "${SERVICE_UNIT}" 2>/dev/null || true)"
log "runner ${RUNNER_NAME} offline (service: ${_svc_state:-unknown}); repair start"

if [ "${CHECK_ONLY}" = "1" ]; then
  die "verify-only: runner offline (repair skipped)"
fi

# Repair discipline (audit BLOCKER-7G-C-1): never touch the registration
# under a running job, and never attempt repairs more often than once per
# cooldown period, so a persistent failure cannot loop the timer.
if pgrep -u "${SERVICE_USER}" -f 'Runner\.Worker' >/dev/null; then
  log "job in flight (Runner.Worker alive); skipping repair — re-checked next tick"
  exit 0
fi

now="$(date +%s)"
COOLDOWN_FILE="${COOLDOWN_FILE:-/run/ensure-runner.last-repair}"
COOLDOWN_SECS="${COOLDOWN_SECS:-1800}"
if [ -r "${COOLDOWN_FILE}" ]; then
  _last="$(cat "${COOLDOWN_FILE}" 2>/dev/null || echo 0)"
  case "${_last}" in
    ''|*[!0-9]*) _last=0 ;;
  esac
  if [ "$(( now - _last ))" -lt "${COOLDOWN_SECS}" ]; then
    die "still offline, but a repair was attempted $(( now - _last ))s ago (cooldown ${COOLDOWN_SECS}s) — no new attempt"
  fi
fi
# The attempt is recorded before it runs, so a failed attempt is also
# rate-limited; the file lives on tmpfs and resets at boot.
{ printf '%s\n' "${now}" >"${COOLDOWN_FILE}"; } 2>/dev/null \
  || log "warning: could not write ${COOLDOWN_FILE} (cooldown not persisted)"

[ -r "${PAT_FILE}" ] || die "PAT file ${PAT_FILE} not readable (create it: Administration: write PAT of a repo admin, mode 0600, owner root)"
PAT_PERMS="$(stat -c '%a:%U' "${PAT_FILE}")"
[ "${PAT_PERMS}" = "600:${PAT_OWNER}" ] || die "PAT file ${PAT_FILE} must be 0600, owner ${PAT_OWNER} (is ${PAT_PERMS})"
PAT="$(cat "${PAT_FILE}")"
case "${PAT}" in
  github_pat_*|ghp_*) ;;
  "") die "PAT file ${PAT_FILE} is empty" ;;
  *) die "PAT file ${PAT_FILE} does not contain a GitHub PAT" ;;
esac

OWNER="$(sed -E 's#https://github\.com/([^/]+)/.*#\1#' <<<"${REPO_URL}")"
REPO="$(sed -E 's#https://github\.com/[^/]+/(.*)#\1#' <<<"${REPO_URL}")"

# A fresh registration token (one-time, short-lived). The PAT never enters
# argv (audit BLOCKER-7G-C-2): it is written to a root-owned, 0600 temp curl
# config file and handed to curl via -K/--config, so no header value can be
# read from /proc/<pid>/cmdline by any local user during the request. Both
# temp files are removed on exit (including the failure paths via die).
TOKEN_JSON="$(mktemp "${TMPDIR:-/tmp}/runner-regjson.XXXXXX")"
HDR_CFG="$(mktemp "${TMPDIR:-/tmp}/.runner-hdr.XXXXXX")"
chmod 600 "${TOKEN_JSON}" "${HDR_CFG}"
trap 'rm -f "${TOKEN_JSON}" "${HDR_CFG}"' EXIT
printf 'header = "Authorization: Bearer %s"\n' "${PAT}" >"${HDR_CFG}"
if ! timeout "${CURL_MAX_TIME_SECS}s" curl -fsS -X POST \
  --connect-timeout "${CURL_CONNECT_TIMEOUT_SECS}" \
  --max-time "${CURL_MAX_TIME_SECS}" \
  -K "${HDR_CFG}" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/${OWNER}/${REPO}/actions/runners/registration-token" \
  -o "${TOKEN_JSON}" 2>/dev/null; then
  die "registration-token API call failed (check the PAT scope: Administration: write)"
fi
unset PAT
TOKEN="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["token"])' "${TOKEN_JSON}")"
rm -f "${TOKEN_JSON}" "${HDR_CFG}"
[ -n "${TOKEN}" ] || die "could not parse a registration token from the API answer"
trap - EXIT

# Re-register (config.sh --replace). Run as the runner user so file ownership
# matches the existing service installation.
log "re-registering runner ${RUNNER_NAME} (labels: ${RUNNER_LABELS})"
if ! timeout "${CONFIG_TIMEOUT_SECS}s" \
  runuser -u "${SERVICE_USER}" -- "${RUNNER_DIR}/config.sh" \
  --url "${REPO_URL}" \
  --token "${TOKEN}" \
  --name "${RUNNER_NAME}" \
  --labels "${RUNNER_LABELS}" \
  --work "_work" \
  --replace --unattended >>"${LOG_FILE}" 2>&1; then
  die "config.sh --replace failed (see ${LOG_FILE})"
fi
unset TOKEN

log "re-registered; restarting ${SERVICE_UNIT}"
if ! timeout "${RESTART_TIMEOUT_SECS}s" \
  systemctl restart "${SERVICE_UNIT}"; then
  die "service restart failed or timed out"
fi

sleep 15
if runner_online; then
  log "runner ${RUNNER_NAME} repaired and online"
  exit 0
fi
die "repair ran but the runner is still not listening"
