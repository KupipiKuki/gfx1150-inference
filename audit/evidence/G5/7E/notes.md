# 7E notes — design, event-graph rationale, measurements, limitations, provenance

**Package:** 7E Stream Topology & Pipeline (Gate G5)
**Branch:** `wp/7E-stream-topology`; brief `PHASE7_7E_STREAM_TOPOLOGY_BRIEF.md`
**Parent (brief base):** `1604beb` — **Candidate work commit:** `7c61ea7`
**Evidence contract:** `audit/evidence/G5/7E/README.md`

## Design decisions and why

1. **Explicit copy/compute streams with a per-slot event graph** (7E-1).
   `DeviceLayerWorkspace` owns `copy_stream` and `compute_stream`;
   `copy_done[2]`/`compute_done[2]` guard the double-buffered weight slots,
   plus `inputs_done`, `ffn_norm_done` (staging) and `norm_consumed`,
   `layer_out_ready` (consumption) events; see `event-graph.md` for the full
   dependency list. All NULL-stream semantics are gone: kernels launch on
   the compute stream via a `hipStream_t` parameter added to every
   `launch_*_device` helper (headers keep an identical `hipStream_t` typedef
   so `bindings.cpp`, which builds as plain CXX, still compiles — no binding
   or Python-visible signature changed). The D2D KV writes in
   `launch_gqa_attention_cached_fp16_device` are `hipMemcpyAsync` on the
   compute stream (same-stream ordered with the attention kernel). The final
   D2H waits on `layer_out_ready` — never on the copy stream as a proxy — and
   `hipStreamSynchronize(copy_stream)` is the single layer-boundary sync.
2. **Double buffer + pinned staging** (7E-2). Projections q,k,v,o,gate,up,down
   alternate two device slots; the copy stream waits `compute_done[slot]`
   before overwriting and the compute stream waits `copy_done[slot]` before
   consuming, so a copy never races its slot's previous kernel. Host staging
   prefers `hipHostRegister` on page-aligned weight spans; in practice the
   streamed tensor views are 32-byte aligned (GGUF `general.alignment`), not
   page aligned, so the registered path is mostly theoretical on this engine
   — the live path is a per-slot `hipHostMalloc` slab whose CPU `memcpy`
   overlaps the compute stream's previous kernel and whose reuse waits on
   its own previous `copy_done[slot]` (no CPU/GPU race on the slab). The
   first projection's copy has nothing to overlap (documented). Registration
   is paired: spans are unregistered at layer end after the boundary sync,
   and the RAII layer guard unregisters (after draining) on exceptions, so no
   registration outlives the call that made it.
3. **Sync-before-free, destructor drain, exception guard** (7E-3). All
   growth paths (`ensure`, `ensure_weight_slot`, `AttentionWorkspace::ensure`)
   drain before `hipFree`; the workspace destructor drains before destroying
   buffers, events, then streams; `DeviceKVCachePool::release()` performs a
   device sync because its D2D writes now land on the compute stream; a
   `LayerGuard` RAII in the layer function drains + unregisters on any
   exception after enqueue (the exception-after-enqueue test proves the
   workspace survives bit-exactly).
4. **Measured, not asserted** (7E-2/7E-4). `GFX1150_STREAM_TRACE=1` adds
   timing events only in trace mode and prints per-layer copy/compute
   windows plus overlap. Measurements: larger F16 prefill model
   (hidden 2048/inter 8192): overlap 1.28 ms (11.2% of layer kernel time) at
   seq=32 and 5.03 ms (18.1%) at seq=256; small in-suite fixture
   (hidden 256): microsecond kernels, ~0.06 ms absolute overlap — no
   meaningful claim for such shapes. The overlap claim is qualified exactly
   to the shapes where it was measured; no throughput claim anywhere
   (7F-3 owns benchmarks).
5. **Per-layer boundary honesty.** The Python `forward_layer_cached` API
   returns host hidden states per layer, so the G5 boundary is **one sync per
   layer (N per token)** — recorded in `sync-count.log` with the source
   enumeration (7 `hipStreamSynchronize` sites total in `attention.hip`: 4
   host-workspace realloc drains + the 2-line `drain()` + exactly 1
   steady-state boundary sync). Ledger row 15 stays **NOT YET** with this
   qualification; a one-sync/token claim would need a separately approved
   multi-layer API change.
6. **Per-thread default-stream validation.** New CMake option
   `GFX1150_7E_PTDS_TEST` builds the module with
   `HIP_API_PER_THREAD_DEFAULT_STREAM=1` (test-only, no packaging change).
   The PTDS module (verified by path) produces bit-identical digest outputs
   and passes sequential non-main-thread engine loops (`per-thread.log`),
   plus the full gpu lane. `build-ptds/` is a local test build directory and
   intentionally not committed (also not gitignored — noted here; no
   `.gitignore` change was in the 7E allowed-file set).

## Measurements on this host

- `overlap.log`: trace windows; `sync-count.log`: one boundary sync per
  layer call (trace test: 4 layer summaries, all `boundary_syncs=1`).
- `correctness.log`: parent (1604beb) vs candidate (7c61ea7) prefill logits
  sha256 `a8547f8c…4e2b31`, decode logits sha256 `49da87df…400464`, greedy
  IDs `[27, 31, 27, 31, 17, 27, 4, 24]` — bit-identical (no tolerance
  needed). Anchors locked in `tests/test_stream_topology.py`.

## What is NOT claimed / deferred

- No one-sync-per-token claim (per-layer boundary documented; row 15 NOT YET).
- No throughput/benchmark claims; overlap % is of layer kernel time on
  synthetic F16 prefill shapes only — 7F-3 owns real model benchmarks.
- hipHostRegister not effective on 32-byte-aligned streamed tensor views;
  the pinned-slab fallback is the live staging path and is the honest
  mechanism documented in README/PLAN wording changes (PLAN only; README
  makes no sync/overlap assertion and was not touched).
- 7C/7D packages untouched: tokenizer/model-spec, kv_cache/weight_loader/
  memory_budget, bindings.cpp, CI — all zero-diff (see `diffstat.txt`).
- No multi-layer C++ loop: that would cross the non-goal boundary of the
  brief §1 without a separately approved API change.

## Reproducibility

- `cmake -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build -j`
- `cmake -B build-ptds -DCMAKE_BUILD_TYPE=Release -DGFX1150_7E_PTDS_TEST=ON`
- `python -m pytest -m gpu -q` / `-m "not gpu" -q`
- `python3 audit/evidence/G5/7E/qaqc-probes/stream_source_scan.py .`
- `GFX1150_STREAM_TRACE=1 python3 audit/evidence/G5/7E/qaqc-probes/overlap_probe.py`
- `python3 audit/evidence/G5/7E/qaqc-probes/ptds_probe.py`
- `python3 scripts/qa/check_claims.py && python3 scripts/qa/canary_claims.py`

## Known limitations

- The trace mode measures with `hipEventElapsedTime` windows; GPU
  clock-granularity gives ~microsecond precision — for the tiny in-suite
  fixture the absolute overlap is at noise scale, hence the qualified claim.
- The stress thread test runs threads one at a time (process-global GPU
  workspaces are single-instance by design); concurrent multi-threaded GPU
  use remains out of scope (S-3 mutex still guards it).
- `7c/` at the repo root is pre-existing untracked content, unrelated to 7E.
