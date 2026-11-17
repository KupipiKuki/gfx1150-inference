"""C2b — scripted checks for the runner watchdog orchestrator.

``scripts/ci/ensure_runner_registered.sh`` no longer decides health itself: it
runs the layered doctor and acts on the verdict (see
``PHASE7_7G_C2_RUNNER_REBUILD_PLAN.md`` §6–§7). These tests drive the real
orchestrator through a *fake doctor* (a script that emits a chosen JSON verdict
and exit code) plus PATH shims for ``systemctl``, ``pgrep``, ``curl``,
``runuser`` and ``sleep``.

What is asserted here is the decision logic the rebuild is about:

* a clock-skew verdict never repairs (exit 2);
* a healthy verdict never repairs or alerts;
* an offline verdict repairs once, verifies, and emits one alert + one
  recovery line;
* a labels/not-visible misconfiguration repairs, while any other
  misconfiguration is an owner action;
* the PAT never reaches argv or the log;
* a job in flight defers repair;
* the cooldown and the verify-only mode both suppress repair.

All checks are CPU-lane: pure bash subprocesses, no HIP extension, no GPU, no
network.
"""

from __future__ import annotations

import json
import os
import pathlib
import pwd
import subprocess
import time

import pytest

pytestmark = pytest.mark.cpu

CI_DIR = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "ci"
SCRIPT = CI_DIR / "ensure_runner_registered.sh"
SPEC = CI_DIR / "runner.env"

FAKE_PAT = "github_pat_11FAKE0000orchestratortokennotdeployed"
FAKE_TOKEN = "FAKE_REGISTRATION_TOKEN"


def _write(path: pathlib.Path, body: str, mode: int = 0o755) -> None:
    path.write_text(body)
    path.chmod(mode)


@pytest.fixture()
def host(tmp_path: pathlib.Path):
    """A fake host: fake doctor, PATH shims, PAT, runner dir, state files."""
    state = tmp_path / "state"
    state.mkdir()
    shims = tmp_path / "shims"
    shims.mkdir()

    # --- fake doctor: verdict/cause/code are files the test flips -------------
    _write(
        shims / "doctor",
        """#!/usr/bin/env bash
STATE="${SHIM_STATE:?}"
printf '%s\\n' "$*" >> "${STATE}/doctor-calls.log"
python3 - "$(cat "${STATE}/doctor-verdict")" "$(cat "${STATE}/doctor-cause")" \\
  "$(cat "${STATE}/doctor-code")" <<'PY'
import json
import sys

verdict, cause, code = sys.argv[1:4]
print(json.dumps({
    "verdict": verdict,
    "cause": cause,
    "exit_code": int(code),
    "warnings": 0,
    "generated_at": "2026-11-14T00:00:00Z",
    "checks": [],
}))
PY
exit "$(cat "${STATE}/doctor-code")"
""",
    )
    (state / "doctor-verdict").write_text("HEALTHY\n")
    (state / "doctor-cause").write_text("\n")
    (state / "doctor-code").write_text("0\n")
    (state / "doctor-calls.log").write_text("")

    # --- systemctl: restart increments a counter, start records the alert ----
    _write(
        shims / "systemctl",
        """#!/usr/bin/env bash
STATE="${SHIM_STATE:?}"
printf '%s\\n' "$*" >> "${STATE}/systemctl.log"
case "$1" in
  restart)
    n="$(cat "${STATE}/restarts")"; printf '%s\\n' "$((n + 1))" > "${STATE}/restarts" ;;
  start) : ;;
esac
exit 0
""",
    )
    (state / "restarts").write_text("0\n")
    (state / "systemctl.log").write_text("")

    # --- pgrep: only Runner.Worker is modelled here --------------------------
    _write(
        shims / "pgrep",
        """#!/usr/bin/env bash
STATE="${SHIM_STATE:?}"
if printf '%s\\n' "$*" | grep -q 'Worker'; then
  if [ "$(cat "${STATE}/worker-alive")" = 1 ]; then
    printf '9999\\n'; exit 0
  fi
fi
exit 1
""",
    )
    (state / "worker-alive").write_text("0\n")

    # --- curl: serves a registration token and records its argv --------------
    _write(
        shims / "curl",
        """#!/usr/bin/env bash
STATE="${SHIM_STATE:?}"
printf '%s\\n' "$*" >> "${STATE}/curl-args.log"
out=""; prev=""
for a in "$@"; do
  [ "$prev" = "-o" ] && out="$a"
  prev="$a"
done
if printf '%s\\n' "$*" | grep -qF 'registration-token'; then
  printf '{"token": "FAKE_REGISTRATION_TOKEN"}' > "$out"
  exit 0
fi
echo "curl shim: unhandled $*" >&2
exit 1
""",
    )
    (state / "curl-args.log").write_text("")

    # --- runuser: records argv, then runs config.sh as the same user ---------
    _write(
        shims / "runuser",
        """#!/usr/bin/env bash
STATE="${SHIM_STATE:?}"
printf '%s\\n' "$*" >> "${STATE}/runuser-args.log"
shift 3
exec "$@"
""",
    )
    (state / "runuser-args.log").write_text("")

    # --- sleep: the verify poll must not slow the suite ----------------------
    _write(shims / "sleep", "#!/usr/bin/env bash\nexit 0\n")

    # --- runner dir + a config.sh that heals the fake doctor -----------------
    runner_dir = tmp_path / "actions-runner"
    (runner_dir / "_diag").mkdir(parents=True)
    # A server-side deletion leaves the local config behind; the watchdog must
    # remove it before config.sh, which refuses an already-configured runner.
    (runner_dir / ".runner").write_text('{"agentId": 23}\n')
    (runner_dir / ".credentials").write_text("stale\n")
    (runner_dir / ".credentials_rsaparams").write_text("stale\n")
    # Migration markers: ConfigurationStore.IsConfigured() counts them, so the
    # real config.sh refuses to run while they exist (2026-11-16 outage).
    (runner_dir / ".runner_migrated").write_text('{"agentId": 23}\n')
    (runner_dir / ".credentials_migrated").write_text("stale\n")
    config = runner_dir / "config.sh"
    config.write_text(
        """#!/usr/bin/env bash
STATE="${SHIM_STATE:?}"
printf '%s\\n' "$*" >> "${STATE}/config-args.log"
here="$(cd -- "$(dirname -- "$0")" && pwd)"
if [ -e "${here}/.runner" ] || [ -e "${here}/.credentials" ] \
  || [ -e "${here}/.runner_migrated" ]; then
  echo "config.sh: stale local config still present" >&2
  exit 1
fi
printf 'HEALTHY\\n' > "${STATE}/doctor-verdict"
printf '\\n' > "${STATE}/doctor-cause"
printf '0\\n' > "${STATE}/doctor-code"
"""
    )
    config.chmod(0o755)
    (state / "config-args.log").write_text("")

    pat_file = tmp_path / "runner.pat"
    pat_file.write_text(FAKE_PAT + "\n")
    pat_file.chmod(0o600)

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{shims}:{env.get('PATH', '/usr/bin:/bin')}",
            "SHIM_STATE": str(state),
            "RUNNER_ENV": str(SPEC),
            "RUNNER_DOCTOR": str(shims / "doctor"),
            "RUNNER_DIR": str(runner_dir),
            "RUNNER_NAME": "fake-host",
            "RUNNER_USER": env.get("USER", "nobody"),
            "RUNNER_LABELS": "gfx1150,rocm",
            "RUNNER_WORK": "_work",
            "SERVICE_UNIT": "actions.runner.fake.fake.service",
            "REPO_SLUG": "owner/repo",
            "PAT_FILE": str(pat_file),
            "PAT_OWNER": pwd.getpwuid(os.getuid()).pw_name,
            "PAT_MODE": "600",
            "LOG_FILE": str(tmp_path / "ensure-runner.log"),
            "COOLDOWN_FILE": str(state / "last-repair"),
            "STATE_FILE": str(state / "runner.state"),
            "ALERT_UNIT": "fake-alert.service",
            "COOLDOWN_SECS": "1800",
            "DOCTOR_TIMEOUT_SECS": "10",
            "REPAIR_VERIFY_SECS": "0",
            "REPAIR_VERIFY_POLLS": "1",
            "CURL_MAX_TIME_SECS": "10",
            "CONFIG_TIMEOUT_SECS": "10",
            "RESTART_TIMEOUT_SECS": "10",
            "TMPDIR": str(tmp_path),
        }
    )
    return {
        "env": env,
        "state": state,
        "tmp": tmp_path,
        "runner_dir": runner_dir,
        "pat": pat_file,
        "log": tmp_path / "ensure-runner.log",
        "shims": shims,
    }


def _set_doctor(host, verdict: str, cause: str = "", code: int = 0) -> None:
    state = host["state"]
    (state / "doctor-verdict").write_text(verdict + "\n")
    (state / "doctor-cause").write_text(cause + "\n")
    (state / "doctor-code").write_text(f"{code}\n")


def _run(host, *args: str, env: dict[str, str] | None = None):
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        env=env or host["env"],
        capture_output=True,
        text=True,
        timeout=60,
    )


def _read(host, name: str) -> str:
    path = host["state"] / name
    return path.read_text() if path.exists() else ""


def _log(host) -> str:
    return host["log"].read_text() if host["log"].exists() else ""


# ------------------------------------------------------------------ healthy --


def test_healthy_verdict_does_nothing(host):
    result = _run(host)

    assert result.returncode == 0, result.stderr
    assert _read(host, "curl-args.log") == ""
    assert _read(host, "restarts").strip() == "0"
    assert _read(host, "runner.state").strip() == "HEALTHY"
    assert "ALERT:" not in _log(host)


def test_job_in_flight_is_a_deferral_not_an_alert(host):
    _set_doctor(host, "HEALTHY", "JOB_IN_FLIGHT", 0)

    result = _run(host)

    assert result.returncode == 0, result.stderr
    assert _read(host, "curl-args.log") == ""
    assert _read(host, "restarts").strip() == "0"
    assert "ALERT:" not in _log(host)
    assert "JOB_IN_FLIGHT" in _log(host)


# --------------------------------------------------------------- clock skew --


def test_clock_skew_never_repairs(host):
    _set_doctor(host, "CLOCK_SKEW", "CLOCK_SKEW: host is 3600s from GitHub", 2)

    result = _run(host)

    assert result.returncode == 2, result.stderr
    assert _read(host, "curl-args.log") == ""
    assert _read(host, "restarts").strip() == "0"
    assert "repair forbidden" in _log(host)
    assert "ALERT: runner CLOCK_SKEW" in _log(host)


# ------------------------------------------------------------------- repair --


def test_offline_repairs_once_then_recovers(host):
    _set_doctor(host, "OFFLINE", "REGISTRATION_DELETED: rejected after listening", 1)

    result = _run(host)

    assert result.returncode == 0, result.stdout + result.stderr
    assert len([x for x in _read(host, "curl-args.log").splitlines() if x]) == 1
    assert _read(host, "restarts").strip() == "1"
    assert "ALERT: runner OFFLINE" in _log(host)
    assert "RECOVERED:" in _log(host)
    assert "repaired and healthy" in _log(host)


def test_repair_removes_the_stale_local_config(host):
    """config.sh refuses an already-configured runner; --replace only replaces
    the server-side record. The repair must remove .runner/.credentials first,
    including the .runner_migrated/.credentials_migrated migration markers that
    IsConfigured() also counts (the 2026-11-16 outage)."""
    _set_doctor(host, "OFFLINE", "REGISTRATION_DELETED: rejected after listening", 1)

    result = _run(host)

    assert result.returncode == 0, result.stdout + result.stderr
    assert not (host["runner_dir"] / ".runner").exists()
    assert not (host["runner_dir"] / ".credentials").exists()
    assert not (host["runner_dir"] / ".credentials_rsaparams").exists()
    assert not (host["runner_dir"] / ".runner_migrated").exists()
    assert not (host["runner_dir"] / ".credentials_migrated").exists()


def test_missing_pat_is_a_clear_failure_without_a_token_call(host):
    host["pat"].unlink()
    _set_doctor(host, "OFFLINE", "REGISTRATION_DELETED: rejected after listening", 1)

    result = _run(host)

    assert result.returncode == 1
    assert _read(host, "curl-args.log") == ""
    assert "PAT file" in result.stderr
    # one alert for the outage, no recovery
    assert _log(host).count("ALERT: runner OFFLINE") == 1
    assert "RECOVERED:" not in _log(host)


def test_pat_never_appears_in_argv_or_the_log(host):
    _set_doctor(host, "OFFLINE", "REGISTRATION_DELETED: rejected after listening", 1)

    result = _run(host)

    assert result.returncode == 0, result.stderr
    assert FAKE_PAT not in _read(host, "curl-args.log")
    assert "Bearer" not in _read(host, "curl-args.log")
    assert FAKE_PAT not in _log(host)
    # The one-time registration token does reach config.sh argv (documented).
    assert FAKE_TOKEN in _read(host, "runuser-args.log")
    assert FAKE_TOKEN in _read(host, "config-args.log")


def test_repair_uses_the_spec_labels(host):
    _set_doctor(host, "OFFLINE", "REGISTRATION_DELETED: rejected after listening", 1)

    result = _run(host)

    assert result.returncode == 0, result.stderr
    config_args = _read(host, "config-args.log")
    assert "--labels gfx1150,rocm" in config_args
    assert "--name fake-host" in config_args
    assert "--work _work" in config_args


def test_job_in_flight_blocks_repair_even_if_the_doctor_says_offline(host):
    (host["state"] / "worker-alive").write_text("1\n")
    _set_doctor(host, "OFFLINE", "REGISTRATION_DELETED: rejected after listening", 1)

    result = _run(host)

    assert result.returncode == 0, result.stderr
    assert _read(host, "curl-args.log") == ""
    assert _read(host, "restarts").strip() == "0"
    assert "job in flight" in _log(host)


def test_cooldown_suppresses_a_second_attempt(host):
    _set_doctor(host, "OFFLINE", "REGISTRATION_DELETED: rejected after listening", 1)
    (host["state"] / "last-repair").write_text(f"{int(time.time())}\n")

    result = _run(host)

    assert result.returncode == 1
    assert _read(host, "curl-args.log") == ""
    assert _read(host, "restarts").strip() == "0"
    assert "cooldown" in _log(host)
    assert "ALERT: runner OFFLINE" in _log(host)


# ---------------------------------------------------------- misconfiguration --


def test_labels_mismatch_repairs_with_the_spec_labels(host):
    _set_doctor(
        host,
        "MISCONFIGURED",
        "LABELS_MISMATCH: missing ['rocm']; labels=['gfx1150']",
        3,
    )

    result = _run(host)

    assert result.returncode == 0, result.stderr
    assert len([x for x in _read(host, "curl-args.log").splitlines() if x]) == 1
    assert "--labels gfx1150,rocm" in _read(host, "config-args.log")
    assert "ALERT: runner MISCONFIGURED" in _log(host)
    assert "RECOVERED:" in _log(host)


def test_registration_not_visible_repairs(host):
    _set_doctor(
        host,
        "MISCONFIGURED",
        "REGISTRATION_NOT_VISIBLE: fake-host is not available to this repo",
        3,
    )

    result = _run(host)

    assert result.returncode == 0, result.stderr
    assert len([x for x in _read(host, "curl-args.log").splitlines() if x]) == 1


def test_other_misconfiguration_is_an_owner_action(host):
    _set_doctor(host, "MISCONFIGURED", "job name 'wrong' != required check", 3)

    result = _run(host)

    assert result.returncode == 3
    assert _read(host, "curl-args.log") == ""
    assert _read(host, "restarts").strip() == "0"
    assert "owner action" in _log(host)
    assert "ALERT: runner MISCONFIGURED" in _log(host)


# -------------------------------------------------------------- verify-only --


def test_check_mode_reports_without_repairing_or_writing_state(host):
    _set_doctor(host, "OFFLINE", "REGISTRATION_DELETED: rejected after listening", 1)

    result = _run(host, "--check")

    assert result.returncode == 1
    assert _read(host, "curl-args.log") == ""
    assert _read(host, "restarts").strip() == "0"
    assert not (host["state"] / "runner.state").exists()
    assert not (host["state"] / "last-repair").exists()
    assert "verify-only" in _log(host)


def test_check_mode_preserves_the_misconfigured_exit_code(host):
    _set_doctor(host, "MISCONFIGURED", "LABELS_MISMATCH: missing ['rocm']", 3)

    result = _run(host, "--check")

    assert result.returncode == 3
    assert _read(host, "curl-args.log") == ""


# ------------------------------------------------------------ alert dedup ----


def test_alert_dedup_one_alert_and_one_recovery(host):
    # healthy -> broken -> broken (cooldown) -> healthy
    assert _run(host).returncode == 0

    _set_doctor(host, "OFFLINE", "REGISTRATION_DELETED: rejected after listening", 1)
    host["pat"].unlink()  # force the repair to fail fast
    assert _run(host).returncode == 1
    assert _run(host).returncode == 1  # inside cooldown

    _set_doctor(host, "HEALTHY")
    assert _run(host).returncode == 0

    log = _log(host)
    assert log.count("ALERT: runner OFFLINE") == 1, log
    assert log.count("RECOVERED:") == 1, log


# ------------------------------------------------------------------ bounded --


def test_hung_doctor_is_bounded_and_refuses_to_repair(host):
    _write(host["shims"] / "doctor", "#!/usr/bin/env bash\nexec /bin/sleep 5\n")
    env = host["env"] | {"DOCTOR_TIMEOUT_SECS": "1"}

    started = time.monotonic()
    result = _run(host, "--check", env=env)
    elapsed = time.monotonic() - started

    assert result.returncode == 3
    assert elapsed < 4
    assert _read(host, "curl-args.log") == ""


def test_registration_request_timeout_is_bounded(host):
    _set_doctor(host, "OFFLINE", "REGISTRATION_DELETED: rejected after listening", 1)
    _write(host["shims"] / "curl", "#!/usr/bin/env bash\nexec /bin/sleep 5\n")
    env = host["env"] | {"CURL_MAX_TIME_SECS": "1"}

    started = time.monotonic()
    result = _run(host, env=env)
    elapsed = time.monotonic() - started

    assert result.returncode == 1
    assert "registration-token API call failed" in result.stderr
    assert elapsed < 4


# ---------------------------------------------------------- static guards ----


def test_script_never_passes_the_pat_in_a_header_argument():
    body = SCRIPT.read_text(encoding="utf-8")
    assert 'header = "Authorization: Bearer %s"' in body
    assert '-K "${hdr_cfg}"' in body
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("-H"):
            assert "${pat}" not in stripped
            assert "Bearer" not in stripped


def test_script_does_not_reimplement_health():
    """The watchdog must consume the doctor, not grep the diag log itself."""
    body = SCRIPT.read_text(encoding="utf-8")
    assert "Listening for Jobs" not in body
    assert "registration has been deleted" not in body
    assert "journalctl" not in body
    assert "ls -t" not in body
    assert "runner_doctor.sh" in body
