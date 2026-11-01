# G0 Baseline Report — gfx1150-inference

**Package:** 7.0 — Baseline freeze and governance
**Gate:** G0
**Audit trace:** process prerequisite for all findings
**Branch:** `wp/7.0-baseline`
**Parent (tree under test):** `ea6dbeb1db990bc11d991f7f9940a113fd21efd1`
**Candidate:** see `candidate-sha.txt` (content commit; a metadata follow-up commit adds
`candidate-sha.txt` and `diffstat.txt`, since a commit cannot contain its own SHA)
**Host:** AMD Ryzen AI 9 HX 370 w/ Radeon 890M (`gfx1150`) · Linux Mint 22.3 · ROCm 10.1 (HIP 7.16.26385) · Python 3.14.10 · NumPy 2.5.3 · pybind11 3.1.0 · CMake 3.28.3
**Date:** 2026-11-01

---

## Verdict

**PASS WITH CONDITIONS.** The baseline is frozen, the tree is clean, all CPU and GPU suites
are green, the full sdist install succeeds on the target platform, the claims ledger has
been reconciled against the live public docs, and a manual GPU baseline is recorded. Two
conditions (below) are documentation/packaging defects that do not block 7A but must be
closed by 7A-5 and before release.

## Exit criteria (handoff §6, 7.0)

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | Baseline SHA recorded; tree clean | ✅ | `parent-sha.txt`, `candidate-sha.txt`, `diffstat.txt`, `gate-commands.log` |
| 2 | All suites green, or failures documented as known baseline defects | ✅ | `cpu-suite.log`, `gpu-suite.log` — 12/12 + 12/12 + 30 passed (CPU); 5/5 GPU suites exit 0 |
| 3 | Full sdist install succeeds on the target platform | ✅ | `sdist-install.log` — full HIP build in a clean venv, all 7 modules import, CLI works |
| 4 | Claims ledger exists and marks unverified claims | ✅ | `audit/CLAIMS_LEDGER.md` (30 rows), `claims-check.log` |
| 5 | Manual GPU baseline recorded with environment and logs | ✅ | `env.txt`, `build.log`, `gpu-suite.log`, `gate-commands.log` |
| 6 | Auditor signs the baseline report | ✅ | this document |

## Stop condition (§6, 7.0)

> "If any previously green suite is red, do not start 7A."

**Not triggered.** Every suite that was green at the 2026-11-01 verification is green at
G0. No regression was found.

---

## Tasks completed (§6, 7.0)

1. ✅ **Commit or park the 2026-11-01 verification changes; record the exact baseline SHA.**
   Already committed — the `setup.py` pybind11 fix and the documentation pass are in
   `cca793e`, inside the merge `089ed8e` (PR #7). Nothing needed parking. Baseline tree
   under test: `ea6dbeb`. Full commit chain in `notes.md` §1.
2. ✅ **Confirm `git status --porcelain` is empty.** Empty at package start and at the
   candidate.
3. ✅ **Record environment and GPU (`rocminfo`).** `env.txt` — kernel, OS, ROCm/HIP/AMD
   clang versions, `rocminfo` GPU agents, CMake/gcc/Python/NumPy/pybind11/pytest/
   hypothesis versions, CPU, memory, storage, `git rev-parse HEAD`.
4. ✅ **Build from a clean directory; record configure/build logs.** `build.log` — a fresh
   build dir outside the repo, Attempt 1 (documented command) and Attempt 2 (with
   `pybind11_DIR`). Attempt 1 **fails**; see condition C-1.
5. ✅ **Run the CPU suite (normal + `-O`) and all five GPU suites; record results.**
   `cpu-suite.log`, `gpu-suite.log`. Also `pytest -m "not gpu"` → 30 passed.
6. ✅ **Build the sdist and perform a full `pip install` from it in a clean venv.** PASS —
   full HIP build, not only `GFX1150_SKIP_CMAKE=1`. `sdist-install.log`.
7. ✅ **Confirm the `tests/fixtures/PROVENANCE.md` registry and the `audit/evidence/`
   layout.** Both present and correct; the fixture registry is legitimately empty at
   baseline (7A-3 populates it). `notes.md` §7.
8. ✅ **Review and update the seeded claims ledger with every current README/audit claim
   and its evidence status.** Ledger expanded 17 → 30 rows with four classes of defect
   corrected. `claims-check.log`, `notes.md` §6.
9. ✅ **Record the GPU baseline manually on the gfx1150 host.** `env.txt` + `build.log` +
   `gpu-suite.log` + `gate-commands.log`. No CI runner is required or used at G0.

---

## Conditions (non-blocking, with owner and target)

### C-1 — The README's documented build command fails on a clean checkout
**Owner: 7A-5 · Target: G1**

`README.md` documents `cmake -B build -DCMAKE_BUILD_TYPE=Release`, which fails at
`CMakeLists.txt:17` with "Could not find a package configuration file provided by
pybind11". `setup.py` works only because it passes `-Dpybind11_DIR` explicitly. This is
audit **B-3**, still open, and it is a first-time-user-affecting documentation defect.
7.0 cannot fix it (no source/build changes allowed at this gate).

### C-2 — Four published performance figures do not reproduce
**Owner: 7F-3 · Target: G6**

1.12 TFLOPS → 1.02; 983.4 tok/s → 849.3; 0.50 ms → 0.75 ms; 2.76 ms → 1.00 ms. The E2E
throughput figure has now taken three different values across three runs of the same
synthetic test. Recorded as `UNVERIFIED` (ledger IDs 26–29). Must be re-recorded with a
warm-up + ≥20-iteration median/p95 harness, or removed. Deliberately **not** added to the
ratchet baseline — the correct outcome is deletion.

---

## Governance notes for 7A

- **`audit/claims_baseline.txt` must gain entries at 7A-6** for the nine ledger rows whose
  qualification flag is `no` (IDs 13, 14, 18, 19, 20, 26, 27, 28, 29, 30), plus the two
  new candidates recorded in the ledger (ID 6 / README / `Q4_K_M`; ID 10 / README /
  `qwen2`). Every entry targets G6.
- **The sdist-install CI job (7A-5) should import the three CPU modules**
  (`gguf_parser`, `tokenizer`, `weight_loader`) and assert that `kv_cache`, `layer`, and
  `inference` raise the actionable `ImportError` without `matmul_module` — that is the
  designed CPU-only surface, per `test_cpu_only.py` V-3/G-1.
- **`check_claims.py` (7A-6) must parse the ledger table robustly**: the ratchet
  sub-table below the main ledger also starts with `|`, and escaped `|` characters inside
  a cell break naive column splits. The G0 manual checker (`claims-check.log`) parses by
  anchoring on the `| ID | Claim |` header and stopping at the first non-table line.
- **The G0 baseline software version is ROCm 10.1, not the ROCm 7.0.0 recorded in
  `audit/VERIFICATION_2026-11-01.md` §1.** Later gates must cite `env.txt` as the
  authoritative baseline software version and treat the verification doc as historical.
- **Performance comparisons against the 2026-11-01 figures are not valid across ROCm
  versions.** This applies to 7F-3's benchmark baseline.

---

## Baseline reference values (measured at G0)

Use these as the comparison basis for every later gate.

| Metric | G0 baseline |
|---|---|
| FP16 matmul 1024³ | max err `6.1e-5`, 1.02 TFLOPS, 2.1 ms |
| Fused Q4_0 matmul M=1 N=4096 K=4096 | max err `3.1e-5`, 0.75 ms, 12.6 GB/s |
| Fused Q4_K matmul 1×1024×8192 (70B dim) | max err `1.95e-3`, 1.00 ms |
| 2-layer synthetic E2E | 849.3 tok/s (decode 866.5 tok/s) |
| CLI single-prompt E2E | 90.03 tok/s (decode 107.26 tok/s), 4 tokens in 0.04 s |
| `TILE_M=4` vs `M=1` prefill | bit-identical (Q4_0, Q8_0, Q4_K) |
| `matmul_module.so` | 592,488 bytes, sha256 `c8f6b19b9baca6ee6c9f8da1ac5788dda1049d2311294b62fb46670a281b0a03` |
| sdist | `gfx1150_inference-0.6.1.tar.gz`, sha256 `af75cb09d9ef9af62c0b05d20e2878e52794ba7cae1b4551b0c4855b075d6bc7` |

---

## Auditor decision

**Decision: APPROVE**

The G0 gate is satisfied. The baseline is frozen at the recorded candidate SHA, the tree
is clean, all suites are green, the full sdist install is verified on the target
platform, the claims ledger is reconciled and machine-checkable, and a manual GPU baseline
is recorded with environment and logs. C-1 and C-2 are carried forward with owners and
targets and do not block the start of 7A.

**Next work package authorized:** 7A-1 (pytest harness), 7A-6 (claims checker),
7A-7 (GPU workflow scaffold) — these three are independent and unblock the rest of 7A
(handoff §14.3).

**Not authorized:** 7B. 7B is gated by G1 and by the 7A-3 goldens.

**Claims ledger updated:** yes — `audit/CLAIMS_LEDGER.md`, 17 → 30 rows.

**Sign-off:** Auditor (this role), 2026-11-01.

> Independence note (handoff §1): this baseline was executed and signed by the same role
> that owns the gate decisions. It is therefore **self-tested**, not independently tested.
> QAQC must re-run G0 from a clean clone — at minimum the five GPU suites, the CPU suite
> under `-O`, and the full sdist install — before 7A-1 is merged, and record the result in
> `audit/evidence/G0/7.0-baseline/qaqc-probes/`. The `--strict` claims check and the
> ledger's own status values should also be spot-checked against the live documents.
