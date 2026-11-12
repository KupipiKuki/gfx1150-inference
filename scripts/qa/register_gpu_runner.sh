#!/usr/bin/env bash
# 7F-1 self-hosted gfx1150 runner registration helper (Gate G6).
#
# Run ON the gfx1150 host as the runner user (default: kupipi), after:
#   1. making the repository private (or enabling fork-PR approval), and
#   2. obtaining the tarball URL + registration token from
#      GitHub -> Settings -> Actions -> Runners -> New self-hosted runner.
#
# The token is read silently, used once for config.sh, and never written by
# this script. The script does not touch the repository working tree.
#
# Usage:
#   RUNNER_URL="https://github.com/actions/runner/releases/download/.../actions-runner-linux-x64-....tar.gz" \
#     bash scripts/qa/register_gpu_runner.sh
#
# Optional:
#   RUNNER_SHA256=<sha256 from the GitHub page>   verify the download
#   RUNNER_DIR=$HOME/actions-runner              install directory
#   RUNNER_NAME=gfx1150-host                     runner name
#   RUNNER_LABELS=gfx1150,rocm                   labels (must match ci-gpu.yml)
#   SERVICE_USER=kupipi                          systemd service user
#   REPO_URL=https://github.com/KupipiKuki/gfx1150-inference
#
# Exit: 0 registered + service started; non-zero on any failed step.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REPO_URL="${REPO_URL:-https://github.com/KupipiKuki/gfx1150-inference}"
RUNNER_URL="${RUNNER_URL:-}"
RUNNER_SHA256="${RUNNER_SHA256:-}"
RUNNER_DIR="${RUNNER_DIR:-$HOME/actions-runner}"
RUNNER_NAME="${RUNNER_NAME:-gfx1150-host}"
RUNNER_LABELS="${RUNNER_LABELS:-gfx1150,rocm}"
SERVICE_USER="${SERVICE_USER:-$USER}"

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

[ -n "${RUNNER_URL}" ] || die "set RUNNER_URL to the actions-runner-linux-x64 tarball URL from the GitHub UI"
[ "$(id -un)" = "${SERVICE_USER}" ] || die "run this as ${SERVICE_USER} (current: $(id -un)); the service is installed for that user"

echo "== 7F-1 runner registration =="
echo "repo:        ${REPO_URL}"
echo "runner dir:  ${RUNNER_DIR}"
echo "runner name: ${RUNNER_NAME}"
echo "labels:      ${RUNNER_LABELS}"
echo "service user:${SERVICE_USER}"
echo

echo "-- preflight --"
bash "${REPO_ROOT}/scripts/qa/preflight_gpu_runner.sh"
echo

echo "-- security confirmation --"
echo "A self-hosted runner on a public repo can execute fork-PR code on this host."
read -r -p "Has the repo been made private OR fork-PR approval enabled for all outside collaborators? [y/N] " answer
[ "${answer}" = "y" ] || [ "${answer}" = "Y" ] || die "secure the repository first (see PHASE7_7F1_RUNNER_RUNBOOK.md §2)"
echo

if [ -e "${RUNNER_DIR}/config.sh" ]; then
  die "${RUNNER_DIR} already contains a configured runner; remove it first (runbook §10)"
fi

mkdir -p "${RUNNER_DIR}"
cd "${RUNNER_DIR}"

echo "-- download --"
curl -fL --retry 3 -o actions-runner.tar.gz "${RUNNER_URL}"
if [ -n "${RUNNER_SHA256}" ]; then
  printf '%s  %s\n' "${RUNNER_SHA256}" actions-runner.tar.gz | sha256sum -c -
else
  echo "WARN: RUNNER_SHA256 not set; compare the checksum shown by GitHub manually"
fi
tar xzf actions-runner.tar.gz
echo

echo "-- configure --"
read -r -s -p "Paste the GitHub registration token (not echoed): " RUNNER_TOKEN
echo
[ -n "${RUNNER_TOKEN}" ] || die "empty registration token"
./config.sh \
  --url "${REPO_URL}" \
  --token "${RUNNER_TOKEN}" \
  --name "${RUNNER_NAME}" \
  --labels "${RUNNER_LABELS}" \
  --work _work \
  --unattended
unset RUNNER_TOKEN
echo

echo "-- service environment --"
cat > .env <<EOF
PATH=${HOME}/.pyenv/shims:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ROCM_PATH=/opt/rocm
EOF
chmod 600 .env
echo "wrote ${RUNNER_DIR}/.env (pyenv Python + ROCm path)"
echo

echo "-- install + start the service (sudo will prompt) --"
sudo ./svc.sh install "${SERVICE_USER}"
sudo ./svc.sh start
sudo ./svc.sh status
echo

cat <<EOF
== registered ==
Runner: ${RUNNER_NAME}  labels: ${RUNNER_LABELS}  dir: ${RUNNER_DIR}
Service: actions.runner.*.service (user ${SERVICE_USER})

Next (PHASE7_7F1_RUNNER_RUNBOOK.md §6-§7):
  1. Open a PR from wp/7F-evidence-release to vibe/phase7-220201, or dispatch
     "Self-Hosted GPU CI" on wp/7F-evidence-release.
  2. Confirm the job log: "GPU lane: 45 passed, 0 skipped" and
     "PASS: the GPU lane ran, with no skips".
  3. Remove continue-on-error: true from .github/workflows/ci-gpu.yml, push,
     and confirm a green run without the bypass.
  4. Require "GPU correctness (self-hosted gfx1150)" in branch protection for
     main and vibe/phase7-220201.
  5. Red-team a deliberately failing GPU PR and confirm the merge is blocked.
  6. Send the run URLs/IDs to the auditor for G6 signoff.
EOF
