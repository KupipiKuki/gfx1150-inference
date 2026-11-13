# Independent 7A-8 Audit — Clean-Clone Build Entry Point (G0 C-1)

**Auditor:** DeepSeek V4.1 Flash (independent of the coder and QAQC)
**Date:** 2026-11-02
**Target:** `wp/7A-8-build-entrypoint` @ `abc5870` (work candidate `9c04912`)
**Parent:** `4bcffeb` (branch base)
**Coder:** GLM5.3 · **QAQC:** independent session (`qaqc-probes/qaqc-report.md`)
**Scope:** 7A-8 only. **G1 remains unsigned.**

---

## 1. Verdict

**PASS WITH CONDITIONS — G0 C-1 is closed in substance.**

The documented `cmake -B build -DCMAKE_BUILD_TYPE=Release` now works from a fresh clone
with no ambient `pybind11_DIR` and no cache. I reproduced the red/green pair on this host,
including the environment-dependent "lucky PATH" case, the explicit `-Dpybind11_DIR`
override, the parent-fails guard, the 43/18/61 suites, and the QF-2 merge drift. The
scope is clean.

One condition blocks the "CI reproduces it" acceptance: **QF-1** — the committed
`ci-build.yml` smoke-test step runs `python -m pytest`, but the job never installs
pytest, so it will fail on its first run. **QF-2** is a merge-time ledger refresh, not a
defect on this branch. The multi-gigabyte per-push ROCm install is an open cost decision
for G1.

---

## 2. Reproduction

| Probe | Result |
|---|---|
| **Parent red**, fresh clone, no `pybind11_DIR`, shims PATH | **exit 1** at `CMakeLists.txt:17`, pybind11 not found |
| **Parent "lucky"**, interpreter bin on PATH | **exit 0** — the environment dependence is real |
| **Candidate green**, fresh clone, no `pybind11_DIR`, shims PATH | **exit 0** — `pybind11 CMake package: <site-packages>` marker |
| Candidate with interpreter bin on PATH | exit 0, explicit marker |
| Candidate with explicit `-Dpybind11_DIR=...` | exit 0, explicit marker (override wins) |
| `cmake --build` | exit 0, `matmul_module.so` 592,488 bytes |
| Guard on the parent's `CMakeLists.txt` | **fails** — discovery marker absent |
| Guard on the candidate | **3/3 pass** |
| `pytest -m "not gpu"` | **43 passed, 18 deselected** |
| `pytest -m gpu` | **18 passed, 43 deselected** |
| `pytest -q` | **61 passed** |
| `test_cpu_only.py` / `-O` | 12/12 each |
| Sdist full install (QAQC, live) | exit 0, 7 modules import, CLI works |
| Keyring fingerprint | `D0F004A0025A1145C7807FCD0701EAC4D5E02107` — matches this host |
| Restricted surfaces | `setup.py`, `pyproject.toml`, `MANIFEST.in`, `src/`, `scripts/qa/**`, ledger, baseline, 7A-6 evidence: **empty diff** |
| YAML | `ci-build.yml` valid, 10 steps, `ubuntu-24.04` |

The `CMakeLists.txt` discovery-before-`project()` choice is accepted: ROCm paths are still
set before `project()`, and the guard/CI can exercise the pybind11 fix without ROCm. The
status marker is what makes the guard non-tautological.

---

## 3. Conditions and notes

### QF-1 (Condition, blocks CI acceptance) — `ci-build.yml` lacks pytest

The job installs `numpy`, `setuptools`, `wheel`, `pybind11` and then runs:

```yaml
- name: Run the configure smoke test
  run: python -m pytest tests/test_build_configure.py -v
```

`actions/setup-python` does not ship pytest, and the prerequisites step does not install
it. The job will fail with `No module named pytest` on its first run. This does not
affect the build fix or the local tests; it blocks only the "CI reproduces it"
acceptance.

**Required (C-7A8-1):** add `pytest` to the prerequisites step, push, and record **one
green run** of `ci-build.yml` (or an equivalent run log). That is the only way to
demonstrate the CI acceptance rather than design it.

### QF-2 (Merge note for G1) — README shift moves the 7A-6 ledger references

I simulated the merge with `vibe/phase7-220201` (`43642b5`) in a throw-away worktree. The
merge is clean, and `check_claims.py` exits **0** with **9 drift warnings** (0 stale-scope,
0 findings):

| Claim | Old README line | Merged line |
|---|---|---|
| 8, 9 (qualified) | 111 | 130 |
| 10, 11, 12 (109/110 sites) | 110, 111 | 129, 130 |
| 21 | 104 | 123 |

The ID-3 locator block moves from **L85–L89 to L98–L102**. The `id3_claim_removed` canary
is line-independent and survives. This is the checker's designed drift behavior, not a
failure, but the ledger prose/scope annotations should be refreshed at merge time so the
warnings return to zero.

**Required (C-7A8-2, merge owner):** at the 7A-8 merge, refresh the nine README scope
references (+19) and the ID-3 prose (L85–L89 → L98–L102), then re-run
`check_claims.py` and require zero drift warnings. This is a G1 merge-checklist item.

### Observation — ROCm install cost

`ci-build.yml` installs ROCm from AMD's stable apt repository on every push/PR, a
multi-gigabyte download. It is honestly disclosed. The auditor's ruling for G1: accept
it for now **or** narrow the hosted job to the configure-only check and move the full
build to the self-hosted gfx1150 runner (7A-7/7F-1). Not a 7A-8 condition.

---

## 4. Gate impact

- **G0 C-1:** closed in substance by the build fix.
- **7A-8:** not merge-approved until C-7A8-1 lands (pytest + one green run). QF-2 is
  applied at merge.
- **7A-7/7A-6/7A-5:** unaffected.
- **G1:** unsigned — 7A-2..7A-5, 7A-7 and C-7A8-1 remain; C-7A1-5/6 carry.
- **7B:** blocked until G1 and the 7A-3 goldens.

---

## 5. Sign-off

**7A-8 decision: PASS WITH CONDITIONS.** The build fix is real and verified; the CI
dependency and the merge-time ledger refresh are the remaining bookkeeping.

**Sign-off:** DeepSeek V4.1 Flash, 2026-11-02.
