# Auditor probes — 7A-6

**Auditor:** DeepSeek V4.1 Flash
**Date:** 2026-11-02
**Candidate:** `994d62922af7ed9f5b9546d787d8c05606cdb8f1`
**Tip verified:** `f0a73a18cbfdc661f878d645f0fdae34a4fe1e2c` (code/ledger/CI identical)
**Clean clone:** `/tmp/opencode/audit-7a6`

| Probe | Result |
|---|---|
| Default `check_claims.py` | exit 0, 0 new / 17 baselined / 0 expired / 0 findings |
| `--strict` | exit 1, 17 unqualified |
| `--json` | valid, `ok=true`, 30 claims, 17 baselined |
| Canaries | 10/10 pass |
| Canary mutation (force checker exit 0) | exactly 8/10 canaries fail |
| CPU / GPU lanes | 37 passed / 18 passed |
| Baseline | byte-identical to parent (15 exact entries) |
| Ledger statuses/flags | unchanged vs parent; only literals + scope annotations |
| A2 second unqualified `qwen2` | **fails** — README:115 NEW VIOLATION |
| A3 baseline entry removed | **fails** — README:109 NEW VIOLATION |
| A4 wildcard baseline | exit 2 |
| A5 malformed baseline | exit 2 |
| A6 invalid status | exit 1, `invalid-status` |
| A7 duplicate claim ID | exit 2 |
| A9 line shift | exit 0, exactly 13 drift warnings |
| A10 qualifier bullet removed | exit 1, 5 stale-scope + 1 unresolved |
| **Strict-clean output** | **exit 0 but prints `RESULT: FAIL`** — finding AUD-7A6-1 |

Full transcript: `probe-commands.log`.
