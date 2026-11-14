"""C2a — scripted checks for ``scripts/ci/runner_doctor.sh``.

The doctor is the single layered diagnosis that replaces ad-hoc journal
grepping (see ``PHASE7_7G_C2_RUNNER_REBUILD_PLAN.md`` §5). These tests drive
the *real* script through PATH shims for ``systemctl``, ``pgrep`` and
``timedatectl``, against a fake runner directory, so the decision logic is
exercised without root, without a real runner and without the network.

The decisive regressions are the two failure modes the audit proved:

* a healthy runner whose ``_diag`` mtime order was corrupted by a clock jump
  must still be HEALTHY (BLOCKER-7G-C-3);
* a *skew* rejection (``not valid until``) must be reported as CLOCK_SKEW
  (exit 2, repair forbidden), not as a deleted registration (BLOCKER-7G-C-2's
  root cause in ``audit/AUDIT_7G_C_2026-11-14.md`` §3b).

All checks are CPU-lane: pure bash subprocesses, no HIP extension, no GPU.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import time

import pytest

pytestmark = pytest.mark.cpu

CI_DIR = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "ci"
DOCTOR = CI_DIR / "runner_doctor.sh"
SPEC = CI_DIR / "runner.env"

LISTEN = "Listening for Jobs"
DELETED = "registration has been deleted from the server"
SKEW = "The token is not valid until 11/11/2026 03:40:47. Current server time is 11/10/2026 22:40:22."


def _write(path: pathlib.Path, body: str, mode: int = 0o755) -> None:
    path.write_text(body)
    path.chmod(mode)


@pytest.fixture()
def host(tmp_path: pathlib.Path):
    """A fake host: shims, service state, and a current-session diag log."""
    state = tmp_path / "state"
    state.mkdir()
    shims = tmp_path / "shims"
    shims.mkdir()

    # 1 hour ago, in the clock the service and the diag filename share.
    start_epoch = int(time.time()) - 3600
    start_str = subprocess.check_output(
        ["date", "-d", f"@{start_epoch}", "+%Y-%m-%d %H:%M:%S"], text=True
    ).strip()
    utc_stamp = subprocess.check_output(
        ["date", "-u", "-d", f"@{start_epoch}", "+%Y%m%d-%H%M%S"], text=True
    ).strip()

    (state / "active-state").write_text("active\n")
    (state / "sub-state").write_text("running\n")
    (state / "start-ts").write_text(start_str + "\n")
    (state / "nrestarts").write_text("0\n")
    (state / "listener-alive").write_text("1\n")
    (state / "local-rtc").write_text("no\n")
    (state / "ntp-synced").write_text("yes\n")
    (state / "timer-enabled").write_text("disabled\n")
    (state / "timer-active").write_text("inactive\n")

    _write(
        shims / "systemctl",
        """#!/usr/bin/env bash
STATE="${SHIM_STATE:?}"
case "$1" in
  show)
    shift
    key=""
    while [ "$#" -gt 0 ]; do
      case "$1" in
        -p) key="$2"; shift 2; break ;;
        *) shift ;;
      esac
    done
    case "${key}" in
      ActiveState) cat "${STATE}/active-state" ;;
      SubState) cat "${STATE}/sub-state" ;;
      ExecMainStartTimestamp) cat "${STATE}/start-ts" ;;
      NRestarts) cat "${STATE}/nrestarts" ;;
      *) printf '\\n' ;;
    esac
    ;;
  is-enabled) cat "${STATE}/timer-enabled" ;;
  is-active) cat "${STATE}/timer-active" ;;
  *) exit 0 ;;
esac
""",
    )
    _write(
        shims / "pgrep",
        """#!/usr/bin/env bash
STATE="${SHIM_STATE:?}"
if printf '%s\\n' "$*" | grep -q 'Listener'; then
  if [ "$(cat "${STATE}/listener-alive")" = 1 ]; then
    printf '4242\\n'
    exit 0
  fi
fi
exit 1
""",
    )
    _write(
        shims / "timedatectl",
        """#!/usr/bin/env bash
STATE="${SHIM_STATE:?}"
if [ "${1:-}" = show ]; then
  case "${3:-}" in
    LocalRTC) cat "${STATE}/local-rtc" ;;
    NTPSynchronized) cat "${STATE}/ntp-synced" ;;
    *) printf '\\n' ;;
  esac
  exit 0
fi
exit 0
""",
    )

    _write(
        shims / "curl",
        """#!/usr/bin/env bash
STATE="${SHIM_STATE:?}"
cat "${STATE}/runners.json"
""",
    )

    # A readable, well-formed PAT so L4 can be exercised without the network.
    pat_file = tmp_path / "runner.pat"
    pat_file.write_text("github_pat_fake0000000000000000000000000000000000000000000000000000\n")
    pat_file.chmod(0o600)
    (state / "runners.json").write_text(
        json.dumps({
            "runners": [{
                "id": 1,
                "name": "fake-host",
                "status": "online",
                "labels": [{"name": n} for n in ("self-hosted", "Linux", "X64", "gfx1150", "rocm")],
            }]
        })
    )

    runner_dir = tmp_path / "actions-runner"
    diag_dir = runner_dir / "_diag"
    diag_dir.mkdir(parents=True)
    current = diag_dir / f"Runner_{utc_stamp}-utc.log"
    current.write_text(f"{LISTEN}\n")

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{shims}:{env.get('PATH', '/usr/bin:/bin')}",
            "SHIM_STATE": str(state),
            "SERVICE_UNIT": "actions.runner.fake.fake.service",
            "RUNNER_DIR": str(runner_dir),
            "RUNNER_USER": env.get("USER", "nobody"),
            "RUNNER_NAME": "fake-host",
            "RUNNER_LABELS": "gfx1150,rocm",
            "PAT_FILE": str(pat_file),
            "WATCHDOG_TIMER": "fake-watchdog.timer",
            "WATCHDOG_INSTALLED": str(tmp_path / "no-such-watchdog"),
            "WATCHDOG_LEGACY_INSTALLED": str(tmp_path / "no-such-legacy"),
            "WATCHDOG_LOG": str(tmp_path / "ensure-runner.log"),
            "COOLDOWN_FILE": str(tmp_path / "last-repair"),
            "RUNNER_DOCTOR_FAKE_SKEW": "0",
        }
    )
    return {
        "env": env,
        "state": state,
        "diag": diag_dir,
        "current": current,
        "runner_dir": runner_dir,
        "tmp": tmp_path,
    }


def _run(host, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(DOCTOR), "--check", "--no-network", *args],
        env=host["env"],
        capture_output=True,
        text=True,
        timeout=60,
    )


def _mark_current(host, body: str) -> None:
    host["current"].write_text(body)


def _set_state(host, name: str, value: str) -> None:
    (host["state"] / name).write_text(value + "\n")


# ---------------------------------------------------------------- healthy --


def test_healthy_runner_exits_zero(host):
    result = _run(host)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "VERDICT: HEALTHY" in result.stdout
    assert "L3  PASS" in result.stdout


def test_mtime_poison_does_not_make_a_healthy_runner_offline(host):
    """BLOCKER-7G-C-3: a stale session log from the previous boot carries a
    FUTURE mtime (the clock jumped). The doctor must select by filename, so
    the healthy current session still wins."""
    stale = host["diag"] / "Runner_20261114-000000-utc.log"
    stale.write_text(f"{LISTEN}\n{DELETED}\n")
    future = time.time() + 86400
    os.utime(stale, (future, future))

    result = _run(host)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "VERDICT: HEALTHY" in result.stdout
    assert "REGISTRATION_DELETED" not in result.stdout


def test_starting_grace_exits_zero(host):
    """A service younger than the grace period without a session log is
    STARTING, not offline: the watchdog must not repair during startup."""
    host["current"].unlink()
    _set_state(host, "start-ts", subprocess.check_output(
        ["date", "-d", "@%d" % (int(time.time()) - 30), "+%Y-%m-%d %H:%M:%S"],
        text=True,
    ).strip())

    result = _run(host)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "STARTING" in result.stdout


# ---------------------------------------------------------------- offline --


def test_deletion_after_listen_is_offline(host):
    _mark_current(host, f"{LISTEN}\n{DELETED}\n")

    result = _run(host)

    assert result.returncode == 1
    assert "REGISTRATION_DELETED" in result.stdout


def test_deletion_before_listen_is_healthy(host):
    """A deletion from an earlier failed start inside the same log must not
    poison a later successful listen (line order, not mere presence)."""
    _mark_current(host, f"{DELETED}\n{LISTEN}\n")

    result = _run(host)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "VERDICT: HEALTHY" in result.stdout


def test_listener_dead_is_offline(host):
    _set_state(host, "listener-alive", "0")

    result = _run(host)

    assert result.returncode == 1
    assert "LISTENER_DEAD" in result.stdout


def test_service_down_is_offline(host):
    _set_state(host, "active-state", "failed")
    _set_state(host, "sub-state", "failed")

    result = _run(host)

    assert result.returncode == 1
    assert "SERVICE_DOWN" in result.stdout


def test_not_listening_after_grace_is_offline(host):
    _mark_current(host, "no marker here\n")

    result = _run(host)

    assert result.returncode == 1
    assert "never listened" in result.stdout


# -------------------------------------------------------------- clock skew --


def test_skew_rejection_is_exit_two_not_deleted(host):
    """The runner reports a clock-skew rejection as 'registration deleted'.
    The doctor must disambiguate and forbid repair."""
    _mark_current(host, f"{LISTEN}\n{SKEW}\n")

    result = _run(host)

    assert result.returncode == 2
    assert "SESSION_SKEW" in result.stdout
    assert "REGISTRATION_DELETED" not in result.stdout


def test_fake_skew_guard_exits_two(host):
    host["env"]["RUNNER_DOCTOR_FAKE_SKEW"] = "3600"

    result = _run(host)

    assert result.returncode == 2
    assert "CLOCK_SKEW" in result.stdout


# --------------------------------------------------------------- interface --


def test_json_output_is_parseable(host):
    result = _run(host, "--json")

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["verdict"] == "HEALTHY"
    assert payload["exit_code"] == 0
    assert payload["checks"]
    assert {row["layer"] for row in payload["checks"]} >= {"L0", "L1", "L2", "L3"}


def test_quiet_prints_only_the_verdict(host):
    result = _run(host, "--quiet")

    assert result.returncode == 0
    assert result.stdout.strip() == "VERDICT: HEALTHY"


# ---------------------------------------------------------------- L4 --------


def _run_network(host) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(DOCTOR), "--check"],
        env=host["env"],
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_labels_mismatch_is_exit_three(host):
    (host["state"] / "runners.json").write_text(json.dumps({
        "runners": [{
            "id": 1,
            "name": "fake-host",
            "status": "online",
            "labels": [{"name": "self-hosted"}, {"name": "gfx1150"}],
        }]
    }))

    result = _run_network(host)

    assert result.returncode == 3
    assert "LABELS_MISMATCH" in result.stdout
    assert "rocm" in result.stdout


def test_agent_absent_is_exit_three(host):
    (host["state"] / "runners.json").write_text(json.dumps({"runners": []}))

    result = _run_network(host)

    assert result.returncode == 3
    assert "REGISTRATION_NOT_VISIBLE" in result.stdout


def test_matching_labels_pass(host):
    result = _run_network(host)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "L4  PASS" in result.stdout
    assert "rocm" in result.stdout


# ---------------------------------------------------------------- static ---


def test_doctor_never_uses_mtime_or_a_moving_journal_window():
    body = DOCTOR.read_text(encoding="utf-8")
    assert "ls -t" not in body
    assert "--since" not in body


def test_doctor_keeps_the_pat_out_of_argv():
    body = DOCTOR.read_text(encoding="utf-8")
    assert '-K "${HDR_FILE}"' in body
    assert 'header = "Authorization: Bearer %s"' in body
    for line in body.splitlines():
        if line.strip().startswith("-H"):
            assert "${pat_value}" not in line
            assert "Bearer" not in line


def test_doctor_takes_runner_configuration_from_the_spec():
    body = DOCTOR.read_text(encoding="utf-8")
    assert '. "${SCRIPT_DIR}/runner.env"' in body
    assert "actions.runner." not in body


def test_spec_is_shell_sourceable():
    result = subprocess.run(
        ["bash", "-c", f'. "{SPEC}"; printf "%s|%s\\n" "$RUNNER_LABELS" "$SERVICE_UNIT"'],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    labels, unit = result.stdout.strip().split("|")
    assert labels == "gfx1150,rocm"
    assert unit.startswith("actions.runner.")
