# G5 / 7E — Stream topology & pipeline evidence bundle

This directory is the coder/QAQC bundle for Phase 7E (Gate G5). The primary audit
report/signoff will be added by the auditor; do not pre-fill an audit verdict.

## Required files

| File | Contents |
|---|---|
| `env.txt` | OS/kernel, ROCm/HIP, `rocminfo`, Python, NumPy, CMake, `git rev-parse HEAD` |
| `parent-sha.txt` | the brief base (G4-signed tip) |
| `candidate-sha.txt` | the frozen work commit under review |
| `diffstat.txt` | file delta and allowed/forbidden set |
| `red.log` | parent red: the stream/source probe or per-thread-default-stream probe fails for the expected reason |
| `green.log` | same probe/test passes on the candidate |
| `event-graph.md` | exact copy/compute stream + `copy_done`/`compute_done` dependency graph; every copy consumer wait and every slot/free drain |
| `overlap.log` | `hipEventElapsedTime` (or equivalent) copy-vs-compute overlap; if no overlap, the removal/qualification note |
| `sync-count.log` | measured syncs: 1 per layer, N per token; no one-sync/token claim |
| `stress.log` | repeated forward passes, varying M/seq, forced growth/shrink/reuse, exception-after-enqueue, many iterations |
| `per-thread.log` | per-thread-default-stream build/run, or the documented limitation + non-main-thread stress |
| `correctness.log` | parent-vs-candidate greedy token IDs/logits |
| `gpu-lane.log` | `pytest -m gpu -q` and the stream/layer/e2e suites |
| `cpu-lane.log` | `pytest -m "not gpu" -q` |
| `claims.log` | `scripts/qa/check_claims.py` |
| `canary.log` | `scripts/qa/canary_claims.py` |
| `qaqc-probes/` | independent QAQC probes/logs |
| `notes.md` | design, event graph rationale, measurements, limitations, provenance |

## Rules

- **Explicit streams only.** Kernels in the layer path launch on the compute
  stream; no `hipStreamWaitEvent(0, ...)`; no implicit NULL-stream dependency.
- **Every async copy has a consumer wait.** Every slot reuse waits on
  compute-done. Every free/realloc/destroy drains in-flight work first.
- **Double buffer correctness.** Two weight slots; no overwrite while a kernel
  reads; forced growth/shrink/slot reuse is safe.
- **Pinned staging honesty.** `hipHostRegister` or a pinned slab; fallback
  documented; no claim of async overlap from pageable copies unless measured.
- **Measure, don’t assert.** Overlap and sync counts are evidence, not code
  shape. If overlap is absent, remove/qualify the claim.
- **Per-layer boundary.** The Python `forward_layer_cached` API returns host
  hidden states per layer; 7E documents **one sync per layer (N/token)**. Do not
  claim one sync/token without a separately approved multi-layer API change.
- **Correctness first.** Parent-vs-candidate token IDs/logits must match (or the
  documented FP16 tolerance); all GPU suites green.
- **No 7F/G6 work.** No throughput/benchmark claim; 7F-3 owns that.
- **Claims/canaries.** Update only row 15 (and exact scope sites); keep the
  claims checker and canaries green.

## Gate exit (G5)

- Explicit compute/copy streams + events; no NULL-stream reliance.
- Double-buffered staging, pinned host or fallback; overlap measured or claim
  removed.
- Sync-before-free/destructor drain; stress/per-thread clean.
- Correctness unchanged; per-layer sync boundary measured/documented.
- Claims/docs honest; CPU/GPU/claims/canaries green; evidence complete.
