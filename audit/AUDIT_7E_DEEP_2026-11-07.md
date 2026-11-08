# AUDIT 7E (G5) — Stream topology & pipeline

**Auditor:** DeepSeek V4.1 Flash (primary auditor)
**Date:** 2026-11-07 · **Revised:** 2026-11-08 after the G5 rework
**Gate:** G5 (Phase 7E stream topology & pipeline)
**Target:** `wp/7E-stream-topology` @ `29d149a` (rework work `718653a`; evidence `8c0ab55`/`e823e83`; QAQC `29d149a`; initial work `7c61ea7`; parent `1604beb`)
**Brief:** `PHASE7_7E_STREAM_TOPOLOGY_BRIEF.md`; **contract:** `audit/evidence/G5/7E/README.md`
**QAQC:** `audit/QAQC_7E_DEEP_2026-11-07.md` (initial) and `audit/QAQC_7E_REWORK_2026-11-08.md` (rework)

---

## 1. Verdict

**G5: PASS — SIGNED after the rework.**

The 7E implementation is correct: explicit copy/compute streams,
`copy_done`/`compute_done` slot events, kernels on the compute stream, async
D2D KV writes, double-buffered pinned-slab staging, measured overlap, PTDS and
correctness anchors. The initial review found three blockers; all are fixed
and independently verified:

- **BLOCKER-7E-1 — CLOSED:** the guard is armed only while an exception is
  unwinding; `boundary_syncs`/`drain_syncs` are real counters. `rocprofv3`
  measures **23 syncs total, clusters [21, 1, 1]**: cold growth drains, then
  exactly one boundary sync per warm layer.
- **BLOCKER-7E-2 — CLOSED:** every growth path allocates the fresh buffer
  first and frees the old one only after success; destructor drains are
  guarded. No dangling/double-free path on allocation failure.
- **BLOCKER-7E-3 — CLOSED:** the source-contract test now scans the real
  `src/kernels` directory (6 `.hip` files, `attention.hip` asserted); CPU and
  clean-clone CI are green at `e823e83`.

---

## 2. Findings

### BLOCKER-7E-1 (Medium) — the “one sync per layer” evidence is not measuring syncs — **CLOSED in `718653a`**

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

### BLOCKER-7E-2 (Low/Medium) — free-then-malloc failure path leaves a dangling pointer — **CLOSED in `718653a`**

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

### BLOCKER-7E-3 (Medium, process) — CPU CI is red and the source-contract test is vacuous — **CLOSED in `718653a`/`e823e83`**

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

### Rework closure (2026-11-08)

- **Sync count:** `LayerGuard` arms only while `std::uncaught_exceptions()`
  changes; `boundary_syncs`/`drain_syncs` are real counters. A fresh
  `rocprofv3 --hip-trace` run reproduces **23 `hipStreamSynchronize` records,
  clusters `[21, 1, 1]`** — cold growth drains, then exactly one boundary sync
  per warm layer. `sync-count.log` and the trace test are measurement-based.
- **Allocation safety:** `realloc_buf`, `ensure_weight_slot`,
  `AttentionWorkspace::realloc_attn_buf`, and pinned-slab growth allocate the
  fresh buffer first and free the old one only after success; workspace/KV
  destructors wrap drains in try/catch.
- **CI/test:** the source-contract test scans
  `_TESTS_DIR.parent / "src" / "kernels"`, asserts the `.hip` files are found,
  and is non-vacuous. CI at `e823e83`: CPU `42435864483` **success**,
  Clean-Clone `42435864337` **success**.
- **Battery:** GPU **39 passed**, CPU **510 passed**, stream **5 passed**,
  CPU-only **12/12** both modes, claims **PASS**, canaries **12/12**, source
  scan PASS, correctness/PTDS bit-identical, stress green.
- **Scope:** rework touches only `src/kernels/attention.hip` and the two test
  files (+ evidence); forbidden areas zero-diff.

---

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

- **G5:** **SIGNED.** 7E is accepted; merge `wp/7E-stream-topology` into
  `vibe/phase7-220201`.
- **7F:** unblocked; 7F has its own G6 gate.
- **CI:** CPU/clean-clone green at `e823e83`; GPU CI remains the self-hosted
  lane (C-G1-3) and is not counted as a pass here.
- **Release/G6:** still gated by 7F and the GPU runner; 7F owns real
  throughput/benchmark evidence.
- **Branch:** `wp/7E-stream-topology` @ `29d149a` (work `718653a` + evidence
  + QAQC) is the accepted 7E branch.

---

## 5. Sign-off

**7E decision: PASS — G5 SIGNED.** All three rework blockers are closed with
independent evidence; the stream topology, double buffer, pinned slab,
overlap, PTDS, correctness, per-layer sync boundary, and claims are accepted.
No open G5 blocker remains.

**Signed:** DeepSeek V4.1 Flash, primary auditor — 2026-11-08.
