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

## Rework record (2026-11-07, per PHASE7_7D_REWORK_BRIEF.md)

Base: `1ad01c9` (auditor's NOT-SIGNED review). Work commit: `a380003`.

- **Fix 1 (QAQC-7D-1, negative block_count).** `_cross_check_block_count`
  (`src/weight_loader.py`) now rejects `declared_count < 0` explicitly
  ("must be >= 0") before the index-set compare: `llama.block_count = INT32(-1)`
  with zero `blk.*` tensors previously slipped through (`list(range(-1))` is
  empty) and produced `num_layers = -1`. Two new tests cover the -1/zero-tensor
  and -1/with-tensors cases (red at `1ad01c9` in `rework-red.log`, green at
  `a380003`).
- **Fix 2 (engine no-source AUTO provenance).**
  `LlamaInferenceEngine._apply_residency_policy` (`src/inference.py`) now
  passes `weight_budget=None` to `decide_residency` when no source was readable
  (`available_bytes is None`), preserving the `sources` argument so the
  `NoBudgetFallbackWarning` names them and the decision reason reads
  "no readable source". The previous behavior (effective STREAM, but
  `weight_budget=0` with the reason "exceed the budget (0)" and **no**
  warning) contradicted the documented "AUTO never invents a budget". New
  engine-level test asserts the warning, effective STREAM, `weight_budget is
  None`, and the reason text.
- **Adjudication QAQC-7D-3 (accepted, no code change).** Per the auditor
  (`audit/AUDIT_7D_DEEP_2026-11-07.md`): the `MADV_DONTNEED` PTE-drop used as
  an enabler before `posix_fadvise(POSIX_FADV_DONTNEED)` (when `MADV_PAGEOUT`
  is absent) is **accepted**; the docs/ledger present DONTNEED as an enabler,
  never as page-cache eviction, and fadvise-only is not presented as
  equivalent on this host (evidence: `red.log` — fadvise alone leaves RSS and
  page cache untouched). The mechanism is unchanged.
- **Scope:** claims statuses and the baseline count (6) are untouched; lanes
  CPU 506 / GPU 34, CPU-only both modes, claims checker, all 12 canaries, and
  the two bundle probes are green on the reworked candidate
  (`rework-green.log`, `qaqc-probes/qaqc-run.log` predates the rework and is
  superseded for the cgroup sections by this run: both probe scripts exit 0).
