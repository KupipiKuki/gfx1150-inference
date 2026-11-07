# Auditor probes — 7A-4

**Auditor:** DeepSeek V4.1 Flash
**Date:** 2026-11-04
**Candidate:** `a14fcfa` · **Tip:** `5795107`

| Probe | Result |
|---|---|
| CI run `41762204487` | API: **completed / success**, head `a14fcfa` |
| CPU lane | **108 passed / 24 deselected / 5 xfailed** |
| GPU lane | **24 passed / 113 deselected** |
| `--runxfail` | 5 failures: 4 tokenizer pins + nested-array blocker |
| Fuzz settings | 10,000 examples, `derandomize=True`, `database=None`, `deadline=None` |
| Fuzz statistics | 6,386 ValueError / 3,614 accepted / **0 other exceptions** |
| `test_cpu_only.py` / `-O` | 12/12 each |
| Scope | only `ci-cpu.yml`, `test_fuzz_gguf.py`, `EXPECTED_LANES`, evidence; restricted diff empty |
| **BLOCKER-7A4-1** | Confirmed in `src/gguf_parser.py` `_read_value`: ARRAY element type recurses |
| Minimized example | `_nested_array_header(992)` = 11,962 bytes, sha256 `28fe58bf8fee9e0d9e0987b3cc2e09922ffb968f9f8809de34c7305d086bbebb` |
| Boundary | depth 300 parsed invalid; depth 1000 `RecursionError`; threshold stack-dependent |
| Pinned test | strict xfail; fails under `--runxfail` |
| Fix proposal | reject `ARRAY` as element type; correct |

Full transcript: `probe-commands.log`.
