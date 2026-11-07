# Auditor probes — 7A-3

**Auditor:** DeepSeek V4.1 Flash
**Date:** 2026-11-04
**Candidate:** `2c59c5e` · **Tip:** `a9c5785`
**Clean clone:** `/tmp/opencode/audit-7a3`

| Probe | Result |
|---|---|
| `verify-provenance.py` | **137/137**; all tracked fixture hashes match the registry |
| Generator independence | imports only stdlib + NumPy; no `src/`; drives llama.cpp tools/gguf-py |
| Tracked fixtures | 12 files, **2.75 MiB**, each ≤ 2 MB |
| CPU lane | 91 passed / 24 deselected / **2 xfailed** |
| GPU lane | **24 passed** / 93 deselected |
| `--runxfail` | 2 failures: `add_bos` default + special-token encode (expected 7B bugs) |
| Offline golden modules, no extension | 36 passed / 2 xfailed, exit 0 |
| Sdist | **13 fixture entries** |
| CI run `41749187809` | API: **success**, head `2c59c5e` |
| Lane registration | 3 CPU + 1 GPU golden modules in `EXPECTED_LANES` |
| **SentencePiece coverage** | **only one case** (`spm_absent_add_bos_metadata`); no plain/double/multibyte/BOS on-off cases — condition C-7A3-1 |

Full transcript: `probe-commands.log`.
