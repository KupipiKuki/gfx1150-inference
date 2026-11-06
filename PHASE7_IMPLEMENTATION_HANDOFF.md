# Phase 7 Implementation & QAQC Handoff Plan

> **Status:** Active execution plan for Phase 7 (`v0.6.2` → `v0.7.0`).
> **Authority:** This document governs *how* Phase 7 work is implemented and accepted. `IMPLEMENTATION_PLAN.md` remains the high-level roadmap; the audit reports remain the source of findings. If they conflict, this document wins for process, and the audit reports win for technical findings.
> **Baseline:** `9b2deb0` plus the 2026-11-01 verification changes (`setup.py` pybind11 discovery, documentation). See `audit/VERIFICATION_2026-11-01.md`.

---

## 0. Why this document exists

Phase 7 is not a feature phase. It is a **correctness and evidence phase**. The previous rounds showed the main failure mode clearly:

- code was added faster than it could be independently verified;
- "fixed" claims were sometimes only partially true (special tokens, `add_bos`, Phi-3/Gemma, residency, streams);
- tests were self-referential (repo encoder vs repo decoder, synthetic vocab vs synthetic vocab);
- performance numbers were quoted without reproducible artifacts.

The rules below exist to prevent a repeat. A work package is **not done** because the code compiles or because the coder says it works. It is done when an independent QAQC pass reproduces the evidence and the auditor signs the gate.

### 0.1 Review of the previous Phase 7 plan

The previous plan had four broad stages (7A test infrastructure, 7B hardware gate, 7C remediation code, 7D merge). It was directionally right but not executable as a handoff. Gaps found:

| Gap | Consequence | Fix in this plan |
|---|---|---|
| No entry/exit criteria per stage | "Done" was subjective | Every package has acceptance criteria and a gate checklist |
| No role separation | The coder could also declare success | Coder / QAQC / auditor with an independence rule |
| No evidence contract | Claims could not be reproduced | `audit/evidence/` bundle with red/green logs and environment |
| No red→green requirement | A test could pass without exercising the bug | Red on parent, green on candidate is mandatory |
| No stop conditions | Scope creep and bundled fixes | Hard stop points S0–S7 and eight stop triggers |
| Test work mixed with remediation | A failing P0 could be hidden in a test refactor | 7A is `src/`-free; remediation starts at 7B |
| No file ownership | Parallel work conflicts in `inference.py` | Allowed file set per package; sequential for shared files |
| No traceability or claims ledger | Audit findings could be silently dropped | Matrix in §11 and `audit/CLAIMS_LEDGER.md` |
| Hardware claims unverifiable | "983 tok/s" and "bit-identical" were owner-only | 7F-2/7F-3 require recorded artifacts |
| No GPU CI workflow or runner | G5/G6 had no enforcement mechanism | 7A-7 adds `ci-gpu.yml` with `continue-on-error`; 7F-1 registers the runner and makes it required |
| Claims ledger had no enforcement | `UNVERIFIED`/`NOT YET` claims could remain in README | 7A-6 adds `scripts/qa/check_claims.py`; G6 makes it release-blocking and diffs ledger vs README |
| No release gate | Merge on "CI green" alone | G6 requires golden logits, benchmark baseline, clean claims ledger |

The phase count was also too coarse: tokenizer, model families, memory, and streams have different owners, risks, and evidence. They are now separate gates so a failure in one does not block or contaminate the others.

---

## 1. Roles

| Role | Responsibility | Must not |
|---|---|---|
| **Coder** (another model) | Implement exactly one work package; add tests; produce evidence; update docs; stop at the gate | Start the next package before signoff; weaken/delete tests; bundle unrelated fixes; claim hardware results without artifacts |
| **QAQC** | Independently reproduce the gate from a clean checkout; write adversarial probes; verify red→green; check regressions, docs, and evidence | Accept coder summaries as evidence; edit production code to make a test pass; approve its own work |
| **Auditor** (this role) | Own traceability, gate decisions, claims ledger, and release signoff; review design and evidence; reject insufficient work | Implement production code in the same package being audited; waive a P0 without a written, time-bound exception |
| **Owner / Release manager** | Merge only after auditor approval; publish release notes from the claims ledger | Merge on "CI green" alone; expand release scope without a new gate |

**Independence rule:** the person/model that wrote a work package cannot be the sole QAQC for it. If only one model is available, QAQC must at minimum re-run from a clean clone and write new probes; the auditor then treats the result as "self-tested, independently re-run", not "independently tested".

---

## 2. Operating model: one package, one gate

Every work package follows the same state machine:

```
SCOPED → IMPLEMENTED → CODER-REPORTED → QAQC-PASSED → AUDITOR-APPROVED → MERGED
                │              │               │
                └──────────────┴───────────────┴──→ STOP / REWORK
```

### 2.1 Hard stop points

At every gate the coder **stops**. No new work package, no opportunistic refactor, no "while I was in there" changes. The only permitted activity while waiting is answering QAQC questions or producing missing evidence.

| Stop | After | Do not proceed until |
|---|---|---|
| **S0** | 7.0 Baseline | Baseline report signed; tree clean; CPU + GPU suites recorded |
| **S1** | 7A Test infrastructure | QAQC confirms tests are meaningful (fail on parent/bad input) and CI jobs work |
| **S2** | 7B Tokenizer | Golden vectors pass; special tokens and `add_bos` verified; no silent drops |
| **S3** | 7C Model families | Per-arch fixtures and reference logits pass; README compatibility matrix is honest |
| **S4** | 7D Memory & robustness | Hostile-input, cgroup, fd/mmap, and residency evidence passes |
| **S5** | 7E Stream topology | Event graph reviewed; race/stress test passes; no implicit NULL-stream reliance |
| **S6** | 7F Evidence & release | GPU CI, golden logits, benchmark baseline, and claims ledger pass |
| **S7** | 7G Post-release (optional) | Only after v0.7.0 ships |

### 2.2 Stop conditions (any one triggers an immediate halt)

1. Baseline regression in a previously green suite.
2. A test is deleted, skipped, or its tolerance is loosened without written auditor approval.
3. A public API or on-disk format changes without versioning/deprecation.
4. A new runtime dependency or network access is introduced without approval.
5. A security guard is weakened (parser bounds, KV file flags, binding checks, `sys.path`).
6. A claim is made without a reproducible command and artifact.
7. The diff exceeds the package's allowed file set.
8. Two consecutive QAQC failures on the same acceptance criterion.

When stopped, the coder writes a **Blocker Report** (§8.4) and waits. Do not "fix forward" silently.

---

## 3. Non-negotiable rules for the coder

1. **One work package per branch/PR.** Branch name: `wp/<id>-<slug>` (e.g. `wp/7B-1-special-token-encode`).
2. **Frozen review SHA.** Once QAQC starts, no force-push. Fixes go in new commits on the same branch and QAQC re-runs the gate.
3. **Red before green.** Every behavioral fix must have a test that fails on the parent commit and passes on the candidate. Commit both logs.
4. **Tests are the specification.** Never change a golden value or tolerance to match the implementation. If the golden is wrong, prove it with provenance and get auditor approval first.
5. **No silent fallbacks.** Unsupported models/tensors/quants raise an explicit, actionable error listing what is missing.
6. **No self-referential validation.** New correctness tests must compare against an external reference (llama.cpp output, hand-computed vector, independent NumPy translation) or a committed fixture with provenance.
7. **CPU-first testability.** `import matmul_module` must not run at module import time in files that a CPU-only environment needs to collect. Use lazy import / `pytest.importorskip`.
8. **Docs in the same PR.** If behavior or scope changes, update README/audit text in the same package. Update the claims ledger (§10).
9. **Determinism.** Fixed seeds, `time.perf_counter`, `tmp_path`, no fixed filenames in tests, no wall-clock assertions.
10. **Evidence, not adjectives.** "Faster", "fixed", "production-ready", "bit-identical" require a command, an artifact, and a scope.
11. **No scope creep.** P2 items (flash attention, RoPE scaling, SWA, namespace package, etc.) are out of scope until 7G or a new approved plan.
12. **Diff budget.** Target ≤400 changed lines excluding tests/fixtures. Larger requires a written justification in the coder report.
13. **Run the full gate, not the happy path.** CPU suite normal and `-O`; GPU suites on gfx1150 when in scope; packaging from sdist.
14. **Report failures honestly.** A partial fix with a precise limitation is acceptable; an overstated fix is a gate failure.

---

## 4. Evidence contract

All evidence lives under `audit/evidence/<gate>/<work-package>/`. Text logs only; no multi-megabyte binaries. Large fixtures are committed under `tests/fixtures/` with a `PROVENANCE.md`.

Each evidence bundle must contain:

| File | Content |
|---|---|
| `env.txt` | `uname -a`, ROCm/HIP version, `rocminfo` GPU line, Python/NumPy/pybind11/CMake versions, `git rev-parse HEAD` |
| `parent-sha.txt` / `candidate-sha.txt` | Exact commits tested |
| `diffstat.txt` | `git diff --stat parent..candidate` |
| `red.log` | The new test failing on the parent commit |
| `green.log` | The same test passing on the candidate |
| `cpu-suite.log` | `python -m pytest -m "not gpu"` and `python tests/test_cpu_only.py` (normal + `-O`) |
| `gpu-suite.log` | `python -m pytest -m gpu` on gfx1150, when in scope |
| `gate-commands.log` | Every command in the package's "Required checks", with exit codes |
| `claims-check.log` | Output of `scripts/qa/check_claims.py` (default mode from 7A-6; `--strict` at G6) |
| `qaqc-probes/` | QAQC's own probes, independent of the coder's tests |
| `notes.md` | Limitations, follow-ups, rollback, claims changed |

**Provenance for golden data** must state: upstream project and commit/version, exact command used, input hash, output hash, and license. Example:

```
llama.cpp @ <sha>, built with <flags>
command: ./llama-tokenize -m <model> -p "Hello  world" --ids
model sha256: ...
output: [ ... ]
```

A golden without provenance is not evidence.

**Red/green is conditional:** `red.log` and `green.log` are required only when the package
changes behavior (a fix, a new guard, a changed API). A non-behavioral package (baseline,
test-harness, CI, docs) must state `red/green: N/A (no behavioral change)` in `notes.md`
and include the green suite logs; no separate file is required. This resolves the G0
AUD-5 discrepancy without weakening the red→green rule for behavioral work.

---

## 5. Phase map

| Phase | Goal | Gate | Hardware needed |
|---|---|---|---|
| **7.0** | Freeze baseline, record environment, verify current green state | **G0** | Yes (manual GPU baseline on the available host) |
| **7A** | Test infrastructure: pytest, goldens, fuzz, CPU/sdist CI, GPU CI scaffold, claims checker, clean-clone build entry point | **G1** | CPU CI; GPU workflow scaffold (`continue-on-error`) |
| **7B** | Tokenizer correctness (P0-1) | **G2** | CPU; GPU optional |
| **7C** | Model-family support (P0-2) | **G3** | CPU fixtures + GPU reference logits |
| **7D** | Memory honesty & robustness (P0-3, P1-5) | **G4** | CPU + cgroup; GPU residency evidence |
| **7E** | Stream topology (P1-4) | **G5** | Yes (7A-7 workflow or manual) |
| **7F** | Evidence & release gates (P1-6), promote GPU CI to required | **G6** | Yes (required) |
| **7G** | Post-release polish (P2) | **G7** | As needed |

**Sequencing:** 7.0 → 7A → 7B → 7C → 7D → 7E → 7F → release. 7G is deferred. Do not parallelize packages that touch `src/inference.py`; file ownership is listed per package.

---

## 6. Detailed work packages

### 7.0 — Baseline freeze and governance (Gate G0)

**Audit trace:** process prerequisite for all findings.
**Allowed files:** `audit/CLAIMS_LEDGER.md`, `audit/evidence/G0/**`, baseline report. **No source, test, workflow, or packaging changes.**

**Tasks**
1. Commit or explicitly park the 2026-11-01 verification changes; record the exact baseline SHA.
2. Confirm `git status --porcelain` is empty.
3. Record environment and GPU (`rocminfo`).
4. Build from a clean directory; record configure/build logs.
5. Run the CPU suite (normal + `-O`) and all five GPU suites; record results.
6. Build the sdist and perform a **full** `pip install` from it in a clean venv (not only `GFX1150_SKIP_CMAKE=1`).
7. Confirm the `tests/fixtures/PROVENANCE.md` registry and the `audit/evidence/` layout (§4).
8. Review and update the seeded claims ledger (§10) with every current README/audit claim and its evidence status.
9. Record the GPU baseline **manually** on the available gfx1150 host. Automated enforcement is added in 7A-7 (`continue-on-error`) and becomes mandatory at G6; G0 does not wait for a CI runner.

**Exit criteria (G0)**
- [ ] Baseline SHA recorded; tree clean.
- [ ] All suites green, or every failure documented as a known baseline defect.
- [ ] Full sdist install succeeds on the target platform.
- [ ] Claims ledger exists and marks unverified claims.
- [ ] Manual GPU baseline recorded with environment and logs.
- [ ] Auditor signs the baseline report.

**Stop:** If any previously green suite is red, do not start 7A. Diagnose first.

---

### 7A — Test infrastructure (Gate G1)

**Audit trace:** T-1, T-2, T-3, T-4, T-5, T-6, T-7; B-1 residual (sdist install); G0 audit AUD-2..AUD-5; QAQC-2; Phase 7A-1..7A-8.
**Allowed files:** `tests/**`, `pyproject.toml` (pytest config only), `.github/workflows/**`, `scripts/qa/**` (new), `audit/CLAIMS_LEDGER.md`, `audit/claims_baseline.txt`, `README.md` (claims wording; **7A-8 may edit the build section**), `CMakeLists.txt` (**7A-8 only**), `MANIFEST.in` (**7A-5 for `tests *.py`; 7A-3 for `tests/fixtures` globs only**), `audit/evidence/7A/**`, `tests/fixtures/**`, docs. **No `src/` changes.** 7A-1..7A-7 must not touch `CMakeLists.txt`; 7A-8 owns the build entry point; 7A-5 owns the test-module manifest rule; 7A-3 owns the fixture globs.

**Work packages**

| ID | Task | Acceptance |
|---|---|---|
| 7A-1 | Add `tests/conftest.py` with a `matmul_module` fixture using `pytest.importorskip`; add `gpu`/`slow` markers; convert the five GPU scripts to pytest. **Every `test_*` function must use `assert`/raise and return `None`**; turn `PytestReturnNotNoneWarning` into an error; verify collection from a clean clone with no pre-built extension. | `pytest -m "not gpu"` collects **only CPU tests** and passes on CPU; `pytest -m gpu` collects only GPU tests, skips cleanly without the extension, and passes on gfx1150; a test returning `False` **fails**; one mutated assertion fails; no `def test_* -> bool` remains |
| 7A-2 | Add `[tool.pytest.ini_options]` (`markers`, `testpaths`, `addopts`); keep `test_cpu_only.py` runnable as unittest. *(Implemented as part of 7A-1; this is now a verification/evidence closeout, not new code.)* | `python tests/test_cpu_only.py` still 12/12; `python -O` still 12/12 |
| 7A-3 | **Golden data + provenance:** GPT-2/SentencePiece token IDs for plain text, multibyte, double spaces, special tokens, `add_bos` on/off; Q4_0/Q4_K/Q6_K golden blocks; one tiny GGUF fixture. Goldens must be external (llama.cpp or another independent reference), registered in `tests/fixtures/PROVENANCE.md`; add fixture globs to `MANIFEST.in`; register CPU/GPU tests in `EXPECTED_LANES`. Known open-bug goldens (tokenizer special tokens / `add_bos`) are `xfail(strict=True)` until 7B so G1 stays green; record the red evidence with `--runxfail`. | Goldens load offline; provenance complete (source/version/command/hashes); no self-referential generation; the sdist contains the fixtures; current CPU/GPU lanes green; `--runxfail` shows the known-bug goldens failing; no `src/` change |
| 7A-4 | Add deterministic `hypothesis` fuzz for GGUF headers (alignment, counts, dims, truncation, duplicates). Install `hypothesis` in the CPU and sdist CI jobs; the fuzz test is CPU-lane and marked `slow` so the packaging job can deselect it. If fuzzing finds a parser defect, stop and file a blocker/new package — do **not** edit `src/` in 7A-4. | ≥10,000 examples, no crash; failures minimized; deterministic (fixed seed/`derandomize`, no local database); CPU lane green; no `src/` change |
| 7A-5 | **CI + sdist install (C-7A1-5):** CPU pytest job; sdist-install job (`GFX1150_SKIP_CMAKE=1`, assert `tests/conftest.py` is present, import the three CPU modules, assert the three GPU modules raise the actionable `ImportError`, run the installed CPU suite); add `recursive-include tests *.py` to `MANIFEST.in`; keep existing CI/claims steps. | Jobs green on PR; the sdist contains `tests/conftest.py` and `tests/test_harness_contract.py`; the installed tree collects and runs `pytest -m "not gpu"` cleanly (no exit 2); a real install, not an archive listing |
| 7A-6 | Add `scripts/qa/check_claims.py` with default CI mode and `--strict`; parse the ledger and **enforce `Qualified in place?`**, not just literal presence; use claim-specific literals; scan `README.md` and `IMPLEMENTATION_PLAN.md`; require evidence paths for `VERIFIED` rows; review the seeded `audit/claims_baseline.txt` (15 exact entries: 11 `no` rows + ID 13's unqualified L209 instance) with a `G6` expiry. Wire default mode into CPU CI (strict is advisory until G6). | Default mode green with the exact reviewed baseline; `--strict` detects injected canaries; baseline entries are exact and target G6; no generic/allow-all literal; the checker reports every unqualified row instead of "none" |
| 7A-7 | Add `.github/workflows/ci-gpu.yml` targeting `runs-on: [self-hosted, gfx1150, rocm]`; build with CMake and run `pytest -m gpu`; upload logs/artifacts. Set `continue-on-error: true` until a runner registers, with an issue link in the workflow comment. | Workflow is valid YAML, triggers on PR/nightly, and either runs green on a registered runner or is explicitly `continue-on-error` with a tracked issue; it is **not** counted as a gate pass while skipped |
| 7A-8 | **Clean-clone build entry point (C-1):** make the documented `cmake -B build -DCMAKE_BUILD_TYPE=Release` succeed without `pybind11_DIR` or a pre-existing cache (or correct the README to the command that works); add a CI job that runs it from a fresh clone. | Fresh clone + documented prerequisites + documented command succeeds with no ambient `pybind11_DIR` and no build cache; CI reproduces it; README command matches the verified path |

**Required checks**
```bash
python -m pytest -m "not gpu" -q                  # must collect only CPU tests
python -m pytest -m gpu --collect-only -q         # CPU host: must skip, not error
python -W error::pytest.PytestReturnNotNoneWarning -m pytest -m "not gpu" -q
if grep -R -n "def test_.*-> bool" tests/; then echo "test functions must return None"; exit 1; fi
python tests/test_cpu_only.py
python -O tests/test_cpu_only.py
python scripts/qa/check_claims.py                 # default CI mode (baseline-aware)
python scripts/qa/check_claims.py --strict        # advisory until G6; must be clean at G6
python setup.py sdist
# clean venv:
pip install --no-build-isolation dist/*.tar.gz     # full build on gfx1150
GFX1150_SKIP_CMAKE=1 pip install --no-build-isolation dist/*.tar.gz  # CPU-only runner
# 7A-8: fresh clone, no pybind11_DIR, no build cache
rm -rf /tmp/7a-build && cmake -S . -B /tmp/7a-build -DCMAKE_BUILD_TYPE=Release
cmake --build /tmp/7a-build -j 8
# workflow sanity:
python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/ci-gpu.yml'))"
```

**QAQC adversarial checks**
- Mutation test the tests: revert a known fix locally (e.g. remove the parser bound) and confirm the relevant test fails. A test that cannot fail is not a test.
- **Canary test:** add `def test_returns_false(): return False`; `pytest` must fail (not warn/pass), then remove it.
- Confirm `pytest -m "not gpu"` collects **zero** GPU tests and `pytest -m gpu` collects all GPU tests.
- Confirm a clean clone with no `matmul_module` collects/skips cleanly, not exit 2.
- Confirm goldens are external, not generated by the code under test.
- Confirm GPU tests skip, not silently pass, on CPU.
- Confirm no test is skipped in the CPU job without a reason.
- Inject a `NOT YET` claim into `README.md` and an unqualified `Q4_K_M`/`qwen2` canary; `check_claims.py` must fail; restore them.
- Confirm the ledger's ID 6/10 flags are `no`/`partial` and the baseline has exact entries.
- Confirm `ci-gpu.yml` is genuinely `continue-on-error` (not silently skipped) and that its logs are uploaded when a runner exists.
- Confirm 7A-8's fresh-clone command works with no ambient `pybind11_DIR` and no build cache.

**Exit criteria (G1)**
- [ ] CPU and GPU collection behavior correct; no `test_*` returns non-`None`; a False return fails.
- [ ] Goldens have provenance and exercise the known P0 bugs (red evidence).
- [ ] Fuzz runs deterministically.
- [ ] CPU + sdist CI jobs green; full sdist install verified.
- [ ] Claims checker default mode green; baseline reviewed and exact; qualification and canaries detected.
- [ ] GPU workflow exists and is valid; it is green or explicitly `continue-on-error` with a tracked runner issue. GPU correctness is **not** a G1 gate (G0's manual baseline covers the current host); it becomes required at G6.
- [ ] **Fresh-clone documented build succeeds (C-1/7A-8) with no `pybind11_DIR` and no build cache.**
- [ ] No `src/` diff.

**Stop:** Do not start 7B until G1 is signed. 7B is gated by 7A-3 goldens.

---

### 7A-9 (Post-G1 P0): BLOCKER-7A4-1 parser fix

**Status:** **ACCEPTED (2026-11-04)** — work commit `1bce3d0`, tip `9493cf8`; audit
`audit/AUDIT_7A-9_PARSER_FIX_DEEP_2026-11-04.md`. The parser blocker is closed; no
conditions. G6 still depends on the later gates.

**Allowed files:** `src/gguf_parser.py`, `tests/**` (remove the pinned xfail, add direct boundary tests), `audit/evidence/G1/7A-9/**`, docs (`IMPLEMENTATION_PLAN.md` claim correction, `BLOCKER.md` wording). No CMake, packaging, CI, ledger, or unrelated source changes.

**Required:** reject a metadata array whose element type is `ARRAY` with the parser’s documented `ValueError` at the point where the element type is read. A valid GGUF has no nested arrays, so the scalar check is sufficient; a recursion limit is optional defence only. Remove the `xfail` from `test_nested_arrays_are_rejected_with_a_value_error`, assert `ValueError` for the pinned 11,962-byte example and for a below-threshold depth, and keep the fuzz/direct tests green. Soften the `BLOCKER.md` “every caller catches ValueError” wording (QF-1). Remove the exception from the `IMPLEMENTATION_PLAN.md` fail-closed claim once fixed.

**Acceptance:** pinned test passes without xfail; depth-300 and depth-1000 nested-array cases both raise `ValueError`; CPU/GPU lanes green; fuzz 10k unchanged; no parser regression; public claim no longer carries the exception; evidence bundle under `audit/evidence/G1/7A-9/`.

**Stop:** Stop for QAQC/auditor. 7B may run in parallel from the same base; release G6 remains blocked until this lands.

> **Update 2026-11-04:** 7A-9 landed (`1bce3d0`) and was accepted by the primary audit
> with no conditions. C-G1-1 and C-G1-2 are closed. This section is retained as the
> package record; the parser may now be described as fail-closed for the malformed
> classes the suite covers.

---

### 7B — Tokenizer correctness (Gate G2)

> **G1 is signed (2026-11-04); 7B is authorized.** The 7A-9 parser fix has landed and is
> accepted, so 7B is fully independent of the parser work. The 7A-3 goldens are the
> acceptance vectors.
>
> **G2 status (2026-11-05): NOT SIGNED.** The first 7B candidate
> (`wp/7B-tokenizer` @ `e091fcf`, work `70c5ab2`) closes the four xfails and passes all
> 23 goldens, but the SPM path does not match the pinned llama.cpp reference on mixed
> text around special tokens (**BLOCKER-7B-1**) or on ordinary common words
> (**BLOCKER-7B-2**). See `audit/AUDIT_7B_TOKENIZER_DEEP_2026-11-05.md` and
> `audit/G2_SIGNOFF_2026-11-05.md`. Do not merge the branch; 7C remains blocked.

**Audit trace:** C-2 (partial), N-2, T-3; v0.6.2 §6 P0-1.
**Allowed files:** `src/tokenizer.py`, `src/inference.py` (BOS call sites only), `tests/**` tokenizer tests, `tests/fixtures/**` only if a golden needs correction (do not rewrite 7A-3 goldens), `README.md` (tokenizer/claims wording), docs, `audit/evidence/G2/7B/**`.

**Work packages**

| ID | Task | Acceptance |
|---|---|---|
| 7B-1 | Special-token split on **encode**: longest-match trie over control/user-defined tokens; special IDs emitted directly; no byte mapping inside a special token; no splitting inside ordinary text | `encode("<\|im_start\|>")` → `[special_id]`; mixed text `"hi<\|im_start\|>there"` splits correctly; plain text unchanged |
| 7B-2 | Read `tokenizer.ggml.add_bos_token`; precedence: explicit `add_bos` argument > metadata > default; `generate()` / `generate_batch_ids()` stop hardcoding `True` | Tests for metadata true/false/absent; no duplicate BOS; Qwen2/GPT-2-style no-BOS model behaves correctly |
| 7B-3 | Replace the `\w`/`\d` pre-tokenizer with the GPT-2 spec regex (Unicode `\p{L}`/`\p{N}`) or a golden-verified equivalent; resolve the SentencePiece golden mismatches or explicitly re-scope them | 7A-3 goldens pass for GPT-2 and SentencePiece: `Hello123`, `café123`, `a_b`, contractions, double spaces, emoji, control tokens; no remaining tokenizer `xfail` without auditor approval |
| 7B-4 | Uniform unmappable-byte handling in both branches: try `<0xXX>` before raising; never silently drop | Probe with minimal vocabs (GPT-2 and SentencePiece); missing byte raises `ValueError` with byte value |

**Required checks**
```bash
python -m pytest -m "not gpu" -q -k "tokenizer or bpe or golden"
python -m pytest -m "not gpu" -q --runxfail -k "tokenizer or bpe or golden"
python tests/test_cpu_only.py
python -O tests/test_cpu_only.py
# independent probe: special token, mixed text, add_bos true/false/absent
```

**QAQC adversarial checks**
- Special token that is a prefix of another special token (longest match).
- Special token adjacent to whitespace and punctuation.
- `add_bos` metadata absent vs `false` vs `true`; explicit argument overrides.
- Text that looks like a special token but must not be treated as one (e.g. escaped/user text), if the tokenizer spec requires it.
- Multi-byte UTF-8, lone surrogate handling, empty string.
- Decode round-trip with `skip_special_tokens` true/false.
- The 7A-3 golden vectors: zero tokenizer failures under `--runxfail`.

**Exit criteria (G2)**
- [ ] 7A-3 goldens pass; special-token and `add_bos` tests pass.
- [ ] No silent character/byte loss.
- [ ] SentencePiece goldens pass, or a documented, auditor-approved scope reduction exists.
- [ ] No tokenizer `xfail` remains except explicitly approved 7C scope.
- [ ] README tokenizer/claims are updated and the claims checker is green.
- [ ] 7A-9 is not required for 7B; it has landed and is accepted. Release remains blocked by G2/G3 and the later gates.

**Stop:** Do not start 7C until G2 is signed.

---

### 7C — Model-family support (Gate G3)

**Audit trace:** C-3 (partial), C-4/C-5 (scope decision), N-3; v0.6.2 §6 P0-2.
**Allowed files:** `src/layer.py`, `src/inference.py` (model spec / embedding / logits), `src/gguf_parser.py` (only if metadata access needs it), `src/kernels/**` (only if a fused-QKV kernel is required), tests, docs, evidence.

**Work packages**

| ID | Task | Acceptance |
|---|---|---|
| 7C-1 | Add a `ModelSpec` / tensor-name map: required tensors, optional biases, fused-QKV presence, embedding scale, logit soft-cap, key/value length; fail fast with a list of missing tensors | Unknown architecture → explicit error; llama path unchanged; unsupported quant list is fail-fast |
| 7C-2 | Phi-3 fused `attn_qkv.weight` (+ bias): split or fused matmul path; FFN biases if present; shape validation | Synthetic Phi-3 fixture constructs and runs; logits match reference; no `KeyError` |
| 7C-3 | Gemma: `sqrt(hidden)` embedding scale, final-logit soft-cap, `{arch}.attention.key_length` / `value_length`, correct head dim | Synthetic Gemma fixture runs; logits match reference; RoPE/reshape correct |
| 7C-4 | Publish an honest compatibility matrix (arch × quant × context) and fix README claims | Matrix matches tests; no unsupported family listed as supported |

**Required checks**
```bash
python -m pytest -m "not gpu" -q -k "model_spec or phi3 or gemma or compat"
python -m pytest -m gpu -q -k "phi3 or gemma or llama_regression"
python tests/test_cpu_only.py && python -O tests/test_cpu_only.py
```

**QAQC adversarial checks**
- Tensor names taken from **real** GGUF headers, not invented; record header dumps.
- Missing optional tensor vs missing required tensor produce different, actionable errors.
- Head-dim math for Gemma 7B (explicit key length ≠ hidden/heads).
- Bias path and fused path produce the same result where both exist.
- Llama regression: identical token IDs on the fixed golden prompt.

**Exit criteria (G3)**
- [ ] Per-arch fixtures and reference logits pass.
- [ ] Llama-family behavior unchanged.
- [ ] Compatibility matrix and README are accurate.
- [ ] Unsupported families fail fast with a clear message.

**Stop:** Do not start 7D until G3 is signed. If Phi-3/Gemma cannot be evidenced, keep them explicitly unsupported and close the package as "documented limitation" — do not claim support.

---

### 7D — Memory honesty and robustness (Gate G4)

**Audit trace:** D-1, P-2, S-1 residual, R-1/R-2 residual; v0.6.2 §6 P0-3 and P1-5.
**Allowed files:** `src/weight_loader.py`, `src/kv_cache.py`, `src/inference.py` (residency/init/close), tests, docs, evidence.

**Work packages**

| ID | Task | Acceptance |
|---|---|---|
| 7D-1 | Replace the `MADV_DONTNEED` claim with the correct mechanism: `posix_fadvise(POSIX_FADV_DONTNEED)` (best-effort) and/or `MADV_PAGEOUT` where available; keep `MADV_WILLNEED` prefetch | Docs match behavior; tests cover unavailable-syscall fallback; no false "bounded RAM" claim |
| 7D-2 | Implement a budgeted residency policy: `AUTO` (pin if it fits), `PIN_ALL`, `STREAM`; budget = free GTT/RAM − KV − activations − safety; make `cache_weights` map to a real policy or deprecate it | `AUTO` pins a fitting model; `STREAM` streams; measured GTT/RSS reflects the policy; CLI exposes it |
| 7D-3 | KV/allocation hardening: clamp to `min(free_mem/2, cgroup_limit, cap)`; cross-check `block_count` vs `blk.N.*` prefixes; unlink-before-map on POSIX; disk-space check; `close()`/constructor preserve the original exception | Hostile header tests pass; cgroup-limited run refuses cleanly; repeated open/close leaks no fd/mmap; original exception is not masked |

**Required checks**
```bash
python -m pytest -m "not gpu" -q -k "memory or kv or residency or parser"
python -m pytest -m gpu -q -k "residency or kv"
python tests/test_cpu_only.py && python -O tests/test_cpu_only.py
# cgroup-limited probe, e.g. systemd-run --scope -p MemoryMax=...
# fd/mmap leak probe: repeat open/close 1000x, check /proc/self/fd and maps
```

**QAQC adversarial checks**
- `general.alignment=0`, truncation, huge `block_count`, negative/zero dims, duplicate names.
- `block_count` says 999 but only 2 `blk.*` prefixes exist.
- KV directory on a full filesystem; symlink at the target path; crash/kill before close.
- `close()` with a live view: mapping is released or a clear warning is emitted; fd is closed; original constructor error survives.
- Residency: model smaller than budget → pinned; model larger → streamed; no silent fallback.

**Exit criteria (G4)**
- [ ] Memory behavior matches the documented policy.
- [ ] Hostile inputs fail closed.
- [ ] No fd/mmap leaks; exception masking fixed.
- [ ] 70B "bounded RAM" claim either evidenced or removed.

**Stop:** Do not start 7E until G4 is signed.

---

### 7E — Stream topology and pipeline (Gate G5)

**Audit trace:** P-1 residual; v0.6.2 §6 P1-4.
**Allowed files:** `src/kernels/attention.hip`, `src/python_bindings/bindings.cpp`, tests, docs, evidence. **No Python API changes without approval.**

**Work packages**

| ID | Task | Acceptance |
|---|---|---|
| 7E-1 | Explicit compute stream + `compute_done` event; copy stream waits on compute; kernels launch on the compute stream; remove `hipStreamWaitEvent(0, ...)` reliance | Event graph reviewed; one synchronization per token (or documented per-layer boundary); no implicit NULL-stream dependency |
| 7E-2 | Double-buffer weight staging (or per-projection buffers); pinned host staging (`hipHostRegister` / pinned slab); overlap copy with compute | Two in-flight weight slots; no overwrite while a kernel reads; measured overlap |
| 7E-3 | `ensure()` / `ensure_weight()` sync before free/realloc; destructor waits or drains; per-thread default-stream test | No use-after-free under stress; no race under `HIP_LAUNCH_BLOCKING` / serialized and normal modes |

**Required checks**
```bash
python -m pytest -m gpu -q -k "stream or layer or e2e"
python tests/test_layer.py
python tests/test_full_model.py
python tests/test_phase5_scale.py
# stress: repeated forward passes, varying M, forced realloc, per-thread default stream
```

**QAQC adversarial checks**
- Review the event graph line by line: every async copy has a consumer wait; every free has a preceding sync.
- Force buffer growth/shrink between calls; force an exception after enqueue; run many iterations.
- Compare output before/after the change on the same seed; must be identical or within documented tolerance.
- Confirm the claimed overlap with timing/event evidence, not just code shape.

**Exit criteria (G5)**
- [ ] Correctness unchanged on all GPU suites.
- [ ] No implicit NULL-stream reliance; race/stress test passes.
- [ ] Overlap is demonstrated or the claim is removed.
- [ ] Single sync/token (or documented exception) is measured.

**Stop:** Do not start 7F until G5 is signed.

---

### 7F — Evidence and release gates (Gate G6)

**Audit trace:** T-1..T-7, B-1 residual, unverified hardware claims; v0.6.2 §6 P1-6.
**Allowed files:** `tests/**`, `.github/workflows/**`, `scripts/bench/**` (new), `scripts/qa/**`, `audit/CLAIMS_LEDGER.md`, `README.md`, docs, evidence.

**Work packages**

| ID | Task | Acceptance |
|---|---|---|
| 7F-1 | Register the self-hosted gfx1150 runner with labels `gfx1150`, `rocm`; remove `continue-on-error` from `ci-gpu.yml` (added in 7A-7) and make `pytest -m gpu` required on PR + nightly | GPU CI green on a real runner with no `continue-on-error`; logs/artifacts retained; branch protection requires it |
| 7F-2 | Real Q4_K_M/Q6_K GGUF golden run: fixed prompt, `temperature=0`, fixed seed; compare token IDs exactly and logits within a stated tolerance vs llama.cpp | Token IDs match; logits within tolerance; artifacts committed |
| 7F-3 | Benchmark harness: warm-up, `hipEvent`, ≥20 iterations, median/p95, hardware/ROCm recorded, checked-in baseline; fail on regression beyond an agreed ratio | Reproducible numbers; baseline file; CI gate or documented manual gate |
| 7F-4 | Telemetry: `--stats` / `--json` with bytes read, major faults, GTT peak, per-kernel ms, tok/s; `perf_counter` everywhere | Metrics reproducible; no prompt leakage in logs |
| 7F-5 | **Claims release gate:** `scripts/qa/check_claims.py --strict` runs in CI and the release checklist with `audit/claims_baseline.txt` **empty**; it diffs `audit/CLAIMS_LEDGER.md` against `README.md`/`IMPLEMENTATION_PLAN.md` and fails if any `UNVERIFIED`/`NOT YET` claim appears unqualified, or if a `VERIFIED` row lacks an existing evidence path | Release-blocking; baseline empty; canary claim fails; ledger/README diff is part of the release evidence; no unqualified `phi3`/`gemma`, chat, or throughput claim remains |

**Required checks**
```bash
python -m pytest -m "not gpu" -q
python -m pytest -m gpu -q
python tests/test_cpu_only.py && python -O tests/test_cpu_only.py
python scripts/qa/check_claims.py --strict
test ! -s audit/claims_baseline.txt            # baseline must be empty at G6
python scripts/bench/run.py --model <fixture> --json > bench.json
git diff "$(git merge-base HEAD origin/main)" -- audit/CLAIMS_LEDGER.md README.md IMPLEMENTATION_PLAN.md
```

**QAQC adversarial checks**
- Re-run from a clean clone on a clean machine; verify artifact hashes.
- Confirm token IDs are compared exactly, not "close enough".
- Confirm benchmark includes warm-up and reports variance; rerun to check stability.
- Confirm claims ledger matches measured numbers; delete or qualify any unsupported claim.
- Inject an `UNVERIFIED` canary into `README.md` and confirm 7F-5 fails; inject a `VERIFIED` row with a missing evidence path and confirm it fails.
- Confirm the GPU CI job is required (no `continue-on-error`) and would block a red GPU suite.

**Exit criteria (G6)**
- [ ] CPU + GPU CI green; GPU job is required, not `continue-on-error`.
- [ ] Golden token/logit artifacts pass.
- [ ] Benchmark baseline and regression gate exist.
- [ ] Telemetry works and is documented.
- [ ] Claims check is release-blocking and green; no `UNVERIFIED`/`NOT YET` claim appears unqualified in public docs.
- [ ] Auditor signs the release candidate.

**Release statement:** text-only llama-family `Q4_0`/`Q4_K`/`Q8_0` on gfx1150. No Qwen2/Llama-3 chat, Phi-3, or Gemma claim unless G2/G3 evidence exists. No throughput claim without 7F-3 artifacts.

---

### 7G — Post-release polish (Gate G7, deferred)

Only after v0.7.0. Candidate items: PEP 639 license, `__version__`, namespace package (`gfx1150/`), `top_k`/`top_p` validation, `dequantize_q6_k_cpu` block guard, `embed_tokens` boundary guard, `matmul` positive-dim validation, flash-style attention + GQA sharing, RoPE scaling (linear/YaRN), sliding-window attention, continuous batching, prompt cache. Each gets its own work package and gate; do not bundle.

---

## 7. QAQC gate checklist (use for every gate)

### 7.1 Generic checklist

- [ ] Candidate SHA is frozen; `git status --porcelain` is clean.
- [ ] Diff is limited to the package's allowed files; no unrelated changes.
- [ ] Every claim has a command and an artifact under `audit/evidence/`.
- [ ] Red evidence exists on the parent; green evidence exists on the candidate.
- [ ] CPU suite passes normal and `-O`.
- [ ] GPU suites pass on the recorded gfx1150 environment (when in scope).
- [ ] No test was deleted, skipped, or weakened without written approval.
- [ ] No new dependency/network access without approval.
- [ ] Error paths and hostile inputs are tested, not just happy paths.
- [ ] Docs and compatibility matrix match behavior.
- [ ] Claims ledger updated; `scripts/qa/check_claims.py` default mode passes from 7A-6 onward; `--strict` passes at G6 with an empty baseline.
- [ ] GPU CI workflow exists; its `continue-on-error` state matches the phase (allowed in 7A–7E, forbidden at G6).
- [ ] Rollback plan is stated and plausible.
- [ ] Commit messages reference the work package and audit IDs.

### 7.2 Gate-specific additions

| Gate | Additional checks |
|---|---|
| G1 | Mutation test at least one fix; goldens external; GPU tests skip on CPU; claims checker mutation-tested; `ci-gpu.yml` present and valid |
| G2 | Special-token longest match; `add_bos` precedence; no silent byte loss |
| G3 | Real GGUF tensor names; head-dim math; llama regression; no fake support claim |
| G4 | cgroup/full-disk/symlink/huge-header; fd/mmap leak; exception masking |
| G5 | Event-graph review; stress/realloc; output equivalence; overlap evidence; GPU workflow run (or tracked `continue-on-error`) |
| G6 | Clean-clone reproduction; exact token IDs; benchmark variance; claims ledger diff vs README; `check_claims.py --strict` release-blocking with empty baseline; GPU CI required |
| G7 | Same as G1–G6, scoped to the item |

### 7.3 Verdicts

- **PASS** — all criteria met; auditor may approve.
- **PASS WITH CONDITIONS** — non-blocking issues with a written follow-up and owner; auditor decides whether the next package may start.
- **FAIL** — any stop condition or unmet acceptance criterion; coder reworks; no next package.

---

## 8. Handoff templates

Copy these into the PR/issue. Do not replace them with prose summaries.

### 8.1 Coder completion report

```markdown
## Work package: 7B-1 — Special-token encode
Audit trace: C-2, N-2, T-3
Parent SHA: <sha>
Candidate SHA: <sha>
Files changed: <list; confirm within allowed set>
Public API changes: <none | details + versioning>
Design summary: <5–10 lines>

Tests added/changed (map to audit IDs):
- <test name> — <audit ID> — <what it proves>

Red evidence: audit/evidence/G2/7B-1/red.log — `<command>` → <failure>
Green evidence: audit/evidence/G2/7B-1/green.log — `<command>` → <pass>
CPU suite: <log path, result>
GPU suite: <log path, result | N/A>
Sdist install: <log path, result | N/A>

Known limitations / follow-ups:
- <item>

Rollback: <how to revert safely>
Docs updated: <files>
Claims changed: <claims ledger rows>
Self-assessment against gate checklist: <pass/fail per item>
```

### 8.2 QAQC report

```markdown
## QAQC — Gate G2 (7B Tokenizer)
Candidate SHA: <sha>
Environment: <CPU/GPU/ROCm/Python>
Clean checkout: <path> — `git status` clean

Commands run and results:
| Command | Result | Log |
|---|---|---|
| ... | PASS/FAIL | ... |

Independent probes (not the coder's tests):
- <probe> → <result>

Regression results:
- CPU normal / -O: ...
- GPU: ...
- Llama golden: ...

Adversarial checks:
- <check> → <result>

Evidence verification:
- Red log fails on parent: yes/no
- Green log passes on candidate: yes/no
- Provenance complete: yes/no
- Hashes/artifacts: ...

Verdict: PASS | PASS WITH CONDITIONS | FAIL
Conditions/blockers:
- <item>

Sign-off: <name/model, date>
```

### 8.3 Auditor gate decision

```markdown
## Auditor decision — Gate G2
Candidate SHA: <sha>
Traceability review: <audit IDs covered / not covered>
Evidence sufficiency: <sufficient / gaps>
Risk review: <residual risks>
Decision: APPROVE | HOLD | REJECT
Conditions (if HOLD):
- <item + owner + deadline>
Next work package authorized: <ID or none>
Claims ledger updated: yes/no
Sign-off: <date>
```

### 8.4 Blocker report

```markdown
## Blocker — <work package>
Stop condition triggered: <one of §2.2>
Impact: <what cannot proceed>
Evidence: <logs/paths>
What was tried: <list>
Options:
1. <option + trade-off>
2. <option + trade-off>
Recommendation: <option>
Decision needed by: <date/role>
```

---

## 9. Test matrix and CI topology

| Layer | Runs on | Trigger | Contents |
|---|---|---|---|
| **CPU unit/integration** | GitHub `ubuntu-latest` | Every push/PR | Parser, fuzz, tokenizer goldens, sampler, model-spec, KV safety, packaging, CPU quantizers |
| **CPU packaging** | `ubuntu-latest` | Every push/PR | sdist build, clean install (`SKIP_CMAKE=1`), import CPU modules, run CPU suite |
| **GPU correctness** | Self-hosted gfx1150 | PR (`continue-on-error` from 7A-7; **required at G6**) + nightly | Kernels, layer, E2E, golden token IDs/logits |
| **GPU performance** | Self-hosted gfx1150 | Nightly/manual | Warm-up + ≥20-iteration medians, regression ratio |
| **Claims/packaging** | `ubuntu-latest` | Every push/PR + release | `check_claims.py` default (PR) / `--strict` (release), sdist build/install, README/ledger diff |
| **Release gate** | Self-hosted gfx1150 | Tag/release | Full matrix + sdist full install + claims ledger + required GPU CI |

**Tolerances:** use relative/statistical tolerances for FP16 (e.g. max error ≤ a documented multiple of ULP + quant error), not a single absolute constant for all K. Golden token IDs are exact. Logits use a stated absolute/relative bound per model.

**Skips:** `pytest.importorskip("matmul_module")` and `@pytest.mark.gpu`; a skip is visible in the report, never a silent pass.

---

## 10. Claims ledger (required, machine-checkable)

Maintain `audit/CLAIMS_LEDGER.md` (seeded 2026-11-01; update during 7.0 and at every gate). Every public claim gets a row with a **README match string** and a **qualified?** flag so the gate can be enforced mechanically:

| ID | Claim | Status | README match (literal) | Qualified in place? | Evidence | Scope |
|---|---|---|---|---|---|---|
| 1 | Builds from sdist | VERIFIED | `Builds and installs from the sdist` | n/a | `audit/evidence/G0/.../sdist-install.log` | gfx1150 host |
| 6 | Real `Q4_K_M` support | PARTIAL | `Q4_K_M` | yes, inline | 7F-2 | synthetic today; real GGUF pending |
| 8 | Chat special tokens | NOT YET | `<\|im_start\|>` | no | 7B-1 | not implemented |
| 10 | Qwen2 support | NOT YET | `qwen2` | yes, "verified: llama, qwen2" | 7B/7C | metadata only |
| 11 | Phi-3 support | NOT YET | `phi3` | yes, "metadata resolves, not supported" | 7C | not supported |
| 12 | Gemma support | NOT YET | `gemma` | yes, "metadata resolves, not supported" | 7C | not supported |
| 13 | 983 tok/s | UNVERIFIED | `983` | no | 7F-3 | synthetic, owner-only |

**Enforcement (`scripts/qa/check_claims.py`, added in 7A-6; `--strict` is release-blocking at G6):**
- Parse the ledger table; every row must have a valid status, a match string, and an evidence pointer for `VERIFIED`.
- Scan `README.md` and `IMPLEMENTATION_PLAN.md` for each `UNVERIFIED` / `NOT YET` match string.
- Fail if a match appears and `Qualified in place?` is `no`.
- Fail if a `VERIFIED` row's evidence path does not exist.
- Fail if the ledger has not changed in a PR that changes a claim line in `README.md`/`IMPLEMENTATION_PLAN.md` (release check: `git diff` includes both files).
- Inline qualification must be within the same paragraph/bullet as the match, not only in a separate later section.

**Ratchet (adoption without weakening the release gate):**
- `audit/claims_baseline.txt` lists known violations, one per line as `<claim-id> <path> <literal>`, each with a target gate of `G6`. It is **not** a waiver of the claim.
- Default CI mode (7A-6 onward) exits non-zero for new violations but tolerates exact baseline entries; it also warns on any entry whose target gate has passed.
- `--strict` (G6/release) ignores the baseline entirely and fails on every violation. At G6 the baseline file must be empty.
- QAQC must review the baseline at G1 and reject it if it hides a claim that can be fixed cheaply (e.g. the `phi3`/`gemma` bullet).

Rules:
- `UNVERIFIED` claims must be removed or explicitly labelled before release.
- A claim's scope must name model family, quant, context, hardware, and software versions.
- Performance claims require the benchmark artifact and the exact command.
- The auditor updates the ledger when accepting/rejecting a gate; the coder updates it in the same PR as any public-claim change.

---

## 11. Traceability matrix

Status as of the 2026-11-01 verification. `D` = deferred to 7G.

| Audit ID | Finding | Status | Work package |
|---|---|---|---|
| B-1 | sdist missing sources | ✅ fixed + full install verified | 7.0 / 7A-5 |
| B-2 | unused hipblas/rocblas | ✅ fixed (CMake) | — |
| B-3 | setup.py quality | ◐ partial (pybind11_DIR fixed; preflight/bounded -j present; clean-clone command open) | 7A-8 |
| B-4 | PEP 639 license | ❌ open | 7G |
| B-5 | top-level namespace | ❌ open | 7G |
| C-1 | Q6_K unsupported | ✅ kernels + CPU; real GGUF golden pending | 7F-2 |
| C-2 | GPT-2/Ġ tokenizer | ◐ plain text fixed; special tokens/`add_bos` open | 7B |
| C-3 | arch keys / biases | ◐ metadata fixed; Phi-3/Gemma open | 7C |
| C-4 | RoPE scaling | ❌ open | 7G |
| C-5 | SWA / attention biases / per-layer KV heads | ❌ open | 7G |
| C-6 | host transposes | ✅ `matmul_nt` | — |
| C-7 | generation edges | ✅ fixed | — |
| C-8 | sampler validation | ✅ fixed (minor `top_k`/`top_p==0`) | 7G |
| C-9 | quantizer fidelity / goldens | ◐ self-referential tests | 7A-3 / 7F-2 |
| C-10 | parse hygiene | ✅ fixed | — |
| S-1 | unvalidated GGUF | ✅ bounds/alignment/counts; KV clamp open | 7D-3 |
| S-2 | binding validation | ✅ fixed | — |
| S-3 | static workspace race | ✅ mutex | 7E (stress) |
| S-4 | KV file safety | ✅ TOCTOU fixed; crash cleanup/disk check open | 7D-3 |
| S-5 | sys.path injection | ◐ de-prioritized `append`; still dev-only | 7G |
| P-1 | blocking round trips / no overlap | ◐ async syntax, no overlap | 7E |
| P-2 | streaming default / residency | ◐ boolean `cache_weights` | 7D-2 |
| P-3 | quantized prefill tiling | ✅ `TILE_M=4` | — |
| P-4 | GQA attention reuse | ❌ open | 7G |
| D-1 | MADV_DONTNEED claim | ◐ docs softened; mechanism wrong | 7D-1 |
| R-1 | close() fd/mmap leak | ◐ fd fixed; mmap on BufferError open | 7D-3 |
| R-2 | ctor leak/masking | ◐ cleanup present; masking possible | 7D-3 |
| T-1..T-7 | tests/CI/telemetry | ◐ CPU suite; pytest/goldens/fuzz/GPU CI/telemetry open | 7A / 7F |
| N-1 | SentencePiece fallback drop | ✅ retracted (not reproducible) | — |
| N-2 | GPT-2 minimal-vocab byte fallback | ❌ open | 7B-4 |
| N-3 | bias disables fused path | ❌ open | 7C-2 |

---

## 12. Definition of Done (per package and release)

**Per work package**
- [ ] Acceptance criteria met and evidenced.
- [ ] Red→green test pair committed.
- [ ] Full relevant suite green; no regressions.
- [ ] Docs and claims ledger updated.
- [ ] QAQC PASS; auditor APPROVE.
- [ ] Merged with the reviewed SHA; branch deleted.

**Release v0.7.0**
- [ ] G0–G6 signed.
- [ ] CPU + GPU CI green; GPU job required (no `continue-on-error`).
- [ ] sdist full install verified on gfx1150.
- [ ] Golden token IDs/logits pass on a real GGUF.
- [ ] Benchmark baseline recorded; no unsupported perf claim.
- [ ] `check_claims.py --strict` green with an empty `audit/claims_baseline.txt`; README/ledger diff reviewed; no unqualified `UNVERIFIED`/`NOT YET` claim.
- [ ] Compatibility matrix and release statement accurate.
- [ ] No open P0 in the release scope.
- [ ] `audit/RELEASE_VERIFICATION_v0.7.0.md` written and signed.

---

## 13. Change control

- Amendments to this plan require an auditor-written change note (why, what, impact, new gate) and owner approval.
- A new P0 finding discovered mid-phase is handled as a **new work package**, not folded into the current one, unless it blocks the current acceptance criteria.
- Deferring a P0 requires a written exception with risk, mitigation, and target date.
- If a package exceeds 2× its estimate or 2 QAQC failures, the auditor calls a scope review before more code is written.

---

## 14. First action

1. Commit/park the current verification changes and freeze the baseline (7.0).
2. Run G0 and record the evidence bundle (manual GPU baseline; no runner required).
3. Authorize **7A-1** (pytest harness), **7A-6** (claims checker), **7A-7** (GPU workflow scaffold), and **7A-8** (clean-clone build entry point) first; they are independent and unblock the rest of 7A. Use one branch per work package; start with `wp/7A-1-pytest-harness`.
4. Do not authorize 7B until G1 is signed.

The coder receives exactly one work package ID, the allowed file set, the acceptance criteria, and the evidence template. Anything else is out of scope.
