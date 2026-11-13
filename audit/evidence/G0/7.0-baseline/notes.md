# G0 — Baseline notes

**Package:** 7.0 — Baseline freeze and governance
**Audit trace:** process prerequisite for all findings (handoff §6, 7.0)
**Branch:** `wp/7.0-baseline`
**Parent (tree under test):** `ea6dbeb1db290bc11d991f7f9940a113fd21efd1`
**Candidate (this package):** recorded in `candidate-sha.txt`
**Commit structure:** a content commit plus follow-up commits. The **content commit**
(`candidate-sha.txt`) holds the evidence bundle and the ledger corrections. A **metadata
follow-up** adds `candidate-sha.txt` and `diffstat.txt`, because a commit cannot contain
its own SHA; a **documentation follow-up** records the structure here and in the report;
the **QAQC-1 correction commit** applies the post-QAQC erratum. All are inside the 7.0
allowed file set and none touches `src/`.
**Host:** AMD Ryzen AI 9 HX 370 w/ Radeon 890M (gfx1150), Linux Mint 22.3, ROCm 10.1 (HIP 7.16.26385)

---

## 1. Baseline SHA and provenance

The 2026-11-01 verification changes are **already committed** — nothing needed to be parked.
The baseline tree under test is `ea6dbeb`, which sits on top of the `9b2deb0` audit
baseline and contains the `setup.py` pybind11-discovery fix plus the documentation pass.

```
(vibe/audit-remediation-220201, oldest -> newest)
adfb97c / 64b8a8d / 797076c / c75914b / 986d033 / f0b54e4  v0.6.x remediation + QAQC passes
  └─ 8038012  Fix CPU CI: install setuptools+wheel so test_v8 can build the sdist
     └─ 7cd9519  Reorganize audit reports into audit/
        └─ 9b2deb0  Deepseek Audit files added             <- audit baseline named in handoff §header
           └─ ead5f3f  DeepSeek review and phase7 implementation handoff   <- setup.py pybind11 fix
              └─ cca793e  revised documentation per QAQC comments
                 └─ 089ed8e  Merge PR #7 (vibe/audit-remediation-220201; second parent = cca793e)
                    └─ ea6dbeb  Scaffold audit/evidence/G0 baseline bundle  <- PARENT (tree under test)
                       └─ 04e47dc  7.0 G0 evidence bundle + ledger corrections  <- candidate
                          └─ aff43b2 / bbef1b6  metadata + documentation follow-ups
```

`cca793e` is the head of the PR branch merged at `089ed8e` (the merge's second parent),
and `ea6dbeb`'s parent is `089ed8e`. `ea6dbeb` was first created on `vibe/phase7-220201`
(hence its commit message); `wp/7.0-baseline` continues from it.

`git status --porcelain` was empty at the start of the package and is empty at the
candidate (verified in `gate-commands.log`).

**Note on the G0 README:** `audit/evidence/G0/README.md` still names `cca793e` as the
baseline SHA and says "Logs pending G0 execution". That file is stale and is superseded
by this bundle. Updating it is inside the 7.0 allowed file set
(`audit/evidence/G0/**`); the final candidate SHA is recorded in `candidate-sha.txt`.

---

## 2. Environment delta versus the 2026-11-01 verification

`audit/VERIFICATION_2026-11-01.md` §1 records ROCm **7.0.0**. The G0 host reports
ROCm **10.1** at `/opt/rocm` (symlink to `/opt/rocm/core-10.1`), HIP `7.16.26385-0000000`,
AMD clang `24.0.0git`. The HIP version string is identical to the verification record
(`7.16.26385`); the ROCm packaging differs.

This matters for two reasons:

1. **The verification doc's §1 ROCm value is no longer accurate for this host.** Any later
   gate that cites "ROCm 7.0.0" as the baseline software version is citing a host state
   that no longer exists. The G0 baseline software version is **ROCm 10.1 / HIP 7.16.26385 /
   AMD clang 24.0.0git / Python 3.14.10 / NumPy 2.5.3 / pybind11 3.1.0 / CMake 3.28.3**.
   `audit/VERIFICATION_2026-11-01.md` should be treated as a historical record, not as the
   current baseline; the authoritative baseline is `env.txt` in this bundle.
2. **Performance numbers are not comparable across the two ROCm versions.** This is
   directly relevant to the stale figures recorded in the claims ledger (IDs 26–29).

---

## 3. Build: one documented command fails (audit B-3 still open)

`README.md` §"Build, Install & Test" documents:

```bash
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j
```

On a **clean tree** this **fails**:

```
CMake Error at CMakeLists.txt:17 (find_package):
  Could not find a package configuration file provided by "pybind11"
```

`CMakeLists.txt:17` calls `find_package(pybind11 REQUIRED)` but never points CMake at
pybind11's config directory. The `setup.py` path works only because the `pybind11_DIR`
block (added in `ead5f3f`) explicitly passes
`-Dpybind11_DIR=<site-packages>/pybind11/share/cmake/pybind11`.
The in-tree `build/` directory in this working copy had a cached `pybind11_DIR` from an
earlier run, which masked the problem — exactly the failure mode B-3 describes.

**Not fixed here.** 7.0's allowed file set explicitly excludes source, build, and packaging
changes. Both attempts are recorded in `build.log` (Attempt 1 = documented command, fails;
Attempt 2 = with `pybind11_DIR`, succeeds and produces a 592 KB `matmul_module.so`).

**Action:** carry to **7A-8** (clean-clone build entry point, which owns
`CMakeLists.txt` and the README build section): either `CMakeLists.txt` gains a pybind11
discovery step, or the README build command is corrected to match what actually works,
with a fresh-clone CI test. Until then, **the README's build instructions do not work on a
clean checkout** — a first-time user following the README will hit the error. This is a
documentation defect in a public claim surface and should be treated as a release blocker
for the README, independent of the audit ID.

---

## 4. Suite results

All suites are green. Full logs in `cpu-suite.log` and `gpu-suite.log`.

| Suite | Command | Result |
|---|---|---|
| CPU (normal) | `python3 tests/test_cpu_only.py` | **12/12 OK**, exit 0 |
| CPU (`-O`) | `python3 -O tests/test_cpu_only.py` | **12/12 OK**, exit 0 |
| CPU (pytest) | `python3 -m pytest -m "not gpu" -q` | **30 passed**, exit 0 |
| GPU: matmul | `python3 tests/test_matmul.py` | exit 0 — 1024³ max err `6.1e-5`, 1.02 TFLOPS |
| GPU: GGUF+Q4 | `python3 tests/test_gguf_and_q4.py` | exit 0 — Q4_0 dequant exact; fused matmul max err ≤ `6.1e-5` |
| GPU: layer | `python3 tests/test_layer.py` | exit 0 — RMSNorm, RoPE (llama + NeoX), GQA, SwiGLU, E2E layer |
| GPU: full model | `python3 tests/test_full_model.py` | exit 0 — 2-layer E2E, 849.3 tok/s (decode 866.5) |
| GPU: phase5 scale | `python3 tests/test_phase5_scale.py` | exit 0 — Q8_0/Q4_K/Q6_K, 70B-dim `1×1024×8192` in 1.00 ms, `TILE_M=4` bit-identical |

No previously-green suite is red, so the §6 stop condition for 7.0 ("if any previously
green suite is red, do not start 7A") is **not** triggered.

### 4.1 Performance figures measured at G0 (baseline reference)

These are the *measured* baseline numbers on this host, for comparison against the
figures published in `IMPLEMENTATION_PLAN.md`:

| Published claim | Plan location | G0 measured | Delta |
|---|---|---|---|
| 1.12 TFLOPS | L45, L53, L261 | **1.02 TFLOPS** | −9% |
| 983.4 tok/s (decode 1107.9) | L209, L266 | **849.3 tok/s** (decode 866.5) | −14% |
| 0.50 ms @ 1×4096×4096 | L81 | **0.75 ms** | +50% |
| 2.76 ms @ 1×1024×8192 (Q4_K) | L178 | **1.00 ms** | −64% |
| — | — | 788.6 tok/s at verification 2026-11-01 | third distinct value for the same E2E test |

The E2E throughput figure has now been observed at **three different values**
(788.6 → 849.3 → 983.4 tok/s) for the same synthetic test. This is strong evidence that
these are single-run synthetic measurements with high run-to-run variance and no
statistical discipline. They are recorded as `UNVERIFIED` in the claims ledger (IDs 26–29)
and **must be re-recorded with a warm-up + ≥20-iteration median/p95 harness (7F-3) or
removed**. They were deliberately **not** added to `audit/claims_baseline.txt`: the correct
outcome is deletion, not tolerance.

---

## 5. sdist and install

Full log in `sdist-install.log`.

| Check | Result |
|---|---|
| `python3 setup.py sdist` | PASS — `gfx1150_inference-0.6.1.tar.gz` (sha256 `af75cb09…d6bc7` = the artifact tested below; sdists are not reproducible — see the report erratum) |
| sdist completeness | PASS — contains `CMakeLists.txt`, `MANIFEST.in`, all 6 `*.hip` + 6 `*.h`, `bindings.cpp`, all 6 `src/*.py`, all 6 test files |
| **Full** clean-venv `pip install --no-build-isolation` (real HIP/CMake build) | **PASS** — exit 0, real `matmul_module.so` built, all 7 modules import, CLI `gfx1150-infer --help` works |
| Installed CPU suite from the sdist | PASS — 12/12 |
| CPU-only clean-venv install (`GFX1150_SKIP_CMAKE=1`) | PASS — exit 0, 3 CPU modules import |
| Installed CPU suite from the CPU-only sdist | PASS — 12/12 |

The **full** install path (task 6's explicit requirement, and the gap B-1 called out) is
verified, not merely the `GFX1150_SKIP_CMAKE=1` path.

In the CPU-only venv, `kv_cache`, `layer`, and `inference` raise `ImportError` when
`matmul_module` is absent. This is **by design** — `test_cpu_only.py` V-3/G-1 asserts
exactly that behaviour. The CPU-only install therefore exposes three importable CPU
modules (`gguf_parser`, `tokenizer`, `weight_loader`). Recorded so 7A-5's sdist-install
CI job asserts the right thing: it should import the **three CPU modules**, not all six,
and should assert that the other three raise the actionable `ImportError`.

Minor observation: `pyproject.toml` declares `version = "0.6.1"` while the release line is
`v0.6.2` → `v0.7.0`. The sdist filename recorded in this bundle is therefore
`gfx1150_inference-0.6.1.tar.gz`. Version metadata is 7G scope (`__version__`, PEP 639);
noted here so the release checklist does not treat the filename as a surprise.

---

## 6. Claims ledger review (task 8)

The seeded ledger (`audit/CLAIMS_LEDGER.md`, 17 rows) was reviewed line-by-line against the
live `README.md` and `IMPLEMENTATION_PLAN.md`. Full report in `claims-check.log`.

**Four classes of defect were found and fixed:**

1. **Broken match literals.** Seeded row 4's literal (`` `Q4_0`, `Q4_K`, `Q8_0` ``) and row
   8's literal (`` `<|im_start|>` ``) do not appear verbatim in any public document — a
   checker scanning for them would never fire, so both claims were effectively unenforced.
   Row 8's literal also contained unescaped `|` characters that break Markdown table
   rendering and any naive column split. Both now use literals that resolve.
2. **Qualification flags did not match the prose.** The seeded table quoted qualification
   text ("tensor types; real-GGUF validation pending", "metadata resolves; model support
   not yet verified", …) that **does not exist anywhere** in the README. The README *does*
   qualify these claims inline, in different words. The flags and quotes now match reality.
3. **Rows 15–17 were phantom claims.** Their literals (`one synchronization per token`,
   `PEP 639`, `top-level module`) exist only in the handoff and audit reports, not in any
   public document. They are now marked *(no public literal)* — still tracked for their
   owning packages, but not treated as live unqualified public claims.
4. **Thirteen public claims had no ledger row at all.** A systematic scan of every
   assertive statement in README and PLAN found claims the seeded ledger did not cover —
   most importantly the 7B–70B scope (ID 18), the 8-hour runtime (ID 19), the Active RAM
   Cap table (ID 20), the `MADV_DONTNEED` mechanism (ID 21), and the four stale
   performance figures (IDs 26–29), plus the resident-RAM figure (ID 30).

**The ledger now has 30 rows** — 10 `VERIFIED`, 3 `PARTIAL`, 8 `NOT YET`, 9 `UNVERIFIED` —
and every literal resolves in a public document, with every `VERIFIED` row pointing at an
evidence path that exists on disk.

**Two new ratchet candidates** are recorded in the ledger's "G0 additions to the ratchet"
section for 7A-6 to land in `audit/claims_baseline.txt` (that file is owned by 7A-6):

- ID 6 / `README.md` / `Q4_K_M` — README L10 lists `Q4_K_M` in the project-goal sentence
  unqualified, while L108 scopes the verified release to `Q4_0`/`Q4_K`/`Q8_0`.
- ID 10 / `README.md` / `qwen2` — README L107 says "Supports … GPT-2 / Llama-3 / Qwen2
  byte-level … BPE vocabularies", which reads as a support claim; L108 qualifies it in
  the *next* bullet, but the handoff requires the qualifier in the *same* bullet.

Both are cheap to fix in wording and should leave the baseline as soon as 7B/7C rewrite
those bullets.

**Nine ledger rows have `Qualified in place? = no`** and therefore need either inline
qualification or an exact baseline entry: IDs 14, 18, 19, 20, 26, 27, 28, 29, 30. ID 13's
flag is `partial` (PLAN L266 qualifies the figure; **L209 is unqualified**), so its L209
instance also needs a baseline entry. 7A-6 must build `audit/claims_baseline.txt` from
this list; QAQC must reject any entry that hides a claim which could be fixed cheaply.

---

## 7. Evidence layout and fixture registry (task 7)

- `audit/evidence/README.md` — layout, rules, and the required-file list. Confirmed
  present. The G0 bundle path `audit/evidence/G0/7.0-baseline/` matches the documented
  layout exactly.
- `tests/fixtures/PROVENANCE.md` — the registry exists with the required field schema
  (`id`, `path`, `kind`, `source`, `command`, `input_sha256`, `output_sha256`, `license`,
  `notes`) and the required-field/size rules. The registry table is currently **empty**,
  marked "populated in 7A-3" — correct for the baseline, since no committed fixture
  exists yet. The five test files currently synthesize their GGUF data in-process rather
  than loading committed fixtures.

**Bundle completeness against `audit/evidence/README.md`:** the required-file list in §4 of
the handoff expects `env.txt`, `parent-sha.txt`, `candidate-sha.txt`, `diffstat.txt`,
`cpu-suite.log`, `gpu-suite.log`, `sdist-install.log`, `notes.md`. All present. G0 also
adds `build.log`, `gate-commands.log`, `claims-check.log`, and `baseline-report.md`.
`red.log`/`green.log` are **not applicable at G0** — 7.0 introduces no behavioural fix, so
there is no parent/candidate red→green pair. This is the one deviation from the generic
§4 file list and it is recorded here explicitly rather than silently.

---

## 8. Known baseline defects carried forward (not fixed in 7.0)

| ID | Defect | Where it lives now | Owner |
|---|---|---|---|
| B-3 | Documented `cmake -B build` fails on a clean tree (pybind11 not found) | `CMakeLists.txt:17`, README build section | 7A-8 |
| — | `pyproject.toml` version `0.6.1` vs release line `v0.6.2`→`v0.7.0` | `pyproject.toml` | 7G |
| — | Four published performance figures do not reproduce | `IMPLEMENTATION_PLAN.md` L45/L53/L81/L178/L209/L261 | 7F-3 |
| — | README L107 "Supports … Qwen2 …" reads as a support claim | `README.md` | 7B/7C |
| — | README L10 lists `Q4_K_M` in the goal sentence unqualified | `README.md` | 7C-4 |
| — | `audit/evidence/G0/README.md` names the pre-G0 SHA | `audit/evidence/G0/README.md` | 7.0 (fixed in this package) |

---

## 9. No source, test, workflow, or packaging changes

7.0's allowed file set is `audit/CLAIMS_LEDGER.md`, `audit/evidence/G0/**`, and the
baseline report. Verified by `diffstat.txt`:

```
git diff --stat <parent>..<candidate> -- src/ tests/ .github/ setup.py pyproject.toml CMakeLists.txt MANIFEST.in
```

is **empty**. The package changed only the claims ledger and the evidence bundle.

---

## 10. Rollback

`git revert` the single 7.0 commit. The package touches no source, no test, and no
packaging, so reverting cannot change build or runtime behaviour. The only residue after
revert is the absence of the evidence bundle.
