# G1 / 7A-9 — BLOCKER-7A4-1 parser fix

**Package:** 7A-9 (post-G1 P0: the GGUF nested-array parser fix)
**Branch:** `wp/7A-9-gguf-array-fix`
**Parent:** `3af32d4` (brief-prep commit; `src/` and `tests/` identical to the
G1 base `e9b6b80`)
**Candidate:** `1bce3d0` (work commit under review)

---

## The defect and the fix

`GGUFParser._read_value` read a metadata array's element type and recursed
into `_read_value(elem_type)` without checking the element type. An `ARRAY`
element type is invalid in GGUF, so a nested-array header recursed once per
nesting level: a ~12 KiB hostile file raised `RecursionError`, and
below-threshold nesting (depth 300, 3.6 KiB) was **accepted**. Both are
BLOCKER-7A4-1 (`../7A-4/BLOCKER.md`).

The fix is exactly the blocker report's proposed line, in
`src/gguf_parser.py::_read_value`:

```python
if elem_type == GGUFValueType.ARRAY:
    raise ValueError("GGUF array element type must not be an array")
```

raised before the values are read. `src/` otherwise untouched — see the
`diffstat.txt` src diff, which is the entire functional change. No
recursion-depth limit was added: the brief's optional defence is unnecessary
once the invalid element type is rejected, and the brief's fix was preferred
as the minimal change.

## red / green

The pinned test is `tests/test_fuzz_gguf.py::
test_nested_arrays_are_rejected_with_a_value_error`; the red/green pair is
that test with the xfail removed (`--runxfail` on the parent).

- **red** (`red.log`): on the parent, `--runxfail` fails with
  `RecursionError: maximum recursion depth exceeded`.
- **green** (`green.log`): on the candidate, the strict xfail is gone and
  the test passes.
- **boundary** (`nested-array-boundary.log`): depth 300 (below the old
  threshold; previously *accepted*) raises `ValueError`, and the minimized
  example from the blocker report —
  `_nested_array_header(992)`, **11,962 bytes**, sha256
  `28fe58bf8fee9e0d9e0987b3cc2e09922ffb968f9f8809de34c7305d086bbebb` —
  raises `ValueError`. The length and the digest are asserted in the test,
  so the example cannot silently change shape.

Exact commands (all from the repo root, on the candidate):

```
python3 -m pytest tests/test_fuzz_gguf.py::test_nested_arrays_are_rejected_with_a_value_error --runxfail -v   # red, on 3af32d4
python3 -m pytest tests/test_fuzz_gguf.py::test_nested_arrays_are_rejected_with_a_value_error -v              # green, on 1bce3d0
python3 -m pytest tests/test_fuzz_gguf.py -k nested -v                                                       # the three nested tests
python3 -m pytest tests/test_fuzz_gguf.py::test_fuzz_gguf_headers tests/test_fuzz_gguf.py::test_fuzz_gguf_headers_are_deterministic -v  # the 10k fuzz, re-run
python3 -m pytest -m "not gpu" -q        # the CPU lane
python3 -m pytest --runxfail -m "not gpu" -q
python3 -m pytest -m gpu -q              # the GPU lane
python3 tests/test_cpu_only.py && python3 -O tests/test_cpu_only.py
python3 scripts/qa/check_claims.py
```

## Results

| lane | result |
|---|---|
| CPU lane | **111 passed / 24 deselected / 4 xfailed** |
| `--runxfail` CPU lane | **4 failed** (the tokenizer 7B/7C pins only), 111 passed; no parser failure |
| GPU lane | **24 passed** (unchanged) |
| `tests/test_cpu_only.py` | **12/12 OK**, in both `python3` and `python3 -O` |
| claims checker | **PASS** — 0 new violations, 17 baselined, 0 findings |
| the 10k fuzz | **2 passed** (both fuzz tests, re-run on the candidate), no unhandled exception |

The brief expected "109 passed / 24 deselected / 4 xfailed"; the +2 are the
two boundary tests the brief itself required (the count was written before
they were added). The remaining 4 xfails are the tokenizer 7B/7C pins, as
the brief states.

## Test-suite notes

- The strict xfail is removed; the test now asserts the documented
  behaviour directly (a `ValueError`), for the depth-1000 header it already
  covered.
- Two new tests: `test_a_nested_array_below_the_recursion_threshold_is_rejected`
  (depth 300) and `test_the_minimized_nested_array_example_is_rejected`
  (depth 992 with the length and sha256 assertions).
- The harness contract requires a top-level `assert`/`raise` in every test;
  the new tests use the module's existing try/except idiom rather than
  `pytest.raises` to satisfy it (the first CPU-lane run caught this; the
  committed form passes).
- The fuzz, the direct tests and the module's lane markers are unchanged.

## Documentation

- `../7A-4/BLOCKER.md`: status marked **fixed by Phase 7A-9**; §3.1's QF-1
  wording now states the parser's documented contract (asserted by the
  tests) rather than repo-internal caller behaviour, per the brief.
- `IMPLEMENTATION_PLAN.md` success criterion: the BLOCKER-7A4-1 exception is
  removed from the fail-closed claim, replaced by a pointer to this
  evidence.
- The claims ledger does not carry a parser-claim row, so per the brief it
  is left untouched.
- Not touched: CMake, packaging, CI workflows, `scripts/qa/**`, ledger /
  baseline arithmetic, the 7A-4 evidence records (other than the status and
  QF-1 wording the brief requires), and the 7B files.

## Claims-checker scope drift (pre-existing, informational)

`check_claims.py` reports that claim 26's scope
`IMPLEMENTATION_PLAN.md:261` drifted to line 300 and claim 27's
`IMPLEMENTATION_PLAN.md:266` to line 305. That drift comes from the
brief-prep commit `3af32d4` (+2 lines to the plan), not from this package;
the checker result is still PASS and the ledger is out of scope here
("do not touch ledger arithmetic"). Flagged for the auditor / 7A-6.

## Verdict

The nested-array class is rejected with the parser's documented
`ValueError` at every depth; the stack-exhaustion path and the silent
acceptance of invalid files are both gone. Every lane is green with the
xfail removed. Ready for QAQC/auditor review; per the brief, stop here —
G6 remains blocked until the fix is accepted.
