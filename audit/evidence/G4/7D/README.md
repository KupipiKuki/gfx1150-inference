# G4 / 7D — Memory honesty & robustness evidence bundle

This directory is the coder/QAQC bundle for Phase 7D (Gate G4). The primary audit
report/signoff will be added by the auditor; do not pre-fill an audit verdict.

## Required files

| File | Contents |
|---|---|
| `env.txt` | OS/kernel, ROCm/HIP, `rocminfo`, Python, NumPy, cgroup/GTT sources, `git rev-parse HEAD` |
| `parent-sha.txt` | the brief base (normally `8426ec6` or the G3-signed tip) |
| `candidate-sha.txt` | the frozen work commit under review |
| `diffstat.txt` | file delta and allowed/forbidden set |
| `red.log` | new memory/KV/residency tests failing on the parent for the expected reasons |
| `green.log` | same tests passing on the candidate |
| `eviction.log` | `posix_fadvise(POSIX_FADV_DONTNEED)` / `MADV_PAGEOUT` / prefetch calls; missing-syscall fallback; no false `MADV_DONTNEED` page-cache claim |
| `residency.log` | AUTO/PIN_ALL/STREAM decisions and reasons; measured VmRSS/page-cache (and GTT if a reading exists) |
| `kv-hardening.log` | cgroup/full-disk/symlink/block-count/duplicate-name/huge-dimension probes |
| `leak.log` | 1,000× open/close `/proc/self/fd` and `/proc/self/maps` counts |
| `exception.log` | live-view close, constructor cleanup, original-exception preservation |
| `compat-memory.md` | policy/limits/claims matrix; what is evidenced vs deferred to 7F |
| `cpu-lane.log` | `pytest -m "not gpu" -q` |
| `gpu-lane.log` | `pytest -m gpu -q` |
| `cpu-only.log` | `tests/test_cpu_only.py` and `-O` |
| `claims.log` | `scripts/qa/check_claims.py` |
| `canary.log` | `scripts/qa/canary_claims.py` |
| `qaqc-probes/` | independent QAQC scripts/logs |
| `notes.md` | design, measurements, limitations, provenance |

## Rules

- **No fake memory guarantees.** `posix_fadvise`/`MADV_PAGEOUT` are best-effort;
  `MADV_DONTNEED` on a read-only mapping is not page-cache eviction. State the
  mechanism and limits in README/PLAN/claims.
- **Real budget sources.** Record which of GTT sysfs, `/proc/meminfo`, and
  cgroup v1/v2 were used. If a source is unavailable, fail safe to STREAM and
  document it; do not invent a budget.
- **PIN means host page cache.** A full GTT weight cache is out of 7D scope;
  weights are still H2D per projection. Do not claim GTT pinning without a
  separately implemented and measured device cache.
- **Measure, don't assert.** Include RSS/page-cache before/after for PIN vs
  STREAM, and GTT only if a real reading exists. A synthetic model is not 70B
  evidence; real 70B/8-hour claims belong to 7F-2/7F-3/7F-4.
- **Hostile inputs fail closed.** cgroup-limited KV, full disk, symlink,
  duplicate names, `block_count` mismatch, huge dims/alignment, truncation.
- **Cleanup preserves the original error.** Live-view `BufferError` is warned,
  not masked; fds closed; mappings released or clearly reported.
- **Claims/canaries.** Update README/PLAN/ledger rows 14/18/19/20/21/30,
  baseline entries, and `EXPECTED_BASELINE_ENTRIES` together; both checkers
  green.
- **No 7E/7F work.** One package, one gate.

## Gate exit (G4)

- Memory behavior matches the documented policy; no false bounded-RAM claim.
- AUTO/PIN/STREAM implemented and measured; CLI exposes it.
- Hostile inputs, cgroup/full-disk/symlink/block-count/duplicates covered.
- No fd/mmap leaks; exception masking fixed.
- 70B bounded-RAM claim evidenced or removed/qualified.
- CPU/GPU/CPU-only/claims/canaries green; evidence complete.
