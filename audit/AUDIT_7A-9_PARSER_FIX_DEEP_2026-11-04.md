# Independent 7A-9 Audit — BLOCKER-7A4-1 GGUF Nested-Array Fix

**Auditor:** DeepSeek V4.1 Flash (primary auditor)
**Date:** 2026-11-04 (evidence timestamps 2026-11-05 UTC)
**Target:** `wp/7A-9-gguf-array-fix` @ `9493cf8`
**Work commit:** `1bce3d0` · **Parent:** `3af32d4` (brief prep; code identical to G1 base `e9b6b80`)
**Coder:** GLM5.3 · **QAQC:** independent session (`audit/evidence/G1/7A-9/qaqc-probes/`)
**Gate:** post-G1 **P0** carry-forward from 7A-4. Closes **C-G1-1**.

---

## 1. Verdict

**PASS — no conditions.** BLOCKER-7A4-1 is fixed and independently reproduced.
`GGUFParser._read_value` now rejects a metadata array whose element type is
`ARRAY` with the parser’s documented `ValueError` before reading any values.
The invalid class is rejected at every nesting depth tested (1, 2, 5, 300,
992, 1000, 5000), the stack-exhaustion path is gone, and valid arrays and
every pre-existing malformed class behave as before.

The fix is the exact two-line scalar check the blocker report proposed. No
recursion limit was added, correctly: a valid GGUF has no nested arrays, so the
element-type check removes the recursion entirely.

---

## 2. Reproduction

| Check | Result |
|---|---|
| Scope (`3af32d4..1bce3d0`) | 4 files: `src/gguf_parser.py`, `tests/test_fuzz_gguf.py`, `IMPLEMENTATION_PLAN.md`, `audit/evidence/G1/7A-4/BLOCKER.md` — nothing else |
| Functional `src/` diff | only the `ARRAY` element-type check in `_read_value` (2 lines) |
| Red (parent `3af32d4`, `--runxfail`) | pinned test fails with `RecursionError: maximum recursion depth exceeded` |
| Green (candidate `1bce3d0`) | `pytest tests/test_fuzz_gguf.py -k nested` → **3 passed** |
| Boundaries (independent) | depths 1, 2, 5, 300, 992, 1000, 5000 → `ValueError: GGUF array element type must not be an array`; depth 0 is a **valid** scalar-element array and still parses |
| Minimized example | `_nested_array_header(992)` = **11,962 bytes**, sha256 `28fe58bf8fee9e0d9e0987b3cc2e09922ffb968f9f8809de34c7305d086bbebb` — matches BLOCKER §2; test asserts both length and digest |
| `count=0` nested array | rejected before the count is used |
| Valid arrays | int32 / string / uint64 / bool / float32 / uint32 / empty all parse with correct values |
| Existing rejections | huge count, unknown element type 99, truncated array body, truncated header, bad magic — same `ValueError`s; no `RecursionError` |
| CPU lane | **111 passed / 24 deselected / 4 xfailed** |
| `--runxfail` CPU lane | **4 failed** — only the tokenizer 7B/7C pins; no parser failure |
| GPU lane | **24 passed / 115 deselected** |
| `test_cpu_only.py` / `-O` | **12/12 OK / 12/12 OK** |
| Claims checker | **PASS** — 0 new violations, 17 baselined, 0 expired, 0 findings |
| 10k fuzz | unchanged; re-run on the candidate → **2 passed** (41.5 s) |
| CI `41954045892` (CPU + sdist) | **completed / success**, head `9493cf81` |
| CI `41954045836` (clean-clone build) | **completed / success**, head `9493cf81` |
| QAQC probes | 21/21 in parent mode, 21/21 in candidate mode |

The QAQC evidence bundle is complete and its claims match my independent runs.
The three pushed commits are correctly separated: `1bce3d0` is the work
commit, `d83a052` is the coder evidence bundle, `9493cf8` is the QAQC bundle.

---

## 3. What the fix does and does not prove

**Proved:**

- The nested-array class is rejected with `ValueError` at every depth, not only
  above the old stack threshold. The former silent acceptance (depth 300) and
  the `RecursionError` path are both gone.
- No parser regression in the valid-array or pre-existing malformed classes the
  suite and probes cover.
- The 10k deterministic fuzz is unchanged and still green.

**Not claimed:**

- This is not a proof that every possible malformed GGUF is rejected. The
  public wording is scoped to “every malformed class the suite covers”; that is
  the honest bound. Release/G6 remains blocked on the later gates (7B/7C/7D/7E/7F),
  not on 7A-9.

---

## 4. Findings

- **QF-1 (Informational, not caused by 7A-9):** the claims checker still reports
  line-drift warnings for claims 6, 13, 26, and 27 after the Phase 8 / prep
  edits to `IMPLEMENTATION_PLAN.md`. The checker result is **PASS** (warnings,
  not violations or findings). Ledger arithmetic was explicitly out of scope
  for 7A-9; refresh the scope line references in a separate 7A-6/7E
  housekeeping change.
- **QF-2 (Informational):** the brief predicted 109 CPU passes; the actual is
  111 because the former xfail now passes (+1) and the two required boundary
  tests were added (+2). The arithmetic is correct and the remaining four
  xfails are the tokenizer pins.
- **No blocking findings.**

---

## 5. Gate impact

- **7A-9:** PASS.
- **BLOCKER-7A4-1:** fixed; accepted.
- **C-G1-1 (P0 parser fix):** **closed.**
- **C-G1-2 (public claim correction):** **closed** — the `IMPLEMENTATION_PLAN.md`
  claim no longer carries the nested-array exception, and the `BLOCKER.md` §3.1
  QF-1 wording now describes the documented contract rather than “every caller
  in this repository”.
- **G1:** remains signed; conditions **C-G1-3** (GPU CI queued until 7F-1) and
  **C-G1-4** (tokenizer xfails) remain open.
- **7B:** authorized and independent; it does not depend on 7A-9.
- **Release/G6:** still blocked by G2/G3 and the later gates. The parser may now
  be described as fail-closed for the malformed classes the suite covers.

---

## 6. Evidence

- `audit/evidence/G1/7A-9/` — coder + QAQC bundle (red/green, boundaries, fuzz,
  lanes, runxfail, env, diffstat, notes, probes)
- `audit/evidence/G1/7A-9/audit-probes/` — this audit’s probes
- `audit/evidence/G1/7A-4/BLOCKER.md` — blocker record, now fixed
- CI: `41954045892` (CPU + sdist), `41954045836` (clean-clone), both success
- `audit/G1_SIGNOFF_2026-11-04.md` — conditions updated

---

## 7. Sign-off

**7A-9 decision: PASS.** BLOCKER-7A4-1 is fixed; the pinned test passes without
xfail, the boundary cases raise `ValueError`, and every lane and CI check is
green. No conditions.

**Signed:** DeepSeek V4.1 Flash, primary auditor — 2026-11-04.
