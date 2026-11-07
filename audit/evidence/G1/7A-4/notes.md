# G1 / 7A-4 — Deterministic GGUF fuzz

**Package:** 7A-4 (G1 item: deterministic fuzz for the GGUF header parser)
**Branch:** `wp/7A-4-fuzz`
**Base:** `vibe/phase7-220201` @ `758e500` (7A-3 + follow-up merged)
**red/green:** **N/A** in the usual sense — this package is green *resilience*
evidence. But the fuzz **found a real parser defect**, which is filed as
**BLOCKER-7A4-1** (`BLOCKER.md`); that finding is the red.

---

## The headline

The fuzz runs 10,000 deterministic examples against the GGUF parser and finds
**no unhandled exception** in the mutation space the brief defines: every
malformed header is either accepted or rejected with the parser's documented
`ValueError`.

It also found **one** defect outside that space: a header whose metadata array
has an `ARRAY` element type makes the parser **recurse until the interpreter's
stack is exhausted**, so a hostile file of about 12 KiB raises `RecursionError`
instead of a `ValueError`. That is filed as **BLOCKER-7A4-1** with the
minimized example, the threshold and the proposed fix. Per the brief, `src/` is
**not** touched here: the fix is a new work package.

So the honest verdict on this package is: *the parser fails closed for every
malformed header the brief lists, and there is one documented way in which it
does not.*

---

## What was added

### `tests/test_fuzz_gguf.py` — the fuzz

CPU-lane (the module's only lane marker is `cpu`, as the harness contract
requires), with the fuzz tests marked `slow` so that the packaging job can
deselect them.

| test | what it does |
|---|---|
| `test_fuzz_gguf_headers` | 10,000 examples: the buffer must be accepted or rejected with a `ValueError`; any other exception fails. The layer helpers are exercised on the accepted buffers |
| `test_fuzz_gguf_headers_are_deterministic` | 10,000 examples: parsing the same buffer twice must give the same result |
| `test_nested_arrays_are_rejected_with_a_value_error` | the known defect, pinned (strict xfail) — see below |
| `test_the_layer_span_is_split_by_an_interleaved_foreign_tensor` | the interleaved layer-span hull case, checked directly |
| `test_a_duplicate_tensor_name_is_rejected` | the duplicate-name case, checked directly |
| `test_parsing_from_a_file_releases_the_descriptor` | the file and mapping path: no descriptor or mapping is leaked |

The settings are exactly the brief's:

```python
@settings(max_examples=10_000, derandomize=True, deadline=None, database=None)
```

`derandomize=True` fixes the seed and `database=None` keeps the run
independent of any local `.hypothesis` database. Two runs of the fuzz differ
only in their wall-clock timings (`fuzz-rerun.log`).

### The seed and the mutations

The seed is a **valid minimal GGUF v3 buffer built in the test** — header,
metadata and tensor index — and the mutations are *structured*: the test draws
a **description** of a GGUF file and serialises it, so an example is a
well-formed file except in the way the test intends. That is why the fuzz
reaches deep into the parser instead of being rejected at the first check.

Every mutation class the brief lists is drawn, and every one of them is
exercised hundreds to thousands of times over the run
(`fuzz.log`, from `measure-fuzz-coverage.py`):

| mutation class | examples carrying it |
|---|---|
| `general.alignment` (0, 1, 3, huge, non-power-of-two) | 570 |
| `kv_count` (0, large, count-vs-bytes mismatch) | 1 052 |
| `tensor_count` | 1 456 |
| string / array lengths (huge, truncated) | 708 |
| `n_dims` (0, 5..8, huge) | 1 270 |
| dimensions (zero, huge, product overflow) | 9 560 |
| `ggml_type` (valid, unknown, reserved) | 801 reserved + 2 275 unknown |
| tensor offsets / sizes (misaligned, overlapping, past the end) | 763 |
| duplicate tensor names | 3 022 |
| the version (not 2 or 3) | 2 215 |
| truncation at the header, metadata, tensor-index and data boundaries | the strategy's `_Built.boundaries` |

And the parser's answer to 10,000 drawn buffers:

| outcome | count |
|---|---|
| accepted | **3 614** (of which 929 with a tensor table) |
| rejected with the documented `ValueError` | **6 386** |
| **any other exception** | **0** |

So the fuzz exercises the successful path as well as the rejection path, and
the layer-span helpers are reached (the dedicated interleaved test states the
expected result).

The writer is defensive by construction: it never sizes a buffer from a
hostile field (the payload is capped, the padding uses a safe alignment), so a
hostile value always reaches the *parser* rather than destabilising the
harness. The input is bounded at 64 KiB, so a hostile header cannot make the
harness itself unsafe.

### The known defect, pinned

`test_nested_arrays_are_rejected_with_a_value_error` is a **strict** xfail: it
asserts the behaviour the parser *should* have (a `ValueError`), so it fails
today and passes when the defect is fixed — and because it is strict, the
suite fails if it starts passing while the xfail is still in place, so the fix
cannot land unnoticed.

The fuzz's own space keeps to the GGUF format's rule that an array's element
type is a scalar. That is not a way of hiding the defect: the defect has its
own test, its own minimized example, and a blocker report. The fuzz's
contract — *any unhandled exception is a failure* — is not weakened.

---

## The CI wiring

| change | where |
|---|---|
| `hypothesis` added to the CPU job's dependencies | `ci-cpu.yml`, the `cpu-smoke` job |
| `hypothesis` added to the sdist-install venv | `ci-cpu.yml`, the `sdist-install` job |
| the sdist job's CPU lane deselects `slow` | `python -m pytest -m "not gpu and not slow" -q` |
| the sdist job's full lane deselects `slow` | `python -m pytest -m "not slow" -q -rs` |
| the CPU job's lane is unchanged | it runs the fuzz, blocking |

The venv needs `hypothesis` even though the fuzz is deselected there: the
shipped module *imports* it at collection time, and without it the packaging
job would fail with a collection error.

The rehearsal of the whole job (`sdist-install.log`) shows the effect: the
packaging job's CPU lane runs in **3.1 s** instead of ~45 s, with the fuzz
deselected and everything else unchanged.

`EXPECTED_LANES` gains `"test_fuzz_gguf.py": "cpu"`.

---

## What was verified

| check | result |
|---|---|
| the fuzz runs 10,000 examples per test | yes — `10000 passing examples, 0 failing examples` (`fuzz.log`) |
| the run is deterministic | yes — two runs, identical apart from the timings (`fuzz-rerun.log`) |
| no unhandled exception from a malformed / truncated / duplicate / hostile header | yes — 6 386 rejections, all `ValueError`; 3 614 acceptances; **0** other exceptions |
| every mutation class the brief lists is exercised | yes — the table above |
| the CPU lane is green | yes — **108 passed, 24 deselected, 5 xfailed**, exit 0 |
| the GPU lane is unchanged | yes — **24 passed**, exit 0 |
| `test_cpu_only.py` | **12/12** in normal and `-O` mode |
| the claims checker is unchanged | PASS, 12 of 12 canaries |
| the sdist-install job still collects and runs, with `slow` deselected | yes — the rehearsal: 104 passed, 5 xfailed, exit 0 (`sdist-install.log`) |
| the provenance verifier still passes | 137/137 |
| no `src/`, CMake, packaging, README/PLAN, ledger or baseline change | confirmed by `diffstat.txt` |
| no test deleted, skipped or weakened | confirmed — the only xfail added is the one that pins the defect |

The five xfails in the CPU lane are the four pre-existing tokenizer ones (7B)
and the new nested-array one (BLOCKER-7A4-1).

---

## The defect, in short

`GGUFParser._read_value` reads a metadata array by reading its element type
and then reading that many values *of that element type*. Nothing checks that
the element type is a scalar, so an array whose element type is `ARRAY` is read
by recursion, one level per nesting:

| nesting depth | result |
|---|---|
| 991 | parsed (the parser also **accepts** an invalid file) |
| **992** | **RecursionError** |

The minimized example is **11 962 bytes** (58 bytes of header plus 12 bytes
per level), sha256
`28fe58bf8fee9e0d9e0987b3cc2e09922ffb968f9f8809de34c7305d086bbebb`.

Why it matters: a caller that catches `ValueError` — which is what the
parser's documentation and every caller in this repository do — does not catch
`RecursionError`, so the malformed file escapes as an unexpected exception;
and the depth is chosen by the attacker, not by the file size, so it is a
stack-exhaustion path in front of any server that parses untrusted models.

The proposed fix (a **new** package, not this one) is one line at the point
where the array is read: reject an `ARRAY` element type with a `ValueError`.

`BLOCKER.md` has the full report.

---

## Limitations and follow-ups

1. **The parser is not yet fail-closed.** Until BLOCKER-7A4-1 is fixed, G1
   should treat the GGUF parser as having one known hostile-input path. The
   evidence here is that the path is *known, pinned and reported* rather than
   unknown.
2. **The fuzz's space follows the GGUF format** (an array's element type is a
   scalar). That is the format's rule, and the one place where breaking it
   matters is covered by its own pinned test. A future package could widen the
   space deliberately, at the cost of the fuzz's contract.
3. **The fuzz does not cover the file-system path** (mmap, madvise). It parses
   buffers; the file path is covered by one focused test that asserts the
   descriptor and the mapping are released.
4. **The 10,000 examples take ~45 s** on this host. The CPU CI job owns that
   run; the packaging job deselects it.
5. **7A-4 does not fix the defect it found.** That is deliberate: the brief
   forbids a `src/` change here, and the fix is a new work package.

---

## Rollback

Delete `tests/test_fuzz_gguf.py`, remove the `"test_fuzz_gguf.py": "cpu"`
entry from `EXPECTED_LANES`, and revert the two CI edits (the `hypothesis`
dependencies and the `slow` deselection). Nothing else in the repository
changes, so the rollback cannot affect the build, the packaging job or any
other package's evidence. The evidence bundle is additive.

## Claims changed

None. No public claim was added, removed or re-qualified. This package adds a
fuzz, the CI wiring it needs, and the report of the defect it found.
