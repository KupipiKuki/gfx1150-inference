#!/usr/bin/env bash
# 7G-C (C2b) — gfx1150 runner watchdog: doctor -> decision -> repair -> verify.
#
# The watchdog no longer decides health itself. It runs the single layered
# doctor (scripts/ci/runner_doctor.sh) and acts on its verdict:
#
#   HEALTHY / JOB_IN_FLIGHT / STARTING  -> exit 0, no repair, no alert
#   CLOCK_SKEW                          -> exit 2, alert once, repair FORBIDDEN
#   OFFLINE                             -> repair once (subject to cooldown)
#   MISCONFIGURED (labels/not-visible)  -> repair once (re-register with labels)
#   MISCONFIGURED (anything else)       -> exit 3, alert once, owner action
#
# This split is the point of the rebuild: the two failure modes that produced
# four false "registration deleted" episodes on this host (a moving journal
# window, and a clock-skew rejection misread as a deletion) are decided in the
# doctor, where they are unit-tested, and the watchdog can no longer repair a
# clock problem.
#
# Repair discipline (unchanged, still normative):
#   * never under a live Runner.Worker (a job is in flight);
#   * at most one attempt per COOLDOWN_SECS, recorded before the attempt so a
#     failure is rate-limited too;
#   * the PAT is read from PAT_FILE (0600, owner root) and handed to curl via
#     -K (a 0600 temp config file), never argv (BLOCKER-7G-C-2);
#   * the one-time registration token appears transiently in config.sh argv,
#     run as the runner user — documented, accepted, low severity.
#
# Alerts are transition-based (state file on tmpfs): one line when the runner
# becomes broken, one recovery line when it is healthy again, never one per
# tick.
#
# Usage: sudo scripts/ci/ensure_runner_registered.sh [--check]
#   --check  verify-only: run the doctor, report, never repair or write state.
#
# Exit: 0 healthy/deferred/repaired, 1 still offline, 2 clock skew,
#       3 misconfigured (owner action).

set -uo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

# Same spec search as the doctor: explicit override, next to the script in the
# repository, then the installed location.
RUNNER_ENV_FILE=""
for candidate in "${RUNNER_ENV:-}" "${SCRIPT_DIR}/runner.env" "/etc/gfx1150-runner/runner.env"; do
  if [ -n "${candidate}" ] && [ -r "${candidate}" ]; then
    RUNNER_ENV_FILE="${candidate}"
    break
  fi
done
if [ -z "${RUNNER_ENV_FILE}" ]; then
  printf 'ensure_runner_registered: runner.env not found (set RUNNER_ENV)\n' >&2
  exit 3
fi
# shellcheck source=runner.env
. "${RUNNER_ENV_FILE}"

# The doctor is next to the script in the repository and installed under
# /usr/local/sbin by C2d.
if [ -z "${RUNNER_DOCTOR:-}" ]; then
  for candidate in "${SCRIPT_DIR}/runner_doctor.sh" "${DOCTOR_INSTALLED}"; do
    if [ -x "${candidate}" ]; then
      RUNNER_DOCTOR="${candidate}"
      break
    fi
  done
fi
if [ -z "${RUNNER_DOCTOR:-}" ] || [ ! -r "${RUNNER_DOCTOR}" ]; then
  printf 'ensure_runner_registered: doctor not found (set RUNNER_DOCTOR)\n' >&2
  exit 3
fi

LOG_FILE="${LOG_FILE:-${WATCHDOG_LOG}}"
COOLDOWN_FILE="${COOLDOWN_FILE:-/run/ensure-runner.last-repair}"

CHECK_ONLY=0
case "${1:-}" in
  "") ;;
  --check) CHECK_ONLY=1 ;;
  -h|--help)
    printf 'Usage: ensure_runner_registered.sh [--check]\n'
    exit 0
    ;;
  *)
    printf 'ensure_runner_registered: unknown option: %s\n' "$1" >&2
    exit 3
    ;;
esac

log() {
  local line
  line="$(printf '%s %s' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*")"
  printf '%s\n' "${line}" >&2
  # Best effort: a non-root --check run may not be able to write /var/log.
  { printf '%s\n' "${line}" >>"${LOG_FILE}" ; } 2>/dev/null || true
}

die() { log "RUNNER-REGISTRATION-OFFLINE: $*"; exit 1; }

# ------------------------------------------------------------------ doctor --

DOCTOR_JSON=""
DOCTOR_RC=0
DOCTOR_VERDICT=""
DOCTOR_CAUSE=""
DOCTOR_CODE=""

run_doctor() {
  local err="${LOG_FILE}"
  { : >>"${err}" ; } 2>/dev/null || err=/dev/null
  DOCTOR_JSON="$(timeout "${DOCTOR_TIMEOUT_SECS}s" \
    bash "${RUNNER_DOCTOR}" --check --json 2>>"${err}")"
  DOCTOR_RC=$?
}

parse_doctor() {
  local parsed rest
  parsed="$(python3 - "${DOCTOR_JSON}" <<'PY' 2>/dev/null || true
import json
import sys

try:
    data = json.loads(sys.argv[1])
except Exception:
    print("||")
    raise SystemExit(0)
print(f"{data.get('verdict', '')}|{data.get('cause', '')}|{data.get('exit_code', '')}")
PY
)"
  DOCTOR_VERDICT="${parsed%%|*}"
  rest="${parsed#*|}"
  DOCTOR_CAUSE="${rest%%|*}"
  DOCTOR_CODE="${rest##*|}"
}

# ------------------------------------------------------------------- alert --

notify() {  # $1 = verdict/state, $2 = cause
  local state="$1" cause="$2" last=""
  [ "${CHECK_ONLY}" = 1 ] && return 0
  [ -r "${STATE_FILE}" ] && last="$(cat "${STATE_FILE}" 2>/dev/null || true)"
  { printf '%s\n' "${state}" >"${STATE_FILE}" ; } 2>/dev/null || true
  [ "${state}" = "${last}" ] && return 0
  if [ "${state}" = "HEALTHY" ]; then
    # The first observation of a healthy runner is not a recovery.
    if [ -n "${last}" ]; then
      log "RECOVERED: runner is healthy again (was ${last})"
    fi
  else
    log "ALERT: runner ${state} - ${cause}"
    systemctl start --no-block "${ALERT_UNIT}" >/dev/null 2>&1 || true
  fi
}

# ------------------------------------------------------------------ repair --

repair() {
  local cause="$1"
  local pat perms token_json hdr_cfg token

  [ -r "${PAT_FILE}" ] || die "PAT file ${PAT_FILE} not readable (Administration: write PAT of a repo admin, mode ${PAT_MODE}, owner ${PAT_OWNER})"
  perms="$(stat -c '%a:%U' "${PAT_FILE}" 2>/dev/null || true)"
  [ "${perms}" = "${PAT_MODE}:${PAT_OWNER}" ] || die "PAT file ${PAT_FILE} must be ${PAT_MODE}, owner ${PAT_OWNER} (is ${perms:-unknown})"
  pat="$(tr -d '\r\n' <"${PAT_FILE}")"
  case "${pat}" in
    github_pat_*|ghp_*) ;;
    "") die "PAT file ${PAT_FILE} is empty" ;;
    *) die "PAT file ${PAT_FILE} does not contain a GitHub PAT" ;;
  esac

  token_json="$(mktemp "${TMPDIR:-/tmp}/runner-regjson.XXXXXX")"
  hdr_cfg="$(mktemp "${TMPDIR:-/tmp}/.runner-hdr.XXXXXX")"
  chmod 600 "${token_json}" "${hdr_cfg}"
  # shellcheck disable=SC2064
  trap "rm -f '${token_json}' '${hdr_cfg}'" EXIT
  printf 'header = "Authorization: Bearer %s"\n' "${pat}" >"${hdr_cfg}"
  unset pat

  if ! timeout "${CURL_MAX_TIME_SECS:-60}s" curl -fsS -X POST \
    --connect-timeout "${CURL_CONNECT_TIMEOUT_SECS:-10}" \
    --max-time "${CURL_MAX_TIME_SECS:-60}" \
    -K "${hdr_cfg}" \
    -H "Accept: application/vnd.github+json" \
    "https://api.github.com/repos/${REPO_SLUG}/actions/runners/registration-token" \
    -o "${token_json}" 2>/dev/null; then
    die "registration-token API call failed (check the PAT scope: Administration: write)"
  fi

  token="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["token"])' "${token_json}" 2>/dev/null || true)"
  rm -f "${token_json}" "${hdr_cfg}"
  trap - EXIT
  [ -n "${token}" ] || die "could not parse a registration token from the API answer"

  # A server-side deletion leaves .runner/.credentials in place, and config.sh
  # refuses to configure an already-configured runner ("Cannot configure the
  # runner because it is already configured"). --replace only replaces the
  # server-side runner; it does not clear the local config. Stop the service,
  # remove the stale local config (the same files `config.sh remove --local`
  # deletes), then configure with --replace so a still-existing server runner
  # with the same name is replaced too.
  log "stopping ${SERVICE_UNIT} and removing the stale local runner config"
  systemctl stop "${SERVICE_UNIT}" >/dev/null 2>&1 || true
  if ! rm -f "${RUNNER_DIR}/.runner" "${RUNNER_DIR}/.credentials" \
    "${RUNNER_DIR}/.credentials_rsaparams"; then
    die "could not remove the stale local runner config in ${RUNNER_DIR}"
  fi

  log "re-registering runner ${RUNNER_NAME} (labels: ${RUNNER_LABELS}); cause: ${cause}"
  if ! timeout "${CONFIG_TIMEOUT_SECS:-120}s" \
    runuser -u "${RUNNER_USER}" -- "${RUNNER_DIR}/config.sh" \
    --url "${REPO_URL}" \
    --token "${token}" \
    --name "${RUNNER_NAME}" \
    --labels "${RUNNER_LABELS}" \
    --work "${RUNNER_WORK}" \
    --replace --unattended >>"${LOG_FILE}" 2>&1; then
    die "config.sh --replace failed (see ${LOG_FILE})"
  fi
  unset token

  log "re-registered; restarting ${SERVICE_UNIT}"
  if ! timeout "${RESTART_TIMEOUT_SECS:-30}s" systemctl restart "${SERVICE_UNIT}"; then
    die "service restart failed or timed out"
  fi
}

verify_repair() {
  local i
  for i in $(seq 1 "${REPAIR_VERIFY_POLLS}"); do
    sleep "${REPAIR_VERIFY_SECS}"
    run_doctor
    parse_doctor
    if [ "${DOCTOR_RC}" -eq 0 ] && [ "${DOCTOR_VERDICT}" = "HEALTHY" ]; then
      notify HEALTHY ""
      log "runner ${RUNNER_NAME} repaired and healthy"
      exit 0
    fi
  done
  log "repair ran but the runner is still ${DOCTOR_VERDICT:-unknown}: ${DOCTOR_CAUSE}"
  exit 1
}

handle_broken() {  # $1 = state, $2 = cause, $3 = verify-only exit code
  local state="$1" cause="$2" check_code="$3" now last

  notify "${state}" "${cause}"

  if [ "${CHECK_ONLY}" = 1 ]; then
    log "verify-only: ${state} - ${cause}"
    exit "${check_code}"
  fi

  # The doctor already treats a live worker as JOB_IN_FLIGHT/exit 0. This is a
  # belt-and-braces guard against a race between the doctor's pgrep and ours.
  if pgrep -u "${RUNNER_USER}" -f 'Runner\.Worker' >/dev/null 2>&1; then
    log "job in flight (Runner.Worker alive); deferring repair to the next tick"
    exit 0
  fi

  now="$(date +%s)"
  if [ -r "${COOLDOWN_FILE}" ]; then
    last="$(cat "${COOLDOWN_FILE}" 2>/dev/null || echo 0)"
    case "${last}" in
      ''|*[!0-9]*) last=0 ;;
    esac
    if [ "$(( now - last ))" -lt "${COOLDOWN_SECS}" ]; then
      log "still ${state}; a repair was attempted $(( now - last ))s ago (cooldown ${COOLDOWN_SECS}s) — no new attempt"
      exit 1
    fi
  fi

  # Record the attempt before it runs, so a failed attempt is rate-limited too.
  { printf '%s\n' "${now}" >"${COOLDOWN_FILE}" ; } 2>/dev/null \
    || log "warning: could not write ${COOLDOWN_FILE} (cooldown not persisted)"

  repair "${cause}"
  verify_repair
}

# -------------------------------------------------------------------- main --

run_doctor
parse_doctor

if [ -z "${DOCTOR_VERDICT}" ]; then
  log "doctor produced no verdict (exit ${DOCTOR_RC}); refusing to repair"
  notify MISCONFIGURED "doctor failed (exit ${DOCTOR_RC})"
  exit 3
fi

case "${DOCTOR_VERDICT}" in
  HEALTHY)
    notify HEALTHY ""
    log "runner ${RUNNER_NAME} healthy${DOCTOR_CAUSE:+ (${DOCTOR_CAUSE})}"
    exit 0
    ;;
  CLOCK_SKEW)
    notify CLOCK_SKEW "${DOCTOR_CAUSE}"
    log "CLOCK_SKEW: ${DOCTOR_CAUSE}; repair forbidden (fix timekeeping first)"
    exit 2
    ;;
  OFFLINE)
    handle_broken OFFLINE "${DOCTOR_CAUSE}" 1
    ;;
  MISCONFIGURED)
    case "${DOCTOR_CAUSE}" in
      *LABELS_MISMATCH*|*REGISTRATION_NOT_VISIBLE*)
        handle_broken MISCONFIGURED "${DOCTOR_CAUSE}" 3
        ;;
      *)
        notify MISCONFIGURED "${DOCTOR_CAUSE}"
        log "MISCONFIGURED: ${DOCTOR_CAUSE}; owner action required"
        exit 3
        ;;
    esac
    ;;
  *)
    notify OFFLINE "${DOCTOR_CAUSE}"
    log "unexpected verdict '${DOCTOR_VERDICT}': ${DOCTOR_CAUSE}"
    exit 1
    ;;
esac
