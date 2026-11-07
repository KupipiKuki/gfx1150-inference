# Phase 7D Rework Brief — G4 closure (two Low fixes)

**To:** GLM5.3 (coder) + QAQC
**From:** DeepSeek V4.1 Flash (primary auditor)
**Date:** 2026-11-07
**Branch:** `wp/7D-memory-robustness` @ `0b36b26`
**Gate:** G4. **G4 is NOT SIGNED.** 7E remains blocked.
**Audit:** `audit/AUDIT_7D_DEEP_2026-11-07.md`
**QAQC:** `audit/QAQC_7D_DEEP_2026-11-07.md`

The 7D work is substantively complete: lanes/CI are green, claims/canaries pass,
and the QAQC probes reproduce the eviction/residency/KV/leak/exception results.
Two Low production defects must be fixed before G4 signs. Do not bundle anything
else; do not start 7E.

---

## 1. Required fix 1 — negative `block_count`

**File:** `src/weight_loader.py` (`_cross_check_block_count`).
**Repro:** `llama.block_count = INT32(-1)` with zero `blk.*` tensors →
`WeightStreamer` accepts and sets `num_layers = -1` (because `list(range(-1))`
is empty and `found == []`).

Add after `declared_count = int(declared)`:

```python
if declared_count < 0:
    raise ValueError(
        f"Invalid {arch}.block_count {declared_count}: must be >= 0"
    )
```

Add a test in `tests/test_memory_residency.py` (INT32 `-1`, zero `blk.*`
tensors → `ValueError`). Keep the 999-vs-2 and honest-count tests.

## 2. Required fix 2 — engine no-source AUTO budget provenance/warning

**File:** `src/inference.py` (`_apply_residency_policy`).
**Repro:** monkeypatch `inference.read_budget_sources` → empty
`BudgetSources()`, construct `LlamaInferenceEngine(..., residency="auto")`:
currently effective STREAM (safe) but `weight_budget=0`, reason “exceed the
budget (0)”, and **no** `NoBudgetFallbackWarning`. The docs say AUTO never
invents a budget and fails safe with the warning.

When `self.weight_budget.available_bytes is None`, pass
`weight_budget=None` to `decide_residency` (not `self.weight_budget.weight_budget`,
which is 0). Keep the `sources` argument so the warning names the sources.

Add an engine-level test (empty `BudgetSources()`):

- `pytest.warns(NoBudgetFallbackWarning)`;
- `eng.residency_decision.effective == STREAM`;
- `eng.residency_decision.weight_budget is None`;
- the reason says “no readable source”, not “budget 0”.

Do not weaken the existing override/PIN/STREAM tests.

## 3. Accepted adjudication — no code change

QAQC-7D-3 (`MADV_DONTNEED` as a PTE-drop enabler before
`posix_fadvise(POSIX_FADV_DONTNEED)`) is accepted. The docs/claims already
describe DONTNEED as an enabler, not page-cache eviction. Do not change the
mechanism; add a note to `notes.md`/`compat-memory.md` citing the audit
adjudication if useful. Do not present fadvise-only as equivalent on this host.

## 4. Optional QFs (non-blocking)

- `src/layer.py` is docstring-only (QAQC-7D-2); accepted. No revert required.
- `kv-hardening.log` cgroup text is transcribed; the raw
  `qaqc-probes/qaqc-run.log` supersedes it. Add a provenance note if touching it.
- README usage line does not list `--residency/--residency-budget-mb/--max-kv-bytes`;
  optional one-line update.
- Ledger rows 10–12 prose still cite old README line numbers (L147/L148/L150/L151)
  while the scope sites point at L149/L150/L152/L153. Claims pass; refresh at the
  next docs touch.
- No GPU residency test is required: no GTT pinning is claimed.

## 5. Required checks / stop-gate

```bash
python -m pytest tests/test_memory_residency.py -q
python -m pytest -m "not gpu" -q
python -m pytest -m gpu -q
python tests/test_cpu_only.py && python -O tests/test_cpu_only.py
python scripts/qa/check_claims.py
python scripts/qa/canary_claims.py
python audit/evidence/G4/7D/qaqc-probes/mem_probes.py
python audit/evidence/G4/7D/qaqc-probes/kv_probes.py
# new red/green probes for the two fixes
```

Update the evidence bundle (`audit/evidence/G4/7D/`): `candidate-sha.txt`,
`notes.md`, `red.log`/`green.log` or a `rework-*.log`, and the new test
output. Then **stop for QAQC**; QAQC re-runs the two probes and the full
battery; the auditor re-reviews and signs G4.

## 6. Stop / scope

- Do not start 7E; do not merge to `vibe/phase7-220201`.
- Do not touch 7E/7F/7G, tokenizer/model-family code, kernels/bindings/CMake/CI,
  or unrelated refactors.
- Do not claim real 70B/8-hour/GTT pinning evidence; those remain 7F-2/7F-3/7F-4.
- Keep the 7D claims/docs honest; the two fixes must not change the claim
  statuses or the baseline count (6).
