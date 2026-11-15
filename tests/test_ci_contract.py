"""C2f — the runner/workflow contract, checked in the CPU lane.

``.github/workflows/ci-gpu.yml`` and ``scripts/ci/runner.env`` are one
contract: the workflow runs on the labels the runner carries, the job name is
the required-check name, and the schedule clears the host's boot window. The
doctor checks the same things at runtime (L5), but a drift must fail a PR
before it reaches the host — that is this module.

Parsing is regex-based on purpose: the CPU lane must not depend on PyYAML, and
the file is small enough that a full YAML parse would hide which line drifted.

The mutation tests are the proof that the checks are real: a wrong label, a
renamed job, a push trigger, a missing fork guard and a too-early cron each
make the corresponding check fail.
"""

from __future__ import annotations

import pathlib
import re
import subprocess

import pytest

pytestmark = pytest.mark.cpu

ROOT = pathlib.Path(__file__).resolve().parent.parent
CI_DIR = ROOT / "scripts" / "ci"
WORKFLOW = ROOT / ".github" / "workflows" / "ci-gpu.yml"
SPEC = CI_DIR / "runner.env"

AUTOMATIC_LABELS = {"self-hosted", "Linux", "X64"}


def _spec() -> dict[str, str]:
    keys = ["RUNNER_LABELS", "REQUIRED_GPU_CHECK", "BOOT_WINDOW_UTC", "CRON_MARGIN_MIN"]
    script = '. "$1"; shift; for k in "$@"; do printf "%s\\n" "${!k}"; done'
    out = subprocess.check_output(
        ["bash", "-c", script, "_", str(SPEC), *keys], text=True, timeout=30
    )
    return dict(zip(keys, out.splitlines()))


SPEC_VALUES = _spec()


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def _cron_minutes(text: str) -> int | None:
    match = re.search(r"cron:\s*[\"']([^\"']+)[\"']", text)
    if not match:
        return None
    fields = match.group(1).split()
    try:
        return int(fields[1]) * 60 + int(fields[0])
    except (IndexError, ValueError):
        return None


def _boot_minutes() -> int:
    hour, minute = (int(x) for x in SPEC_VALUES["BOOT_WINDOW_UTC"].split(":"))
    return hour * 60 + minute


# --------------------------------------------------------------- the checks --


def check_runs_on(text: str) -> list[str]:
    match = re.search(r"^\s*runs-on:\s*\[(.*?)\]\s*$", text, re.M)
    if not match:
        return ["runs-on: no list found"]
    got = {x.strip().strip("'\"") for x in match.group(1).split(",") if x.strip()}
    allowed = {
        x.strip() for x in SPEC_VALUES["RUNNER_LABELS"].split(",") if x.strip()
    } | AUTOMATIC_LABELS
    missing = sorted(got - allowed)
    return [f"runs-on: labels not on the runner: {missing}"] if missing else []


def check_job_name(text: str) -> list[str]:
    match = re.search(r"^\s{4}name:\s*(.+?)\s*$", text, re.M)
    if not match:
        return ["job name: not found"]
    if match.group(1) != SPEC_VALUES["REQUIRED_GPU_CHECK"]:
        return [
            f"job name: '{match.group(1)}' != required check "
            f"'{SPEC_VALUES['REQUIRED_GPU_CHECK']}'"
        ]
    return []


def check_no_push(text: str) -> list[str]:
    return ["push: a push trigger is not allowed"] if re.search(
        r"^\s{2}push:", text, re.M
    ) else []


def check_cron(text: str) -> list[str]:
    cron = _cron_minutes(text)
    if cron is None:
        return ["cron: not found or unparseable"]
    margin = (cron - _boot_minutes()) % (24 * 60)
    want = int(SPEC_VALUES["CRON_MARGIN_MIN"])
    if margin < want:
        return [f"cron: leaves {margin} min after boot (want >= {want})"]
    return []


def check_permissions(text: str) -> list[str]:
    if not re.search(r"^permissions:\s*$", text, re.M):
        return ["permissions: block missing"]
    if not re.search(r"^\s{2}contents:\s*read\s*$", text, re.M):
        return ["permissions: contents: read missing"]
    return []


def check_concurrency(text: str) -> list[str]:
    errors = []
    if not re.search(r"^concurrency:\s*$", text, re.M):
        errors.append("concurrency: block missing")
    if "cancel-in-progress: false" not in text:
        errors.append("concurrency: cancel-in-progress must be false")
    return errors


def check_fork_guard(text: str) -> list[str]:
    return [] if "github.event.pull_request.head.repo.full_name == github.repository" in text \
        else ["fork guard: untrusted PR code would run on the host"]


def check_junit_guard(text: str) -> list[str]:
    errors = []
    if "skip is not a pass" not in text:
        errors.append("junit: skip-is-not-pass guard missing")
    if "gpu-lane.xml" not in text:
        errors.append("junit: gpu-lane.xml report missing")
    return errors


def check_timeout(text: str) -> list[str]:
    return [] if re.search(r"^\s{4}timeout-minutes:\s*\d+\s*$", text, re.M) \
        else ["timeout-minutes: job timeout missing"]


CONFIG_SCRIPTS = (
    "runner_doctor.sh",
    "ensure_runner_registered.sh",
    "install_runner_watchdog.sh",
)


def check_spec_is_the_only_source() -> list[str]:
    errors = []
    for name in CONFIG_SCRIPTS:
        path = CI_DIR / name
        if not path.exists():
            errors.append(f"spec: {name} missing")
            continue
        body = path.read_text(encoding="utf-8")
        if "runner.env" not in body:
            errors.append(f"spec: {name} does not source runner.env")
        if "actions.runner." in body:
            errors.append(f"spec: {name} hardcodes a service unit")
        if "github.com/KupipiKuki/gfx1150-inference" in body:
            errors.append(f"spec: {name} hardcodes the repository URL")
    return errors


ALL_CHECKS = (
    check_runs_on,
    check_job_name,
    check_no_push,
    check_cron,
    check_permissions,
    check_concurrency,
    check_fork_guard,
    check_junit_guard,
    check_timeout,
)


def _violations(text: str) -> list[str]:
    errors: list[str] = []
    for check in ALL_CHECKS:
        errors.extend(check(text))
    errors.extend(check_spec_is_the_only_source())
    return errors


# ------------------------------------------------------------ the contract --


def test_workflow_satisfies_the_contract():
    assert _violations(_text()) == []


def test_spec_is_shell_sourceable():
    result = subprocess.run(
        ["bash", "-c", f'. "{SPEC}"; printf "%s\\n" "$RUNNER_LABELS"'],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "gfx1150,rocm"


# ------------------------------------------------------------- mutations -----


def test_wrong_label_is_detected():
    mutated = _text().replace(
        "runs-on: [self-hosted, gfx1150, rocm]",
        "runs-on: [self-hosted, gfx1150, rocm, windows]",
    )
    assert mutated != _text()
    assert check_runs_on(mutated)


def test_renamed_job_is_detected():
    mutated = _text().replace(
        "name: GPU correctness (self-hosted gfx1150)",
        "name: GPU correctness (renamed)",
    )
    assert mutated != _text()
    assert check_job_name(mutated)


def test_push_trigger_is_detected():
    mutated = _text().replace(
        "on:\n  pull_request:",
        "on:\n  push:\n    branches: [main]\n  pull_request:",
    )
    assert mutated != _text()
    assert check_no_push(mutated)


def test_missing_fork_guard_is_detected():
    mutated = _text().replace(
        "github.event.pull_request.head.repo.full_name == github.repository",
        "true",
    )
    assert mutated != _text()
    assert check_fork_guard(mutated)


def test_too_early_cron_is_detected():
    mutated = _text().replace('cron: "0 5 * * *"', 'cron: "0 4 * * *"')
    assert mutated != _text()
    assert check_cron(mutated)


# ---------------------------------------------------------- static guards ----


def test_pat_only_travels_through_a_curl_config_file():
    for name in ("runner_doctor.sh", "ensure_runner_registered.sh"):
        body = (CI_DIR / name).read_text(encoding="utf-8")
        assert 'header = "Authorization: Bearer %s"' in body
        assert "-K " in body
        for line in body.splitlines():
            stripped = line.strip()
            if stripped.startswith("-H"):
                assert "Bearer" not in stripped
                assert "pat" not in stripped


def test_sdist_manifest_ships_the_runner_ci_fixtures():
    """The C2 tests read scripts/ci/ and the workflow; the sdist must carry
    them or the extracted-tree lane cannot collect those tests."""
    manifest = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")
    assert "recursive-include scripts/ci" in manifest
    assert ".github/workflows/ci-gpu.yml" in manifest


def test_no_moving_journal_window_in_health_checks():
    for name in ("runner_doctor.sh", "ensure_runner_registered.sh"):
        body = (CI_DIR / name).read_text(encoding="utf-8")
        assert "journalctl" not in body
        assert "--since" not in body


def test_no_mtime_selection_in_health_checks():
    for name in ("runner_doctor.sh", "ensure_runner_registered.sh"):
        body = (CI_DIR / name).read_text(encoding="utf-8")
        assert "ls -t" not in body
