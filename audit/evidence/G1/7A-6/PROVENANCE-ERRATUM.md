# 7A-6 evidence provenance erratum

**Raised by:** the independent 7A-6 audit (`audit/AUDIT_7A-6_CLAIMS_CHECKER_DEEP_2026-11-02.md`
§4, condition C-7A6-3), which confirmed QAQC's findings 1–3.
**Closed by:** the 7A-6 follow-up (this bundle: `audit/evidence/G1/7A-6-followup/`).
**Date:** 2026-11-02.

This file is the erratum the handoff allows in place of editing the captured
logs. **No captured log was edited**: `claims-check.log`, `canary-claims.log`,
`canary-nested.log`, `canary-wronglane.log`, `cpu-suite.log`, `gpu-suite.log`,
`gate-commands.log` and `env.txt` are exactly as the 7A-6 candidate produced
them.

---

## 1. `f6924ff` and `994d629` are the same candidate

The 7A-6 bundle's log headers and `env.txt` name `f6924ff` as the candidate.
`candidate-sha.txt` names `994d629`. Both refer to **the same work**: `f6924ff`
is a pre-amend commit that was amended into `994d629`.

```
$ git show -s --format='%H %P %s' f6924ff
f6924ff... 4bcffeb... G1/7A-6: add the claims checker, its canaries and the ledger scope annotations

$ git show -s --format='%H %P %s' 994d629
994d629... 4bcffeb... G1/7A-6: add the claims checker, its canaries and the ledger scope annotations
```

The restricted delta between them is **empty** — the amend touched evidence
files only:

```
$ git diff --stat f6924ff..994d629 -- src tests scripts .github \
      audit/CLAIMS_LEDGER.md audit/claims_baseline.txt
(empty)

$ git diff --stat f6924ff..994d629
 audit/evidence/G1/7A-6/canary-claims.log    | 2 +-
 audit/evidence/G1/7A-6/canary-nested.log    | 2 +-
 audit/evidence/G1/7A-6/canary-wronglane.log | 2 +-
 audit/evidence/G1/7A-6/candidate-sha.txt    | 2 +-
 audit/evidence/G1/7A-6/claims-check.log     | 2 +-
 audit/evidence/G1/7A-6/cpu-suite.log        | 2 +-
 audit/evidence/G1/7A-6/env.txt              | 5 +++--
 audit/evidence/G1/7A-6/gate-commands.log    | 2 +-
 audit/evidence/G1/7A-6/gpu-suite.log        | 2 +-
 9 files changed, 11 insertions(+), 10 deletions(-)
```

**Conclusion.** The evidence is valid for the candidate `994d629`. `f6924ff`
is unreachable from any branch and will eventually be garbage-collected, which
is why it must not be cited as the candidate.

**Authoritative records.** `audit/evidence/G1/7A-6/candidate-sha.txt` and
`audit/evidence/G1/7A-6/parent-sha.txt` are the authoritative provenance
(candidate `994d629`, parent `4bcffeb`). Where a log header names a
different SHA, that header is a capture artifact and the authoritative file
wins.

## 2. `diffstat.txt` summary line corrected

`diffstat.txt` recorded "17 files changed, 2661 insertions(+), 23 deletions(-)",
captured before the final evidence-file edits. The true `4bcffeb..994d629`
figure is:

```
$ git diff --shortstat 4bcffeb..994d629
 17 files changed, 2691 insertions(+), 24 deletions(-)
```

`diffstat.txt`'s summary line has been corrected to 2691 / 24. Its per-file
diffstat was already correct and was not touched.

## 3. `env.txt` repeats the `candidate:` line

`env.txt` contains the `candidate:` line three times, with different spacing.
This is a capture artifact: `env.txt` was written once per amend cycle, and
each cycle rewrote the header while the earlier copies of the line stayed in
the file. **The repetition is not a discrepancy** — every copy names the same
candidate, and `candidate-sha.txt` is authoritative.

`env.txt` was **not** edited (it is a captured log). This section is the note
the audit asked for.

## 4. What the 7A-6 follow-up changed in the 7A-6 bundle

For completeness — the follow-up's changes to `audit/evidence/G1/7A-6/`:

| file | change | why |
|---|---|---|
| `diffstat.txt` | summary line 2661/23 → 2691/24 | condition C-7A6-3 |
| `qaqc-probes/probe-commands.log` | corrected (B2 exit, A10 removal + findings, summary labelled, "see earlier run" replaced by results) and a corrections section added | condition C-7A6-2 |
| `qaqc-probes/qaqc-report.md` | the two `final-probe-commands.log` references now name the files that exist | condition C-7A6-2 |
| `qaqc-probes/probe-commands-full.log` | **new** — the full probe transcript, reproduced at the follow-up commit | condition C-7A6-2 |

`notes.md` and `coder-report.md` were **not** edited; they remain the 7A-6
package's own record. Where the follow-up supersedes them (the ID 3 literal
rule, the strict-clean rendering), the follow-up's `notes.md` says so
explicitly.
