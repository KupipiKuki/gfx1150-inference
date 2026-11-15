# C2 remediation — BLOCKER-7G-C-1 and BLOCKER-7G-C-2 fixed

**2026-11-14, remediation of `audit/AUDIT_7G_C_2026-11-14.md` §3.**
Both blockers were fixed in `scripts/ci/ensure_runner_registered.sh` (the
snapshot in this directory is updated to the fixed version); the original
flagged version lives in git history (commit `c0cd063` tree).

## BLOCKER-7G-C-1 (High) — health check + repair discipline

**Health check.** `runner_online()` no longer greps a *moving* journal window
(`journalctl --since "-10 min"`) for the startup-only `Listening for Jobs`
marker — the exact defect the auditor proved (marker 0 hits inside the
window while the runner was working). Health is now decided from the
*current* state only:

1. `systemctl is-active --quiet` on the unit;
2. `systemctl show -p ActiveState -p SubState --value` contains `active`
   (rejects activating / crash-looping);
3. a `Runner.Listener` process owned by the runner user is alive
   (`pgrep -u "${SERVICE_USER}" -f 'Runner\.Listener'`);
4. the newest `_diag/Runner_*.log` records `Listening for Jobs` AND does not
   contain `registration has been deleted`.

No timestamp/age is consulted anywhere; a runner up for hours with a 30-minute
old startup marker is healthy, which is what the acceptance case demands.

**Repair discipline** (in addition to logging + non-zero exits already
present):

- the repair is skipped while a `Runner.Worker` process exists (a job is in
  flight): log line + exit 0, the next tick re-checks;
- attempts are rate-limited to one per cooldown (default 1800 s via
  `COOLDOWN_SECS`, state on tmpfs at `/run/ensure-runner.last-repair`,
  overridable through `COOLDOWN_FILE`); the attempt is recorded *before* it
  runs, so failed attempts are also counted.

**Deviation from the auditor's suggested snippet, flagged for re-review:**
the suggested `systemctl show ... | grep -q '^active$'` pipeline races under
`set -o pipefail` — `grep -q` exits at the first match and the writer can die
of SIGPIPE, making a healthy runner flakily "offline". The fix captures the
`systemctl show` output before grepping (same for `ls | head` over the diag
glob). This was reproduced against the suggested form in the sandbox before
hardening it.

## BLOCKER-7G-C-2 (Medium) — PAT never in argv

The `-H "Authorization: Bearer ${PAT}"` argv leak is gone: the PAT is written
to a `mktemp` file (mode 0600), handed to curl via `--config`/`-K`
(`header = "Authorization: Bearer <PAT>"` inside the file), and the temp file
is removed on every exit path (single EXIT trap shared with the token-JSON
temp file; `die` triggers it). `unset PAT` runs as soon as the header file is
built. No curl argument contains the PAT, so nothing readable in
`/proc/<pid>/cmdline` for the request lifetime is new; the raw JSON answer
still lands only in a root-only 0600 temp file.

## Comment correction (requested in the same finding)

The header comment no longer claims "root-only /proc slot" for the
registration token. It now states accurately: the token is passed to
`config.sh --token` as an argument of a process run **as the runner user**
(via `runuser -u`), so it appears transiently in `/proc/<pid>/cmdline`,
readable by any local user for roughly the one second the call takes; it is
single-use, short-lived and grants only runner registration — accepted as low
severity, documented rather than hidden.

## Scripted check (auditor's required deliverable)

`tests/test_runner_watchdog.py` (CPU lane, registered in
`test_harness_contract.py::EXPECTED_LANES`) drives the real script through
PATH-shimmed `systemctl`/`pgrep`/`journalctl`/`curl`/`runuser` around a fake
runner directory. It asserts, among others:

* `--check` exits **0** on a healthy runner whose startup marker is
  30+ minutes old with a journal window that reports nothing — the auditor's
  BLOCKER-7G-C-1 acceptance case;
* `--check` exits **1** on a deleted registration;
* a deleted registration triggers **exactly one** repair (one
  registration-token request) and then reports healthy — C2's original
  acceptance, minus the real-runner transcript;
* the PAT never appears in curl's argv during the repair (and the header temp
  file is removed), while the registration token does appear in
  `runuser`/`config.sh` argv exactly as documented;
* no repair while a `Runner.Worker` process exists;
* a second offline tick inside the cooldown makes no new attempt;
* static guards: no `journalctl`/`--since` in the script, no `${PAT}` inside
  any `-H` argument.

Run record: `scripted-check-2026-11-14.log` in this directory —
**9 passed**.

## Still owner-pending (unchanged dependency, per §6 of the audit)

The QAQC "watchdog brings the runner back" acceptance must be re-run against
a **real** healthy runner with the real PAT:
`SIMULATION-TRANSCRIPT-OWNER-PENDING.md` in this directory describes it
verbatim, including the audited healthy-state case. The PAT still does not
exist; nothing in this remediation handles or deploys it.
