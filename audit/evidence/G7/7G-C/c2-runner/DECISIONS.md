# C2/C4 — decisions recorded in the evidence

## Cron alignment (C2 item 3) — decision: move the nightly cron

`PHASE7_7G_CLOSURE_BRIEF.md` offered two options: move the 03:00 UTC nightly
GPU schedule after the ~03:38 UTC boot window, or make the nightly run
tolerant of a queued runner.

**Decision: the schedule was moved, not the job made tolerant.** The cron in
`.github/workflows/ci-gpu.yml` now fires at **04:00 UTC** (`"0 4 * * *"`),
~22 minutes after this host's ~03:38 UTC boot, so the nightly job finds the
runner online instead of queuing on it. Reasons:

- option (a) is a one-line, zero-risk change to one file;
- a queued-runner tolerance would have to be learned and asserted inside the
  workflow (fragile, and it would still burn queued minutes);
- the runner-registration outage (C2's actual defect) is orthogonal and is
  handled by the watchdog, not by the schedule.

The diff between parent and candidate touches only the `cron:` value and a
comment (see `../diffstat.txt`).

## Enforcement (C4) — decision: no push trigger

The owner decided (2026-11-13) **not** to add a `push` trigger to
`ci-gpu.yml`. The workflow keeps `pull_request`, `schedule` and
`workflow_dispatch` and stays **advisory** while the G6 enforcement waiver is
in force; per the waiver addendum the required-GPU-check enforcement is
restored when C2 lands (owner PAT + live simulation transcript).

The replacement interim control ran on this host before merge and is recorded
in `../gpu-lane.log`: `PYTHONPATH=build python -m pytest -m gpu -q` —
**45 passed, 547 deselected** at the frozen candidate
`cac3eeddc02164fcb98e654c24b4b8aa27d6a05c`.
