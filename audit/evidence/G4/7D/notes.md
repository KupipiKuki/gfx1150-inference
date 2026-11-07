# 7D notes — design, measurements, limitations, provenance

**Package:** 7D Memory Honesty & Robustness (Gate G4)
**Branch:** `wp/7D-memory-robustness`; brief `PHASE7_7D_MEMORY_ROBUSTNESS_BRIEF.md`
**Parent (brief base):** `003f4e5` — **Candidate work commit:** `c9c484a`
**Evidence contract:** `audit/evidence/G4/7D/README.md`

## Design decisions and why

1. **Eviction = PTE drop + fadvise** (7D-1). Empirical fact discovered on
   this host (kernel 6.x, Python without `mmap.MADV_PAGEOUT`):
   `posix_fadvise(fd, ..., POSIX_FADV_DONTNEED)` **cannot** free pages of a
   range that is still mapped (RSS and page cache unchanged — raw probe in
   `red.log`/probe history), because the kernel will not reclaim mapped file
   pages for an advice-only hint. `MADV_DONTNEED` on the read-only mapping
   drops the PTEs (zero data loss; pages re-fault from the file) and thereby
   *enables* the fadvise to act. The 7D implementation therefore issues, per
   span: a PTE drop (`MADV_PAGEOUT` when exposed, else `MADV_DONTNEED`) **then**
   `posix_fadvise(POSIX_FADV_DONTNEED)` as the primary page-cache hint. The
   docs never present `MADV_DONTNEED` as page-cache eviction; when neither
   advice channel exists, the PTE-only fallback warns once
   (`EvictionFallbackWarning`). `MADV_WILLNEED` prefetch is kept for all
   policies (all three policies want warm pages ahead of use).
2. **Measured, not asserted.** The eviction's page-cache effect is proven by a
   major-fault re-touch probe: after STREAM evicts a layer, re-touching it
   takes disk-re-faults (majflt ≥ 1, readahead may coalesce the count); a warm
   re-touch under PIN takes none (majflt = 0). RSS deltas: PIN ≈ +64 MiB
   (model size), STREAM ≈ 0 kB. Sources: `/proc/self/status` VmRSS,
   `/proc/self/stat` minflt/majflt. Caveat: page-cache reclamation is
   kernel best-effort; the numbers are for a synthetic 64–67 MB model on
   this quiet host, not for 70B.
3. **Budget readers live in `src/memory_budget.py`** (pure stdlib; CPU-CI
   safe; added to `pyproject.toml` `py-modules` and picked up by the
   `test_v8` sdist/py-modules self-check — the BLOCKER-7C-1 lesson). Readers
   are deliberately path-injectable (`_cgroup_v2_available_bytes(proc, base)`)
   so the cgroup logic is unit-tested against fake trees rather than wishing
   for a limited host.
4. **AUTO fails safe.** No readable source ⇒ no budget ⇒ STREAM, with a
   `NoBudgetFallbackWarning` when an actual decision was requested with no
   budget; never an invented number. `decide_residency` is the single
   decision/warning point shared by the engine and the standalone streamer.
5. **KV caps before allocation.** `min(user cap, GTT, MemAvailable, cgroup)`
   minus a 10% margin; refusal message names requested bytes, effective
   budget, and every source value (including `max_kv_bytes`, so test caps are
   reproducible). mmap files are unlinked immediately after mapping
   (crash-safe, POSIX; `O_CREAT|O_EXCL|O_RDWR|O_NOFOLLOW` retained), sized
   only after a `statvfs` check, allocated with `posix_fallocate` (ftruncate
   fallback). `statvfs` disk-space refusal happens **before** any file is
   created (no partial files).
6. **Exception preservation.** `WeightStreamer.close()`,
   `KVCacheManager.close()`, and `LlamaInferenceEngine.close()` never raise:
   cleanup failures (`BufferError` from live views, driver errors) become
   `RuntimeWarning`s; fds are still closed; mappings are dropped or clearly
   reported. Constructor `except: self.close(); raise` paths therefore
   surface the original error (verified for missing files, corrupt GGUFs,
   and over-budget KV requests inside the engine ctor).
7. **`block_count` cross-check in the loader** (not the parser): declared
   `{arch}.block_count` must equal the actual `blk.N.*` index set, else a
   concise `ValueError` with declared/found/min/max. A 999-vs-2 header no
   longer produces a 999-entry missing-tensor list. Duplicate names were
   already rejected at parse (7C/7A); covered again at loader level.
8. **Claims honesty (7D-4).** Row 14 REMOVED (no bound claimed anywhere);
   rows 18/19/20/30 qualified in place; row 21 replaced by the verified
   fadvise+PTE-drop mechanism row. Eight baseline entries removed; canary
   `EXPECTED_BASELINE_ENTRIES` 14 → 6 in the same change. All other rows'
   scope line numbers were refreshed because the docs shifted.

## Measurements on this host

- Budget sources: `gtt_sysfs` ≈ 49.2 GiB free (amdgpu sysfs, real GTT),
  `host_memavailable` ≈ 91–92.5 GiB, cgroup v2 unlimited in the session
  scope; cgroup v2 headroom honored under `systemd-run --user --scope -p
  MemoryMax=256M` (~245.6 MiB) — real cgroup-limited KV refusal recorded in
  `kv-hardening.log`. No `systemd-run` privileges beyond `--user` were used.
- 1,000×/1,100× open-close leak probe: fd delta ≤ 1 (an unrelated fd opened
  during the run), model-related mmap count delta stable (0 growth) across
  the 100/600/1100 checkpoints.

## Environment notes

- This is the real gfx1150 APU host (ROCm loaded, `matmul_module` prebuilt):
  the GPU lane ran for real (34 passed), not skipped. CPU lane 503 passed;
  `tests/test_cpu_only.py` green in both modes (with and without `-O`).
- Python 3.14.10 does not expose `mmap.MADV_PAGEOUT` on this kernel/host
  (env.txt records it), so the `MADV_PAGEOUT` path is covered by unit tests
  through monkeypatched presence/absence, and the PTE-drop enabler
  (`MADV_DONTNEED`) is the live path here — explicitly documented in
  README/PLAN and this bundle.

## QaQC reproducibility

- `python3 -m pytest -m "not gpu" -q` — CPU lane
- `python3 -m pytest -m gpu -q` — GPU lane (real hardware)
- `python3 -m pytest tests/test_memory_residency.py -q` — 7D suite
- `python3 audit/evidence/G4/7D/qaqc-probes/mem_probes.py`
- `python3 audit/evidence/G4/7D/qaqc-probes/kv_probes.py`
- `python3 scripts/qa/check_claims.py && python3 scripts/qa/canary_claims.py`

## Limitations / not evidenced in 7D

- No real 70B GGUF was run; all models here are synthetic fixtures. 70B,
  real-GGUF, 8-hour endurance, and throughput claims stay UNVERIFIED and
  deferred to 7F-2/7F-3/7F-4. A synthetic model is not 70B evidence.
- The RSS/major-fault probe measures the mechanism, not 70B behavior; the
  kernel may aggregate readahead faults, hence the low absolute majflt count —
  the asserted property is "evicted spans re-fault from disk, warm spans do
  not".
- No GTT weight cache: PIN is host page-cache residency only; no GTT delta is
  claimed (weights are H2D per projection in every policy).
- The leak probe tolerates ±2 fds / ±4 model-related maps to absorb
  unrelated runtime noise; per-checkpoint deltas observed were 0–1.
