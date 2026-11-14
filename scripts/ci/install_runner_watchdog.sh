#!/usr/bin/env bash
# 7G-C (C2d) — install, verify and remove the gfx1150 runner watchdog.
#
# The watchdog is only useful if what runs on the host is exactly what the
# repository says. The audit found the installed script drifted from the
# repository (and the timer was disabled), so installation is now explicit and
# drift is detectable:
#
#   --apply      install script + doctor + spec + units + logrotate, reload
#                systemd, enable and start the timer
#   --check      compare every installed file with the repository by sha256 and
#                report unit/timer state; exit 1 on drift or a missing file
#   --uninstall  disable the timer, remove units/scripts/logrotate; keep the
#                PAT and the log (they are evidence, not installation)
#
# The installer never reads or prints the PAT. --apply refuses to run without
# it unless --allow-no-pat is given (a dry run / staging install).
#
# Destination directories are overridable so the script can be exercised in a
# sandbox (SYSTEMD_DIR, LOGROTATE_DIR, CONFIG_DIR, WATCHDOG_INSTALLED,
# DOCTOR_INSTALLED).

set -uo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

RUNNER_ENV_FILE=""
for candidate in "${RUNNER_ENV:-}" "${SCRIPT_DIR}/runner.env" "/etc/gfx1150-runner/runner.env"; do
  if [ -n "${candidate}" ] && [ -r "${candidate}" ]; then
    RUNNER_ENV_FILE="${candidate}"
    break
  fi
done
if [ -z "${RUNNER_ENV_FILE}" ]; then
  printf 'install_runner_watchdog: runner.env not found (set RUNNER_ENV)\n' >&2
  exit 3
fi
# shellcheck source=runner.env
. "${RUNNER_ENV_FILE}"

SYSTEMD_DIR="${SYSTEMD_DIR:-/etc/systemd/system}"
LOGROTATE_DIR="${LOGROTATE_DIR:-/etc/logrotate.d}"
CONFIG_DIR="${CONFIG_DIR:-/etc/gfx1150-runner}"

SRC_WATCHDOG="${SCRIPT_DIR}/ensure_runner_registered.sh"
SRC_DOCTOR="${SCRIPT_DIR}/runner_doctor.sh"
SRC_SPEC="${SCRIPT_DIR}/runner.env"
SRC_SERVICE="${SCRIPT_DIR}/gfx1150-runner-watchdog.service"
SRC_TIMER="${SCRIPT_DIR}/gfx1150-runner-watchdog.timer"
SRC_ALERT="${SCRIPT_DIR}/gfx1150-runner-watchdog-alert.service"
SRC_LOGROTATE="${SCRIPT_DIR}/gfx1150-runner-watchdog.logrotate"

DEST_WATCHDOG="${WATCHDOG_INSTALLED}"
DEST_DOCTOR="${DOCTOR_INSTALLED}"
DEST_SPEC="${CONFIG_DIR}/runner.env"
DEST_SERVICE="${SYSTEMD_DIR}/gfx1150-runner-watchdog.service"
DEST_TIMER="${SYSTEMD_DIR}/gfx1150-runner-watchdog.timer"
DEST_ALERT="${SYSTEMD_DIR}/gfx1150-runner-watchdog-alert.service"
DEST_LOGROTATE="${LOGROTATE_DIR}/gfx1150-runner-watchdog"
DEST_MANIFEST="${CONFIG_DIR}/watchdog.sha256"

MODE=""
ALLOW_NO_PAT=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --apply) MODE=apply ;;
    --check) MODE=check ;;
    --uninstall) MODE=uninstall ;;
    --allow-no-pat) ALLOW_NO_PAT=1 ;;
    -h|--help)
      cat <<'EOF'
Usage: install_runner_watchdog.sh --apply|--check|--uninstall [--allow-no-pat]

  --apply      install the watchdog, doctor, spec, units and logrotate
  --check      verify installed files against the repository (sha256)
  --uninstall  remove the watchdog, keep the PAT and the log
EOF
      exit 0
      ;;
    *)
      printf 'install_runner_watchdog: unknown option: %s\n' "$1" >&2
      exit 3
      ;;
  esac
  shift
done

if [ -z "${MODE}" ]; then
  printf 'install_runner_watchdog: choose --apply, --check or --uninstall\n' >&2
  exit 3
fi

FAILED=0

sha_of() { sha256sum "$1" 2>/dev/null | cut -d' ' -f1; }

check_file() {
  local label="$1" src="$2" dest="$3"
  local src_sha dest_sha
  if [ ! -e "${dest}" ]; then
    printf '%-10s %-52s MISSING\n' "${label}" "${dest}"
    FAILED=1
    return 0
  fi
  src_sha="$(sha_of "${src}")"
  dest_sha="$(sha_of "${dest}")"
  if [ -n "${src_sha}" ] && [ "${src_sha}" = "${dest_sha}" ]; then
    printf '%-10s %-52s OK (sha256 match)\n' "${label}" "${dest}"
  else
    printf '%-10s %-52s DRIFT\n' "${label}" "${dest}"
    FAILED=1
  fi
}

check_manifest() {
  local expected got
  if [ ! -e "${DEST_MANIFEST}" ]; then
    printf '%-10s %-52s MISSING\n' "manifest" "${DEST_MANIFEST}"
    FAILED=1
    return 0
  fi
  expected="$(sha_of "${SRC_WATCHDOG}")"
  got="$(cut -d' ' -f1 <"${DEST_MANIFEST}" 2>/dev/null || true)"
  if [ -n "${expected}" ] && [ "${expected}" = "${got}" ]; then
    printf '%-10s %-52s OK\n' "manifest" "${DEST_MANIFEST}"
  else
    printf '%-10s %-52s DRIFT\n' "manifest" "${DEST_MANIFEST}"
    FAILED=1
  fi
}

check_pat() {
  local perms
  if [ ! -e "${PAT_FILE}" ]; then
    printf '%-10s %-52s MISSING (owner action)\n' "PAT" "${PAT_FILE}"
    return 0
  fi
  perms="$(stat -c '%a:%U' "${PAT_FILE}" 2>/dev/null || true)"
  if [ "${perms}" = "${PAT_MODE}:${PAT_OWNER}" ]; then
    printf '%-10s %-52s OK (%s)\n' "PAT" "${PAT_FILE}" "${perms}"
  else
    printf '%-10s %-52s BAD PERMS (%s, want %s:%s)\n' \
      "PAT" "${PAT_FILE}" "${perms:-unknown}" "${PAT_MODE}" "${PAT_OWNER}"
    FAILED=1
  fi
}

check_units() {
  local enabled active
  enabled="$(systemctl is-enabled "${WATCHDOG_TIMER}" 2>/dev/null || true)"
  active="$(systemctl is-active "${WATCHDOG_TIMER}" 2>/dev/null || true)"
  if [ "${enabled}" = "enabled" ]; then
    printf '%-10s %-52s OK (enabled)\n' "unit" "${WATCHDOG_TIMER}"
  else
    printf '%-10s %-52s NOT ENABLED (%s)\n' "unit" "${WATCHDOG_TIMER}" "${enabled:-absent}"
    FAILED=1
  fi
  if [ "${active}" = "active" ]; then
    printf '%-10s %-52s OK (active)\n' "unit" "${WATCHDOG_TIMER}"
  else
    printf '%-10s %-52s NOT ACTIVE (%s)\n' "unit" "${WATCHDOG_TIMER}" "${active:-absent}"
    FAILED=1
  fi
}

install_one() {
  local src="$1" dest="$2" mode="$3"
  install -D -m "${mode}" "${src}" "${dest}"
}

apply() {
  if [ ! -e "${PAT_FILE}" ] && [ "${ALLOW_NO_PAT}" != 1 ]; then
    printf 'install_runner_watchdog: PAT %s is missing; refusing --apply\n' "${PAT_FILE}" >&2
    printf '  deploy it first (Administration: write, mode %s, owner %s) or use --allow-no-pat\n' \
      "${PAT_MODE}" "${PAT_OWNER}" >&2
    exit 3
  fi

  install_one "${SRC_WATCHDOG}" "${DEST_WATCHDOG}" 0755 || exit 1
  install_one "${SRC_DOCTOR}" "${DEST_DOCTOR}" 0755 || exit 1
  install_one "${SRC_SPEC}" "${DEST_SPEC}" 0644 || exit 1
  install_one "${SRC_SERVICE}" "${DEST_SERVICE}" 0644 || exit 1
  install_one "${SRC_TIMER}" "${DEST_TIMER}" 0644 || exit 1
  install_one "${SRC_ALERT}" "${DEST_ALERT}" 0644 || exit 1
  install_one "${SRC_LOGROTATE}" "${DEST_LOGROTATE}" 0644 || exit 1

  # The installed doctor cannot see the repository, so record the expected
  # watchdog hash for its L6 drift check.
  manifest="$(sha_of "${SRC_WATCHDOG}")"
  if [ -z "${manifest}" ]; then
    printf 'install_runner_watchdog: cannot hash %s\n' "${SRC_WATCHDOG}" >&2
    exit 1
  fi
  printf '%s\n' "${manifest}" >"${DEST_MANIFEST}" || exit 1
  chmod 0644 "${DEST_MANIFEST}" 2>/dev/null || true

  # The pre-C2d deployment used a different script name; remove it so only one
  # watchdog can ever run.
  if [ "${WATCHDOG_LEGACY_INSTALLED}" != "${DEST_WATCHDOG}" ] \
    && [ -e "${WATCHDOG_LEGACY_INSTALLED}" ]; then
    rm -f "${WATCHDOG_LEGACY_INSTALLED}" || exit 1
  fi

  systemctl daemon-reload || exit 1
  systemctl enable --now "${WATCHDOG_TIMER}" || exit 1
  printf 'installed: %s, %s, %s, %s\n' \
    "${DEST_WATCHDOG}" "${DEST_DOCTOR}" "${DEST_SPEC}" "${DEST_TIMER}"
}

uninstall() {
  systemctl disable --now "${WATCHDOG_TIMER}" 2>/dev/null || true
  systemctl stop "${SERVICE_UNIT}" 2>/dev/null || true
  rm -f "${DEST_SERVICE}" "${DEST_TIMER}" "${DEST_ALERT}" "${DEST_LOGROTATE}"
  rm -f "${DEST_WATCHDOG}" "${DEST_DOCTOR}" "${DEST_SPEC}" "${DEST_MANIFEST}"
  if [ "${WATCHDOG_LEGACY_INSTALLED}" != "${DEST_WATCHDOG}" ]; then
    rm -f "${WATCHDOG_LEGACY_INSTALLED}" 2>/dev/null || true
  fi
  systemctl daemon-reload 2>/dev/null || true
  printf 'uninstalled; kept %s and %s\n' "${PAT_FILE}" "${WATCHDOG_LOG}"
}

case "${MODE}" in
  check)
    check_file script "${SRC_WATCHDOG}" "${DEST_WATCHDOG}"
    check_file script "${SRC_DOCTOR}" "${DEST_DOCTOR}"
    check_file spec "${SRC_SPEC}" "${DEST_SPEC}"
    check_file unit "${SRC_SERVICE}" "${DEST_SERVICE}"
    check_file unit "${SRC_TIMER}" "${DEST_TIMER}"
    check_file unit "${SRC_ALERT}" "${DEST_ALERT}"
    check_file logrotate "${SRC_LOGROTATE}" "${DEST_LOGROTATE}"
    check_manifest
    check_units
    check_pat
    if [ "${FAILED}" = 0 ]; then
      printf 'RESULT: OK\n'
      exit 0
    fi
    printf 'RESULT: DRIFT\n'
    exit 1
    ;;
  apply)
    apply
    ;;
  uninstall)
    uninstall
    ;;
esac
