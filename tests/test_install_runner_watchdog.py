"""C2d — scripted checks for ``scripts/ci/install_runner_watchdog.sh``.

The installer is what closes the audit finding that the installed watchdog
drifted from the repository and the timer was disabled. These tests run the
real script into a sandbox (SYSTEMD_DIR, LOGROTATE_DIR, CONFIG_DIR and the two
installed script paths are overridable) with a ``systemctl`` shim.

The decisive check is the drift drill (D7): ``--check`` is OK after
``--apply``, DRIFT after a manual edit, and OK again after another
``--apply``.
"""

from __future__ import annotations

import os
import pathlib
import subprocess

import pytest

pytestmark = pytest.mark.cpu

CI_DIR = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "ci"
INSTALLER = CI_DIR / "install_runner_watchdog.sh"
SPEC = CI_DIR / "runner.env"


def _write(path: pathlib.Path, body: str, mode: int = 0o755) -> None:
    path.write_text(body)
    path.chmod(mode)


@pytest.fixture()
def sandbox(tmp_path: pathlib.Path):
    state = tmp_path / "state"
    state.mkdir()
    shims = tmp_path / "shims"
    shims.mkdir()
    _write(
        shims / "systemctl",
        """#!/usr/bin/env bash
STATE="${SHIM_STATE:?}"
printf '%s\\n' "$*" >> "${STATE}/systemctl.log"
case "$1" in
  is-enabled) printf 'enabled\\n' ;;
  is-active) printf 'active\\n' ;;
esac
exit 0
""",
    )
    (state / "systemctl.log").write_text("")

    systemd_dir = tmp_path / "systemd"
    logrotate_dir = tmp_path / "logrotate"
    config_dir = tmp_path / "etc-gfx1150-runner"
    sbin_dir = tmp_path / "sbin"
    systemd_dir.mkdir()
    logrotate_dir.mkdir()
    config_dir.mkdir()
    sbin_dir.mkdir()

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{shims}:{env.get('PATH', '/usr/bin:/bin')}",
            "SHIM_STATE": str(state),
            "RUNNER_ENV": str(SPEC),
            "SYSTEMD_DIR": str(systemd_dir),
            "LOGROTATE_DIR": str(logrotate_dir),
            "CONFIG_DIR": str(config_dir),
            "WATCHDOG_INSTALLED": str(sbin_dir / "gfx1150-runner-watchdog"),
            "WATCHDOG_LEGACY_INSTALLED": str(sbin_dir / "legacy-ensure-runner.sh"),
            "DOCTOR_INSTALLED": str(sbin_dir / "gfx1150-runner-doctor"),
            "WATCHDOG_TIMER": "gfx1150-runner-watchdog.timer",
            "PAT_FILE": str(tmp_path / "runner.pat"),
            "WATCHDOG_LOG": str(tmp_path / "ensure-runner.log"),
        }
    )
    return {
        "env": env,
        "state": state,
        "systemd": systemd_dir,
        "logrotate": logrotate_dir,
        "config": config_dir,
        "sbin": sbin_dir,
        "tmp": tmp_path,
    }


def _run(sandbox, *args: str):
    return subprocess.run(
        ["bash", str(INSTALLER), *args],
        env=sandbox["env"],
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_apply_installs_every_file(sandbox):
    result = _run(sandbox, "--apply", "--allow-no-pat")

    assert result.returncode == 0, result.stdout + result.stderr
    assert (sandbox["sbin"] / "gfx1150-runner-watchdog").exists()
    assert (sandbox["sbin"] / "gfx1150-runner-doctor").exists()
    assert (sandbox["config"] / "runner.env").exists()
    assert (sandbox["systemd"] / "gfx1150-runner-watchdog.service").exists()
    assert (sandbox["systemd"] / "gfx1150-runner-watchdog.timer").exists()
    assert (sandbox["systemd"] / "gfx1150-runner-watchdog-alert.service").exists()
    assert (sandbox["logrotate"] / "gfx1150-runner-watchdog").exists()
    systemctl = (sandbox["state"] / "systemctl.log").read_text()
    assert "daemon-reload" in systemctl
    assert "enable --now gfx1150-runner-watchdog.timer" in systemctl


def test_check_is_ok_after_apply(sandbox):
    assert _run(sandbox, "--apply", "--allow-no-pat").returncode == 0

    result = _run(sandbox, "--check")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "RESULT: OK" in result.stdout
    assert "DRIFT" not in result.stdout


def test_check_detects_drift_and_apply_restores(sandbox):
    """D7: edit the installed script -> DRIFT; --apply -> OK."""
    assert _run(sandbox, "--apply", "--allow-no-pat").returncode == 0

    installed = sandbox["sbin"] / "gfx1150-runner-watchdog"
    installed.write_text(installed.read_text() + "\n# manual edit\n")

    drift = _run(sandbox, "--check")
    assert drift.returncode == 1
    assert "DRIFT" in drift.stdout
    assert "RESULT: DRIFT" in drift.stdout

    assert _run(sandbox, "--apply", "--allow-no-pat").returncode == 0
    restored = _run(sandbox, "--check")
    assert restored.returncode == 0, restored.stdout
    assert "RESULT: OK" in restored.stdout


def test_apply_refuses_without_a_pat(sandbox):
    result = _run(sandbox, "--apply")

    assert result.returncode == 3
    assert "refusing --apply" in result.stderr
    assert not (sandbox["sbin"] / "gfx1150-runner-watchdog").exists()


def test_apply_accepts_a_valid_pat(sandbox):
    pat = sandbox["tmp"] / "runner.pat"
    pat.write_text("github_pat_fake0000000000000000000000000000000000000000000000000000\n")
    pat.chmod(0o600)

    result = _run(sandbox, "--apply")

    assert result.returncode == 0, result.stdout + result.stderr


def test_uninstall_removes_units_and_scripts_but_keeps_the_pat(sandbox):
    pat = sandbox["tmp"] / "runner.pat"
    pat.write_text("github_pat_fake0000000000000000000000000000000000000000000000000000\n")
    pat.chmod(0o600)
    log = sandbox["tmp"] / "ensure-runner.log"
    log.write_text("evidence\n")

    assert _run(sandbox, "--apply").returncode == 0
    result = _run(sandbox, "--uninstall")

    assert result.returncode == 0, result.stdout + result.stderr
    assert not (sandbox["sbin"] / "gfx1150-runner-watchdog").exists()
    assert not (sandbox["systemd"] / "gfx1150-runner-watchdog.timer").exists()
    assert pat.exists()
    assert log.exists()


def test_unknown_option_is_rejected(sandbox):
    result = _run(sandbox, "--frobnicate")

    assert result.returncode == 3
    assert "unknown option" in result.stderr


def test_installer_never_reads_the_pat_contents():
    body = INSTALLER.read_text(encoding="utf-8")
    # It may test existence and permissions; it must never cat/read the value.
    assert 'cat "${PAT_FILE}"' not in body
    assert "tr -d" not in body
    assert "Bearer" not in body
