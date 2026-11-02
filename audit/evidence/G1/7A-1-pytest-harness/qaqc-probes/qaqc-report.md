# QAQC Report — Work package 7A-1 (Pytest harness and marker conversion)

**Role:** QAQC (independent session, per handoff §1 and brief §8)
**Date:** 2026-11-02
**Tree tested:** candidate `f0ce20e0021a313d3cb23a33f9b97b2638f56176` via a fresh
`git clone` to `/tmp/opencode/qaqc-7a1/clone` (no `build/`, `PYTHONPATH` unset for the
clean-host probes). Branch tip `cefebef` verified identical to the candidate for
`tests/**` and `pyproject.toml` (evidence commits add only bundle files).
**Probes:** `probe-commands.log` (this directory) — full transcript with exit codes.

---

## Verdict

**PASS.** Every 7A-1 acceptance criterion is met and independently reproduced; every
recorded claim in the coder report verifies; no stop condition (handoff §2.2) is
triggered; the diff is strictly inside the allowed file set (`tests/**`,
`pyproject.toml` pytest section, evidence bundle) with **zero** `src/`, `CMakeLists.txt`,
`.github/`, ledger, or public-doc changes. Adversarial probes — including two the coder
did not run — confirm the harness is genuinely fail-capable and self-enforcing.

Three minor record corrections (QF-1..QF-3) are recommended for the auditor; none is
blocking, none affects an acceptance criterion or a gate datum, and none requires
re-running the package. Two carry-forwards to later packages (QF-4/QF-5) were verified
rather than merely accepted.

---

## Acceptance criteria — all reproduced

| Criterion (brief/handoff 7A-1) | Claimed | QAQC result |
|---|---|---|
| `pytest -m "not gpu"` collects only CPU tests, passes on CPU | 37 passed, 18 deselected | **Reproduced exactly** — 37 passed, 18 deselected, exit 0 (gfx1150 host and clean clone) |
| `pytest -m gpu` collects only GPU tests | 18/55 collected | **Reproduced** — 18/55, exit 0 |
| `pytest -m gpu` passes on gfx1150 | 18 passed, 0 skipped | **Reproduced** — 18 passed, 37 deselected, exit 0 (G0 baseline `.so` per `env.txt`) |
| `pytest -m gpu` skips cleanly without the extension | 18 skipped, exit 0 | **Reproduced** — 18 skipped, 0 passed, 0 errors, exit 0, actionable build-command reason |
| Clean clone, no pre-built extension (QAQC-2 fix) | exit 0 (was exit 2, 4 collection errors) | **Reproduced** — `-m "not gpu"` 37 passed; `-m gpu` 18 skipped; `--collect-only` exit 0 |
| A test returning `False` fails | exit 1 | **Reproduced and strengthened** — both `return False` **and** `return True` canaries FAIL (exit 1) |
| No `def test_* -> bool` remains | grep empty | **Reproduced** — no matches |
| One mutated assertion fails | exit 1 → restored → exit 0 | **Reproduced and strengthened** — the recorded `test_matmul` mutation (1e-12) fails, and a QAQC mutation in a *different* module (`test_layer` rmsnorm `2e-3`→`1e-12`) also fails; both restore to green |
| `test_cpu_only.py` 12/12 normal and `-O`; runnable without pytest | 12/12 | **Reproduced** — 12/12 in all modes, including with `import pytest` blocked (ci-cpu.yml stays green) |
| Five GPU scripts still run standalone | exit 0 each | **Reproduced** — exit 0 each |

## Static verification (no weakening)

- **Test names identical** per file, parent → candidate (no test deleted, added, or renamed).
- **Assert counts never drop**: matmul 0→3 (+1 raise), gguf_and_q4 9→11, layer 0→6,
  full_model 9→9, phase5_scale 25→25 (raises 5→5). The suite is strictly stronger.
- **Every numeric tolerance identical**: `1e-3`, `1e-2`, `2e-3`, `5e-3`, `5e-2` all carried
  over verbatim; the only semantic change is `if x >= t: FAIL` → `assert x < t`
  (logically equivalent). Numeric-literal deltas outside comparison expressions are
  restructure noise only.
- **No module-scope `matmul_module` import remains in any test module** (AST check);
  `src/layer.py`, `src/kv_cache.py`, `src/inference.py` keep their module-scope imports —
  correctly untouched, since the test bodies now defer their imports of those packages.
- **Allowed file set respected**: only `tests/**`, the `[tool.pytest.ini_options]` section
  of `pyproject.toml`, and `audit/evidence/G1/**`. Ledger, `claims_baseline.txt`,
  `.github/`, `README.md`, `IMPLEMENTATION_PLAN.md`, `MANIFEST.in`, `setup.py`,
  `CMakeLists.txt`, `src/`: all empty diffs.
- **G0 record correction verified**: the G0 "30 passed" was 12 CPU + 18 GPU (no markers
  existed); the corrected split is 37 CPU (+25 new harness meta-tests) / 18 GPU, and the
  same 18 GPU tests exist at the parent.

## Adversarial probes beyond the coder's set

1. **`return True` canary** — the coder probed only `return False`; a test that returns
   `True` is equally unfailable-by-assertion. It FAILS (escalated warning), exit 1. ✅
2. **Harness self-enforcement against *new* files** — injecting the canary file also
   tripped the contract meta-tests (`test_no_test_function_returns_a_value` and
   `test_every_test_function_asserts_or_raises` on the new module), so the contract is
   enforced against future files, not just the converted ones. 4 failed → exit 1. ✅
3. **Second mutation in a different module** (`test_layer` rmsnorm) — fails properly.
   Mutation detection is not local to `test_matmul`. ✅
4. **`--strict-markers` hygiene** — an unregistered marker on an injected test is
   rejected at collection (exit 2), so a typo'd marker can't silently deselect a lane. ✅
5. **`-m cpu` selects the same 37** as `-m "not gpu"` — the `cpu` marker is consistent
   with the deselection semantics. ✅
6. **sdist packaging probe** — see QF-1/QF-4 below.

## Findings (minor, non-blocking)

### QF-1 — The sdist limitation is half wrong (notes §6.1, coder-report limitation 1)
The bundle claims both `tests/conftest.py` and `tests/test_harness_contract.py` are
excluded from the sdist. Empirically (QAQC probe P10): **`test_harness_contract.py` IS
packaged** (it matches setuptools' `tests/test_*.py` default); **only `conftest.py` is
excluded**. The claim was made without running the sdist command. The actionable
conclusion is unaffected — 7A-5 must still add `recursive-include tests *.py` (for
`conftest.py`) — but the sentence should be corrected when the auditor lands 7A-5 or a
notes erratum.

### QF-2 — "Two commits" wording again understates the package
`notes.md` §4 says 7A-1 is "two commits"; it is four (implementation `f0ce20e`, bundle
`773ff12`, notes-structure `37ee6c6`, coder report `cefebef`). Same self-reference
pattern as G0 F-5, resolved there by the erratum wording "a content commit plus
follow-up commits" — adopt it here for consistency.

### QF-3 — "13 tests could not fail" is a rounded version of the truth
Precisely: 13 test functions returned **bool** at the parent (of which 5 also had
asserts and could fail); 9 had **no failure mechanism at all**; a 14th
(`test_v061_…`) returned a tuple from a nested helper but had asserts and raises. The
fix covers all of them (every test function now asserts and returns `None`), so this is
a precision note, not a defect.

### QF-4 — Carry-forward to 7A-5 (verified): `conftest.py` missing from the sdist
Confirmed by probe: an sdist-installed tree has no `conftest.py`, hence no
`matmul_module` fixture and no gpu-lane skip. A CPU CI job running `pytest -m gpu` from
such a tree would **error** instead of skip. 7A-5's `MANIFEST.in` fix is genuinely
required; 7A-5 should also then assert the sdist tree collects cleanly.

### QF-5 — Carry-forward to 7A-7 (verified): the gpu lane skips, never errors, when the
extension is absent — correct for CPU hosts, but on gfx1150 the lane must be asserted to
**run** (18 passed, 0 skipped). QAQC confirms both sides: on gfx1150 with the extension
the lane runs 18/18; without it the lane reports 18 skips with the actionable build
command. 7A-7's workflow should fail on any skip in the gpu lane, exactly as the notes
recommend.

## QAQC checklist (handoff §7.1)

- Candidate SHA frozen; tree clean — ✅ (clean clone, 0 dirty; no force-push; 4 linear
  commits on the parent).
- Diff limited to allowed files — ✅ (verified per-path).
- Every claim has a command and artifact — ✅ for the package claims; one exception
  noted (QF-1: the sdist limitation was asserted without a probe; QAQC probed it).
- Red/green — ✅ properly declared `N/A (no behavioral change)` per the updated §4;
  canary + mutation probes provide the fail-capability evidence instead.
- CPU suite normal and `-O` — ✅ 12/12 both, with and without pytest.
- GPU suites on gfx1150 — ✅ 18 passed, plus all five standalone scripts exit 0.
- No test deleted, skipped, or weakened — ✅ names, counts, and tolerances all preserved
  or strengthened.
- No new runtime dependency — ✅ pytest is test-only; `[project]` dependencies unchanged.
- Docs/ledger — ✅ untouched (no behavior or claim change).
- GPU CI workflow — N/A at 7A-1 (7A-7 owns it).
- Rollback — ✅ plausible (tests + pytest config only).
- Commit messages reference the package — ✅ (`7A-1` / `G1/7A-1` prefixes).

## Disposition

7A-1 **passes QAQC** and is recommended to the auditor for approval. Per the brief,
7A-6 / 7A-7 / 7A-8 may start from the same base once the auditor accepts; **G1 remains
unsigned** (7A-2..7A-5 are still outstanding). QF-1/QF-2 can be folded into a small notes
erratum or into the 7A-5 package; QF-4/QF-5 are requirements on 7A-5/7A-7, already
acknowledged in the coder's notes and now independently verified.

**QAQC sign-off:** 2026-11-02. Probe transcript: `probe-commands.log` (this directory).
Clone and scratch retained at `/tmp/opencode/qaqc-7a1/` for inspection.
