# Auditor probes — 7A-9 (BLOCKER-7A4-1 fix)

**Auditor:** DeepSeek V4.1 Flash
**Date:** 2026-11-04 (UTC 2026-11-05)
**Candidate:** `1bce3d0` · **Tip:** `9493cf8` · **Parent:** `3af32d4`

| Probe | Result |
|---|---|
| Scope `3af32d4..1bce3d0` | exactly 4 files; `src/` is the 2-line ARRAY check |
| Red (parent, `--runxfail`) | `RecursionError` |
| Green (candidate, `-k nested`) | 3 passed |
| Depths 1/2/5/300/992/1000/5000 | `ValueError("GGUF array element type must not be an array")` |
| Depth 0 | valid scalar-element array; parses (expected) |
| Minimized 992 example | 11,962 bytes, sha256 `28fe58bf8fee9e0d9e0987b3cc2e09922ffb968f9f8809de34c7305d086bbebb` |
| `count=0` nested | rejected before count is used |
| Valid arrays (6 scalar types + empty) | parse with correct values |
| Huge count / type 99 / truncated body / bad magic | unchanged `ValueError`s; no `RecursionError` |
| CPU lane | 111 passed / 24 deselected / 4 xfailed |
| `--runxfail` CPU | 4 failed (tokenizer only), 111 passed |
| GPU lane | 24 passed / 115 deselected |
| `test_cpu_only.py` / `-O` | 12/12 / 12/12 |
| Claims checker | PASS — 0 new / 17 baselined / 0 findings |
| 10k fuzz | 2 passed |
| QAQC probes | 21/21 parent, 21/21 candidate |
| CI `41954045892` | success (CPU + sdist), head `9493cf81` |
| CI `41954045836` | success (clean-clone), head `9493cf81` |

Transcript: `probe-commands.log`.
