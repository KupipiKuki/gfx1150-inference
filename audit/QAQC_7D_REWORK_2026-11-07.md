# QAQC rework review — Phase 7D (Gate G4) after the two Low fixes

> **Scope:** adversarial QAQC of branch `wp/7D-memory-robustness` at tip `a4ad1de`
> (rework work commit `a380003`, evidence commit `a4ad1de`; auditor base `1ad01c9`,
> brief base `003f4e5`). **No existing files were modified by this review** — this
> report and `audit/evidence/G4/7D/qaqc-probes/qaqc-rework-run.log` are the only
> additions.
> **Method:** full battery re-run on this gfx1150 host (ROCm loaded, extension
> prebuilt, so the gpu lane is real), both claims tools re-run, the bundle's
> `qaqc-probes/*.py` re-run (exit 0), plus independent probes of the two rework
> fixes written outside the repo test suite (raw output:
> `qaqc-probes/qaqc-rework-run.log`).
> **Status legend:** ✅ verified · ◐ note · ❌ open

---

## 1. Re-run results at tip `a4ad1de`

| Check | Result |
|---|---|
| `pytest -m "not gpu" -q` | ✅ 506 passed, 34 deselected |
| `pytest -m gpu -q` | ✅ 34 passed, 506 deselected (real hardware) |
| `tests/test_cpu_only.py` / `python -O` | ✅ OK / OK (12 tests each, incl. sdist/py-modules with `memory_budget`) |
| `scripts/qa/check_claims.py` | ✅ PASS — 0 new violations, 8 baselined, 0 expired, 0 findings |
| `scripts/qa/canary_claims.py` | ✅ PASS — all 12 canaries detected; baseline holds exactly 6 entries = `EXPECTED_BASELINE_ENTRIES` |
| `qaqc-probes/mem_probes.py`, `kv_probes.py` | ✅ both exit 0 |
| evidence bundle vs `G4/7D/README.md` contract | ✅ all contract files present (env, parent/candidate sha, diffstat, red/green, eviction, residency, kv-hardening, leak, exception, compat-memory, cpu/gpu lanes, cpu-only, claims, canary, notes) plus rework logs and `qaqc-probes/`; `candidate-sha.txt` = `a3800032623e...` = the rework commit |
| changed-file scope vs brief §2 | ✅ `003f4e5..HEAD` touches only allowed files; `src/gguf_parser.py`, `src/tokenizer.py`, `src/model_spec.py`, `src/kernels/**`, `src/python_bindings/**`, `CMakeLists.txt`, `.github/**` all empty diffs; rework commit `1ad01c9..a380003` touches only `src/weight_loader.py`, `src/inference.py`, `tests/test_memory_residency.py`; `a380003..a4ad1de` touches only evidence files |

## 2. Rework fixes verified independently (not via the repo suite)

Raw output in `qaqc-probes/qaqc-rework-run.log`.

- **Fix 1 (QAQC-7D-1, negative `block_count`)** — ✅ verified:
  - `llama.block_count = INT32(-1)`, zero `blk.*` tensors →
    `ValueError: Invalid llama.block_count -1: must be >= 0` (was: accepted, `num_layers = -1`).
  - `INT32(-1)` with one `blk.0.*` tensor → same explicit guard fires.
  - Regressions: `block_count=2` with 2 layers still loads (`num_layers == 2`);
    `block_count=999` over 2 layers still rejected with the concise
    declared-vs-found/min/max message.
  - Location: `src/weight_loader.py` `_cross_check_block_count`; tests in
    `tests/test_memory_residency.py` (`test_block_count_negative_with_zero_tensors_rejected`,
    `..._with_tensors_rejected`).
- **Fix 2 (engine no-source AUTO)** — ✅ verified: with
  `read_budget_sources` forced to an empty `BudgetSources()`,
  `LlamaInferenceEngine(residency="auto")` emits `NoBudgetFallbackWarning`,
  resolves to `effective=stream`, `weight_budget=None`,
  reason `'AUTO without a budget: no readable source; failed safe to STREAM'`
  (was: `weight_budget=0`, reason "exceed the budget (0)", no warning).
  Location: `src/inference.py::_apply_residency_policy`; engine-level test
  `test_engine_auto_without_sources_warns_and_streams`.
- **Red/green honesty of the rework:** `rework-red.log` shows the three new tests
  failing at the pre-fix tip (`1ad01c9` + test file) for exactly the audited
  reasons (`DID NOT RAISE ValueError`, `DID NOT WARN NoBudgetFallbackWarning`);
  `rework-green.log` shows 42/42 in the 7D suite plus the full battery at `a380003`.

## 3. Brief §5 adversarial checklist — all items re-verified

fadvise/PAGEOUT called in STREAM and not in PIN (syscall-counted) ✅; missing
syscalls warn and never crash ✅; AUTO pin-fits/streams-over-budget, explicit
PIN/STREAM honored, no silent fallback ✅; measured RSS/page-cache difference
PIN (+65.5 MB, warm majflt=0) vs STREAM (dRSS 0, evicted re-touch majflt>0) with
GTT recorded but never claimed as pinned (no device weight cache) ✅;
block_count 999-vs-2 concise, duplicates, alignment=0, truncation, huge dims all
fail closed ✅; cgroup-limited (real `systemd-run MemoryMax=256M`), full-disk,
symlink KV cases refuse cleanly, no file survives crash-before-close ✅; live-view
close warns + fd closed, ctor original error preserved ✅; 1,100×/1,000× leak
probe: fd delta ≤ 1, map delta constant ✅; claims/canaries green, baseline 6,
docs match code, no false bounded-RAM/70B/8-hour/Active-RAM entries ✅.

## 4. Findings

| ID | Severity | Finding |
|---|---|---|
| QAQC-7D-R1 | ❌→✅ closed | QAQC-7D-1 (negative `block_count`) — fixed and independently verified (see §2). |
| QAQC-7D-R2 | ❌→✅ closed | Rework fix 2 (no-source AUTO budget provenance/warning) — fixed and independently verified. |
| QAQC-7D-R3 | ◐ note | `README.md:129` says "ultra-long-context **70B runs**" as the purpose of the KV-offload mode. This is a mode-purpose description, not a measured claim; no ledger row scans the bare literal `70B` (row 18 scans `7B–70B`, row 14 `bounded memory` is REMOVED), and the checker passes. Optional tightening at the next docs touch; not a violation. |
| QAQC-7D-R4 | ◐ note | Ledger rows 10–12 prose still cite pre-7D README line numbers while their scope sites point at the current ones (checker reports this as drift warnings only on line moves; currently 0 drift warnings). Pre-existing, flagged in the rework brief §4 as refresh-at-next-docs-touch; the rework deliberately did not touch README/PLAN so no new drift was introduced. |
| QAQC-7D-R5 | ◐ note | `check_claims.py --strict` still fails on the 8 remaining baselined unqualified occurrences (rows 6/13/26–29) — that is the G6 ratchet by design, not a 7D item. |
| QAQC-7D-R6 | ◐ note | Untracked `7c/` directory at the repo root predates this branch (present at session start); not committed by 7D; left untouched. |
| QAQC-7D-R7 | ◐ note | QAQC-7D-3 (MADV_DONTNEED as PTE-drop enabler before fadvise) is adjudicated **accepted** by the auditor and recorded in `notes.md`; mechanism unchanged; docs/ledger present it as an enabler, never as page-cache eviction. |

No new defects found. No open ❌ items remain.

## 5. Verdict recommendation

**Recommend G4 SIGNED.** Both NOT-SIGNED blockers are fixed, independently
reproduced, red/green-logged, and the full battery (CPU 506, GPU 34, CPU-only both
modes, claims PASS, canaries 12/12, bundle probes exit 0) is green at tip `a4ad1de`.
Scope is clean against brief §2; claims/baseline count unchanged (6). 7E remains
blocked until the auditor merges; 70B/8-hour/benchmark evidence stays with 7F-2/7F-3/7F-4.
