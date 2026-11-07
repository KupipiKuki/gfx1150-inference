#!/usr/bin/env python3
"""Execute a CI workflow job's `run:` scripts locally, verbatim.

Phase 7A-5. The sdist-install job cannot be executed by GitHub Actions from a
sandbox, but every command in it is a plain shell command. This driver reads the
*parsed* workflow, extracts each step's `run:` script exactly as the runner
would see it, and executes it in order with `bash --noprofile --norc -eo
pipefail` (the shell GitHub uses for `shell: bash`). The output and the exit
code of every step are recorded.

Steps that use an `actions/*` action have no `run:` script and are skipped;
the checkout is simulated by a fresh clone made by the caller.

Usage:
    python3 rehearse-workflow.py <workflow.yml> <job-name> <workdir> [env...]

The optional trailing arguments are `KEY=VALUE` environment overrides that are
exported into every step (used to simulate a CPU-only CI host on a machine
that has ROCm installed).
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys

import yaml


def main(argv: list[str]) -> int:
    if len(argv) < 4:
        print(__doc__)
        return 2
    workflow_path = pathlib.Path(argv[1])
    job_name = argv[2]
    workdir = pathlib.Path(argv[3]).resolve()
    overrides = dict(item.split("=", 1) for item in argv[4:] if "=" in item)

    document = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    job = document["jobs"][job_name]
    steps = job.get("steps", [])

    environment = dict(os.environ)
    environment.update(overrides)
    if overrides:
        print(
            "environment overrides: " + ", ".join(f"{k}={v}" for k, v in overrides.items()),
            flush=True,
        )

    script_dir = workdir / ".rehearsal-scripts"
    script_dir.mkdir(parents=True, exist_ok=True)

    print(f"=== job: {job_name} ({workflow_path.name}) ===", flush=True)
    print(f"=== workdir: {workdir} ===", flush=True)

    for index, step in enumerate(steps, start=1):
        name = step.get("name", f"step {index}")
        if "run" not in step:
            print(f"\n----- step {index}: {name} -----", flush=True)
            print("(an actions/* step: no shell script; simulated by the caller)", flush=True)
            continue
        script = step["run"]
        script_file = script_dir / f"step{index:02d}.sh"
        script_file.write_text(script, encoding="utf-8")
        advisory = bool(step.get("continue-on-error"))
        # Flush before running the subprocess, so the markers and the step's
        # output stay in order in a redirected log.
        print(f"\n----- step {index}: {name} -----", flush=True)
        if advisory:
            print("(continue-on-error: true -- a failure here does not fail the job)", flush=True)
        print(f"$ bash {script_file.name}", flush=True)
        completed = subprocess.run(
            ["bash", "--noprofile", "--norc", "-eo", "pipefail", str(script_file)],
            cwd=str(workdir),
            env=environment,
        )
        print(f"----- exit code: {completed.returncode} -----", flush=True)
        if completed.returncode != 0:
            if advisory:
                print(
                    f"step {index} ({name}) failed but is advisory; the job continues.",
                    flush=True,
                )
                continue
            print(
                f"\nFAILED at step {index} ({name}); GitHub Actions would fail the job here.",
                flush=True,
            )
            return completed.returncode

    print("\nAll steps exited 0.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
