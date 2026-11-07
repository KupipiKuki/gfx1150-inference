# Phase 7A-4 Coder Brief — Deterministic GGUF Fuzz

**To:** GLM5.3 (coder)
**From:** DeepSeek V4.1 Flash (primary auditor)
**Date:** 2026-11-04
**Branch:** `wp/7A-4-fuzz`
**Base:** `vibe/phase7-220201` @ `d2d55ea` (7A-3 merged, G1 pending this package)
**Gate:** G1 item **7A-4** — the last open G1 package. **G1 remains unsigned**; 7B remains blocked until G1.

The goal is **executable evidence that malformed GGUF headers cannot crash the parser**,
not a coverage percentage.

---

## 1. Allowed files

- `tests/**` (new fuzz module; register in `EXPECTED_LANES`)
- `tests/fixtures/**` only if a small seed corpus is useful
- `.github/workflows/**` (install `hypothesis`; adjust slow-test selection in the sdist job)
- `audit/evidence/G1/7A-4/**`
- docs

**Do not touch** `src/**`, `CMakeLists.txt`, `setup.py`, `pyproject.toml`, `README.md`,
`IMPLEMENTATION_PLAN.md`, `scripts/qa/**`, the ledger, the baseline, or other packages’
evidence. If fuzzing finds a parser defect, **stop and write a blocker report**; the fix
is a new work package, not a 7A-4 edit.

---

## 2. Fuzz target

Add `tests/test_fuzz_gguf.py` (or similarly named), CPU-lane and marked `slow`, using
`hypothesis`.

Seed with a **valid minimal GGUF v3 buffer** built in the test (header + metadata +
tensor index). Generate mutations with structured strategies, not only random bytes:

- `general.alignment`: 0, 1, 3, huge, non-power-of-two;
- `kv_count` / `tensor_count`: 0, large, count-vs-bytes mismatch;
- string/array lengths: huge, truncated;
- `n_dims`: 0, 5..8, huge;
- dimensions: zero, huge, product overflow;
- `ggml_type`: valid, unknown, reserved;
- tensor offsets/sizes: misaligned, overlapping, `abs_offset + n_bytes > len(buf)`;
- duplicate tensor names;
- truncated buffers at the header, metadata, tensor-index, and data boundaries;
- interleaved non-layer tensor names (layer-span hull case).

For each example:

- parse either succeeds, or raises the parser’s documented `ValueError` /
  `GGUFFormatError`;
- any other exception (`struct.error`, `IndexError`, `KeyError`, `OverflowError`,
  `MemoryError`, `UnicodeDecodeError`, etc.) is a **failure**;
- no unbounded allocation (bound input size/counts; a hostile header must fail closed,
  not OOM);
- no file descriptor / mmap leak (the parser takes a memoryview; if a temp file is used,
  assert cleanup).

Settings:

```python
from hypothesis import settings
@settings(max_examples=10_000, derandomize=True, deadline=None, database=None)
```

`derandomize=True` + `database=None` makes the CI run deterministic and independent of a
local `.hypothesis` database. Do not hide failures with broad `suppress_health_check`;
if a health check fires for a legitimate reason, document it and adjust the strategy.

---

## 3. CI wiring

- Add `hypothesis` to the CPU job’s dependencies and to the sdist-install venv (the
  shipped test module imports it; otherwise the packaging job gets a collection error).
- The CPU job runs the fuzz test (blocking).
- The sdist-install job may deselect `slow` (`-m "not slow"` on its two lane steps) so
  packaging stays fast; the CPU job owns the 10k-example run.
- Keep the claims steps and the `test_cpu_only.py` runs unchanged.
- Register `test_fuzz_gguf.py` as `cpu` in `tests/test_harness_contract.py::EXPECTED_LANES`.

---

## 4. Acceptance

- The fuzz test runs **10,000 examples** deterministically; two runs produce the same
  result.
- No unhandled exception from a malformed/truncated/duplicate/hostile header; failures
  are minimized by Hypothesis if any are found.
- CPU lane green; GPU lane unchanged; `test_cpu_only.py` 12/12 normal and `-O`; claims
  checker unchanged.
- The sdist-install job still collects/runs the CPU lane (with `hypothesis` installed)
  and deselects `slow` only.
- No `src/`, CMake, packaging, README/PLAN, ledger, baseline, or CI semantics change
  beyond the stated dependency/selection edits.
- If a real parser defect is found: stop, preserve the minimizing example, and file a
  blocker/new package. Do **not** edit `src/` here.

---

## 5. Evidence

`audit/evidence/G1/7A-4/` with:

```
env.txt  parent-sha.txt  candidate-sha.txt  diffstat.txt
fuzz.log                  # 10k examples, deterministic seed/profile
fuzz-rerun.log            # second run, same result
cpu-lane.log  gpu-lane.log
sdist-install.log  ci-run.log
notes.md
```

`red/green` is **N/A** if no defect is found (green resilience evidence). If a defect is
found, the minimized failing example and the blocker report are the red evidence; do not
merge a fix in this package.

---

## 6. Stop

After the fuzz test and CI wiring are ready, stop for QAQC. Do not start 7B on this
branch. G1 remains unsigned until 7A-4 is audited; 7B remains blocked.
