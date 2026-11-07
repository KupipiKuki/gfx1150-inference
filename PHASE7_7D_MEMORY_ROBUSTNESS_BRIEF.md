# Phase 7D Coder Brief — Memory Honesty & Robustness (Gate G4)

**To:** GLM5.3 (coder)
**From:** DeepSeek V4.1 Flash (primary auditor)
**Date:** 2026-11-07
**Branch:** `wp/7D-memory-robustness`
**Base:** the tip of `vibe/phase7-220201` that contains this brief (confirm `git log -1 --oneline`; do not start from an older SHA)
**Gate:** G4. **7D is authorized after G3 (2026-11-06). 7E is not authorized.**
**Prior gates:** G3 signed; Phi-3/Gemma are synthetic-only and real-GGUF evidence is 7F-2. Do not reopen 7C or the tokenizer.

---

## 0. Read first

1. `audit/AUDIT_REMEDIATION_v0.6.2.md` §2.3 (D-1/P-2), §2.5 (S-1 residual), §2.6 (R-1/R-2), and the P0/P1 list.
2. `audit/REVIEW_v0.6.1_c75914b.md` §2.3–§2.6 — the original memory/cleanup findings.
3. `PHASE7_IMPLEMENTATION_HANDOFF.md` §1 (roles), §2 (one package/one gate), §7 (evidence), and the 7D section.
4. Current code: `src/weight_loader.py` (`MADV_DONTNEED`, `cache_weights`, `close`), `src/kv_cache.py` (allocation cap, mmap files, close), `src/inference.py` (constructor/close/CLI), `src/gguf_parser.py` (tensor table).
5. Claims: `audit/CLAIMS_LEDGER.md` rows 14, 18, 19, 20, 21, 30; `README.md` L10/L12/L123/L124; `IMPLEMENTATION_PLAN.md` L15/L17/L79/L221.

**Authority:** the measured behavior and the audit findings beat the old README/PLAN wording. When a claim cannot be evidenced in 7D, remove or qualify it; do not restate it.

---

## 1. Objective and non-goals

**Objective:** make the memory behavior honest and safe:

- page-cache eviction actually targets the page cache (`posix_fadvise(POSIX_FADV_DONTNEED)`, optional `MADV_PAGEOUT`), not `MADV_DONTNEED` on a read-only mapping;
- a real budgeted residency policy (`AUTO` / `PIN_ALL` / `STREAM`) instead of a boolean that only skips eviction;
- KV/allocation hardening against hostile headers, cgroups, full disks, symlinks, and leaks;
- constructor/close paths that preserve the original exception;
- README/PLAN/claims that state what is measured, what is best-effort, and what is not yet evidenced.

**Non-goals (do not bundle):**
- 7E stream topology/overlap, 7F real-GGUF/70B/8-hour/benchmark evidence, 7G packaging polish.
- Tokenizer/model-family changes; 7C is closed. Do not add Phi-3/Gemma real-model claims.
- A full persistent **GTT weight cache**. The current kernels copy quantized weights H2D per projection; implementing a device-resident weight cache is a separate architecture/performance package. `PIN_ALL` in this package means **host page-cache residency** unless a real GTT cache is separately implemented and measured. Do not call it GTT pinning.
- General performance tuning, flash attention, RoPE scaling, batching.

---

## 2. Allowed files

- `src/weight_loader.py` — eviction/prefetch, residency policy, cleanup.
- `src/kv_cache.py` — KV budget, mmap hardening, cleanup.
- `src/inference.py` — constructor/close, policy selection, CLI.
- `src/gguf_parser.py` — **only** for duplicate-tensor-name detection or a narrow block-count/tensor-prefix helper if it cannot live in the loader. Do not change fail-closed parsing behavior.
- `src/memory_budget.py` (new, preferred) — budget/cgroup/GTT/host-memory helpers. If added, add it to `pyproject.toml` `py-modules` and the CPU-only sdist/py-modules test (the 7C BLOCKER-7C-1 lesson).
- `src/python_bindings/bindings.cpp`, `CMakeLists.txt` — **only** if a HIP free-memory query is truly required. Prefer the existing readable sources: `/sys/class/drm/card*/device/mem_info_gtt_{total,used}`, `/proc/meminfo`, `/sys/fs/cgroup/...`. Do not add a kernel/binding if sysfs/proc suffices.
- `tests/**` — memory/KV/residency/leak/exception tests; update existing expectations for unlink-before-map.
- `README.md`, `IMPLEMENTATION_PLAN.md` — memory wording and policy.
- `audit/CLAIMS_LEDGER.md` — rows 14, 18, 19, 20, 21, 30 only.
- `audit/claims_baseline.txt` — remove entries whose claims are qualified/removed; update `scripts/qa/canary_claims.py`'s `EXPECTED_BASELINE_ENTRIES` in the same change (the 7C lesson).
- `pyproject.toml` — only for a new memory module in `py-modules`.
- docs and `audit/evidence/G4/7D/**`.

**Forbidden:** 7E/7F/7G work, tokenizer/model-family changes, CI workflow changes, unrelated refactors, deleting/weakening tests, or claiming real 70B/8-hour evidence from synthetic runs.

---

## 3. Work packages

### 7D-1 — Page-cache eviction honesty

Current defect: `WeightStreamer.release_layer()` / `release_tensor()` call
`mmap.madvise(MADV_DONTNEED)` on a read-only file mapping. On Linux this drops
the process's page-table entries; it does not reliably evict clean file-backed
page-cache pages. The README/PLAN therefore overstate the mechanism.

Required:

- Eviction uses `os.posix_fadvise(fd, offset, length, os.POSIX_FADV_DONTNEED)`
  on the model file descriptor as the primary page-cache hint.
- If `mmap.MADV_PAGEOUT` exists, use it on the mapped span as an additional
  best-effort hint; if not, skip it (this host does not expose it).
- Keep `MADV_WILLNEED` prefetch (and optionally `POSIX_FADV_WILLNEED`) for the
  next layer/tensor.
- `MADV_DONTNEED` must not be presented as page-cache eviction. If kept as a
  last-resort fallback when neither fadvise nor pageout exists, emit a clear
  one-time warning and document that it is best-effort/PTE-only.

> **Audit adjudication (2026-11-07):** on Linux, `posix_fadvise` alone is inert
> for spans still mapped by the process; a PTE drop (`MADV_PAGEOUT` when
> available, else `MADV_DONTNEED`) **before** the fadvise is an accepted
> enabler, not page-cache eviction. README/PLAN/claims must state the enabler
> role (they do). This supersedes the “last-resort fallback only” wording above;
> see `audit/AUDIT_7D_DEEP_2026-11-07.md` §4.
- Unavailable syscalls must not crash inference; a deterministic fallback and a
  warning are required. Tests must monkeypatch/remove `os.posix_fadvise` and
  `mmap.MADV_PAGEOUT` to cover both paths.
- `PIN_ALL`/`cache_weights=True` skips eviction; `STREAM` performs it.
- Tests count the syscalls via monkeypatch: STREAM calls fadvise/pageout; PIN
  does not; missing-syscall fallback is safe and warns.
- Docs: replace “MADV_DONTNEED reclaims page-cache” with
  “`posix_fadvise(POSIX_FADV_DONTNEED)` / optional `MADV_PAGEOUT`, best-effort;
  not a hard RAM bound.”

### 7D-2 — Budgeted residency policy

Replace the boolean-only behavior with an explicit policy:

- `ResidencyPolicy`: `AUTO`, `PIN_ALL`, `STREAM` (strings/Enum).
- `AUTO`: pin if the model's weight bytes fit the computed budget; otherwise
  stream. Record the decision and the reason.
- `PIN_ALL`: keep the model's pages resident in the **host page cache** (skip
  eviction; optionally prefetch the whole file). This is not a GTT weight cache;
  document that weights are still H2D per projection.
- `STREAM`: layer-wise mmap + fadvise/pageout eviction (current behavior).
- Budget (document the exact sources actually used):
  - `free_gtt = mem_info_gtt_total - mem_info_gtt_used` from
    `/sys/class/drm/card*/device/mem_info_gtt_{total,used}` when available;
  - `free_host = MemAvailable` from `/proc/meminfo`;
  - `cgroup_available = memory.max - memory.current` (v2) or
    `memory.limit_in_bytes - memory.usage_in_bytes` (v1) when finite;
  - `available = min(free_gtt, free_host, cgroup_available)` (skip unavailable
    sources and record which were used);
  - `reserve = kv_bytes + activation_estimate + safety_margin`;
  - `weight_budget = max(0, available - reserve)`.
  - If no source is available, fail safe to `STREAM` and state why; do not
    invent a budget.
  - `activation_estimate` must be a documented conservative formula (hidden ×
    max_seq_len × dtype × buffers + logits/workspace); `safety_margin` must be
    explicit (e.g., 512 MiB or 10%, documented).
- `weight_bytes` = sum of the parsed tensor `n_bytes` (page-aligned overhead
  included or documented). `kv_bytes` = `KVCacheManager.nbytes`.
- `cache_weights` compatibility: `True` maps to `PIN_ALL`; `False` maps to the
  new default `AUTO` (old behavior is `STREAM`). Emit a deprecation/CLI note
  and document the mapping. Do not silently change semantics without saying so.
- CLI: add `--residency {auto,pin,stream}` (default `auto`), keep
  `--cache-weights` as a deprecated alias for `pin`, and expose a budget
  override (e.g., `--residency-budget-mb`/`--max-kv-bytes`) for reproducible
  tests. `PIN_ALL` over budget must warn clearly (it is an explicit user
  request); `AUTO` must not silently pin an over-budget model.
- `WeightStreamer` supports the policy/budget (standalone: `cache_weights`
  maps True→PIN, False→AUTO, and AUTO without a budget streams safely).
- Tests:
  - small synthetic model + large budget → AUTO chooses PIN (no eviction calls);
  - forced small budget → AUTO chooses STREAM (eviction calls);
  - explicit PIN_ALL/STREAM always honor the request; over-budget PIN warns;
  - `cache_weights` mapping and CLI precedence;
  - measured `VmRSS`/page-cache (and GTT if a reading exists) before/after for
    PIN vs STREAM on a synthetic model; record the source and caveat. A host
    RSS/page-cache difference is required; a GTT difference is **not** claimed
    without a device weight cache.

### 7D-3 — KV/allocation and cleanup hardening

- **KV budget:** compute an effective cap
  `min(free_gtt, free_host, cgroup_available, max_kv_bytes)` with a safety
  margin. If the requested `KVCacheManager.nbytes` exceeds it, raise
  `ValueError` naming requested bytes, effective budget, and the source(s).
  Do not attempt an allocation that can OOM. `max_kv_bytes` remains a user cap.
  A `--max-kv-bytes`/`--kv-budget-mb` CLI option is recommended for tests.
- **cgroup:** support v2 `memory.max`/`memory.current` and v1
  `memory.limit_in_bytes`/`memory.usage_in_bytes`; a finite limit below the
  request must refuse cleanly. A cgroup-limited probe (unit test with
  monkeypatched files, and a real `systemd-run -p MemoryMax=...` probe where
  available) is required.
- **block_count cross-check:** derive the actual `blk.N.*` index set from the
  parsed tensor names; if `general.architecture.block_count` (or
  `llama.block_count`) disagrees, fail fast with declared vs found
  count/min/max. Do not emit a 999-entry missing-tensor list for a 2-layer
  file.
- **duplicate tensor names:** reject duplicate names at parse/load time with a
  clear error (narrow `gguf_parser.py` change or loader check). Tests must
  cover a duplicate header.
- **KV mmap files:** on POSIX, unlink the file immediately after the
  `O_CREAT|O_EXCL|O_RDWR|O_NOFOLLOW` open/ftruncate/mmap so a crash before
  `close()` leaves no files; keep the mapping usable. If a platform cannot
  unlink-before-map, retain the close cleanup and document it.
- **disk-space check:** before `ftruncate`/`posix_fallocate`, use
  `os.statvfs(mmap_dir)` to ensure the requested K+V bytes fit; raise a clear
  `OSError`/`ValueError` with required/free bytes. Use `posix_fallocate` when
  available; otherwise `ftruncate`.
- **symlinks:** keep `O_NOFOLLOW`; test a symlink at the target path.
- **exception masking:** `WeightStreamer.__init__`/`close`,
  `LlamaInferenceEngine.__init__`/`close`, and `KVCacheManager.close`/
  `__del__` must preserve the original exception. A cleanup `BufferError`
  must be warned/logged, not replace the constructor error; fds are closed;
  mappings are released or a clear warning is emitted.
- **leaks:** a 1,000× open/close probe checks `/proc/self/fd` and
  `/proc/self/maps` counts; no fd/mmap growth. `close()` with a live view must
  either release the mapping or warn, with the fd closed.
- **hostile inputs:** `general.alignment=0`, truncation, huge/negative/zero
  dims, huge `block_count`, duplicate names, KV dir full/symlink, cgroup limit
  below request. All fail closed with actionable errors.

### 7D-4 — Memory claims and documentation

Update the public claims to the actual behavior:

- `README.md` L10/L12/L123/L124 and `IMPLEMENTATION_PLAN.md` L15/L17/L79/L221.
- `audit/CLAIMS_LEDGER.md` rows 14, 18, 19, 20, 21, 30 (and any scope sites the
  checker reports).
- Replace “`MADV_DONTNEED` reclaims page-cache” with the fadvise/pageout
  best-effort statement. Remove/qualify “bounded memory”, “without OOM”,
  “8-hour runtimes”, `<500 MB`, and the “Active RAM Cap” table if they are not
  evidenced by a real run in this package.
- `PIN_ALL` wording: host page-cache residency, not GTT pinning; weights are
  still H2D per projection; no throughput claim.
- 70B/8-hour/real-RAM claims remain **UNVERIFIED/7F-2/7F-3/7F-4** unless a real
  70B run with measured RSS/GTT exists in this package. Synthetic evidence is
  not 70B evidence.
- Run `check_claims.py` and `canary_claims.py`; remove/refresh baseline entries
  and the canary count in the same change (7C BLOCKER-7C-2 lesson).
- If a claim is removed, remove its baseline entry; if qualified, update the
  scope sites exactly.

---

## 4. Required checks

```bash
python -m pytest -m "not gpu" -q -k "memory or kv or residency or parser"
python -m pytest -m gpu -q -k "residency or kv"
python -m pytest -m "not gpu" -q
python -m pytest -m gpu -q
python tests/test_cpu_only.py
python -O tests/test_cpu_only.py
python scripts/qa/check_claims.py
python scripts/qa/canary_claims.py
# fd/mmap leak probe: 1000 open/close, diff /proc/self/fd and maps
# cgroup probe: systemd-run --scope -p MemoryMax=... (or a documented unit test)
# syscall fallback: remove/monkeypatch os.posix_fadvise and mmap.MADV_PAGEOUT
# RSS/page-cache/GTT measurements for PIN vs STREAM
```

---

## 5. QAQC adversarial checks

- `MADV_DONTNEED` is not the page-cache story; fadvise/pageout are actually
  called in STREAM, not in PIN.
- Missing `posix_fadvise`/`MADV_PAGEOUT` does not crash and does not silently
  claim eviction; warning/fallback is clear.
- AUTO chooses PIN for a fitting model and STREAM for an over-budget one;
  PIN_ALL/STREAM honor explicit requests; no silent fallback.
- RSS/page-cache measurement reflects AUTO/PIN vs STREAM; GTT is not claimed
  without a device cache.
- `block_count` 999 vs 2 layers fails concisely; duplicate names fail; huge
  dims/alignment=0/truncation fail closed.
- cgroup-limited and full-disk KV allocation refuse cleanly; symlink is
  rejected; no file survives a crash-before-close (unlink-before-map).
- close with a live view: fd closed; mapping released or clear warning; the
  original constructor error survives.
- 1,000× open/close: no fd/mmap growth.
- Claims: no false bounded-RAM/70B/8-hour/active-RAM entries; policy docs match
  code; claims checker + canaries green; baseline/canary count updated.

---

## 6. Acceptance / G4 exit

- [ ] Memory behavior matches the documented best-effort policy; no false
      “bounded RAM” guarantee.
- [ ] AUTO/PIN/STREAM implemented and measured; `cache_weights` mapped/deprecated
      honestly; CLI exposes the policy/budget.
- [ ] Hostile inputs fail closed; cgroup/full-disk/symlink/block-count/duplicate
      cases covered.
- [ ] No fd/mmap leaks; constructor/close preserve the original exception.
- [ ] 70B bounded-RAM claim is evidenced in this package or removed/qualified;
      real 70B/8-hour evidence remains 7F-2/7F-3/7F-4.
- [ ] CPU/GPU lanes, CPU-only both modes, claims checker + canaries green.
- [ ] Evidence bundle complete.

**Fallback:** if a real 70B/GTT measurement is not available, do not fake it;
qualify/remove the claim and record the limitation. If a policy source (GTT,
cgroup) is unavailable, fail safe to STREAM and document the basis.

---

## 7. Evidence bundle — `audit/evidence/G4/7D/`

```
env.txt  parent-sha.txt  candidate-sha.txt  diffstat.txt
red.log            # new memory/KV tests fail on parent 8426ec6 (or the brief base)
green.log          # same tests pass on candidate
eviction.log       # fadvise/pageout/fallback probes
residency.log      # AUTO/PIN/STREAM decisions + RSS/page-cache/GTT measurements
kv-hardening.log   # cgroup, full disk, symlink, block_count, duplicates
leak.log           # 1000x open/close fd/mmap counts
exception.log      # live-view/ctor/close exception preservation
compat-memory.md   # policy/limits/claims matrix
cpu-lane.log  gpu-lane.log  cpu-only.log
claims.log  canary.log
qaqc-probes/
notes.md
```

See `audit/evidence/G4/7D/README.md` for the contract.

---

## 8. Stop / handoff

Stop at G4. Do not start 7E. Do not merge to `vibe/phase7-220201`; the auditor
merges only after G4 is signed. 7F owns real 70B/8-hour/benchmark evidence; 7D
must not claim it.

---

## 9. Start-here checklist

1. `git switch wp/7D-memory-robustness` (from the brief commit); confirm HEAD.
2. Read §0; reproduce the current `MADV_DONTNEED`/cache_weights behavior and
   the KV/close defects on the parent.
3. Record the host budget sources (`/proc/meminfo`, GTT sysfs, cgroup; note
   which are available).
4. Implement 7D-1/7D-2 first; add the red tests and policy probes.
5. Implement 7D-3 hardening; update the existing KV mmap tests for
   unlink-before-map.
6. Update 7D-4 claims/docs; run claims + canaries.
7. Run the full battery; assemble the G4 evidence bundle; stop for QAQC.
