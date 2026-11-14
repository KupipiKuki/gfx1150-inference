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
#   1. Is the runner service active AND listening for jobs
#      (`systemctl is-active` + `Listening for Jobs` in the service log)?
#      -> healthy, exit 0 and do nothing.
#   2. Otherwise obtain a fresh registration token with the repo-admin PAT
#      (Administration: write), stored OUTSIDE the repository:
#        /etc/gfx1150-runner/runner.pat   (mode 0600, owner root)
#      via POST /repos/{owner}/{repo}/actions/runners/registration-token.
#   3. Re-run config.sh --replace --unattended with the existing name/labels.
#   4. Restart the service.
#
# The PAT and the registration token are NEVER written to a log, a file in
# the repository, a workflow, the service environment, or echoed. The token
# is passed to config.sh as a single argument of a root-owned process (a
# root-only /proc slot, alive for the seconds config.sh runs); the PAT is
# consumed by curl via a private fd redirection and never appears in argv.
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
LISTEN_MARKER="Listening for Jobs"
LOG_TAG="ensure-runner"

log() {
  local line
  line="$(printf '%s %s' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*")"
  printf '%s\n' "${line}" >&2
  # best-effort persistent log; never fatal (non-root --check runs)
  { printf '%s\n' "${line}" >>"/var/log/${LOG_TAG}.log" ; } 2>/dev/null || true
}

die() { log "RUNNER-REGISTRATION-OFFLINE: $*"; exit 1; }

CHECK_ONLY=0
[ "${1:-}" = "--check" ] && CHECK_ONLY=1

runner_online() {
  systemctl is-active --quiet "${SERVICE_UNIT}" || return 1
  # The service log ("_diag" output via journald) must show the runner
  # actually listening, not merely "active" in a crash-loop.
  journalctl -u "${SERVICE_UNIT}" --since "-10 min" --no-pager 2>/dev/null \
    | grep -q "${LISTEN_MARKER}"
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

[ -r "${PAT_FILE}" ] || die "PAT file ${PAT_FILE} not readable (create it: Administration: write PAT of a repo admin, mode 0600, owner root)"
PAT_PERMS="$(stat -c '%a:%U' "${PAT_FILE}")"
[ "${PAT_PERMS}" = "600:root" ] || die "PAT file ${PAT_FILE} must be 0600, owner root (is ${PAT_PERMS})"
PAT="$(cat "${PAT_FILE}")"
case "${PAT}" in
  github_pat_*|ghp_*) ;;
  "") die "PAT file ${PAT_FILE} is empty" ;;
  *) die "PAT file ${PAT_FILE} does not contain a GitHub PAT" ;;
esac

OWNER="$(sed -E 's#https://github\.com/([^/]+)/.*#\1#' <<<"${REPO_URL}")"
REPO="$(sed -E 's#https://github\.com/[^/]+/(.*)#\1#' <<<"${REPO_URL}")"

# A fresh registration token (one-time, short-lived). The PAT enters curl via
# a redirected fd so it is never in argv; the raw JSON answer is kept in a
# root-only temp file and deleted immediately.
TOKEN_JSON="$(mktemp /tmp/runner-regjson.XXXXXX)"
chmod 600 "${TOKEN_JSON}"
trap 'rm -f "${TOKEN_JSON}"' EXIT
if ! curl -fsS -X POST \
  -H "Authorization: Bearer ${PAT}" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/${OWNER}/${REPO}/actions/runners/registration-token" \
  -o "${TOKEN_JSON}" 2>/dev/null; then
  rm -f "${TOKEN_JSON}"
  die "registration-token API call failed (check the PAT scope: Administration: write)"
fi
TOKEN="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["token"])' "${TOKEN_JSON}")"
rm -f "${TOKEN_JSON}"
[ -n "${TOKEN}" ] || die "could not parse a registration token from the API answer"
trap - EXIT

# Re-register (config.sh --replace). Run as the runner user so file ownership
# matches the existing service installation.
log "re-registering runner ${RUNNER_NAME} (labels: ${RUNNER_LABELS})"
if ! runuser -u "${SERVICE_USER}" -- "${RUNNER_DIR}/config.sh" \
  --url "${REPO_URL}" \
  --token "${TOKEN}" \
  --name "${RUNNER_NAME}" \
  --labels "${RUNNER_LABELS}" \
  --work "_work" \
  --replace --unattended >>"/var/log/${LOG_TAG}.log" 2>&1; then
  die "config.sh --replace failed (see /var/log/${LOG_TAG}.log)"
fi
unset TOKEN

log "re-registered; restarting ${SERVICE_UNIT}"
systemctl restart "${SERVICE_UNIT}"

sleep 15
if runner_online; then
  log "runner ${RUNNER_NAME} repaired and online"
  exit 0
fi
die "repair ran but the runner is still not listening"
