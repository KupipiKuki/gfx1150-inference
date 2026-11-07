# Phase 7E Coder Brief — Stream Topology & Pipeline (Gate G5)

**To:** GLM5.3 (coder)
**From:** DeepSeek V4.1 Flash (primary auditor)
**Date:** 2026-11-07
**Branch:** `wp/7E-stream-topology`
**Base:** the tip of `vibe/phase7-220201` that contains this brief (confirm `git log -1 --oneline`; do not start from an older SHA)
**Gate:** G5. **7E is authorized after G4 (2026-11-07). 7F is not authorized.**
**Prior gate:** G4 signed; 7D memory/residency accepted. Do not reopen 7B/7C/7D.

---

## 0. Read first

1. `audit/AUDIT_REMEDIATION_v0.6.2.md` §P-1 and `audit/REVIEW_v0.6.1_c75914b.md` §2.4 — the current stream defect.
2. `src/kernels/attention.hip` `DeviceLayerWorkspace`, `project_on_device`, `launch_forward_layer_cached_fp16`; `src/kernels/attention.h`; the `launch_*_device` helpers in `matmul.hip`, `dequantize.hip`, `mlp.hip`, `rmsnorm.hip`, `rope.hip`.
3. `src/python_bindings/bindings.cpp` `forward_layer_cached` (Python-visible signature must stay unchanged).
4. `IMPLEMENTATION_PLAN.md` 7E row; `audit/CLAIMS_LEDGER.md` row 15; `tests/test_layer.py`, `tests/test_full_model.py`, `tests/test_phase5_scale.py`.

**Current defect:** `DeviceLayerWorkspace` has one `hipStream_t stream` used for copies, records `copy_done_event`, then makes the **NULL stream** wait (`hipStreamWaitEvent(0, ...)`) and launches all kernels on stream 0. The final D2H is issued on `ws.stream` without a compute-done event, then `hipStreamSynchronize(ws.stream)`. This is correct only under legacy NULL-stream semantics and delivers no real copy/compute overlap. `ensure()`/`ensure_weight()` free/realloc without draining in-flight work.

---

## 1. Objective and non-goals

**Objective:** make the layer pipeline an explicit stream/event graph:

- separate copy and compute streams;
- kernels launch on the compute stream through explicit stream parameters;
- host→device copies and compute overlap where the dependency allows;
- double-buffered weight staging with no overwrite while a kernel reads a slot;
- pinned host staging where possible;
- sync-before-free/realloc and drain-on-destroy;
- correctness unchanged and overlap/sync counts measured.

**Non-goals (do not bundle):**
- A multi-layer C++ loop that would achieve **one sync per token**. The Python
  `forward_layer_cached` API returns host hidden states after each layer, so the
  documented G5 boundary is **one sync per layer** (N syncs per token for N
  layers). Do not claim one sync/token; row 15 stays NOT YET/qualified unless a
  separately approved multi-layer API change exists.
- Flash attention / P-3, GQA sharing, model-family work, tokenizer, 7F/7G,
  Python public API changes, package/CI changes (except the test build option in
  §2), or performance claims without measured evidence.
- Changing kernel math. The only edits in the other kernel files are the
  `hipStream_t` parameter plumbing.

---

## 2. Allowed files

- `src/kernels/attention.hip`, `src/kernels/attention.h` — workspace, streams,
  events, double-buffer orchestration, `launch_forward_layer_cached_fp16`.
- `src/kernels/{matmul,dequantize,mlp,rmsnorm,rope}.hip` and matching headers —
  **only** to add a `hipStream_t / cudaStream_t`-style stream parameter to the
  `launch_*_device` helpers and pass it to `hipLaunchKernelGGL` (no math, no
  tiling, no algorithm changes).
- `src/python_bindings/bindings.cpp` — only if the internal call plumbing needs
  it. The Python-visible `forward_layer_cached` signature and behavior must stay
  unchanged.
- `tests/**` — Python/C++ stream/stress tests; update only expectations that are
  genuinely changed (no weakening).
- `CMakeLists.txt` — **only** for a per-thread-default-stream test target or a
  test-only compile definition (e.g. `HIP_API_PER_THREAD_DEFAULT_STREAM=1`); no
  packaging/dependency change.
- `README.md`, `IMPLEMENTATION_PLAN.md` — only for stream/sync/overlap wording.
- `audit/CLAIMS_LEDGER.md` — row 15 only (and exact scope sites).
- docs, `audit/evidence/G5/7E/**`.

**Forbidden:** tokenizer/model-family/7D memory policy changes; 7F/7G; public
Python API changes without written auditor approval; kernel math; unrelated
refactors; CI workflow changes beyond the test target; deleting/weakening tests.

---

## 3. Work packages

### 7E-1 — Explicit compute/copy streams and event graph

- Replace the single `ws.stream` with:
  - `copy_stream` — input/norm/weight H2D and final D2H;
  - `compute_stream` — all device kernels and D2D KV writes;
  - `copy_done[slot]` — recorded on `copy_stream` after a staging copy;
  - `compute_done[slot]` — recorded on `compute_stream` after the consumer
    kernels finish with that slot.
- Kernels must launch on `compute_stream`, not stream 0. Add a `hipStream_t`
  parameter to every `launch_*_device` helper used by the layer path and pass it
  to `hipLaunchKernelGGL`.
- Dependencies:
  - compute waits on `copy_done[slot]` before reading staged inputs/weights;
  - copy waits on `compute_done[slot]` before overwriting a slot;
  - the final D2H is issued on `copy_stream` after a compute-done event;
  - `hipStreamSynchronize(copy_stream)` at the **layer boundary** is the single
    documented sync. No `hipStreamSynchronize`/`hipDeviceSynchronize` inside
    the layer for each projection.
- Remove `hipStreamWaitEvent(0, ...)` and any implicit NULL-stream reliance from
  the layer path. A source/QAQC check must show no `hipStreamWaitEvent(0` and no
  stream-less `hipLaunchKernelGGL` in the layer path.
- D2D KV writes in `launch_gqa_attention_cached_fp16_device` must be
  `hipMemcpyAsync` on `compute_stream` (ordered with the kernel), not a blocking
  `hipMemcpy`.
- Record the final `compute_done` after the last residual add; the D2H waits on
  it. Do not use the copy stream as a proxy for compute completion.

### 7E-2 — Double-buffered weight staging, pinned host, overlap

- Use two staging slots (or per-projection buffers) for device weights:
  - slot A is consumed by the current projection while slot B is filled on
    `copy_stream`;
  - `copy_stream` waits on `compute_done[slot]` before reusing a slot;
  - `compute_stream` waits on `copy_done[slot]` before the projection kernel.
- Implement a staged pipeline for the layer projections (Q, K, V, O, gate, up,
  down): stage the next weight before/while launching the current projection.
  The first projection may have no overlap; document it.
- Pinned host staging:
  - prefer `hipHostRegister` on page-aligned weight spans;
  - if the mmap/NumPy pointer cannot be registered, use a reusable pinned slab
    with a host copy and a documented fallback;
  - no correctness difference between pinned and fallback paths;
  - ensure registration/unregistration is paired and leak-free.
- Keep input/norm copies on `copy_stream` with events; compute waits on them.
- Measure overlap with `hipEventElapsedTime` (timing-enabled events) or an
  equivalent recorded trace: copy of slot B overlapping compute of slot A. If
  the measured overlap is absent, remove/qualify the overlap claim; do not
  assert it from code shape alone.
- Double-buffer only within a layer; the per-layer Python boundary remains.

### 7E-3 — Sync-before-free/realloc, destructor drain, race/stress

- `DeviceLayerWorkspace::ensure()` and `ensure_weight()` must drain the relevant
  in-flight work before `hipFree`/`hipMalloc` (e.g. synchronize the compute and
  copy streams or wait on their events). The same applies to
  `AttentionWorkspace::ensure`, `DeviceKVCachePool::init/free`, and any other
  grow-only workspace touched by the layer path.
- The workspace destructor and any shutdown path must synchronize/destroy events
  and streams only after in-flight work is drained. Do not destroy an event or
  stream with pending work.
- Stress tests:
  - repeated forward passes with varying `M`/`seq_len`;
  - forced workspace growth (and shrink/reuse) between calls;
  - an exception thrown after enqueue (e.g. invalid weight type) followed by
    further calls/cleanup;
  - many iterations to catch use-after-free/races;
  - a per-thread-default-stream run (`HIP_API_PER_THREAD_DEFAULT_STREAM=1`) if a
    test target can be built; otherwise a source/QAQC review plus a
    non-main-thread stress run, with the limitation documented.
- Correctness: on the same seed and model, output token IDs/logits must be
  identical to the parent (or within the documented FP16 tolerance; aim for
  identical greedy IDs).

### 7E-4 — Stream claims and docs

- Row 15 (“one synchronization per token”): keep it NOT YET or qualify it
  exactly as “one sync per layer (N per token); no one-sync/token claim” —
  because the Python per-layer boundary remains. Do not claim one/token.
- Update README/PLAN stream wording only where it asserts overlap/sync behavior;
  no throughput claim without 7F-3 evidence.
- The plan’s “ping-pong double-buffered layer pipeline” line must distinguish
  **SSD layer prefetch** (7D/Python) from **GPU copy/compute overlap** (7E) and
  state what is actually measured.
- Run claims checker/canaries; update only row 15 and exact scope sites.

---

## 4. Required checks

```bash
python -m pytest -m gpu -q -k "stream or layer or e2e"
python tests/test_layer.py
python tests/test_full_model.py
python tests/test_phase5_scale.py
python -m pytest -m "not gpu" -q
python scripts/qa/check_claims.py
python scripts/qa/canary_claims.py
# stress: repeated forward, varying M, forced realloc, exception-after-enqueue
# per-thread default stream build/run (or documented source/QAQC review)
# overlap timing: hipEventElapsedTime copy-vs-compute trace
# sync count: 1 per layer, N per token (documented boundary)
# source check: no hipStreamWaitEvent(0, ...) / stream-less kernel launches in the layer path
```

---

## 5. QAQC adversarial checks

- Event graph line by line: every async copy has a consumer wait; every slot
  reuse waits on compute-done; every free/realloc has a preceding drain; no
  event/stream destroyed with pending work.
- No `hipStreamWaitEvent(0, ...)` and no stream-less kernel launch in the layer
  path; kernels use the explicit compute stream.
- Double-buffer: slot B copy overlaps slot A compute; no slot overwritten while
  a kernel reads it; forced growth/shrink does not use-after-free.
- Pinned staging: `hipHostRegister` path and fallback both correct; no leak;
  registration failure handled; no silent pageable-memcpy claim.
- Per-thread default stream: no legacy NULL-stream dependency; stress from a
  non-main thread or the compile-flag build.
- Output vs parent: identical greedy IDs/logits (or documented tolerance).
- Overlap claim backed by timing/event evidence, not code shape; if absent,
  claim removed.
- Sync count: one per layer measured; N per token documented; row 15 honest.
- Claims/docs/canaries stay green; no throughput claim.

---

## 6. Acceptance / G5 exit

- [ ] Explicit compute/copy streams + `copy_done`/`compute_done`; kernels on the
      compute stream; no NULL-stream reliance.
- [ ] Double-buffered weight staging with pinned host or documented fallback;
      no overwrite while a kernel reads; overlap measured or claim removed.
- [ ] `ensure`/`ensure_weight`/workspace/KV/destructor sync before free/destroy;
      forced realloc/exception stress clean.
- [ ] Correctness unchanged on all GPU suites; identical token IDs/logits.
- [ ] Per-layer sync boundary measured and documented; no one-sync/token claim.
- [ ] Claims/README/PLAN honest; claims checker + canaries green.
- [ ] Evidence bundle complete.

**Fallback:** if true overlap cannot be demonstrated, remove/qualify the overlap
claim and keep the correct explicit-stream topology + sync-before-free work. If
the per-thread-default-stream build is infeasible, document the limitation and
provide the source/QAQC review plus non-main-thread stress evidence.

---

## 7. Evidence bundle — `audit/evidence/G5/7E/`

```
env.txt  parent-sha.txt  candidate-sha.txt  diffstat.txt
red.log                 # parent fails the stream/source or per-thread probe
green.log               # candidate passes
event-graph.md          # the exact stream/event dependency graph
overlap.log             # hipEventElapsedTime copy/compute overlap (or the removal note)
sync-count.log          # 1 sync/layer, N/token, measured
stress.log              # repeated/varying M/forced realloc/exception-after-enqueue
per-thread.log          # per-thread default-stream test/limitation
correctness.log         # parent-vs-candidate IDs/logits
gpu-lane.log  cpu-lane.log
claims.log  canary.log
qaqc-probes/
notes.md
```

---

## 8. Stop / handoff

Stop at G5. Do not start 7F. Do not merge to `vibe/phase7-220201`; the auditor
merges only after G5 is signed. 7F-3 owns real throughput/benchmark evidence;
7E must not claim it.

---

## 9. Start-here checklist

1. `git switch wp/7E-stream-topology` (from the brief commit); confirm HEAD.
2. Read §0; trace the current `hipStreamWaitEvent(0, ...)` and stream-0 kernel
   launches; record the parent red probe.
3. Add the stream parameter to the `launch_*_device` helpers first; keep the
   math untouched.
4. Build the explicit copy/compute event graph and layer-boundary sync; verify
   correctness before adding the double buffer.
5. Add the double buffer + pinned staging; measure overlap.
6. Add sync-before-free/destructor drain + stress/per-thread tests.
7. Update row 15/docs; run the full battery; assemble the evidence; stop for QAQC.
