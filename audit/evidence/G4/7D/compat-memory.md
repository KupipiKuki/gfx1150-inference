# 7D compat matrix — policy / limits / claims

Phase 7D (Gate G4) memory policy matrix for `gfx1150-inference`. What is
evidenced in this package, what is best-effort, and what is deferred.

## Residency policy (`--residency {auto,pin,stream}`)

| Policy | Behavior | Budget gate | Evidence |
|---|---|---|---|
| `auto` (default) | PIN the model's file pages in the **host page cache** when `weight_bytes <= weight_budget`, else STREAM | `weight_budget = max(0, available - kv - activations - 512 MiB)`; `available = min` over readable sources; no source readable ⇒ fail safe to STREAM (no invented budget) | `tests/test_memory_residency.py::TestBudgetedResidency`, `TestEngineResidency`; `residency.log`; decisions recorded in `engine.residency_decision` |
| `pin` (`--cache-weights` deprecated alias) | Skip eviction always; host page-cache residency | Over-budget PIN **warns** (`OverBudgetWarning`) but honors the explicit request | `tests/...::test_explicit_stream_honored_and_pin_over_budget_warns` |
| `stream` | `MADV_WILLNEED` prefetch; best-effort eviction per layer/tensor | none (explicit request) | `eviction.log` |

**PIN is not GTT pinning.** In every policy the kernels copy quantized weights
host-to-device per projection; there is no device-resident weight cache in this
package (that is a separate architecture/performance package). No throughput
claim is attached to any policy.

## Eviction mechanism (7D-1)

| Step | Call | Role |
|---|---|---|
| 1 | `madvise(MADV_PAGEOUT)` on the span, **or** `madvise(MADV_DONTNEED)` when the host does not expose `MADV_PAGEOUT` | PTE drop of the read-only mapping so the kernel can free the pages; an **enabler**, not page-cache eviction by itself |
| 2 | `posix_fadvise(fd, off, len, POSIX_FADV_DONTNEED)` | **Primary page-cache hint**: drop the clean file pages |
| fallback | neither channel available ⇒ PTE-only `MADV_DONTNEED` + one-time `EvictionFallbackWarning` | best-effort; memory not bounded |

Measured on this host (no `MADV_PAGEOUT`, kernel 6.x): fadvise alone is inert
for mapped spans (RSS unchanged); PTE drop + fadvise evicts for real
(re-touch after eviction takes major faults; warm re-touch takes none). All
advice is best-effort — **no hard RAM bound is claimed anywhere**.

## Budget sources (7D-2/7D-3)

| Source | Path | This host |
|---|---|---|
| GTT free | `/sys/class/drm/card*/device/mem_info_gtt_{total,used}` | readable (amdgpu, ~49.2 GiB free) |
| Host available | `MemAvailable` in `/proc/meminfo` | readable (~92.5 GiB) |
| cgroup v2 | `memory.max`/`memory.current` for the process's cgroup | unlimited here; verified via fake trees + real `systemd-run --user --scope -p MemoryMax=256M` probe (headroom ~245.6 MiB observed, and an over-budget KV request refused with the cgroup source named) |
| cgroup v1 | `memory.limit_in_bytes`/`memory.usage_in_bytes` | n/a (v2 host); unit-tested with fake trees |

KV cap: `min(max_kv_bytes, free GTT, MemAvailable, cgroup)` − 10% margin;
a request over the cap raises `ValueError` naming requested bytes, effective
budget, and the sources. Weight budget additionally subtracts KV bytes, a
conservative activation estimate (`hidden × max_seq_len × 2 bytes × 4 buffers +
vocab × 2 + 64 MiB`), and a 512 MiB safety margin.

## Claims matrix (ledger rows touched by 7D)

| Row | Claim | After 7D |
|---|---|---|
| 14 | Bounded RAM for 70B | **REMOVED** — withdrawn; no bound is claimed; mechanisms documented best-effort |
| 18 | 7B–70B without OOM | PARTIAL, qualified in place (README L10 / PLAN L12): 70B never run; 7F-2 owns real-GGUF evidence |
| 19 | 8-hour runtimes | UNVERIFIED, qualified in place (README L12 / PLAN L15); 7F-3/7F-4 |
| 20 | Active RAM Cap table | UNVERIFIED, qualified in place (PLAN L228 header + L235 caveat: unmeasured targets, no cap enforced) |
| 21 | Page-cache eviction mechanism | **VERIFIED** for the fadvise+PTE-drop mechanism (syscall-counted; major-fault re-touch probe); superseded the false "`MADV_DONTNEED` reclaims page-cache" row |
| 30 | Resident RAM delta < 500 MB | UNVERIFIED, qualified in place (PLAN L79: never measured; 7F-3) |

Baseline: 14 → 6 entries (rows 14/18/19/20/30 removed with the same change as
the qualification; `EXPECTED_BASELINE_ENTRIES = 6` in
`scripts/qa/canary_claims.py`).

## What is NOT claimed / deferred

- No 70B, real-GGUF, 8-hour, or throughput evidence (7F-2/7F-3/7F-4).
- No device/GTT weight cache; weights are H2D per projection in all policies.
- No hard RAM guarantee: eviction is kernel-advice, best-effort.
- 7E stream topology, 7G packaging: not touched.
