# Phase 7E Rework Brief — G5 closure (three blockers)

**To:** GLM5.3 (coder) + QAQC
**From:** DeepSeek V4.1 Flash (primary auditor)
**Date:** 2026-11-07
**Branch:** `wp/7E-stream-topology` @ `9f90e4f`
**Gate:** G5. **G5 is NOT SIGNED.** 7F remains blocked.
**Audit:** `audit/AUDIT_7E_DEEP_2026-11-07.md`
**QAQC:** `audit/QAQC_7E_DEEP_2026-11-07.md` (its SIGNED recommendation is superseded by this audit)

The explicit stream topology, double buffer, pinned slab, overlap, PTDS,
correctness, and stress work are accepted in principle. Three defects prevent
G5 closure.

---

## 1. BLOCKER-7E-1 — real sync count / guard

**File:** `src/kernels/attention.hip`.

`LayerGuard` is unconditional:

```cpp
struct LayerGuard {
    DeviceLayerWorkspace& ws;
    ~LayerGuard() { try { ws.drain(); } catch (...) {} }
} layer_guard{ws};
```

`drain()` syncs `compute_stream` and `copy_stream`. The normal path also syncs
`copy_stream` at the boundary, so a warm layer performs **3**
`hipStreamSynchronize` calls, not one. The trace field `boundary_syncs=1` is a
hardcoded literal; `sync-count.log` and
`test_7e_trace_reports_one_sync_per_layer` therefore do not measure anything.

Auditor evidence: `rocprofv3 --hip-trace` over two warm
`forward_layer_cached` calls → 26 sync records; the last 3 are the warm second
call (`audit/evidence/G5/7E/audit-probes/`).

**Fix:**

- Arm the guard only while an exception is pending (e.g. `bool armed = true;`
  then `armed = false;` after the normal cleanup; or
  `std::uncaught_exceptions()`), or remove the duplicate normal-path drain.
- Add a real counter for intended boundary syncs (increment at the one boundary
  sync; do not print a literal). Make the trace/test use it.
- Regenerate `sync-count.log` with an actual API/counter measurement. A warm
  layer must measure exactly one boundary sync; growth/exception drains stay
  separate and documented.
- Keep ledger row 15 NOT YET/qualified until the real measurement is green.

## 2. BLOCKER-7E-2 — allocation-failure double-free path

**Files:** `src/kernels/attention.hip`
(`DeviceLayerWorkspace::realloc_buf`, `ensure_weight_slot`,
`AttentionWorkspace::ensure`).

Current pattern frees first, then allocates:

```cpp
if (*ptr) HIP_CHECK(hipFree(*ptr));
HIP_CHECK(hipMalloc(ptr, needed));
```

If `hipMalloc` fails, `*ptr` is dangling and the destructor/next growth frees it
again. Allocate the new buffer first, then free/swap; or set `*ptr = nullptr`
immediately after `hipFree` and keep the cap consistent. Add a failure-path
test or a documented code-review assertion; the `LayerGuard` is created after
`ws.ensure`, so an `ensure` failure is not covered.

## 3. BLOCKER-7E-3 — red CPU CI + vacuous source-contract test

**CI:** pushed tip `9f90e4f` has CPU-Only Verification & Regression CI failure
(job `128565915609`, step “Run the pytest CPU lane”); Clean-Clone passed. Local
CPU lanes pass on 3.14 and on a clean 3.12 venv/worktree with
setuptools/pybind11/cmake (510 each), so the CI log is needed. G5 cannot sign
with red CI.

**Test bug:** `tests/test_harness_contract.py::
test_layer_path_explicit_stream_contract` scans
`_TESTS_DIR.joinpath("..", "..", "src", "kernels")`, which resolves outside the
repo; the glob is empty and the test passes vacuously. Change it to
`_TESTS_DIR.parent / "src" / "kernels"` and assert it found the five `.hip`
files. The standalone QAQC `stream_source_scan.py` is correct and stays the
scanner of record.

**Fix:** retrieve the CI failure log, identify/fix the failing test or
environment, rerun CPU + clean-clone green, and regenerate the CI evidence.

## 4. Optional / accepted

- **QAQC-7E-1 (low):** wrap the workspace/KV destructor drains in try/catch as
  the `LayerGuard` does, or document the static-destruction assumption.
- **QAQC-7E-2:** pinned-slab fallback is the live path; accepted/documented.
- **QAQC-7E-3:** overlap measured/qualified; accepted; no throughput claim.
- **QAQC-7E-4:** PTDS full-suite lane is masked by conftest; keep the dedicated
  `ptds_probe.py` with module path/sha; do not claim a full PTDS lane.
- **QAQC-7E-6:** row 15 stays NOT YET/qualified until the sync counter is real.
- `AttentionWorkspace::ensure` NULL-stream sync is legacy host-wrapper only;
  accepted as long as the layer path remains explicit-stream.

## 5. Required checks / stop-gate

```bash
python -m pytest -m gpu -q
python -m pytest -m "not gpu" -q
python -m pytest tests/test_stream_topology.py -q
python tests/test_cpu_only.py && python -O tests/test_cpu_only.py
python scripts/qa/check_claims.py
python scripts/qa/canary_claims.py
python audit/evidence/G5/7E/qaqc-probes/stream_source_scan.py .
# real sync count: rocprofv3 or an in-code counter; warm layer must be 1
# allocation-failure path: review/unit test
# CI: CPU + clean-clone green (retrieve/fix the 9f90e4f failure)
```

Update `audit/evidence/G5/7E/` (`sync-count.log`, `notes.md`,
`candidate-sha.txt`, a `rework-*.log`) and the trace/test. Then stop for QAQC;
QAQC re-runs the probes and CI; the auditor re-reviews and signs G5.

## 6. Stop / scope

- Do not start 7F; do not merge `wp/7E-stream-topology`.
- Do not claim one sync/token or throughput.
- Do not change kernel math, tokenizer/model, 7D memory policy, bindings public
  API, or CI workflows beyond the test/PTDS option.
- Keep the 7E scope: stream topology, staging, sync-before-free, claims.
