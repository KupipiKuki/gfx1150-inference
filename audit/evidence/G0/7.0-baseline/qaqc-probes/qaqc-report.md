# QAQC Report — Gate G0 (7.0 Baseline freeze and governance)

**Role:** QAQC (independent re-run per handoff §1 and the G0 baseline report's independence note)
**Date:** 2026-11-01
**Tree tested:** candidate `04e47dc81a9d3b155ef6ca6700a220abec32a1c1` (content commit; runtime surface verified byte-identical from parent `ea6dbeb` through branch tip `bbef1b6`)
**Method:** fresh `git clone` to `/tmp/opencode/qaqc-g0/clone` (no in-tree `build/`, no `dist/`, no cached state), fresh out-of-repo CMake build dir, two fresh venvs
**Probes:** `probe-commands.log` (full transcript, exit codes), `claims-spotcheck.log` (ledger verification)

---

## Verdict

**PASS WITH CONDITIONS.** Every G0 runtime and process claim independently reproduces from a
clean clone on the same gfx1150 host. The frozen baseline (suites, sdist install path,
CPU-only surface, claims ledger) is **confirmed**. However, the evidence bundle itself
carries documentation-integrity defects — most seriously a **one-character corruption of
the parent SHA in the signed report** — that must be corrected in a small follow-up commit
(inside 7.0's allowed file set) **before 7A-1 merges**. No gate re-run is required: the
underlying facts are unchanged and are what this QAQC reproduced.

Per handoff §1, the G0 execution's status is hereby upgraded from *self-tested* to
**self-tested, independently re-run**.

---

## Required re-runs — all reproduced

| # | Probe | G0 claim | QAQC result |
|---|---|---|---|
| 1 | CPU suite `python3 tests/test_cpu_only.py` | 12/12, exit 0 | **12/12 OK, exit 0** |
| 2 | CPU suite `-O` | 12/12, exit 0 | **12/12 OK, exit 0** |
| 3 | `pytest -m "not gpu"` | 30 passed | **30 passed, 14 warnings, exit 0** (needs the built extension importable — see F-6) |
| 4 | GPU `test_matmul.py` | exit 0 | **exit 0**; max_err `6.1e-5` identical |
| 5 | GPU `test_gguf_and_q4.py` | exit 0 | **exit 0**; max_err `3.1e-5` identical |
| 6 | GPU `test_layer.py` | exit 0 | **exit 0**; all max_err identical |
| 7 | GPU `test_full_model.py` | exit 0, 849.3 tok/s | **exit 0**; identical generated text `t ROCmt cr is gfx1150 ROCmD`; 818.6 tok/s (see F-7) |
| 8 | GPU `test_phase5_scale.py` | exit 0 | **exit 0**; `TILE_M=4` bit-identical, `device_bytes=0` both offload modes, CLI exit 0 |
| 9 | sdist + full clean-venv `pip install --no-build-isolation` | exit 0, real HIP build | **exit 0, real HIP build** |
| 10 | 7 modules import in full venv | all 7 | **all 7 import** |
| 11 | `gfx1150-infer --help` | works | **exit 0** |
| 12 | Installed CPU suite (full venv) | 12/12 | **12/12 OK** |
| 13 | CPU-only venv (`GFX1150_SKIP_CMAKE=1`) | 3 import / 3 raise | **`gguf_parser`/`tokenizer`/`weight_loader` import; `kv_cache`/`layer`/`inference` raise the actionable ImportError** |
| 14 | Installed CPU suite (cpu-only venv) | 12/12 | **12/12 OK** |
| 15 | Claims ledger review | 30 rows, literals resolve, VERIFIED paths exist | **confirmed — see `claims-spotcheck.log`** |
| 16 | README build command (condition C-1) | fails at `CMakeLists.txt:17` | **REPRODUCED — exit 1, identical pybind11 error** |
| 17 | Restricted-path diff (no src/test/packaging change) | empty | **empty for `ea6dbeb..04e47dc` and `ea6dbeb..bbef1b6`** |
| 18 | Tree clean at candidate | clean | **clean (0 dirty entries in clone; clean at tip)** |

Additional verifications: handoff §6 exit criteria match the report's table one-for-one;
`git diff --stat 9b2deb0..ea6dbeb` matches `diffstat.txt` exactly (11 files, +1022/−31);
fixtures registry is legitimately empty (7A-3 populates it); `scripts/qa/check_claims.py`
and `ci-gpu.yml` correctly absent at baseline; `audit/evidence/G0/README.md` was updated as
claimed; the ROCm 10.1-vs-7.0.0 delta and the three distinct E2E values
(788.6 / 849.3 / 983.4) are real; the ledger's seeded-defect narrative (broken literals,
phantom qualification quotes, phantom rows 15–17, 13 uncovered claims) verifies against
the parent tree.

---

## Findings — defects in the G0 evidence bundle

### F-1 (Major — required correction) Corrupted parent SHA in three signed files
`baseline-report.md` L7, `notes.md` L6, and `diffstat.txt` L2 record the parent as
`ea6dbeb1db990bc11d991f7f9940a113fd21efd1`. The true SHA is
**`ea6dbeb1db290bc11d991f7f9940a113fd21efd1`** (position 11: `2`, not `9` — verified via
`git rev-parse`, and recorded correctly in `env.txt`, `parent-sha.txt`, `gate-commands.log`,
`build.log`, `cpu-suite.log`, `gpu-suite.log`, `sdist-install.log`). The corrupted value
originates in the execution scratch file `/tmp/opencode/parent.txt`. The report/notes were
evidently written from that scratch value rather than from live git output. Since the
report is the document later gates are told to treat as authoritative, this must be fixed.
The short SHA `ea6dbeb` is correct everywhere, so the frozen baseline is not ambiguous.

### F-2 (Major — required correction) The sdist sha256 "reference value" is ambiguous and irreproducible
`baseline-report.md` cites sdist sha256 `af75cb09…d6bc7` (113,199 bytes — the artifact
built and installed in `sdist-install.log`), but `gate-commands.log` [11] records a
different artifact — `015bf7b4…78de`, 113,231 bytes, rebuilt at 17:37 — because
`gate-commands.log` re-ran `setup.py sdist` after the installs. At least **four** distinct
sdists were produced during the session (112,661 / 113,199 / 113,231 bytes in scratch, plus
this QAQC's 112,962 / `8e88db13…`). The artifact matching the report's reference hash was
overwritten mid-gate and no longer exists (`dist/` now holds the `015bf7b4` build).
sdists here are inherently non-reproducible (embedded mtimes). **Action:** drop the sdist
sha256 from the "baseline reference values" (or relabel it "hash of the artifact tested in
`sdist-install.log`, not a comparison basis") and annotate `gate-commands.log` [10]–[11]
that the rebuild changed the artifact.

### F-3 (Minor — fix in same correction commit) `notes.md` §1 commit-chain diagram misstates the DAG
The diagram places `cca793e` *after* the merge `089ed8e` and as `ea6dbeb`'s parent. In
reality `cca793e` is the head of the merged PR branch (second parent of `089ed8e`), and
`ea6dbeb`'s parent is `089ed8e` — as `env.txt` and the report itself state. The
remediation-commit ordering in the diagram is also inverted relative to the actual branch.

### F-4 (Minor — fix in same correction commit) "Nine rows" listed with ten IDs
`baseline-report.md` (governance notes) and `notes.md` §6 list IDs
**13, 14, 18, 19, 20, 26, 27, 28, 29, 30** as "the nine ledger rows whose qualification
flag is `no`". The ledger's actual `no`-flag rows are nine: **14, 18–20, 26–30**. ID 13's
flag is `partial` (PLAN L266 qualifies it; the unqualified L209 instance still warrants a
baseline entry, but the flag description is wrong). If 7A-6 builds
`audit/claims_baseline.txt` from the report's list verbatim, it will mis-handle ID 13.

### F-5 (Minor — fix in same correction commit) "Two commits" understates the package
`notes.md` says "Commit structure: two commits", but the package is three commits
(`04e47dc` content, `aff43b2` metadata, `bbef1b6` documentation fix-up — the third added the
very paragraph that says "two"). Cosmetic self-reference; state it as a content commit
plus follow-up metadata/documentation commits.

### F-6 (Observation → carry to 7A-1) The pytest record omits a build-artifact dependency
In a clean clone, bare `pytest -m "not gpu"` fails collection (4×
`ModuleNotFoundError: matmul_module`, exit 2). The G0 "30 passed" implicitly relied on the
**untracked in-tree `build/matmul_module.so`**, which `cpu-suite.log` does not mention —
the same in-tree artifact that masked audit B-3 (notes §3). With the build dir on
`PYTHONPATH`, the record reproduces exactly (30 passed / 14 warnings). 7A-1's
`pytest.importorskip` fixture must remove this dependency; the G0 record should note it.

### F-7 (Observation → strengthens C-2, carries to 7F-3) Reference-value reproducibility caveats
- `matmul_module.so` sha256 is **source-path-dependent**: two fresh builds from this
  clone were byte-identical (`9c14fd09…`, 592,488 bytes), but differ from the recorded
  `c8f6b19b…` because the build embeds source paths. The reference value holds only for
  builds from the original working-copy path; it is not clone-independent.
- Throughput is unstable even on the same host within minutes — matmul 1024³:
  **0.89 / 1.02 / 1.12 TFLOPS** across three runs (one of which *matches* the PLAN's
  published 1.12, underscoring that no single run is "the truth"); Q4_0 GEMV:
  0.48 / 0.65 / 0.75 ms; Q4_K 1×1024×8192: 1.00 / 1.28 ms; E2E: 818.6 / 849.3 / 852.0
  tok/s. **Correctness is perfectly stable** (identical max_err and identical generated
  text across every run, including G0's). This confirms C-2's premise and its disposition:
  delete or re-record the published figures with a warm-up + ≥20-iteration median/p95
  harness; do not baseline any single-run figure (including G0's).

---

## Conditions

| # | Condition | Owner | Due |
|---|---|---|---|
| QAQC-1 | Correction commit fixing F-1 (SHA in `baseline-report.md`, `notes.md`, `diffstat.txt`), F-2 (sdist sha256 reference + `gate-commands.log` annotation), F-3, F-4, F-5 — all inside the 7.0 allowed file set; no gate re-run needed. **Status: satisfied by the same commit that added this report and the probes** | 7.0 owner | before 7A-1 merges |
| QAQC-2 | F-6: pytest harness must collect without a pre-built extension (7A-1 fixture), and the G0 cpu-suite record should note the in-tree build dependency | 7A-1 | G1 |
| QAQC-3 | F-7 + C-2: re-record or delete published performance figures with statistical discipline; do not treat any single-run figure (G0's included) as a baseline | 7F-3 | G6 |

---

## Authorization status after QAQC

- The G0 baseline is **independently confirmed**: the exit criteria are met, the stop
  condition is not triggered, and every recorded result reproduces from a clean clone.
- **7A-1, 7A-6, 7A-7 may proceed once QAQC-1 lands** (a documentation-only correction; it
  cannot change any behaviour). **7B remains blocked** until G1 is signed and the 7A-3
  goldens exist.
- No re-freeze is required: `candidate-sha.txt` (`04e47dc`) is correct, and the QAQC-1
  correction commit is a bundle-records fix on top, exactly like the existing metadata
  follow-ups.

**QAQC sign-off:** 2026-11-01. Probes: `probe-commands.log`, `claims-spotcheck.log` (this
directory). Clone and scratch retained at `/tmp/opencode/qaqc-g0/` for inspection.
