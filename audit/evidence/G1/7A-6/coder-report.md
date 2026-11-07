# G1 / 7A-6 — claims checker: coder report

**Branch:** `wp/7A-6-claims-checker` · **Parent:** `4bcffeb` · **Audit trace:** AUD-3, T-7
**Status:** complete and ready for QAQC. The coder does not sign G1.

## Summary

The claims ledger was a table nothing enforced. The G0 audit (AUD-3) found that the
manual `claims-check.log` reported "FINDINGS none" while **nine unqualified `no`-flag
rows** plus ID 13's L209 instance plus IDs 6 and 10 were live, and that four literals
(`pip install`, `GPU`, `llama-family`, `test_cpu_only.py`) were too generic to enforce
their claims. 7A-6 makes the ledger enforceable.

`scripts/qa/check_claims.py` now parses the ledger, enforces the `Qualified in place?`
rule, and fails on anything the auditor did not sign off. It reports **all 12**
unqualified rows — the 11 `no`-flag rows plus ID 13 — instead of "none".

## What the auditor asked for, and where it is

| Requirement | Where |
|---|---|
| Main ledger table only, stop at the first non-table line | `check_claims.py` `parse_ledger` — the ratchet sub-tables are prose and are not parsed as claims |
| Validate status, public match, flag per row | `parse_ledger` + `scan_claims` (`invalid-status`, `invalid-flag`, `unreadable scope group`) |
| Scan both public docs for unproven claims, fail if unqualified | `scan_claims` occurrence inventory |
| `VERIFIED` rows need existing evidence paths | `missing-evidence` finding |
| Default mode: tolerate exact baseline entries, fail on new, warn on expired | default mode; `expired_baseline` is a warning, not a failure |
| `--strict` ignores the baseline, fails on every violation | `--strict`; asserted by the `strict_detects_baseline` canary |
| `--json` useful for CI | `--json`; `ok`, `violations`, `expired_baseline`, `findings`, `warnings` |
| Report the unqualified rows, not "FINDINGS none" | 12 rows reported, with file, line and literal |
| 15 exact baseline entries, no wildcards | baseline reviewed and **left unchanged**; `baseline_is_exact` canary |
| ID 6 and 10 are `no`/`partial`, consistent with the ratchet | both `no`; the ledger's ratchet section agrees |
| Claim-specific literals | the four generic literals replaced; the checker rejects generic ones outright |
| Canary tests | `scripts/qa/canary_claims.py`, 10 canaries |
| Wire default mode into CPU CI, strict advisory until G6 | `.github/workflows/ci-cpu.yml` |

## The one design decision worth reviewing

The seeded baseline is **path-level**: `<claim-id> <path> <literal>`. On its own that
cannot distinguish the reviewed unqualified occurrence from a *new* one in the same file,
so an injected claim would be tolerated. The checker therefore needs line-level
precision, and it takes it from the ledger rather than from the baseline file: the
"Qualified in place?" cell now carries a scope annotation that inventories every
occurrence of the claim's literal in the two public documents and classifies each as
`unqualified` / `qualified` / `context`.

`audit/claims_baseline.txt` is **byte-identical** to the auditor's seed — 15 exact
entries, reviewed and confirmed. The extra precision lives in the ledger, where the
auditor owns it.

The classification is mechanical, not a judgement call about wording:

- `unqualified:` — the site asserts the claim without a caveat. These are the ratchet
  items, and they are exactly the sites the baseline covers.
- `qualified:` — the site asserts the claim and qualifies it in place (e.g. ID 8's
  "chat special-token encoding … are not implemented", ID 10's L110 "not yet fully
  supported").
- `context:` — the literal occurs in planning/status prose that does not assert this
  claim (e.g. ID 6's PLAN L25/L165/L170/L179/L265, ID 9's PLAN L241).

Every occurrence must be inventoried. One that is not is a new, unreviewed assertion
and fails the build — which is what makes the ratchet tighten.

## Verification

- `python3 scripts/qa/check_claims.py` → exit 0, `PASS - 0 new violation(s), 17 baselined, 0 expired`.
- `python3 scripts/qa/check_claims.py --strict` → exit 1 (17 unqualified occurrences) — advisory until G6.
- `python3 scripts/qa/canary_claims.py` → all 10 canaries pass.
- `python3 -m pytest -m "not gpu" -q` → 37 passed, 18 deselected (unchanged).
- `python3 -m pytest -m gpu -q` → 18 passed, 37 deselected (unchanged).
- `python3 tests/test_cpu_only.py` and `-O` → 12/12 OK (unchanged).

The canaries were mutation-tested: with the checker forced to exit 0, eight of them
fail, so they test the checker rather than the harness. The two that survive read the
JSON output rather than the exit code, which is the point of those two.

Drift was checked explicitly. Inserting a line at the top of README warns about 13
shifted scope references and still passes (a document edit is not a claim change);
inserting a new unqualified `qwen2` claim fails, wherever it is inserted.

## Things the auditor should look at

1. **The scope annotation syntax** is new to the ledger. It is documented in the
   ledger's Rules section and in the checker's module docstring. If the auditor prefers
   a different notation, the ledger can be re-annotated mechanically — the checker is
   the only consumer.
2. **The `context:` classification** of the PLAN occurrences for IDs 6 and 9. The
   auditor ruled that ID 6's unqualified instance is README L10 and seeded no PLAN
   entry, so those PLAN occurrences are recorded as not asserting the claim. If the
   auditor disagrees, they become `unqualified:` and need baseline entries — which
   would change the 15-entry count the brief specifies.
3. **ID 13 and ID 27 overlap** on `IMPLEMENTATION_PLAN.md` L209 because ID 13's
   literal `983` is a prefix of `983.4 tok/s`. Both rows record both sites; the
   baseline keeps them separate, as seeded.
4. **ID 21** is `partial` with no unqualified site — a wording task for 7D-1, not a
   ratchet item. The checker says so explicitly rather than staying silent.

## Not done here (and why)

- The handoff's "fail if the ledger has not changed in a PR that changes a claim line"
  rule is a **release** check (7F-5 diffs ledger + README + PLAN), not a CI-time
  check. 7F-5 owns it.
- `--strict` cannot pass until G6, when the baseline must be empty and every
  unqualified site must be gone. It is advisory in CI until then.
- The GPU lane reused the G0 build artifact. 7A-6 changes no `src/` file.

## Files touched

| file | change |
|---|---|
| `scripts/qa/check_claims.py` | **new** — the checker |
| `scripts/qa/canary_claims.py` | **new** — 10 canaries |
| `audit/CLAIMS_LEDGER.md` | scope annotations + 4 claim-specific literals + rules text + 7A-6 baseline review |
| `audit/claims_baseline.txt` | **unchanged** (reviewed only) |
| `.github/workflows/ci-cpu.yml` | 3 steps in `cpu-smoke` (jobs only) |
| `audit/evidence/G1/7A-6/**` | evidence bundle |

No `src/`, `pyproject.toml`, `CMakeLists.txt`, `tests/` or packaging change.
