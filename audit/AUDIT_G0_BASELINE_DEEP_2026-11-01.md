# Independent G0 Audit — `wp/7.0-baseline`

**Auditor:** DeepSeek V4.1 Flash (independent of the coder and QAQC)
**Date:** 2026-11-01
**Target branch:** `wp/7.0-baseline` @ `58896273cd3b17f4eddde5e6224a3e68747eaeb6`
**Parent (tree under test):** `ea6dbeb1db290bc11d991f7f9940a113fd21efd1`
**Content candidate:** `04e47dc81a9d3b155ef6ca6700a220abec32a1c1`
**Coder:** Minimax · **QAQC:** GLM5.3
**Audit basis:** `PHASE7_IMPLEMENTATION_HANDOFF.md` §6 (7.0/G0), §4 (evidence), §7 (QAQC checklist), §10 (claims ledger)

---

## 1. Verdict

**PASS WITH CONDITIONS — G0 is approved; 7A-1/7A-6/7A-7 may start.**

The baseline facts reproduce independently: the tree is clean at the reviewed SHA, the
restricted diff is empty, the build works with `pybind11_DIR`, the CPU suite is 12/12 in
normal and `-O` modes, all five GPU suites exit 0, the full sdist install builds and
imports on this gfx1150 host, and the claims ledger parses as 30 rows with the stated
status counts.

The conditions below are **documentation, test-harness, and plan-ownership defects**.
They do not invalidate the frozen baseline and do not require a re-freeze, but several are
**G1-blocking**: they must be closed before G1 is signed, and 7B remains blocked until G1.

This audit differs from the QAQC report on three points: the G0 `pytest` record is not
valid evidence for CPU-only coverage or test effectiveness (AUD-2), two ledger rows carry
a qualification flag that contradicts the ledger's own ratchet section (AUD-3), and C-1
has no authorized file set in 7A (AUD-4).

---

## 2. Method

Fresh clone of `wp/7.0-baseline` to `/tmp/opencode/audit-g0` (no in-tree `build/`, `dist/`,
or cached state). Fresh out-of-repo CMake build. Fresh venvs for full and CPU-only sdist
installs. Independent probes:

| Check | Command | Result |
|---|---|---|
| Tree clean | `git status --porcelain` | empty |
| Restricted diff | `git diff --stat ea6dbeb..04e47dc -- src tests .github setup.py pyproject.toml CMakeLists.txt MANIFEST.in` | empty (also empty at HEAD) |
| Documented build | `cmake -S . -B <fresh> -DCMAKE_BUILD_TYPE=Release` | **exit 1**, `CMakeLists.txt:17` pybind11 not found (C-1 reproduced) |
| Working build | same + `-Dpybind11_DIR=$(python3 -m pybind11 --cmakedir)` | **exit 0**, `matmul_module.so` 592,488 bytes |
| CPU suite | `python3 tests/test_cpu_only.py` | **12/12**, exit 0 |
| CPU suite `-O` | `python3 -O tests/test_cpu_only.py` | **12/12**, exit 0 |
| GPU suites | the five `tests/test_*.py` scripts | **5/5 exit 0**; correctness values stable |
| E2E throughput | `test_full_model.py` | **780.4 tok/s** (decode 831.9) — another distinct value |
| sdist | `python3 setup.py sdist` | build sources present |
| Full install | clean venv `pip install --no-build-isolation <sdist>` | **exit 0**, real HIP build, 7 modules import, CLI works, installed CPU suite 12/12 |
| CPU-only install | `GFX1150_SKIP_CMAKE=1` | **exit 0**, 3 modules import, 3 raise the actionable `ImportError` |
| Ledger parse | independent parser | **30 rows**: 10 VERIFIED, 3 PARTIAL, 8 NOT YET, 9 UNVERIFIED; 9 `Qualified in place? = no`; all VERIFIED evidence paths exist |
| `pytest -m "not gpu"` without build | clean clone | **exit 2**, 4 collection errors (`matmul_module`), confirming QAQC F-6 |
| `pytest -m "not gpu"` with build | clean clone | **30 passed, 14 warnings**, but see AUD-2 |

The recorded G0 bundle's own logs were also reviewed against these results. No previously
green suite regressed; the §6 stop condition is **not** triggered.

---

## 3. Findings

### AUD-1 — Setup.py fix is misattributed to `cca793e` (Minor, documentation; 7.0)

Three places in the signed bundle say the `setup.py` pybind11 fix is in `cca793e`:

- `audit/evidence/G0/7.0-baseline/baseline-report.md` L47–48
- `audit/evidence/G0/7.0-baseline/notes.md` L31 (commit-chain diagram)
- `audit/evidence/G0/7.0-baseline/notes.md` L89–90 ("`setup.py` (added in `cca793e`)")

**Fact:** `git log -S "pybind11_DIR" -- setup.py` returns **`ead5f3f`** ("DeepSeek review
and phase7 implementation handoff"); `git show cca793e -- setup.py` is empty. `cca793e`
is the documentation commit and the PR head merged at `089ed8e`; `ea6dbeb` does contain
the fix via `ead5f3f`. The G0/QAQC F-3 correction fixed the DAG ordering but missed this
attribution.

**Required:** correct the three locations to attribute the fix to `ead5f3f`; the
documentation pass is split across `ead5f3f` and `cca793e`. Documentation-only, inside
the 7.0 allowed file set. This is a **QAQC-1 completeness item**, not a new commit class.

### AUD-2 — The `30 passed` pytest record is not valid CPU-only or test-effectiveness evidence (Major for 7A-1; G1-blocking)

The report's exit-criteria row says "12/12 + 12/12 + 30 passed (CPU)", and
`cpu-suite.log`/`gate-commands.log` record `pytest -m "not gpu"` as 30 passed. Two
independent problems:

1. **It is not CPU-only.** No `gpu` marker exists at baseline. `pytest -m "not gpu"`
   collects **30** tests: 12 from `test_cpu_only.py` plus **18 GPU tests** from
   `test_matmul.py` (2), `test_gguf_and_q4.py` (3), `test_layer.py` (5),
   `test_full_model.py` (3), and `test_phase5_scale.py` (5). The `-m "not gpu"` selector
   selects everything because nothing is marked. `cpu-suite.log` itself labels this a
   "collection check; no pytest markers exist yet", so the report's "CPU (pytest)" label
   overstates it.
2. **Thirteen of those tests cannot fail under pytest.** They return `bool` instead of
   asserting. Pytest emits `PytestReturnNotNoneWarning` and **ignores the return value**.
   Independent probe: a file containing `def test_returns_false(): return False` reports
   `1 passed, 1 warning`, exit 0. The 13 functions are the 3 `test_full_model`, 3
   `test_gguf_and_q4`, 5 `test_layer`, and 2 `test_matmul` test functions. A regression
   that makes one of them return `False` would still show as "passed".

The script-level runs are valid evidence (each script exits non-zero on failure), and the
12-test CPU suite is valid. The `30 passed` line is not. It must not be carried into G1 as
a pass criterion.

**Required (7A-1):**
- Convert every `test_*` function to `assert`/raise and return `None`.
- Add `pytest.ini`/`pyproject.toml` config that turns
  `PytestReturnNotNoneWarning` into an error (or an equivalent meta-test that fails on a
  non-`None` return).
- Add `gpu`/`slow` markers so `pytest -m "not gpu"` collects only CPU tests and
  `pytest -m gpu` only GPU tests.
- Add a mutation probe: break one assertion and confirm pytest fails (not just prints).
- Re-label the G0 record as "pytest collection smoke; includes GPU tests; not a gate".

### AUD-3 — Ledger qualification flags for IDs 6 and 10 contradict the ratchet section (Medium; 7A-6, G1-blocking)

`audit/CLAIMS_LEDGER.md` marks IDs 6 (`Q4_K_M`) and 10 (`qwen2`) as
`Qualified in place? yes`, yet the same file's "G0 additions to the ratchet" section says
both must be added to `audit/claims_baseline.txt` because the unqualified instance is in a
different bullet (README L10 for `Q4_K_M`; L107 for `qwen2`, with L108 qualifying in the
next bullet, which violates the handoff's same-bullet rule). The baseline report and notes
also list them as candidates. A checker reading the flag would not require a baseline
entry, so the two claims would be silently unenforced.

The manual `claims-check.log` compounds this: its summary says **"FINDINGS none"**, but it
only checks literal presence and evidence paths; it does not apply the qualification rule.
The actual result is **9 unqualified `no`-flag rows** (IDs 14, 18–20, 26–30) plus the
unqualified ID 13 instance at `IMPLEMENTATION_PLAN.md` L209 plus IDs 6 and 10.

Separately, several match literals are too generic to enforce their claim:
`pip install` (ID 1), `test_cpu_only.py` (ID 2), `GPU` (ID 3), `llama-family` (ID 4).
Removing the Q4_0/Q4_K/Q8_0 kernel claim would not fail a scan for `llama-family`.

**Required (7A-6):**
- Resolve IDs 6 and 10 to `partial`/`no`, or qualify the exact unqualified occurrence in
  the same bullet and record why; align the table with the ratchet section.
- Make `claims-check.log` report the unqualified rows, not "none".
- Require claim-specific literals (e.g. `Q4_0`, `Q4_K`, `Q8_0` separately; `sdist`;
  `12 tests`) and a negative canary that removes a claim and confirms failure.
- Add the exact baseline entries for the 9 `no` rows, ID 13 L209, and IDs 6/10.

### AUD-4 — C-1 has no authorized file set in 7A (Medium; plan/ownership; G1-blocking)

`baseline-report.md` assigns C-1 (the README's documented `cmake -B build` command fails
on a clean tree) to **7A-5, target G1**. But the handoff's 7A allowed-file set is:

> `tests/**`, `pyproject.toml` (pytest config only), `.github/workflows/**`,
> `scripts/qa/**`, `audit/CLAIMS_LEDGER.md`, `audit/claims_baseline.txt`,
> `README.md` (claims wording only), `audit/evidence/7A/**`, `tests/fixtures/**`, docs.
> **No `src/` changes.**

Fixing C-1 requires either `CMakeLists.txt` (pybind11 discovery) or the README build
section (not "claims wording only"). Neither is in 7A-5's allowed set, and 7A-5 is a CI
job, not a build-documentation package. As written, the coder cannot close C-1 under the
assigned work package.

**Required:** add a dedicated work package (recommended **7A-8 — clean-clone build
entry point**) with allowed files `CMakeLists.txt`, `README.md` (build section),
`pyproject.toml` (build config if needed), `tests/**` (a clean-clone configure test), and
CI. Acceptance: a fresh clone with only documented prerequisites runs the documented
command successfully without `pybind11_DIR` or a pre-existing build cache; the CI job
reproduces it. Add this to the G1 exit criteria. (Alternatively, extend 7A-5's allowed
files and rename its scope; the dedicated package is cleaner.)

### AUD-5 — Evidence contract requires red/green logs that G0 cannot have (Minor; process)

`PHASE7_IMPLEMENTATION_HANDOFF.md` §4 and `audit/evidence/README.md` say every bundle must
contain `red.log` and `green.log`, and that a missing required file is an automatic gate
failure. G0 has neither (correctly — no behavioral fix) and documents the deviation in
`notes.md` and the G0 README. The bundle should not have to rely on a prose exception.

**Required:** amend the contract to make `red.log`/`green.log` conditional ("required when
the package contains a behavioral fix") or add an explicit `red-green-NA.md` to G0. This
is an auditor/process-doc change, not a coder package.

### AUD-6 — "Twelve" vs "Thirteen" ledger additions (Minor; documentation)

`audit/CLAIMS_LEDGER.md` says "**Twelve** uncovered public claims added (IDs 18–30)".
IDs 18–30 inclusive are **13** rows; the same paragraph and `notes.md` say 13. Fix the
number to 13 (or list the rows explicitly).

### AUD-7 — `env.txt` status line is ambiguous (Minor; documentation)

`audit/evidence/G0/7.0-baseline/env.txt` records:

```
status: '?? audit/evidence/G0/7.0-baseline/' (empty = clean)
```

The status is not empty; the evidence bundle was untracked while being written. The report
separately claims "tree clean". Clarify: "clean except the evidence bundle being written"
and record the post-commit empty status separately. This is transparency, not a functional
defect.

### AUD-8 — Throughput variance confirmed (Observation; supports QAQC-3/C-2)

Independent E2E: **780.4 tok/s** (decode 831.9) versus G0's 849.3 and the verification's
788.6, with the plan's 983.4 as a fourth value. Correctness was identical (`max_err` values
and generated text). This strengthens the requirement not to baseline any single-run
figure and to delete or re-record the published numbers in 7F-3.

### AUD-9 — C-1 independently reproduced (Observation; confirms baseline condition)

The documented command fails exactly as recorded (exit 1 at `CMakeLists.txt:17`). The
working build requires `-Dpybind11_DIR`; `setup.py` passes it. No dispute with the G0
record.

---

## 4. Conditions and gate impact

| ID | Condition | Owner | Target | Blocks |
|---|---|---|---|---|
| **C-AUD-1** | AUD-1, AUD-6, AUD-7: correct the setup.py attribution, "Twelve"→"Thirteen", clarify env status. Documentation-only. Accept QAQC-1 as complete once these land. | 7.0 / QAQC | before G1 | G1 |
| **C-AUD-2** | AUD-2 + QAQC-2: pytest harness uses asserts/`None`, `gpu` markers, return-warning-as-error, clean-clone collection, mutation probe. Re-label the G0 `30 passed` record. | 7A-1 | G1 | G1 |
| **C-AUD-3** | AUD-3: fix ledger ID 6/10 flags, report unqualified rows, claim-specific literals, negative canary, exact baseline entries. | 7A-6 | G1 | G1 |
| **C-AUD-4** | AUD-4 + C-1: add 7A-8 (or extend 7A-5) with the build files and a clean-clone documented-build test; add to G1 exit. | 7A-5/7A-8 | G1 | G1 |
| **C-AUD-5** | AUD-5: make red/green conditional or add `red-green-NA.md`. | Auditor / 7A-6 | G1 | G1 |
| **QAQC-3** | Delete or re-record the four performance figures with a warm-up + ≥20-iteration median/p95 harness. | 7F-3 | G6 | G6 |
| **C-1** | README build command; covered by C-AUD-4. | 7A-8 | G1 | G1 |
| **C-2** | Published performance figures; covered by QAQC-3. | 7F-3 | G6 | G6 |

None of these conditions changes a runtime or source file, so **no re-freeze is
required**. `candidate-sha.txt` (`04e47dc`) remains the correct content candidate; the
follow-up commits are documentation and evidence only.

---

## 5. What is confirmed (no action)

- Tree clean at `5889627`; restricted diff empty at `04e47dc` and `HEAD`.
- Only `audit/CLAIMS_LEDGER.md` and `audit/evidence/G0/**` changed in the package.
- The parent SHA is correct in `parent-sha.txt`, `env.txt`, `baseline-report.md`,
  `notes.md`, and `diffstat.txt` after QAQC-1.
- Build, CPU, GPU, sdist, CPU-only install, CLI, and installed CPU suite all reproduce.
- The claims ledger has 30 main rows with the stated 10/3/8/9 status distribution; every
  VERIFIED evidence path exists; all applicable literals resolve.
- The sdist hash caveat (QAQC F-1/F-2) and `.so` source-path caveat (F-7) are valid.
- The ROCm 10.1 / HIP 7.16.26385 baseline is authoritative; `VERIFICATION_2026-11-01.md`
  is historical.

---

## 6. Authorization

- **G0: PASS WITH CONDITIONS.** The baseline is frozen and independently reproduced. The
  G0 gate itself is signed.
- **7A-1, 7A-6, 7A-7 may begin now.** They are independent and unblock the rest of 7A.
  C-AUD-1 should land early because it is documentation-only.
- **G1 cannot be signed** until C-AUD-1 through C-AUD-5 and QAQC-2 are closed.
- **7B remains blocked** until G1 is signed and the 7A-3 goldens exist.
- Mistral 4.0's independent report should be reconciled against this one before G1; if the
  two disagree on a finding, the owner should record the resolution in the next gate
  bundle rather than silently preferring one.

**Independence:** This audit re-ran the baseline from a clean clone and wrote its own
probes. It is independent of the Minimax implementation and the GLM5.3 QAQC pass.

**Sign-off:** DeepSeek V4.1 Flash, 2026-11-01.

---

## 7. Post-audit preparation (2026-11-01)

The primary auditor applied the documentation-only conditions on the integration branch
before handing 7A to the coder:

- **C-AUD-1 applied:** AUD-1 (setup.py attribution → `ead5f3f`), AUD-6 ("Twelve" →
  "Thirteen"), AUD-7 (`env.txt` untracked-bundle clarification, recorded in the report
  erratum rather than editing the captured log).
- **C-AUD-5 applied:** `red.log`/`green.log` are now conditional for behavioral packages;
  non-behavioral packages state `red/green: N/A (no behavioral change)` in `notes.md`.
- **C-AUD-3 partially applied:** ledger IDs 6 and 10 now say `no` (consistent with the
  ratchet section), and `audit/claims_baseline.txt` is seeded with the 15 exact entries
  from this audit. The `check_claims.py` implementation, claim-specific literals, and
  negative canaries remain 7A-6 work.
- **AUD-4 applied to the plan:** 7A-8 (clean-clone build entry point) is added with its own
  file set and G1 criterion; the handoff's 7A-1/7A-6/7A-7 acceptance criteria now include
  the AUD-2/AUD-3 requirements.
- **Coder handoff:** `PHASE7_7A_CODER_BRIEF.md`; first branch `wp/7A-1-pytest-harness`.

Remaining before G1: 7A-1, 7A-6, 7A-7, 7A-8 implementation; QAQC-2; and the rest of 7A
(7A-2..7A-5) as scoped. 7B remains blocked.
