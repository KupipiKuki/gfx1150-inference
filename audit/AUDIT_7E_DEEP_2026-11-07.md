# AUDIT 7E (G5) — Stream topology & pipeline

**Auditor:** DeepSeek V4.1 Flash (primary auditor)
**Date:** 2026-11-07
**Gate:** G5 (Phase 7E stream topology & pipeline)
**Target:** `wp/7E-stream-topology` @ `9f90e4f` (work `7c61ea7`; evidence `98b08c5`; QAQC `9f90e4f`; parent `1604beb`)
**Brief:** `PHASE7_7E_STREAM_TOPOLOGY_BRIEF.md`; **contract:** `audit/evidence/G5/7E/README.md`
**QAQC:** `audit/QAQC_7E_DEEP_2026-11-07.md`

---

## 1. Verdict

**G5: NOT SIGNED — rework required.**

The 7E implementation is substantively strong: explicit copy/compute streams,
`copy_done`/`compute_done` slot events, kernels on the compute stream, async
D2D KV writes, double-buffered pinned-slab staging, measured overlap, PTDS and
correctness anchors. However, the **sync-count claim/evidence is wrong**, the
**CPU CI is red**, and there is a **failure-path allocation bug**. The QAQC
report recommends signoff but missed the first and third items.

---

## 2. Findings

### BLOCKER-7E-1 (Medium) — the “one sync per layer” evidence is not measuring syncs

`launch_forward_layer_cached_fp16` creates a `LayerGuard` whose destructor is
**unconditional**:

```cpp
struct LayerGuard {
    DeviceLayerWorkspace& ws;
    ~LayerGuard() { try { ws.drain(); } catch (...) {} }
} layer_guard{ws};
```

`drain()` calls `hipStreamSynchronize(compute_stream)` and
`hipStreamSynchronize(copy_stream)`. The normal path also calls
`hipStreamSynchronize(ws.copy_stream)` at line 1019. Therefore a **warm** layer
call performs **three** stream synchronizations, not one:
- one boundary sync (line 1019),
- compute + copy syncs in the `LayerGuard` destructor (lines 566–567).

The trace field `boundary_syncs=1` is a **hardcoded literal** in
`print_layer_trace`; it is not a counter. `tests/test_stream_topology.py::
test_7e_trace_reports_one_sync_per_layer` asserts that hardcoded string, and
`sync-count.log` describes lines 566–567 as “growth, exception guard,
destructor” — but the guard runs on every normal return, not only on exceptions.

**Auditor probe:** `rocprofv3 --hip-trace` over two warm
`matmul_module.forward_layer_cached` calls recorded **26**
`hipStreamSynchronize` API calls total; the last **3** are the second (warm)
layer call. See `audit/evidence/G5/7E/audit-probes/` (`sync-count-audit.log`,
`two_layer.py`, `rocprof-two_hip_api_trace.csv`).

This fails the G5 exit “per-layer sync boundary measured/documented” and makes
ledger row 15’s “one sync per layer” claim unsupported. The overlap
measurements themselves (copy/kernel windows) are still valid; the extra guard
syncs are unmeasured overhead.

**Required fix:** arm the guard only while an exception is pending (e.g. a
`bool armed = true;` cleared after the normal cleanup, or
`std::uncaught_exceptions()`), or remove the duplicate normal-path drain.
Add a **real counter** for intended boundary syncs (increment at line 1019; do
not print a literal), make the trace/test use it, and regenerate
`sync-count.log` with an actual API count (rocprof or the counter). The normal
warm layer must measure exactly one boundary sync; the exception/growth drains
remain separate and documented.

### BLOCKER-7E-2 (Low/Medium) — free-then-malloc failure path leaves a dangling pointer

`DeviceLayerWorkspace::realloc_buf` (and `ensure_weight_slot`, and
`AttentionWorkspace::ensure`) use:

```cpp
if (*ptr) HIP_CHECK(hipFree(*ptr));
HIP_CHECK(hipMalloc(ptr, needed));
```

If `hipFree` succeeds and `hipMalloc` fails (OOM), `*ptr` remains a dangling
pointer; the destructor/next growth frees it again. The `LayerGuard` is created
**after** `ws.ensure()`, so an `ensure` failure is not covered by the guard.
The 7E-3 stress tests cover exception-after-enqueue, not allocation failure.

**Required fix:** allocate the replacement first, then free the old pointer and
swap; or set `*ptr = nullptr` immediately after `hipFree` (and keep the cap
consistent) so a failed allocation cannot double-free. Apply to
`realloc_buf`, `ensure_weight_slot`, and `AttentionWorkspace::ensure`; add a
failure-path test or a documented code-review assertion.

### BLOCKER-7E-3 (Medium, process) — CPU CI is red and the source-contract test is vacuous

The pushed tip `9f90e4f` has **CPU-Only Verification & Regression CI failure**
(job `128565915609`, step “Run the pytest CPU lane”); Clean-Clone passed. The
QAQC report recommends SIGNED but did not push/verify CI. Local CPU lanes pass:
Linux/Python 3.14 (510 passed) and a clean Python 3.12 venv/worktree with
setuptools/pybind11/cmake (510 passed), so the failure needs the CI log; the
branch is not signable while its CPU job is red.

Independent test gap: `tests/test_harness_contract.py::
test_layer_path_explicit_stream_contract` scans
`_TESTS_DIR.joinpath("..", "..", "src", "kernels")`, which resolves **outside
the repository** (`repo/tests/../../src/kernels`). The glob is empty, so the
test passes vacuously. The QAQC’s standalone `stream_source_scan.py` uses the
correct path and passes, but the harness test is not the evidence it claims to
be.

**Required fix:** change the path to `_TESTS_DIR.parent / "src" / "kernels"`,
confirm the test actually scans the five `.hip` files, retrieve the CI failure
log, fix the failing test/environment, and re-run CPU/clean-clone CI green.

### QFs / notes

- **QAQC-7E-1 (low):** `~DeviceLayerWorkspace()`/`~DeviceKVCachePool()` call
  throwing `drain()`/`release()` unguarded; wrap in try/catch as the
  `LayerGuard` does, or document the static-destruction assumption. Fold into
  the 7E-2 cleanup fix if convenient.
- **QAQC-7E-2 (accepted):** the pinned-slab fallback is the live path because
  streamed views are 32-byte aligned, not page-aligned; documented honestly.
- **QAQC-7E-3 (accepted):** overlap is measured and qualified to the synthetic
  prefill shapes; no throughput claim.
- **QAQC-7E-4 (note):** `PYTHONPATH=build-ptds pytest` is masked by the conftest
  prepending `./build`; the dedicated `ptds_probe.py` with module path/sha is
  the valid PTDS evidence. Document this and avoid claiming a full-suite PTDS
  lane.
- **QAQC-7E-6:** row 15 should stay NOT YET/qualified; after the sync-counter
  fix it may say “one boundary sync/layer, N/token” only with a real
  measurement.
- **`AttentionWorkspace::ensure`** uses `hipStreamSynchronize(nullptr)` on the
  legacy host-wrapper path; that is outside the layer pipeline and acceptable
  as long as the layer path stays explicit-stream (it does).
- **No code changes in this audit.** The QAQC report, the evidence bundle and
  the work commit are otherwise complete.

---

## 3. What passed

| Check | Result |
|---|---|
| GPU lane | **39 passed** (34 + 5 stream tests) |
| CPU lane (local 3.14 / clean 3.12) | **510 passed** each |
| `test_stream_topology.py` | **5 passed** |
| Claims checker / canaries | **PASS** / **12/12** |
| `test_cpu_only` + `-O` | **OK / OK** |
| Source scan (`stream_source_scan.py`) | **PASS** — no `hipStreamWaitEvent(0)`, explicit stream tokens, async D2D KV |
| Correctness anchors | prefill/decode digests and greedy IDs bit-identical to parent |
| Event graph | copy/compute streams, slot events, pinned slab, layer boundary; no per-projection sync |
| Overlap | measured 1.28 ms (11.2%) seq=32 and 5.03 ms (18.1%) seq=256 on the 118 MiB synthetic prefill model; qualified |
| PTDS | dedicated build/probe bit-identical; source/contract evidence |
| Stress | repeated/varying seq, forced growth/reuse, exception-after-enqueue, non-main-thread |
| Scope / forbidden set | kernel stream plumbing only (no math), CMake test option, tests/evidence; zero diff in bindings/tokenizer/model/7D/CI |

---

## 4. Gate impact

- **G5:** **NOT SIGNED.** 7E stays in rework; do not merge
  `wp/7E-stream-topology`.
- **7F:** blocked until G5 signs.
- **CI:** red on the pushed candidate; must be green before re-signoff.
- **Release/G6:** unchanged; 7F owns real throughput/benchmark evidence.
- **Branch:** the coder/QAQC should fix the three blockers, update the evidence,
  and stop for re-review.

---

## 5. Sign-off

**7E decision: NOT SIGNED — rework required.** The stream topology itself is
largely correct; the sync-count claim/evidence, the allocation-failure path,
and the red CPU CI (plus the vacuous source-contract test) prevent G5 closure.

**Signed:** DeepSeek V4.1 Flash, primary auditor — 2026-11-07.
