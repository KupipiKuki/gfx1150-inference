# AUDIT 7D (G4) — Memory honesty & robustness

**Auditor:** DeepSeek V4.1 Flash (primary auditor)
**Date:** 2026-11-07 · **Revised:** 2026-11-07 after the G4 rework
**Gate:** G4 (Phase 7D memory honesty & robustness)
**Target:** `wp/7D-memory-robustness` @ `09b934d` (rework work `a380003`; evidence `a4ad1de`/`09b934d`; initial work `c9c484a`; audit base `1ad01c9`; parent `003f4e5`)
**Brief:** `PHASE7_7D_MEMORY_ROBUSTNESS_BRIEF.md`; **contract:** `audit/evidence/G4/7D/README.md`
**QAQC:** `audit/QAQC_7D_DEEP_2026-11-07.md` (initial) and `audit/QAQC_7D_REWORK_2026-11-07.md` (rework)

---

## 1. Verdict

**G4: PASS — SIGNED after the rework.**

The implementation is correct and the evidence is strong: eviction is
fadvise-primary with a documented PTE-drop enabler, the AUTO/PIN/STREAM policy
is real and measured, KV/cgroup/disk/block-count/duplicate/leak/exception
hardening is in place, and the memory claims are honest.

The initial review found two Low production defects; both are fixed in
`a380003` and independently verified in the rework. The PTE-drop enabler design
(QAQC-7D-3) is accepted by adjudication; see §4.

- **BLOCKER-7D-1 — CLOSED:** negative `block_count` is now rejected with
  `ValueError("Invalid <arch>.block_count -1: must be >= 0")`; tests cover
  zero-tensor and with-tensor forms.
- **BLOCKER-7D-2 — CLOSED:** the engine no-source AUTO path now passes
  `weight_budget=None`, emits `NoBudgetFallbackWarning`, selects STREAM, and
  records “no readable source” rather than a fabricated 0-byte budget.

---

## 2. Blockers

### BLOCKER-7D-1 (Low) — negative `block_count` accepted with zero layer tensors — **CLOSED in `a380003`**

**Repro (auditor):**

```python
# GGUF metadata: general.architecture="llama", llama.block_count=INT32(-1), no tensors
ws = WeightStreamer(path)
# ACCEPTED, ws.num_layers == -1
```

Root cause: `_cross_check_block_count` compares `found != list(range(declared_count))`.
For `declared_count = -1`, `range(-1)` is empty; with no `blk.*` tensors,
`found == []`, so the mismatch check passes and `-1` is returned.

**Required fix** (`src/weight_loader.py`):

```python
if declared_count < 0:
    raise ValueError(
        f"Invalid {arch}.block_count {declared_count}: must be >= 0"
    )
```

Add a test to `tests/test_memory_residency.py`: INT32 `-1` with zero
`blk.*` tensors → `ValueError`; keep the existing 999-vs-2 test.

### BLOCKER-7D-2 (Low) — engine no-source AUTO invents a 0-byte budget — **CLOSED in `a380003`**

**Repro (auditor):** monkeypatch `inference.read_budget_sources` to return an
empty `BudgetSources()` and construct:

```python
eng = LlamaInferenceEngine(model, max_seq_len=8, offload_kv_to_cpu=True,
                           residency="auto")
# effective = STREAM (safe)
# origin    = "measured sources: none"
# decision.weight_budget = 0
# reason    = "AUTO: weight bytes (19264) exceed the budget (0); streaming"
# warnings  = []          # no NoBudgetFallbackWarning
```

This is safe in behavior but contradicts the documented policy (“AUTO never
invents a budget — with no readable source it fails safe to STREAM” with a
`NoBudgetFallbackWarning`). It also makes the decision reason claim a 0-byte
budget that was never measured.

**Required fix** (`src/inference.py::_apply_residency_policy`): when
`self.weight_budget.available_bytes is None`, pass `weight_budget=None` to
`decide_residency` (not `weight_budget.weight_budget`, which is 0). Keep the
`sources` argument so the warning names the sources. Add an engine-level test
with an empty `BudgetSources()`:

- `pytest.warns(NoBudgetFallbackWarning)`;
- `eng.residency_decision.effective == STREAM`;
- `eng.residency_decision.weight_budget is None`;
- the reason says “no readable source”, not “budget 0”.

Fix `tests/test_memory_residency.py::TestEngineResidency` (or a new test); do
not weaken the existing override tests.

**Auditor probe:** `audit/evidence/G4/7D/audit-probes/rework_probes.py` (current
result **exit 1**: both defects reproduce; after the fixes it must exit 0),
transcript `rework-probes.log`.

### Rework closure (2026-11-07)

- `audit/evidence/G4/7D/audit-probes/rework_probes.py` → **exit 0**:
  negative `block_count` rejected; engine no-source AUTO emits
  `NoBudgetFallbackWarning`, STREAM, `weight_budget=None`.
- `rework-red.log` shows the three new tests failing at the pre-fix tip
  `1ad01c9`; `rework-green.log` shows 42/42 7D tests on `a380003`.
- Full battery on `09b934d`: CPU **506 passed**, GPU **34 passed**, 7D suite
  **42 passed**, `test_cpu_only` **12/12** both modes, claims **PASS**
  (8 baselined), canaries **12/12**, QAQC `mem_probes`/`kv_probes` **exit 0**.
- CI on `09b934d`: CPU `42411098057` **success**, Clean-Clone `42411097747`
  **success**.
- Scope: the rework touches only `src/weight_loader.py`, `src/inference.py`,
  `tests/test_memory_residency.py` (+ evidence); the forbidden set is empty.
- QAQC rework report: `audit/QAQC_7D_REWORK_2026-11-07.md` — no open findings,
  recommends signoff.

---

## 3. What passed

| Check | Result |
|---|---|
| CPU lane | **506 passed / 34 deselected** |
| GPU lane | **34 passed / 506 deselected** (real gfx1150 extension) |
| 7D suite | **42 passed** |
| `test_cpu_only.py` / `-O` | **12/12 / 12/12** |
| Claims checker | **PASS** — 0 new / 8 baselined / 0 expired / 0 findings |
| Canaries | **12/12 PASS** (`EXPECTED_BASELINE_ENTRIES = 6`) |
| CI `09b934d` | CPU `42411098057` success; Clean-Clone `42411097747` success |
| Auditor rework probe | **exit 0** — negative `block_count` rejected; no-source AUTO warns/STREAM/`weight_budget=None` |
| Red on parent `003f4e5` | 7D suite collection error (`memory_budget` absent) + defect probes (no policy, 0 fadvise calls, 999-vs-2 accepted, DONTNEED-only re-touch majflt=0) |
| Eviction | STREAM: fadvise DONTNEED counted/aligned; PIN: 0 calls; missing fadvise+PAGEOUT → one `EvictionFallbackWarning`, no crash; failing fadvise → warned |
| RSS/page-cache | synthetic 64 MiB: PIN dRSS ≈ +65.5 MB, warm re-touch majflt=0; STREAM dRSS=0, re-touch majflt>0 |
| Budget sources | GTT sysfs, `MemAvailable`, cgroup v2/v1 (fake trees + real `systemd-run --user` probe); KV over-budget refused with sources named |
| KV hardening | user/cgroup refusal, full-disk refusal before file creation, symlink rejected, unlink-before-map, duplicate names, block_count 999-vs-2, alignment/truncation |
| Cleanup | live-view close warns + fd closed; engine ctor original exception preserved; 1,100× streamer / 1,000× KV leak probe stable |
| Claims/docs | row 14 REMOVED; 18/19/20/30 qualified in place; row 21 VERIFIED for the fadvise+PTE-drop mechanism; no 70B/8-hour/GTT-pinning claims; baseline 14→6 with canary count updated |
| Scope | work commit touches allowed files; `src/layer.py` is docstring-only (QAQC-7D-2 accepted); no parser/kernels/bindings/CMake/CI changes |

The QAQC probes (`mem_probes.py`, `kv_probes.py`) reproduce the bundle’s
eviction/residency/KV/leak/exception results. CI is green on the reworked
candidate; the two Low fixes are closed.

---

## 4. Adjudication — QAQC-7D-3 (`MADV_DONTNEED` as PTE-drop enabler)

**Accepted, with rationale.** On this host `mmap.MADV_PAGEOUT` is absent.
`posix_fadvise(POSIX_FADV_DONTNEED)` alone is inert for pages still mapped by
the process: the kernel will not reclaim mapped file pages for an advice-only
hint. Dropping the mapping's PTEs first (via `MADV_PAGEOUT` where available,
else `MADV_DONTNEED`) allows the fadvise to act; the pages re-fault from the
file on next use. This is not data loss and is not presented as page-cache
eviction.

The brief’s “fallback-only when neither fadvise nor PAGEOUT exists” wording was
too narrow; the implementation’s enabler ordering is the correct mechanism and
is accurately documented in README/PLAN/claims (DONTNEED = PTE drop; fadvise =
primary page-cache hint). The audit records this as an explicit design
adjudication; no code change is required. The brief/handoff should cite this
adjudication so a future reviewer does not mistake it for a hidden fallback.

---

## 5. QAQC findings disposition

| Finding | Disposition |
|---|---|
| QAQC-7D-1 negative block_count | **Closed** — BLOCKER-7D-1 fixed in `a380003`; explicit negative guard + two tests; auditor rework probe exit 0 |
| QAQC-7D-2 `src/layer.py` docstring-only | **Accepted** (docs-adjacent, no behavior change); no revert required |
| QAQC-7D-3 DONTNEED enabler | **Accepted** with the §4 adjudication |
| QAQC-7D-4 transcribed cgroup log | **Accepted**; raw QAQC probe log supersedes it |
| QAQC-7D-5 red log granularity | **Accepted**; module-level collection error is the honest red |
| QAQC-7D-6 README usage flags | **Optional QF**; add the new flags to the usage block if convenient |
| QAQC-7D-7 no GPU residency test | **Accepted**; no GTT pinning is claimed, so no GPU residency assertion is required |
| QAQC-7D-8 untracked `7c/` | Not part of the branch; leave untouched |

**Additional audit QFs (non-blocking):**

- Ledger rows 10–12 prose still cite old README line numbers (L147/L148/L150/L151)
  while the scope sites correctly point at L149/L150/L152/L153. Claims checker
  passes; refresh the prose at the next docs touch.
- The engine no-source fix is implemented and asserted in
  `test_engine_auto_without_sources_warns_and_streams`; `residency_decision_origin`
  remains “measured sources: none” and the reason names the no-source fallback.

---

## 6. Gate impact

- **G4:** **SIGNED.** 7D is accepted; merge `wp/7D-memory-robustness` into
  `vibe/phase7-220201`.
- **7E:** unblocked after this merge; 7E has its own G5 gate.
- **7F-2/7F-3/7F-4:** real 70B/8-hour/benchmark evidence remains outside 7D.
- **Release/G6:** still gated by 7E/7F and the GPU runner (C-G1-3); no 7D
  blocker remains.
- **CI:** green on `09b934d`; keep the merge green.
- **Branch:** `wp/7D-memory-robustness` @ `09b934d` (work `a380003` + evidence)
  is the accepted 7D branch.

---

## 7. Sign-off

**7D decision: PASS — G4 SIGNED.** The memory honesty/robustness work is
accepted: both Low rework defects are fixed and independently verified, the
PTE-drop enabler design is accepted by adjudication, all lanes/claims/canaries
and CI are green, and the memory claims are honest. No open G4 blocker remains.

**Signed:** DeepSeek V4.1 Flash, primary auditor — 2026-11-07.
