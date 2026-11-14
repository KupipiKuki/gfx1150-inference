# 7G-C closure notes — what changed, what was measured, what remains open

**Branch:** `wp/7G-C-closure` **Parent:** `36c54b095897a5b169f664626593a71606e30823`
(PR #13 merge) **Candidate:** `cac3eeddc02164fcb98e654c24b4b8aa27d6a05c`
**Date:** 2026-11-13. Host: gfx1150 runner host (Linux Mint 22.3, kernel
7.0.0-42, ROCm/HIP 7.16.26385, Python 3.14.10). See `env.txt`.

## What changed

| WP | Change | Tests / evidence |
|---|---|---|
| C1 | `tests/test_memory_residency.py::_build_layer_model` flush+fsyncs the synthetic fixture; `src/weight_loader.py::_evict_spans` falls back to `MADV_DONTNEED` when `MADV_PAGEOUT` raises (previously only when absent); new `test_failing_pageout_falls_back_to_dontneed` drives the failing-PAGEOUT path through an mmap proxy | `c1-residency-probe.log` — probe 3x passed locally, `refault_majflt=1 > 0`, **no skip path used**; the QAQC-adversarial recomputations (dirty fixture, failing PAGEOUT) are exactly the two new/changed test lanes |
| C2 | `scripts/ci/ensure_runner_registered.sh` (PAT via fd; root-only file; `--check` mode; alert contract `RUNNER-REGISTRATION-OFFLINE`; never echoes PAT/token) + systemd `gfx1150-runner-watchdog.{service,timer}` + `-alert.service` + deployment README; nightly cron 03:00 → 04:00 UTC | `c2-runner/` — both script paths functionally exercised with fake systemctl/journalctl; **live deletion-and-recovery simulation is owner-pending** (`c2-runner/SIMULATION-TRANSCRIPT-OWNER-PENDING.md`); cron decision: `c2-runner/DECISIONS.md` |
| C3 | Decisive-walk refinement in `scripts/qa/real_gguf_golden.py` (fork = first token MISMATCH; `MIN_DECISIVE_STEPS = 2`; threshold untouched at 1.0) + two pre-registered new prompts | `c3-golden/` — strict 16-step FAILs recorded **verbatim** on all five runs; decisive 4 PASS / 1 INCONCLUSIVE; both walks (orig + refined) archived; ref artifacts committed with sha256 |
| C4 | **Decision recorded, no code:** no GPU push trigger; workflow triggers unchanged; waiver addendum in `audit/G6_ENFORCEMENT_WAIVER_2026-11-13.md` | `c2-runner/DECISIONS.md` (enforcement section) |
| C5 | `src/inference.py` CLI: `--prompt-file`, `--prompt -`; `_read_prompt_source` (mutual exclusion, clean single-line errors, no traceback); legacy default prompt kept when no source is given (documented design note); never printed into telemetry/stats | `c5-prompt-file.log` — 46080-byte prompt generation, stdin run, five failure modes at exit 2 without traceback, sentinel leak scan clean; 9 unit tests in `tests/test_cli_prompt_source.py` |
| C6 | `src/kv_cache.py::_effective_kv_budget`: CPU-offloaded pool drops `gtt_sysfs`; mmap pool adds `mmap_disk_free` via `_mmap_dir_free_bytes` (nearest existing ancestor walk); device-resident pool unchanged | `c6-kv-budget.log` — parent REFUSED vs candidate ACCEPTED under simulated 64 MiB GTT; real 32K `--offload-kv-cpu` CLI run accepted; device pool kept GTT-bounded (test + CLI run) |
| C7 | `docs/RELEASE_RECORD.md` (closing record), `docs/STATUS.md` (closed label), README banner/pointers, `CAPABILITIES.md` refreshed; ledger rows 5/6/31 re-adjudication, scope line refs re-verified | `claims-strict.log`, `canaries.log` |

Commits, in order: `7bae2f8` (C3 pre-registration) → `1943af6` (C3 walk
refinement code) → `d129eba` (C5/C6/C3 docs + ledger) → `c0cd063` (C2 +
C3 evidence) → `4377d69` (C4 addendum + C7 closing record + ledger scope
refresh) → `cac3eed` (test-lane registration + real assertion).

## What was measured (the battery, all at the frozen candidate)

| check | result |
|---|---|
| `python -m pytest -m "not gpu" -q` | **547 passed**, 45 deselected |
| `python -m pytest -m gpu -q` (PYTHONPATH=build, on host) | **45 passed**, 547 deselected |
| `python tests/test_cpu_only.py` and `python -O ...` | 12 tests OK, both |
| `check_claims.py` (default) | PASS, 0 findings |
| `check_claims.py --strict` | PASS, 0 unqualified |
| baseline `audit/claims_baseline.txt` | **empty** |
| `canary_claims.py` | **16/16** PASS |
| sdist lane (extract, `not gpu and not slow`) | **543 passed**, 49 deselected |

## QAQC adversarial spot-checks (from the brief §6)

- The C1 recomputations are implemented as permanent tests
  (`test_failing_pageout_falls_back_to_dontneed`, dirty-fixture via fsync),
  not one-offs; no skip path taken.
- PAT search: the PAT exists nowhere in the repo (it was never provided to
  the coder); the script reads it from a root-only fd; the workflow files and
  c2 evidence contain no credential; the transcript record explicitly
  redacts PAT/token.
- C5 leak check: sentinel string scanned over stdout + stderr (telemetry and
  stats payloads included) — no hits (`c5-prompt-file.log`, case 4).
- C6 device-KV: `test_kv_device_pool_budget_unchanged` passes; the device
  CLI run still reports the GTT-bounded device budget; G0–G6 evidence shape
  unchanged (same budget formula for `offload_to_CPU=False, mmap_dir=None`).

## What remains open (recorded per brief §7, no gates silently narrowed)

1. **C2 live simulation — owner-pending (the only open item).** Needs the
   owner-created PAT; procedure in `c2-runner/SIMULATION-TRANSCRIPT-OWNER-PENDING.md`.
   Until it lands the watchdog units are authored-but-not-deployed and the
   waiver stays in force.
2. **C1 GitHub-hosted rerun.** Acceptance asks for two consecutive passes on
   the GitHub-hosted runner; the runner is currently offline (C2 deletion),
   so the CI-runner outcome is **pending**: the C1 fix is proven locally 3x
   on this host and lands in the next scheduled GPU PR run (cron 04:00 UTC).
3. C3's one INCONCLUSIVE re-adjudication (`readj-q4km-prompt2`) remains
   INCONCLUSIVE by design — 1 decisive step is below the pre-registered
   minimum of 2; never counted as a pass anywhere.

## Closure summary

All four carried-forward defects are closed (C1, C2 with one owner-pending
simulation, C3) or formally decided (C4). The two measured-workload needs
(C5, C6) are implemented, tested and documented. The closing record
(`docs/RELEASE_RECORD.md`), the closed label (`docs/STATUS.md`) and the
capability/next-project pointers are in place. Nothing G0–G6 signed was
weakened; every public claim still carries its evidence pointer; the strict
claims gate and the canaries are green and the baseline is empty. The
project is ready for the auditor's G7-C signature and the merge to `main`.

---

**Self-reference note (added with the bundle commit):** the only commit after
the frozen candidate `cac3eed` is the evidence bundle itself (this commit),
which touches `audit/evidence/G7/7G-C/**` only (no source, tests, docs or
workflow files). Its SHA is not written into the file it is part of; take it
from `git log`. All battery measurements in this bundle were captured with
the working tree at exactly `cac3eed`.
