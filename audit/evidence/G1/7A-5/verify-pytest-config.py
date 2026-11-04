#!/usr/bin/env python3
"""Verify the pytest configuration that 7A-2 closed out.

Phase 7A-2 was implemented inside 7A-1's `[tool.pytest.ini_options]` block, so
the 7A-2 closeout is a verification, not new code. This script checks the
configuration two ways:

1. **Declared** -- the block in `pyproject.toml` declares the required keys:
   `markers`, `testpaths`, `addopts`, strict markers/config, and the
   `PytestReturnNotNoneWarning` escalation.
2. **Behavioural** -- each strictness is exercised in a scratch directory that
   reproduces the repository's configuration verbatim, so the checks do not
   write anything into the repository:
   - an unknown marker must be an error (`--strict-markers`);
   - an unknown ini option must be an error (`--strict-config`);
   - a test that returns a value instead of asserting must be an error (the
     `PytestReturnNotNoneWarning` escalation).

Usage:
    python3 verify-pytest-config.py [path/to/pyproject.toml]
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11
    import tomli as tomllib  # type: ignore[no-redef]

DEFAULT_PATH = pathlib.Path(__file__).resolve().parents[4] / "pyproject.toml"

failures: list[str] = []
checks = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global checks
    checks += 1
    print(f"  [{'ok  ' if condition else 'FAIL'}] {label}" + (f" -- {detail}" if detail else ""))
    if not condition:
        failures.append(label)


def pytest_run(directory: pathlib.Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "pytest", *args],
        cwd=str(directory),
        capture_output=True,
        text=True,
        check=False,
    )


def main(argv: list[str]) -> int:
    path = pathlib.Path(argv[1]) if len(argv) > 1 else DEFAULT_PATH
    print(f"=== verifying the pytest configuration in {path} ===")
    config = tomllib.loads(path.read_text(encoding="utf-8"))
    options = config.get("tool", {}).get("pytest", {}).get("ini_options")
    if options is None:
        print("  [FAIL] there is no [tool.pytest.ini_options] section")
        return 1

    print("\n=== declared ===")
    check("the section exists", True)
    check("minversion is declared", "minversion" in options, str(options.get("minversion")))
    check(
        "testpaths is ['tests']",
        options.get("testpaths") == ["tests"],
        str(options.get("testpaths")),
    )
    markers = options.get("markers", [])
    for marker in ("gpu", "cpu", "slow"):
        check(
            f"the '{marker}' marker is registered",
            any(str(m).strip().startswith(f"{marker}:") for m in markers),
        )
    addopts = options.get("addopts", [])
    check("--strict-markers is in addopts", "--strict-markers" in addopts)
    check("--strict-config is in addopts", "--strict-config" in addopts)
    check("-ra is in addopts (skip reasons are reported)", "-ra" in addopts)
    check(
        "PytestReturnNotNoneWarning is escalated in addopts",
        "error::pytest.PytestReturnNotNoneWarning" in addopts,
    )
    check(
        "PytestReturnNotNoneWarning is escalated in filterwarnings",
        "error::pytest.PytestReturnNotNoneWarning" in options.get("filterwarnings", []),
    )

    print("\n=== behavioural (in a scratch directory) ===")
    with tempfile.TemporaryDirectory() as tmp:
        scratch = pathlib.Path(tmp)
        # Reproduce the repository's configuration verbatim.
        scratch.joinpath("pyproject.toml").write_text(
            "[tool.pytest.ini_options]\n" + _render(options),
            encoding="utf-8",
        )

        # 1. The registered markers are visible to pytest.
        markers_run = pytest_run(scratch, "--markers")
        for marker in ("gpu", "cpu", "slow"):
            check(
                f"pytest --markers lists '{marker}'",
                f"@pytest.mark.{marker}" in markers_run.stdout,
            )

        # 2. An unknown marker is an error (--strict-markers).
        scratch.joinpath("test_unknown_marker.py").write_text(
            "import pytest\n\n\n@pytest.mark.no_such_marker\ndef test_x():\n    assert True\n",
            encoding="utf-8",
        )
        unknown = pytest_run(scratch, "-q", "test_unknown_marker.py")
        check(
            "an unknown marker is an error, not a warning",
            unknown.returncode != 0 and "not found in `markers`" in unknown.stdout + unknown.stderr,
            f"exit {unknown.returncode}",
        )
        scratch.joinpath("test_unknown_marker.py").unlink()

        # 3. An unknown ini option is an error (--strict-config).
        strict = scratch.joinpath("pyproject.toml")
        original = strict.read_text(encoding="utf-8")
        strict.write_text(original + 'unknown_ini_option = "x"\n', encoding="utf-8")
        strict_config = pytest_run(scratch, "-q", "--collect-only")
        check(
            "an unknown ini option is an error, not a warning",
            strict_config.returncode != 0
            and "Unknown config option" in strict_config.stdout + strict_config.stderr,
            f"exit {strict_config.returncode}",
        )
        strict.write_text(original, encoding="utf-8")

        # 4. A test that returns a value is an error (the escalation).
        scratch.joinpath("test_returns_value.py").write_text(
            "def test_returns_a_value():\n    return True\n",
            encoding="utf-8",
        )
        returns = pytest_run(scratch, "-q", "test_returns_value.py")
        combined = returns.stdout + returns.stderr
        check(
            "a test that returns a value is an error",
            returns.returncode != 0 and "PytestReturnNotNoneWarning" in combined,
            f"exit {returns.returncode}",
        )

    print(f"\n=== {checks - len(failures)}/{checks} checks passed ===")
    if failures:
        print("FAILED: " + "; ".join(failures))
        return 1
    print("PASS: the pytest configuration is complete and strict")
    return 0


def _render(options: dict) -> str:
    """Render the ini options as a TOML table body (the values are literals)."""
    lines = []
    for key, value in options.items():
        if isinstance(value, list):
            lines.append(f"{key} = [")
            lines.extend(f'    "{item}",' for item in value)
            lines.append("]")
        else:
            lines.append(f'{key} = "{value}"')
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.exit(main(sys.argv))
