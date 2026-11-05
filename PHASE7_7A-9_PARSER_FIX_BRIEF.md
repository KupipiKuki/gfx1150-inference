# Phase 7A-9 Coder Brief — BLOCKER-7A4-1 Parser Fix

**To:** GLM5.3 (coder)
**From:** DeepSeek V4.1 Flash (primary auditor)
**Date:** 2026-11-04
**Branch:** `wp/7A-9-gguf-array-fix`
**Base:** `vibe/phase7-220201` @ `e9b6b80` (G1 signed; 7A-4 merged)
**Gate:** post-G1 **P0** fix. G1 is already signed; the release remains blocked until this lands.

This is the one-line `src/` fix the 7A-4 fuzz found. Do not bundle 7B or other work into
it.

---

## 1. The defect

`GGUFParser._read_value` reads a metadata array’s element type and then recurses with
`self._read_value(elem_type)`. An element type of `ARRAY` is invalid in GGUF but is not
rejected, so a nested-array header recurses (a ~12 KiB hostile file raises
`RecursionError`) and below the threshold the invalid file is accepted.

Full report: `audit/evidence/G1/7A-4/BLOCKER.md`.

## 2. Required fix

In `src/gguf_parser.py`, at the `ARRAY` branch of `_read_value`, reject an `ARRAY`
element type with the parser’s documented `ValueError` before reading the values:

```python
if vtype == GGUFValueType.ARRAY:
    elem_type, count = self._read_fmt("<IQ")
    if elem_type == GGUFValueType.ARRAY:
        raise ValueError("GGUF array element type must not be an array")
    ...
```

A recursion-depth limit is optional defence only; a valid GGUF has no nested arrays, so
the scalar check is sufficient. Do not change unrelated parser behavior.

## 3. Tests

- Remove the `xfail` from
  `tests/test_fuzz_gguf.py::test_nested_arrays_are_rejected_with_a_value_error`; it must
  now pass.
- Add/assert both boundary cases:
  - the below-threshold nested header (depth 300) raises `ValueError` instead of
    parsing;
  - the pinned minimized example (`_nested_array_header(992)`, 11,962 bytes, sha256
    `28fe58bf…`) raises `ValueError`; depth 1000 is also acceptable coverage.
- Keep the fuzz/direct tests and the 10k fuzz unchanged.
- Ensure the parser still raises `ValueError` for all existing malformed/truncated
  classes; no regression.

## 4. Documentation / record

- Soften the `BLOCKER.md` §3.1 QF-1 wording (“every caller in this repository catches
  `ValueError`” → the parser’s documented contract, asserted by the tests and followed
  by external consumers). Mark the blocker status fixed.
- Remove the BLOCKER-7A4-1 exception from the `IMPLEMENTATION_PLAN.md` fail-closed
  claim once the fix is verified.
- Update the claims ledger only if the parser claim is represented there; otherwise
  leave it.
- Do not touch CMake, packaging, CI, ledger arithmetic, 7A-4 evidence, or 7B files.

## 5. Acceptance

- Pinned nested-array test passes with no xfail; depth 300 and the minimized 992/1000
  examples raise `ValueError`.
- CPU lane green with the nested xfail gone (expected **109 passed / 24 deselected /
  4 xfailed**; the remaining 4 are tokenizer 7B/7C pins).
- `--runxfail` shows only the four tokenizer failures, no parser failure.
- GPU lane unchanged (24 passed); `test_cpu_only.py` 12/12; claims checker green.
- `src/` diff is limited to the array check; no parser regression.
- Public parser claim no longer carries the exception.

## 6. Evidence

`audit/evidence/G1/7A-9/` with:

```
env.txt  parent-sha.txt  candidate-sha.txt  diffstat.txt
red.log                  # pinned test fails on parent
green.log                # same test passes on candidate
nested-array-boundary.log
fuzz.log  cpu-lane.log  gpu-lane.log  runxfail.log
notes.md
```

`red/green` is the pinned test: fails before, passes after. Record the exact commands
and the minimized example hash.

## 7. Stop

Stop for QAQC/auditor. 7B may proceed in parallel from the same base. The release/G6
remains blocked until this fix is accepted.
