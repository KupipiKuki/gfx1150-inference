# Phase 7G-C Coder Brief — Closure package (Gate G7-C)

**To:** GLM5.3 / Mistral Vibe (coder) + QAQC
**From:** DeepSeek V4.1 Flash (primary auditor)
**Date:** 2026-11-13
**Branch:** `wp/7G-C-closure` (cut from `main` **after** PR #13 merges)
**Base:** `main` at the PR #13 merge commit (record the SHA in the evidence)
**Gate:** G7-C. **This is the last work package of this project.**
**Plan:** [`PHASE7_7G_RESIDENCY_AND_FOLLOWUP_PLAN.md`](PHASE7_7G_RESIDENCY_AND_FOLLOWUP_PLAN.md) §7G-C
**Closure record (already written):** [`docs/CAPABILITIES.md`](docs/CAPABILITIES.md),
[`docs/NEXT_PROJECT_SEED.md`](docs/NEXT_PROJECT_SEED.md)
**Waiver in force:** [`audit/G6_ENFORCEMENT_WAIVER_2026-11-13.md`](audit/G6_ENFORCEMENT_WAIVER_2026-11-13.md)

---

> **AUDIT REWORK (2026-11-14): G7-C is NOT SIGNED.** C1, C3, C4, C5, C6 and C7 are
> accepted (independently reproduced). **C2 has two defects** in
> `scripts/ci/ensure_runner_registered.sh`:
> **(1, High)** the health check greps the journal for `Listening for Jobs`
> inside a *moving 10-minute window*, but that marker is written **once per
> runner start** (3 occurrences vs 8 service starts on this host) — so a healthy
> runner is misread as offline and the 5-minute timer would re-register and
> restart it every 5 minutes (or alert every 5 minutes without a PAT);
> **(2, Medium)** the PAT is passed in `curl`'s **argv**
> (`-H "Authorization: Bearer ${PAT}"`), contradicting both the script's own
> comment and the brief's "never in the process list" requirement. Exact fixes
> are in [`audit/AUDIT_7G_C_2026-11-14.md`](audit/AUDIT_7G_C_2026-11-14.md) §3.
> Also noted there: the logits blobs should be hashes only (N1) and the C3
> pre-registration should live in its own commit (N2).

## 0. Read first

1. `PHASE7_7G_RESIDENCY_AND_FOLLOWUP_PLAN.md` §7G-C (the package table and the
   exit criteria).
2. `audit/G6_SIGNOFF_2026-11-12.md` (the accepted scope) and
   `audit/G6_ENFORCEMENT_WAIVER_2026-11-13.md` (**the required GPU status
   check is suspended** — see §4).
3. `docs/CAPABILITIES.md` (what the engine can do today, with the measured
   numbers) — your changes must not invalidate any of it without updating it.
4. `audit/AUDIT_7F_CI_STATUS_2026-11-11.md` (G6-QF-1…4).

**Project-level decision (owner, 2026-11-13):** this project is **completed and
closed** after this package. The Strata-class work (MoE, CPU compute,
speculation, discrete-VRAM target) moves to a **new project**; its seed is
`docs/NEXT_PROJECT_SEED.md`. Do **not** start any of it here.

---

## 1. Objective

Close the project cleanly:

- four carried-forward defects are fixed (C1–C3) or formally decided (C4);
- two small changes that the measured research workload needs are implemented
  (C5–C6);
- the closing record is produced (C7) and the project's final state is
  labelled;
- nothing that G0–G6 signed is weakened, and no new claim is introduced
  without evidence.

---

## 2. Work packages

### C1 — residency-probe flake (G6-QF-1)

**Defect.** `tests/test_memory_residency.py::test_measured_rss_delta_pin_vs_stream`
failed once on a GitHub-hosted runner (`assert 0 > 0`, `refault majflt=0`: the
page cache retained the synthetic file) and passed on a rerun **with no code
change** — a flake, not a pass.

**Work (in this order).**

1. `tests/test_memory_residency.py::_build_layer_model` (the `with
   open(path, "wb")` block): `fh.flush()` + `os.fsync(fh.fileno())` before
   close, so the synthetic pages are clean when the eviction probe runs
   (`posix_fadvise(DONTNEED)` will not drop dirty pages).
2. `src/weight_loader.py::_evict_spans`: when `MADV_PAGEOUT` is available but
   **raises**, fall back to `MADV_DONTNEED` (drop the PTEs anyway). Today the
   fallback only happens when `MADV_PAGEOUT` is *absent*, so a failing
   `MADV_PAGEOUT` leaves the span mapped and the subsequent `fadvise` cannot
   evict it.
3. Only if 1+2 still leave the runner flaky: make the **major-fault proof** a
   documented `pytest.skip` when `refault_majflt == 0`, keeping the
   PIN/STREAM RSS and PTE assertions. The 7D claim is explicitly best-effort,
   so this is a *measurement* limit, not a claim change — say so in the skip
   message.

**Acceptance.** The test passes on the GitHub-hosted runner **twice in a row**
(no skip, or an explicit skip with the documented reason); the local GPU/CPU
lanes stay green; the 7D evidence bundle and the ledger wording are unchanged.

### C2 — runner registration durability (G6-QF-2)

> **C2 SUPERSEDED (2026-11-14): redeveloped as
> [`PHASE7_7G_C2_RUNNER_REBUILD_PLAN.md`](PHASE7_7G_C2_RUNNER_REBUILD_PLAN.md).**
> The original approach below produced a script whose health check could not
> recognise a healthy runner and whose PAT handling contradicted the brief;
> live verification then found three more defects (mtime-based log selection,
> host clock skew, missing label assertion). The rebuild plan replaces the
> ad-hoc checks with one spec (`scripts/ci/runner.env`), one layered doctor
> (`scripts/ci/runner_doctor.sh`), a current-session health algorithm, a
> transition-based watchdog, a drift-checking installer and a contract test.
> **New acceptance for C2 is §14 of that plan**; the text below is kept for
> traceability only.

**Defect.** The runner's **server-side registration was deleted four times in
four days with no local action** (the local `.runner`/`.credentials` are
unchanged since 2026-11-09). Each deletion leaves the required GPU check
permanently queued and every PR blocked — this is what forced the temporary
enforcement waiver.

**Work.**

1. **Self-repair.** Owner creates a repo-admin PAT with *Administration:
   write* on this repo, stored **outside** the repository, root-readable only
   (e.g. `/etc/gfx1150-runner/runner.pat`, mode `0600`, owner `root`). Add
   `scripts/ci/ensure_runner_registered.sh` (or an equivalent service) that:
   - checks whether the runner service is listening (`systemctl is-active` +
     the `_diag` log's `Listening for Jobs`);
   - if not, obtains a fresh registration token via
     `POST /repos/{owner}/{repo}/actions/runners/registration-token` with the
     PAT, re-runs `config.sh --replace --unattended` with the existing name and
     labels, and restarts the service;
   - logs what it did **without ever echoing the PAT or the token**.
2. **Watchdog.** A systemd timer (or cron) that runs the same script every few
   minutes and alerts (non-zero exit + a log line) when the runner is not
   online, so the failure is visible before it blocks a PR.
3. **Cron alignment.** The nightly GPU schedule (03:00 UTC) fires ~38 minutes
   **before** this host boots (~03:38 UTC), so the nightly job always waits on
   a queued runner. Either move the cron after the boot window (e.g. 04:00
   UTC) or make the nightly run tolerant of a queued runner — the owner's
   choice, recorded in the evidence.

**Acceptance.** A *simulated* failure (stop the service, delete the
registration through the API with the PAT, run the script) brings the runner
back **by itself**, and the watchdog reports the outage. The PAT is never in
the repository, in a log, or in a workflow file. The cron decision is
documented. Re-run the GPU lane locally as the interim control (see §4).

### C3 — decisive-margin evidence (G6-QF-3)

**Defect.** The real-GGUF goldens are recorded honestly, but the two mixed
k-quant prompts are **INCONCLUSIVE** — step 0 is already below the 1.0-logit
decisive threshold, so zero steps are compared.

**Work.** Either (a) add prompts whose first steps are decisive (pre-registered
before the run, committed with the evidence), or (b) require a minimum number
of decisive steps for a run to count as a pass. Re-run the affected goldens and
record **both** the strict 16-step result (unchanged, FAIL) and the decisive
result.

**Acceptance.** The strict FAIL stays recorded verbatim; the new decisive
outcome is recorded with its margins; the ledger wording still claims no exact
golden; artifacts under `audit/evidence/G7/7G-C/golden/`.

### C4 — enforcement: **no push trigger** (decided, 2026-11-13)

The owner decided **not** to add a `push` trigger to `ci-gpu.yml`: the workflow
keeps its existing triggers (`pull_request`, `schedule`, `workflow_dispatch`)
and stays advisory while the waiver is in force. **No code work.** Record the
decision in the evidence and keep
`audit/G6_ENFORCEMENT_WAIVER_2026-11-13.md` accurate: the requirement is
restored when C2 lands.

### C5 — long prompts: `--prompt-file` / `--prompt -`

**Need (measured).** The research profile needs multi-KB prompts; a 45 KB
prompt passed as `--prompt` is unusable (the CLI rejected it during the
2026-11-13 measurement).

**Work (in `src/inference.py`'s CLI).**

- `--prompt-file <path>` — read the prompt from a file (UTF-8);
- `--prompt -` — read the prompt from stdin;
- both mutually exclusive with `--prompt`; exactly one prompt source is
  required; a missing/empty file, a directory, or a non-UTF-8 file must fail
  with a clear message (no traceback);
- the prompt content must never reach the telemetry payload or the stats
  output.

**Acceptance.** A 45 KB prompt file loads and generates; stdin works; the
error cases are clean; a test covers each case; `README.md` (CLI section) and
`docs/CAPABILITIES.md` show the new flags.

### C6 — KV budgeting for CPU/mmap modes

**Defect.** `_effective_kv_budget` (`src/kv_cache.py`) bounds **every** KV
allocation by `min(max_kv_bytes, GTT free, MemAvailable, cgroup)`. For
`--offload-kv-cpu` and `--kv-mmap-dir` the KV does **not** live in the device,
so it must not be bounded by the device share — on a host with a small GTT
share, long-context research runs are refused for the wrong reason.

**Work.**

- For the CPU-offloaded pool: bound by **host RAM** (`MemAvailable` / cgroup),
  not by GTT free.
- For the mmap-backed pool: bound by host RAM **and** by free disk space
  (`os.statvfs`) with a clear error naming the shortfall.
- The device-resident pool keeps today's GTT-bounded behaviour (the G0–G6
  evidence must remain reproducible).

**Acceptance.** A 32K-context CPU-offloaded run succeeds on this host (today
it is refused by a device-side budget); the device-KV path is unchanged; the
error messages still refuse an unbackable allocation; tests cover both paths.

### C7 — the closing record

**Work.**

1. Refresh `docs/CAPABILITIES.md` with any numbers C5/C6 change (and keep the
   ledger row 32 in sync with the final text).
2. Write the final release record: what this project is, what it does, what it
   explicitly does not do, the G0–G6 gate history, the four carry-forwards and
   their closure, the deferral note for 7G-1/7G-2/7G-3 (they live in
   `docs/NEXT_PROJECT_SEED.md` as M0/M3/M4/M6), and the pointer to the next
   project.
3. Label the repository's final state (e.g. README banner or a
   `docs/STATUS.md`): *closed — dense APU inference engine with an evidence
   discipline*.
4. Confirm the claims ledger: `--strict` passes, the baseline is empty, and
   every public claim still has its evidence pointer.

**Acceptance.** The closing record is merged on `main`; the README points at
the capability document and the next-project seed; the strict claims gate and
the canaries are green.

---

## 3. Allowed files

- `src/memory_budget.py`, `src/weight_loader.py`, `src/kv_cache.py`,
  `src/inference.py` (CLI + telemetry only),
- `tests/**`, `scripts/**` (new `scripts/ci/**` allowed),
- `.github/workflows/**` (**no push trigger** — see C4; do not weaken the
  strict claims gate),
- `README.md`, `IMPLEMENTATION_PLAN.md`, `docs/**`, `audit/**`.

**Forbidden:** kernel math; tokenizer/model-family/7D policy changes; deleting
or weakening existing tests; any change to the claims ledger that *removes* a
qualification; anything belonging to the next project (MoE, CPU compute,
speculation, expert cache); enabling the GPU push trigger.

---

## 4. Required checks

```bash
python -m pytest -m "not gpu" -q
python -m pytest -m gpu -q                        # on the gfx1150 host
python tests/test_cpu_only.py && python -O tests/test_cpu_only.py
python scripts/qa/check_claims.py
python scripts/qa/check_claims.py --strict
python scripts/qa/canary_claims.py
test ! -s audit/claims_baseline.txt

# the sdist lane (CI job "Run the shipped CPU lane in the extracted sdist tree")
python setup.py sdist --dist-dir dist
# extract, then: python -m pytest -m "not gpu and not slow" -q
```

**Interim control for the waiver:** because the required GPU check is
suspended, the GPU lane must be run **on this host** before the merge and the
result recorded in the evidence:

```bash
PYTHONPATH=build python3 -m pytest -m gpu -q     # expect: 45 passed
```

A red GPU lane blocks the merge even though CI would not.

---

## 5. Evidence contract — `audit/evidence/G7/7G-C/`

| File | Contents |
|---|---|
| `env.txt` | OS/kernel, ROCm/HIP, `rocminfo`, Python/NumPy/CMake, `git rev-parse HEAD` |
| `parent-sha.txt` / `candidate-sha.txt` | the base (PR #13 merge) and the frozen work commit |
| `diffstat.txt` | the changed files and the allowed/forbidden check |
| `c1-residency-probe.log` | the probe before/after, with the CI-runner outcome (or the documented skip) |
| `c2-runner/` | the self-repair script, the watchdog config, the **simulated** deletion-and-recovery transcript (PAT redacted), the cron decision |
| `c3-golden/` | the re-run goldens: strict result (unchanged FAIL) + decisive result, with margins |
| `c5-prompt-file.log` | the long-prompt and stdin runs, the error cases, the leak check |
| `c6-kv-budget.log` | the 32K CPU-offloaded run that used to be refused; the device-KV regression run |
| `gpu-lane.log` | the interim-control GPU lane before the merge |
| `cpu-lane.log`, `cpu-only.log`, `claims-strict.log`, `canaries.log` | the battery |
| `notes.md` | what changed, what was measured, what remains open, the closure summary |

---

## 6. QAQC adversarial checks

- Recreate the residency-probe failure conditions (dirty fixture, a failing
  `MADV_PAGEOUT`) and confirm the fix handles them; confirm the skip path (if
  used) is explicit and does not hide the RSS/PTE assertions.
- Confirm the PAT never appears in the repo, the logs, the workflow files, the
  service environment, or the process list.
- Kill the runner, delete its registration, and confirm the watchdog brings it
  back **without** human action.
- Confirm the strict claims gate still fails on an injected unqualified claim
  and on a non-empty baseline.
- Confirm the C5 prompt content never appears in the telemetry payload or the
  stderr stats.
- Confirm C6 does not change the device-KV allocation behaviour (the G0–G6
  evidence stays reproducible).

---

## 7. Stop / scope

- **Do not merge** before the auditor signs G7-C.
- Do **not** implement the GPU push trigger (decided) or any next-project work.
- Do not widen or relax a claim to make a test pass; a failing measurement is
  recorded, not explained away.
- The waiver is a **process** exception (enforcement), not a claims change:
  the evidence and the release scope are untouched.
- If a package cannot be completed, stop and record it as `BLOCKED` with the
  reason — do not silently narrow the gate.

---

## 8. Gate exit (G7-C)

- [ ] C1–C3 closed (or C4 decided and recorded).
- [ ] C5 and C6 implemented, tested and documented.
- [ ] The GPU lane green on this host (interim control) and all four CI lanes
      green where they can run.
- [ ] `--strict` claims green, baseline empty, canaries green.
- [ ] Evidence bundle complete under `audit/evidence/G7/7G-C/`.
- [ ] `docs/CAPABILITIES.md` + `docs/NEXT_PROJECT_SEED.md` + the final release
      record merged on `main`; the deferral note recorded.
- [ ] Auditor signs G7-C; the repository is labelled closed.

---

**Do not start the next project from this branch.** The next project starts
from its own repository, seeded by `docs/NEXT_PROJECT_SEED.md` (milestone M0:
the ADR on hardware target and model class).
