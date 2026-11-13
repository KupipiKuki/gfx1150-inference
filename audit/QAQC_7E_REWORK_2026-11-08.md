# QAQC rework review — Phase 7E (Gate G5) after the three blockers

> **Scope:** adversarial QAQC of branch `wp/7E-stream-topology` at tip `e823e83`
> (rework work commit `718653a`, evidence `8c0ab55` + `e823e83`; auditor base
> `3cb3007` / rework brief `PHASE7_7E_REWORK_BRIEF.md`). **This review changed no
> code**: it adds only this report and `audit/evidence/G5/7E/qaqc-probes/qaqc-rework-run.log`.
> **Method:** full battery re-run on the real gfx1150 host; each blocker
> re-verified independently (fresh rocprofv3 measurement, diff review of the
> rework hunks, source-scan, correctness/PTDS probes); CI state queried from
> the GitHub Actions API at the tip.
> **Status legend:** ✅ verified · ◐ note · ❌ open

---

## 1. Re-run results at tip `e823e83`

| Check | Result |
|---|---|
| `pytest -m gpu -q` (real GPU) | ✅ 39 passed, 510 deselected |
| `pytest -m "not gpu" -q` | ✅ 510 passed, 39 deselected |
| `tests/test_cpu_only.py` / `-O` | ✅ OK / OK |
| `check_claims.py` / `canary_claims.py` | ✅ PASS / PASS (12/12); baseline still 6, row 15 still NOT YET/qualified |
| CI at tip `e823e83` (Actions API) | ✅ CPU-Only Verification & Regression CI **success** (incl. the previously-red "Run the pytest CPU lane" step, now with the fixed non-vacuous contract test and the new measured-sync test) and Clean-Clone Build CI **success** |
| `stream_source_scan.py` | ✅ PASS; 0 `hipStreamWaitEvent(0, ...)` in `src/` |
| correctness anchors | ✅ bit-identical to parent (prefill `a8547f8c…4e2b31`, decode `49da87df…400464`, greedy IDs `[27, 31, 27, 31, 17, 27, 4, 24]`) on both the normal and the PTDS module |
| PTDS probe | ✅ module digest verified, non-main-thread stress OK |
| changed-file scope `3cb3007..e823e83` | ✅ only `src/kernels/attention.hip`, `tests/test_harness_contract.py`, `tests/test_stream_topology.py`, and `audit/evidence/G5/7E/**`; everything else zero-diff |

## 2. Blocker-by-blocker verification

- **BLOCKER-7E-1 (real sync count/guard)** — ✅ **fixed and re-measured**:
  `LayerGuard` now arms only while an exception is unwinding
  (`std::uncaught_exceptions()` captured at construction, re-checked in the
  destructor; destructor is `noexcept` with try/catch). `boundary_syncs` and
  `drain_syncs` are real counters incremented at the actual
  `hipStreamSynchronize` sites, reset per layer *before* `ensure()` so
  cold-layer growth drains count. Fresh `rocprofv3 --hip-trace` re-run
  reproduces the bundle's numbers exactly: **23 syncs total, per-call clusters
  [21, 1, 1]** (cold = growth drains, warm calls = exactly 1 boundary sync).
  The rewritten test asserts measured values (`boundary_syncs == 1` every
  layer; warm layer `(1, 0)`) and passes. `sync-count.log` no longer contains
  a hardcoded literal.
- **BLOCKER-7E-2 (allocation-failure double-free)** — ✅ **fixed by review**:
  `realloc_buf`, `ensure_weight_slot`, `AttentionWorkspace::ensure`
  (new `realloc_attn_buf`), and the pinned-slab growth all allocate the fresh
  buffer first and free the old one only after success; on failure the old
  buffer stays valid and owned. Growth drains are preserved. No injectable
  failure-path unit test without kernel changes — documented assertion in
  `rework-green.log`; the enqueue-side failure is covered by the
  exception-after-enqueue test (green).
- **BLOCKER-7E-3 (red CI + vacuous test)** — ✅ **fixed**: the contract test
  now scans `_TESTS_DIR.parent / "src" / "kernels"` (resolves inside the repo,
  6 `.hip` files found, `attention.hip` asserted present) and passes for real.
  CI: the red run at `9f90e4f` (job 128565915609) did not reproduce on
  `3cb3007` (both jobs green; raw log needs admin rights — 403 documented),
  and the rework push at `8c0ab55`/`e823e83` is green on both workflows.
- **QAQC-7E-1 (accepted hardening)** — ✅ both static workspace destructors
  (`~DeviceLayerWorkspace`, `~DeviceKVCachePool`) wrap their drains in
  try/catch now.

## 3. Findings

| ID | Severity | Finding |
|---|---|---|
| QAQC-7E-R1 | ✅ closed | BLOCKER-7E-1 — armed guard + real counters; rocprof re-run [21, 1, 1]; test asserts measurements |
| QAQC-7E-R2 | ✅ closed | BLOCKER-7E-2 — alloc-first-then-free on all growth paths; review-asserted (failure not injectable) |
| QAQC-7E-R3 | ✅ closed | BLOCKER-7E-3 — contract test scans the real kernel dir (6 files, asserted); CI green at the tip on both workflows |
| QAQC-7E-R4 | ◐ note | The cold (first) call's growth drains (21 rocprof syncs / `drain_syncs=22` in the engine fixture) are real and now honestly counted; they are one-off per process and documented as such. Warm steady state is exactly 1 sync per layer call. |
| QAQC-7E-R5 | ◐ note | Untracked local dirs remain as documented: `build-ptds/` (PTDS test build) and pre-existing `7c/`. |
| QAQC-7E-R6 | ◐ note | Overlap qualification unchanged and honest (measured only on the larger prefill shapes; no throughput claim); slab fallback remains the live pinned path (32B-aligned tensor views), documented. |
| QAQC-7E-R7 | ◐ note | The raw text of the failed CI job could not be retrieved without admin API rights; the red is evidenced by the run/job IDs + the two subsequent green runs, and superseded by the green rework push. |

No ❌ open defects. Ledger row 15 remains NOT YET with the measured one-sync-per-layer (N per token) boundary; no one-sync/token or throughput claim anywhere.

## 4. Verdict recommendation

**Recommend G5 SIGNED.** All three blockers are closed with independent,
reproducible evidence (fresh rocprof [21, 1, 1] re-run, diff-reviewed
alloc-first hunks, real-scan contract test, green CI at the pushed tip),
the full battery is green on hardware and CPU-only, correctness is
bit-identical to the parent, and the evidence bundle is complete. 7F remains
gated on the auditor's merge.
