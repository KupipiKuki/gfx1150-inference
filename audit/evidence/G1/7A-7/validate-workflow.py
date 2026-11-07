#!/usr/bin/env python3
"""Validate .github/workflows/ci-gpu.yml against the 7A-7 brief's requirements.

Phase 7A-7. The workflow is not executable yet (no self-hosted runner is
registered), so the requirements are checked mechanically instead of by running
the job. The check is deliberately explicit about every clause of the brief's
section 3, so that a regression in any of them is visible.

Usage::

    python3 audit/evidence/G1/7A-7/validate-workflow.py [path/to/ci-gpu.yml]
"""

from __future__ import annotations

import pathlib
import sys

import yaml

DEFAULT_PATH = (
    pathlib.Path(__file__).resolve().parents[4] / ".github/workflows/ci-gpu.yml"
)

failures: list[str] = []
checks = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global checks
    checks += 1
    mark = "ok  " if condition else "FAIL"
    print(f"  [{mark}] {label}" + (f" -- {detail}" if detail else ""))
    if not condition:
        failures.append(label)


def main(argv: list[str]) -> int:
    path = pathlib.Path(argv[1]) if len(argv) > 1 else DEFAULT_PATH
    print(f"=== validating {path} ===")
    text = path.read_text(encoding="utf-8")
    try:
        document = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        print(f"  [FAIL] the file is not valid YAML -- {exc}")
        return 1
    print("  [ok  ] the file is valid YAML")

    # `on:` is parsed by YAML 1.1 as the boolean True.
    triggers = document.get("on", document.get(True, {}))
    print(f"\n=== triggers ===\n  {sorted(triggers)}")
    check("pull_request trigger", "pull_request" in triggers)
    check("nightly schedule trigger", "schedule" in triggers)
    check(
        "manual trigger",
        "workflow_dispatch" in triggers,
        "workflow_dispatch" in triggers,
    )

    jobs = document.get("jobs", {})
    check("exactly one job", len(jobs) == 1, f"{list(jobs)}")
    job = next(iter(jobs.values()))

    print("\n=== runner and gate state ===")
    check(
        "runs-on is [self-hosted, gfx1150, rocm]",
        job.get("runs-on") == ["self-hosted", "gfx1150", "rocm"],
        str(job.get("runs-on")),
    )
    check(
        "continue-on-error is true while no runner is registered",
        job.get("continue-on-error") is True,
        str(job.get("continue-on-error")),
    )
    check("a timeout is set", isinstance(job.get("timeout-minutes"), int))

    steps = job.get("steps", [])
    names = [step.get("name", "") for step in steps]
    print("\n=== steps ===")
    for name in names:
        print(f"  - {name}")
    blob = "\n".join(text.splitlines())

    check(
        "the checkout action is used",
        any("actions/checkout" in str(step.get("uses", "")) for step in steps),
    )
    check(
        "the documented prerequisites are installed",
        all(
            token in blob
            for token in ("numpy", "setuptools", "wheel", "pybind11", "pytest")
        ),
    )
    check(
        "the configure step is the documented command",
        "env -u pybind11_DIR cmake -B build -DCMAKE_BUILD_TYPE=Release" in blob,
    )
    check(
        "the build step builds the extension",
        "cmake --build build -j" in blob,
    )
    check(
        "the GPU lane runs pytest -m gpu",
        "pytest -m gpu" in blob,
    )
    check(
        "the lane is checked for skips, not only for a non-zero exit code",
        "skipped" in blob and "junitxml" in blob,
    )
    check(
        "the guard requires at least one passing test",
        "passed < 1" in blob,
    )
    check(
        "the guard fails on any skip",
        "a skip is not a pass" in blob,
    )
    check(
        "logs are uploaded as artifacts",
        any("actions/upload-artifact" in str(step.get("uses", "")) for step in steps),
    )
    check(
        "the upload runs even when the lane fails",
        any(
            step.get("uses", "").startswith("actions/upload-artifact")
            and step.get("if") == "always()"
            for step in steps
        ),
    )

    print("\n=== hygiene ===")
    check("no secrets are referenced", "secrets." not in blob)
    check(
        "the tracking issue is named",
        "pull/8" in blob or "7F-1" in blob,
    )
    check(
        "the job is documented as not a G1 pass",
        "not a G1" in blob or "must NOT be counted" in blob,
    )

    print(f"\n=== {checks - len(failures)}/{checks} checks passed ===")
    if failures:
        print("FAILED: " + "; ".join(failures))
        return 1
    print("PASS: the workflow satisfies every clause checked")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
