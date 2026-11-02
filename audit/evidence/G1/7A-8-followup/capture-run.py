#!/usr/bin/env python3
"""Capture the GitHub Actions run evidence for the 7A-8 follow-up (QF-1).

The run's raw log download needs an authenticated API call
(``GET /repos/{owner}/{repo}/actions/runs/{id}/logs`` answers HTTP 403 without a
token), so what is recorded here is the API's own view of the run: the
conclusion, every step's conclusion, and the check-run annotations. That is
enough to show which step failed and that the job now completes.

Usage::

    python3 audit/evidence/G1/7A-8-followup/capture-run.py <run-id> [<run-id> ...]
"""

from __future__ import annotations

import datetime
import json
import sys
import urllib.error
import urllib.request

API = "https://api.github.com/repos/KupipiKuki/gfx1150-inference"


def _get(path: str) -> object:
    request = urllib.request.Request(
        f"{API}{path}", headers={"Accept": "application/vnd.github+json"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def _duration(started: str | None, completed: str | None) -> str:
    if not started or not completed:
        return "-"
    begin = datetime.datetime.fromisoformat(started.replace("Z", "+00:00"))
    end = datetime.datetime.fromisoformat(completed.replace("Z", "+00:00"))
    seconds = int((end - begin).total_seconds())
    return f"{seconds // 60}:{seconds % 60:02d}"


def capture(run_id: str) -> None:
    run = _get(f"/actions/runs/{run_id}")
    assert isinstance(run, dict)
    print(f"=== run {run_id} ===")
    print(f"workflow:   {run['name']}")
    print(f"head sha:   {run['head_sha']}")
    print(f"branch:     {run['head_branch']}")
    print(f"status:     {run['status']}")
    print(f"conclusion: {run['conclusion']}")
    print(f"url:        {run['html_url']}")
    print(f"created:    {run['created_at']}")
    print()

    jobs = _get(f"/actions/runs/{run_id}/jobs")
    assert isinstance(jobs, dict)
    for job in jobs.get("jobs", []):
        wall = _duration(job.get("started_at"), job.get("completed_at"))
        print(f"job: {job['name']}  ({job['status']} / {job['conclusion']})")
        print(f"  job url:    {job['html_url']}")
        print(f"  wall clock: {wall}")
        print(f"  {'step':<56} {'status':<10} {'conclusion':<10} duration")
        for step in job.get("steps", []):
            print(
                f"  {step['number']:>2}. {step['name']:<52} {step['status']:<10} "
                f"{str(step['conclusion']):<10} "
                f"{_duration(step.get('started_at'), step.get('completed_at'))}"
            )
        print()

        for annotation in _get(f"/check-runs/{job['id']}/annotations") or []:
            if isinstance(annotation, dict):
                message = (annotation.get("message") or "").replace("\r", "")
                print(f"  annotation ({annotation.get('path')}):")
                for line in message.splitlines():
                    print(f"    {line}")
        print()


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    for run_id in argv[1:]:
        try:
            capture(run_id)
        except urllib.error.HTTPError as exc:
            print(f"run {run_id}: API error {exc}")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
