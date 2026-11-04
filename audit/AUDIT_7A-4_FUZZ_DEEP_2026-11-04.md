# Independent 7A-4 Audit — Deterministic GGUF Fuzz

**Auditor:** DeepSeek V4.1 Flash (primary auditor)
**Date:** 2026-11-04
**Target:** `wp/7A-4-fuzz` @ `5795107` (work commit `a14fcfa`)
**Base:** `758e500` (7A-4 prep; 7A-3 merged)
**Coder:** GLM5.3 · **QAQC:** independent session (`qaqc-probes/qaqc-report.md`)
**Scope:** 7A-4 only. **G1 decision:** see `audit/G1_SIGNOFF_2026-11-04.md`.

---

## 1. Verdict

**PASS.** The fuzz does what the package required: 10,000 deterministic examples,
structured mutations across every requested class, zero unhandled exceptions in the
drawn fuzz space, two identical runs, and a real parser defect found, minimized,
pinned, and reported as **BLOCKER-7A4-1**. `src/` was correctly left untouched.

The parser is **not yet fail-closed** because of BLOCKER-7A4-1. That is a carry-forward
fix in a new `src/` package, not a 7A-4 failure. G1 is signed with that limitation
explicit; see the signoff document.

---

## 2. Reproduction

| Check | Result |
|---|---|
| CPU lane | **108 passed / 24 deselected / 5 xfailed** |
| GPU lane | **24 passed / 113 deselected** |
| `--runxfail` | 5 expected failures: 4 tokenizer pins + the nested-array blocker |
| `test_cpu_only.py` / `-O` | 12/12 each |
| Fuzz settings | `max_examples=10_000, derandomize=True, deadline=None, database=None` |
| Fuzz statistics | 6,386 rejected (ValueError) / 3,614 accepted / **0 other exceptions** |
| Determinism | `fuzz.log` and `fuzz-rerun.log` identical apart from timings |
| CI run `41762204487` | API: **completed / success**, head `a14fcfa` |
| Scope | `ci-cpu.yml`, `test_fuzz_gguf.py`, `EXPECTED_LANES`, evidence; no `src/`, packaging, README/PLAN, ledger, baseline |
| Hypothesis wiring | CPU job and sdist venv install it; sdist job deselects `slow`, CPU owns 10k |
| Lane registration | `test_fuzz_gguf.py` = `cpu`; `slow` on the fuzz tests |

## 3. BLOCKER-7A4-1

I reproduced the defect from the test’s own helper:

- `_nested_array_header(992)` is **11,962 bytes**, sha256
  `28fe58bf8fee9e0d9e0987b3cc2e09922ffb968f9f8809de34c7305d086bbebb` — exactly the
  blocker’s pinned example.
- At depth 300 (3.6 KiB) the invalid nested-array file is **accepted**.
- At depth 1000 the parser raises **`RecursionError`** instead of the documented
  `ValueError`.
- The exact threshold is stack-depth-dependent (our run: 992 parsed, 1000 recursed;
  QAQC measured a different flip), which the blocker documents; the hash-pinned example
  is the stable artifact.
- The defect is confirmed in `src/gguf_parser.py` `_read_value`: an `ARRAY` element type
  recurses with no scalar check.
- `test_nested_arrays_are_rejected_with_a_value_error` is `xfail(strict=True)` and fails
  under `--runxfail`; the fix (reject an `ARRAY` element type with `ValueError`) is
  correct. A recursion limit is not needed for a valid GGUF (no nesting allowed).

The fuzz’s own space excludes this known class so the 10k contract stays green; the
dedicated pinned test covers it. That is the right trade-off and does not weaken the
property.

## 4. Findings

- **QF-1 (Minor, blocker wording):** `BLOCKER.md` §3.1 says every caller catches
  `ValueError`; `WeightStreamer`/engine clean up and re-raise either exception, and the
  CLI catches neither. The genuine contract consumers are the tests and external
  callers. Soften the wording in the blocker/fix package. Does not affect the defect.
- **No other findings.** The fuzz, CI wiring, lane registration, and scope meet the
  brief.

## 5. Gate impact

- **7A-4:** PASS.
- **BLOCKER-7A4-1:** open, P0 carry-forward; fix is a new `src/` package with the
  strict xfail as acceptance.
- **G1:** signed with the parser limitation made explicit (see
  `audit/G1_SIGNOFF_2026-11-04.md`).
- **7B:** unblocked by G1 + the 7A-3 goldens, but the parser blocker fix is P0 and
  should be prioritized; 7B can proceed in parallel.
- **Release:** do not claim a fail-closed parser until BLOCKER-7A4-1 lands.

## 6. Sign-off

**7A-4 decision: PASS.** The fuzz found a real defect, pinned it, and proved the rest of
the drawn space clean.

**Sign-off:** DeepSeek V4.1 Flash, 2026-11-04.
