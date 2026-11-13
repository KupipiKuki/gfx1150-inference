# Auditor probes — 7A-8

**Auditor:** DeepSeek V4.1 Flash
**Date:** 2026-11-02
**Candidate:** `9c04912` · **Tip:** `abc5870`
**Clean clones:** `/tmp/opencode/audit-7a8` (candidate), `/tmp/opencode/audit-7a8-parent` (parent `4bcffeb`)
**Merge simulation:** `/tmp/opencode/audit-7a8-merge` (`vibe/phase7-220201` + 7A-8)

| Probe | Result |
|---|---|
| Parent, shims PATH, no `pybind11_DIR` | exit 1 — pybind11 not found at `CMakeLists.txt:17` |
| Parent, interpreter bin on PATH | exit 0 — “lucky PATH” reproduced |
| Candidate, shims PATH, no hint | exit 0 — `pybind11 CMake package:` marker |
| Candidate, lucky PATH | exit 0 — explicit marker |
| Candidate, `-Dpybind11_DIR=...` | exit 0 — explicit marker |
| Candidate build | exit 0, 592,488-byte `matmul_module.so` |
| Guard on parent CMakeLists | fails — marker absent |
| Guard on candidate | 3/3 pass |
| CPU / GPU / full pytest | 43 / 18 / 61 |
| `test_cpu_only.py` / `-O` | 12/12 each |
| Keyring fingerprint | `D0F004A0025A1145C7807FCD0701EAC4D5E02107` |
| Merge simulation checker | exit 0, **9 drift warnings**, 0 stale, 0 findings |
| Merge drift | claims 8/9 111→130; 10/11/12 110,111→129,130; 21 104→123; ID3 L85–89→L98–102 |
| QF-1 | `ci-build.yml` prerequisites lack pytest — job would fail at smoke test |

Full transcript: `probe-commands.log`.
