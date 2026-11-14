"""Scripted check for the runner-registration watchdog (7G-C, C2 remediation).

Audit trace: AUDIT_7G_C_2026-11-14.md, BLOCKER-7G-C-1 and BLOCKER-7G-C-2.

The auditor's net requirement for the in-repo fix is a scripted check that
``ensure_runner_registered.sh --check`` returns 0 on a healthy runner that
has been up for more than ten minutes, plus the repair discipline (no repair
under a running job, cooldown between attempts) and a PAT that never appears
in a process argument vector. The live simulated-deletion transcript against
a REAL runner (real systemctl, real PAT) stays owner-pending and is recorded
separately in audit/evidence/G7/7G-C/c2-runner/; what is checked here is the
decision logic of the script itself, driven through PATH-shimmed
systemctl/pgrep/journalctl/curl/runuser around a fake runner directory.

The decisive regression is the exact scenario the auditor proved broken: the
runner is online and working but the "Listening for Jobs" startup marker is
30 minutes old, so the old 10-minute journal window saw 0 hits and every
tick would have flagged the healthy runner offline. The journalctl shim
below reproduces that journal (empty inside the moving window) and the test
still requires --check to exit 0.

Repair paths never need the network here: the fake curl only serves a fake
registration-token JSON and records its argv, which is what the
PAT-not-in-argv assertion inspects.
"""

from __future__ import annotations

import os
import pathlib
import textwrap
import time
import subprocess

import pytest

pytestmark = pytest.mark.cpu

SCRIPT = pathlib.Path(__file__).resolve().parent.parent / (
    "scripts/ci/ensure_runner_registered.sh"
)

LISTEN_MARKER = "Listening for Jobs"
DELETED_MARKER = "the runner registration has been deleted from the server"
FAKE_PAT = "github_pat_11FAKE0000remediationtokennotdeployed"

DIAG_NAME = "Runner_20261114-223000.log"


def _install(path: pathlib.Path, body: str, mode: int = 0o755) -> None:
    path.write_text(body)
    path.chmod(mode)


@pytest.fixture()
def env(tmp_path: pathlib.Path) -> dict[str, str]:
    """Build a fake host: shim PATH, runner dir, PAT file, state files."""
    state = tmp_path / "state"
    state.mkdir()
    shim_dir = tmp_path / "shims"
    shim_dir.mkdir()

    # systemctl reads its desired state from files in SHIM_STATE so tests can
    # flip the service between healthy and broken without restarting anything.
    state.joinpath("is-active").write_text("active\n")
    state.joinpath("active-state").write_text("active")
    state.joinpath("sub-state").write_text("running")
    state.joinpath("restarts").write_text("0\n")
    state.joinpath("listener-alive").write_text("1\n")
    state.joinpath("worker-alive").write_text("0\n")
    state.joinpath("curl-args.log").write_text("")
    state.joinpath("runuser-args.log").write_text("")

    shim_dir.joinpath("systemctl").write_text(textwrap.dedent("""\
        #!/usr/bin/env bash
        STATE_DIR="${SHIM_STATE:?}"
        case "$1" in
          is-active)
            if [ "$2" = "--quiet" ]; then
              grep -q '^active$' "${STATE_DIR}/is-active"; exit $?
            fi
            cat "${STATE_DIR}/is-active"; exit 0 ;;
          show)
            echo "$(cat "${STATE_DIR}/active-state")"
            echo "$(cat "${STATE_DIR}/sub-state")"
            exit 0 ;;
          start|restart|stop)
            n=$(cat "${STATE_DIR}/restarts"); echo $((n + 1)) > "${STATE_DIR}/restarts"
            printf 'active\\n' > "${STATE_DIR}/is-active"
            printf 'active'  > "${STATE_DIR}/active-state"
            printf 'running' > "${STATE_DIR}/sub-state"
            exit 0 ;;
          *) echo "systemctl shim: unhandled $*" >&2; exit 1 ;;
        esac
        """))
    shim_dir.joinpath("pgrep").write_text(textwrap.dedent("""\
        #!/usr/bin/env bash
        STATE_DIR="${SHIM_STATE:?}"
        case "$*" in
          *Listener*) [ "$(cat "${STATE_DIR}/listener-alive")" = 1 ]; exit $? ;;
          *Worker*)   [ "$(cat "${STATE_DIR}/worker-alive")" = 1 ]; exit $? ;;
          *) echo "pgrep shim: unhandled $*" >&2; exit 1 ;;
        esac
        """))
    # The old bug: a moving journal window that contains no startup marker
    # (exactly the host journal the auditor quoted: marker 30 min old).
    shim_dir.joinpath("journalctl").write_text(
        "#!/usr/bin/env bash\n# no marker inside the moving window; the fixed\n"
        "# script must never gate health on this output\nexit 0\n"
    )
    shim_dir.joinpath("sleep").write_text("#!/usr/bin/env bash\nexit 0\n")
    # curl serves a fake registration-token answer and records its argv:
    # the PAT-not-in-argv assertion inspects this record.
    shim_dir.joinpath("curl").write_text(textwrap.dedent("""\
        #!/usr/bin/env bash
        STATE_DIR="${SHIM_STATE:?}"
        printf '%s\\n' "$*" >> "${SHIM_CURL_ARGS:?}"
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
        """))
    shim_dir.joinpath("runuser").write_text(textwrap.dedent("""\
        #!/usr/bin/env bash
        STATE_DIR="${SHIM_STATE:?}"
        printf '%s\\n' "$*" >> "${SHIM_RUNUSER_ARGS:?}"
        # runuser -u USER -- cmd args...
        shift 3
        exec "$@"
        """))
    for shim in shim_dir.iterdir():
        shim.chmod(0o755)

    runner_dir = tmp_path / "actions-runner"
    diag_dir = runner_dir / "_diag"
    diag_dir.mkdir(parents=True)
    diag = diag_dir / DIAG_NAME
    diag.write_text(f"{LISTEN_MARKER}\n")
    # Make the listen marker over 30 minutes old, matching the host journal
    # the auditor quoted; the fixed script must not judge health by marker age.
    old = time.time() - 1800
    os.utime(diag, (old, old))

    # Fake config.sh: on re-registration the diag log is refreshed without the
    # deleted-registration line, and its argv is recorded (the registration
    # token DOES appear there by design — documented, accepted, low severity).
    config = runner_dir / "config.sh"
    config.write_text(textwrap.dedent(f"""\
        #!/usr/bin/env bash
        STATE_DIR="${{SHIM_STATE:?}}"
        printf '%s\\n' "$*" >> "${{SHIM_RUNUSER_ARGS:?}}"
        diag="$(cat "${{STATE_DIR}}/diag-path")"
        printf '%s\\n' "{LISTEN_MARKER}" > "$diag"
        """))
    config.chmod(0o755)
    state.joinpath("diag-path").write_text(str(diag))

    pat_file = tmp_path / "runner.pat"
    pat_file.write_text(f"{FAKE_PAT}\n")
    pat_file.chmod(0o600)

    return {
        "PATH": f"{shim_dir}:{os.environ.get('PATH', '/usr/bin:/bin')}",
        "SHIM_STATE": str(state),
        "SHIM_CURL_ARGS": str(state / "curl-args.log"),
        "SHIM_RUNUSER_ARGS": str(state / "runuser-args.log"),
        "RUNNER_DIR": str(runner_dir),
        "SERVICE_UNIT": "actions.runner.fake.fake.service",
        "SERVICE_USER": "kupipi",
        "PAT_FILE": str(pat_file),
        "PAT_OWNER": "kupipi",  # no root in the sandbox; production default is root
        "LOG_FILE": str(tmp_path / "ensure-runner.log"),  # sandbox: not /var/log
        "COOLDOWN_FILE": str(state / "last-repair"),
        "COOLDOWN_SECS": "1800",
        "TMPDIR": str(tmp_path),
    }


def _mark_deleted(env: dict[str, str]) -> None:
    diag = pathlib.Path(
        pathlib.Path(env["SHIM_STATE"]).joinpath("diag-path").read_text()
    )
    diag.write_text(f"{LISTEN_MARKER}\n{DELETED_MARKER}\n")


def _run(env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


# ---------------------------------------------------------------- healthy --


def test_check_is_zero_on_healthy_runner_up_over_ten_minutes(env):
    """Auditor acceptance: healthy runner, up > 10 min -> --check exits 0,
    performs no repair (no curl call), and does NOT gate on the moving
    journal window that reports nothing (the exact BLOCKER-7G-C-1 failure)."""
    result = _run(env, "--check")
    assert result.returncode == 0, result.stderr
    assert pathlib.Path(env["SHIM_CURL_ARGS"]).read_text() == ""


# ------------------------------------------------------- deleted registration


def test_deleted_registration_performs_exactly_one_repair_then_healthy(env):
    """Auditor acceptance: with the registration deleted, the script performs
    exactly one repair (one registration-token request) and then reports
    healthy."""
    _mark_deleted(env)

    result = _run(env)

    assert result.returncode == 0, result.stderr
    curl_calls = [
        line
        for line in pathlib.Path(env["SHIM_CURL_ARGS"]).read_text().splitlines()
        if line.strip()
    ]
    assert len(curl_calls) == 1, curl_calls
    assert "registration-token" in curl_calls[0]


def test_pat_never_appears_in_any_process_argument_vector(env):
    """BLOCKER-7G-C-2 acceptance: during the repair the PAT must not appear in
    curl's argv (it may only travel through the curl config file), while the
    short-lived registration token is expected IN argv of runuser/config.sh —
    the documented, accepted low-severity window."""
    _mark_deleted(env)

    result = _run(env)
    assert result.returncode == 0, result.stderr

    curl_args = pathlib.Path(env["SHIM_CURL_ARGS"]).read_text()
    runuser_args = pathlib.Path(env["SHIM_RUNUSER_ARGS"]).read_text()
    assert FAKE_PAT not in curl_args
    assert "Bearer" not in curl_args
    # the registration token did reach argv of config.sh, exactly as the
    # audit says it must be documented
    assert "FAKE_REGISTRATION_TOKEN" in runuser_args
    # the header temp file was removed on exit
    for cfg in pathlib.Path(env["TMPDIR"]).glob(".runner-hdr.*"):
        assert FAKE_PAT not in cfg.read_text()


def test_repair_skipped_while_worker_process_is_alive(env):
    """A Runner.Worker process means a job is in flight: no repair, exit 0,
    next tick re-checks."""
    state = pathlib.Path(env["SHIM_STATE"])
    state.joinpath("worker-alive").write_text("1\n")
    _mark_deleted(env)

    result = _run(env)

    assert result.returncode == 0, result.stderr
    assert state.joinpath("restarts").read_text().strip() == "0"
    assert state.joinpath("curl-args.log").read_text() == ""


def test_second_offline_tick_inside_cooldown_makes_no_new_attempt(env):
    """No more than one repair attempt per cooldown period, also for failed
    attempts."""
    _mark_deleted(env)

    first = _run(env)
    assert first.returncode == 0, first.stderr

    # force the runner offline again immediately: inside the cooldown
    state = pathlib.Path(env["SHIM_STATE"])
    state.joinpath("active-state").write_text("failed")
    state.joinpath("sub-state").write_text("failed")
    _mark_deleted(env)

    second = _run(env)
    assert second.returncode != 0
    assert "cooldown" in second.stderr
    curl_calls = [
        line
        for line in state.joinpath("curl-args.log").read_text().splitlines()
        if line.strip()
    ]
    assert len(curl_calls) == 1


def test_check_is_nonzero_on_deleted_registration(env):
    _mark_deleted(env)

    result = _run(env, "--check")

    assert result.returncode == 1
    assert "verify-only" in result.stderr


def test_health_check_requires_a_live_listener_process(env):
    """Active service but no Runner.Listener process (crash loop) is offline,
    even though every other signal looks fine."""
    state = pathlib.Path(env["SHIM_STATE"])
    state.joinpath("listener-alive").write_text("0\n")

    result = _run(env, "--check")

    assert result.returncode == 1


# ---------------------------------------------------------- static guarantees


def test_script_never_passes_the_pat_in_a_header_argument():
    """Static guard: the PAT may only reach curl through --config; a literal
    Authorization header interpolation would regress BLOCKER-7G-C-2."""
    body = SCRIPT.read_text()
    assert 'header = "Authorization: Bearer %s"' in body
    assert '-K "${HDR_CFG}"' in body
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("-H"):
            assert "${PAT}" not in stripped


def test_health_check_does_not_use_a_moving_journal_window():
    """Static guard for BLOCKER-7G-C-1: no journalctl/moving-window gating of
    the startup-only marker."""
    body = SCRIPT.read_text()
    assert "journalctl" not in body
    assert "--since" not in body
