#!/usr/bin/env bash
# Read-only preflight for the 7F-1 self-hosted gfx1150 runner (Gate G6).
#
# Does NOT register anything and does NOT need sudo. Run it on the gfx1150
# host before creating a runner:
#
#   bash scripts/qa/preflight_gpu_runner.sh
#
# For a dedicated runner user, set the interpreter path it will use:
#
#   RUNNER_PATH=/home/gh-runner/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
#     bash scripts/qa/preflight_gpu_runner.sh
#
# Exit: 0 = no FAIL (warnings are allowed), 1 = at least one FAIL.

set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RUNNER_PATH="${RUNNER_PATH:-/home/kupipi/.pyenv/shims:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin}"

fails=0
warns=0
pass() { printf 'PASS  %s\n' "$*"; }
warn() { printf 'WARN  %s\n' "$*"; warns=$((warns + 1)); }
fail() { printf 'FAIL  %s\n' "$*"; fails=$((fails + 1)); }

echo "== 7F-1 self-hosted gfx1150 runner preflight =="
echo "repo:        ${REPO_ROOT}"
echo "runner PATH: ${RUNNER_PATH}"
echo

echo "-- host --"
arch="$(uname -m)"
if [ "${arch}" = "x86_64" ]; then pass "architecture ${arch}"; else fail "architecture ${arch} (the GitHub runner tarball is x86_64)"; fi
if [ -r /etc/os-release ]; then
  # shellcheck disable=SC1091
  . /etc/os-release
  pass "OS ${PRETTY_NAME:-unknown}"
else
  warn "/etc/os-release is missing"
fi
if command -v systemctl >/dev/null 2>&1; then pass "systemd available"; else fail "systemd is required for the runner service"; fi
avail_kb="$(df -Pk / | awk 'NR==2 {print $4}')"
if [ -n "${avail_kb}" ] && [ "${avail_kb}" -ge 20971520 ]; then
  pass "free disk $(awk -v k="${avail_kb}" 'BEGIN{printf "%.1f", k/1048576}') GiB on / (>= 20 GiB)"
else
  fail "free disk is below 20 GiB on / (runner _work + build need room)"
fi
echo

echo "-- GPU / ROCm --"
if command -v rocminfo >/dev/null 2>&1 && rocminfo 2>/dev/null | grep -q "gfx1150"; then
  pass "rocminfo reports gfx1150"
else
  fail "rocminfo does not report gfx1150 (is ROCm installed and the GPU visible?)"
fi
if [ -e /dev/kfd ]; then pass "/dev/kfd present"; else fail "/dev/kfd missing (GPU compute access)"; fi
if compgen -G "/dev/dri/renderD*" >/dev/null; then pass "/dev/dri/renderD* present"; else fail "/dev/dri/renderD* missing (GPU render access)"; fi
if id -nG | tr ' ' '\n' | grep -qx render && id -nG | tr ' ' '\n' | grep -qx video; then
  pass "current user is in render + video groups"
else
  warn "current user is not in BOTH render and video; the runner user must be (usermod -aG render,video <user>)"
fi
if command -v hipcc >/dev/null 2>&1; then pass "hipcc: $(command -v hipcc)"; else fail "hipcc not found (install ROCm or add /opt/rocm/bin to PATH)"; fi
if command -v cmake >/dev/null 2>&1; then pass "cmake: $(command -v cmake)"; else fail "cmake not found"; fi
if command -v make >/dev/null 2>&1; then pass "make: $(command -v make)"; else fail "make not found"; fi
if command -v git >/dev/null 2>&1; then pass "git: $(command -v git)"; else fail "git not found (actions/checkout needs it)"; fi
echo

echo "-- runner user interpreter (the service PATH, not your interactive shell) --"
py_out="$(env -i HOME="${HOME}" PATH="${RUNNER_PATH}" bash -c '
  command -v python3 || exit 1
  python3 --version 2>&1
  python3 -m pip --version 2>&1 | head -1
  python3 - <<"PY"
import sys
try:
    import numpy, pytest, pybind11
    print("packages", numpy.__version__, pytest.__version__, pybind11.__version__)
except Exception as exc:
    print("packages MISSING:", exc)
    sys.exit(1)
PY
' 2>&1)"
py_rc=$?
printf '%s\n' "${py_out}" | sed 's/^/      /'
if [ "${py_rc}" -eq 0 ]; then
  pass "python3 + pip + numpy/pytest/pybind11 work under the runner PATH"
else
  fail "python3/pip/packages are not usable under the runner PATH; set the runner .env PATH or provision a venv (see PHASE7_7F1_RUNNER_RUNBOOK.md)"
fi
echo

echo "-- GitHub / repository --"
origin="$(git -C "${REPO_ROOT}" remote get-url origin 2>/dev/null || true)"
slug=""
case "${origin}" in
  git@github.com:*) slug="${origin#git@github.com:}"; slug="${slug%.git}" ;;
  https://github.com/*) slug="${origin#https://github.com/}"; slug="${slug%.git}" ;;
esac
if [ -n "${slug}" ]; then
  private="$(curl -fsS "https://api.github.com/repos/${slug}" 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin).get("private"))' 2>/dev/null || true)"
  if [ "${private}" = "True" ]; then
    pass "${slug} is private"
  elif [ "${private}" = "False" ]; then
    warn "${slug} is PUBLIC: a self-hosted runner can execute fork-PR code on this host; make it private or require approval for all outside collaborators before registering"
  else
    warn "could not determine ${slug} visibility (offline or API rate limit)"
  fi
else
  warn "could not derive the GitHub slug from origin ${origin:-<none>}"
fi
if [ -d "${HOME}/actions-runner" ]; then
  warn "${HOME}/actions-runner already exists; reconfiguring? use a new directory or remove the old runner first"
else
  pass "no existing ${HOME}/actions-runner"
fi
if systemctl list-units 'actions.runner.*' --no-legend 2>/dev/null | grep -q .; then
  warn "an actions.runner service already exists; check its labels/online state before reconfiguring"
else
  pass "no existing actions.runner service"
fi
if grep -q 'continue-on-error: true' "${REPO_ROOT}/.github/workflows/ci-gpu.yml" 2>/dev/null; then
  warn "ci-gpu.yml still has continue-on-error: true (expected before the first green run; remove it before G6 signoff)"
else
  pass "ci-gpu.yml does not bypass the GPU job"
fi
echo

echo "-- summary --"
echo "FAIL: ${fails}  WARN: ${warns}"
if [ "${fails}" -gt 0 ]; then
  echo "PREFLIGHT: FAIL - fix the FAIL lines before registering the runner."
  exit 1
fi
echo "PREFLIGHT: PASS (warnings are owner decisions, not blockers)."
