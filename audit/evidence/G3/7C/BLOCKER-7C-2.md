# BLOCKER-7C-2 — claims canary expected the old baseline count

**Status:** fixed by the post-audit canary commit.
**Found by:** CPU-Only Verification & Regression CI on the fixed 7C merge
(`eab3771`), after `BLOCKER-7C-1` was green for clean-clone/sdist.

## Symptom

The CPU workflow's `Check the claims checker canaries` step failed while all
code lanes and the default claims check passed:

```
FAIL baseline_is_exact: the mutation was NOT detected
baseline holds 14 entries, expected 15
```

7C-4 legitimately removed the resolved `10 README.md qwen2` baseline entry
(the README L129 bullet now qualifies qwen2 in place), so the reviewed baseline
has 14 entries. `scripts/qa/canary_claims.py` still hardcoded
`EXPECTED_BASELINE_ENTRIES = 15`, so the canary rejected the correct baseline.

## Fix

- Set `EXPECTED_BASELINE_ENTRIES = 14` with a comment tying it to the 7C-4
  row-10 resolution and the maintenance rule.
- Make the success message use the constant instead of a hardcoded "15".

This is claims-infrastructure maintenance, not a model-family code change. It
is a justified exception to the 7C allowed-file list because the baseline
removal that G3 required cannot pass the canary otherwise.

## Verification

```
$ python3 scripts/qa/canary_claims.py
PASS not_yet_claim ... PASS id3_claim_removed
RESULT: PASS - all 12 canaries behaved as required
```

`check_claims.py` remains PASS (0 new, 16 baselined, 0 findings). The final CI
run on the canary-fixed merge is recorded in the G3 signoff.
