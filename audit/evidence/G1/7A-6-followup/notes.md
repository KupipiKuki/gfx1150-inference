# G1 / 7A-6 follow-up — close the auditor conditions

**Package:** 7A-6 follow-up (conditions C-7A6-1, C-7A6-2, C-7A6-3, C-7A6-4)
**Branch:** `wp/7A-6-followup`
**Base:** `b626c94` (the independent audit commit on `wp/7A-6-claims-checker`)
**Content under review:** `994d629` (the 7A-6 candidate)
**Audit trace:** `audit/AUDIT_7A-6_CLAIMS_CHECKER_DEEP_2026-11-02.md` §4
**red/green:** **N/A** — the follow-up changes tooling and evidence only. No
`src/` change, no runtime behaviour change, no public claim added, removed or
re-qualified. The CPU and GPU suites are unchanged (37 passed / 18 deselected,
18 passed / 37 deselected, 12/12).

**The checker is accepted in substance.** The follow-up closes four conditions;
it does not redesign the checker.

---

## C-7A6-1 — strict-clean output must say PASS

**The defect.** `_render()` printed `RESULT: FAIL - N unqualified occurrence(s)`
unconditionally in strict mode. The exit code was correct (0 on a clean ledger),
but the *text* was wrong. At G6 the human-readable `--strict` output is a
release artifact, so it must report the run's actual outcome.

**The fix.** `scripts/qa/check_claims.py` `_render()` now derives the strict
result from `_failed(report, strict)` — the same function the exit code uses —
so a clean run prints `RESULT: PASS`. The default-mode branch was switched to
the same helper, so the two can no longer disagree. The wording is otherwise
unchanged, so the failing case still reads exactly
`RESULT: FAIL - 17 unqualified occurrence(s) (strict mode ignores the baseline)`.

**Red/green** (`strict-clean.log`):

| tree | `--strict` text | exit | `--strict --json` |
|---|---|---|---|
| parent `b626c94` | `RESULT: FAIL - 0 unqualified occurrence(s)` | 0 | `ok: true` |
| candidate | `RESULT: PASS - 0 unqualified occurrence(s)` | 0 | `ok: true` |

The exit code is 0 in both cases — only the text was wrong, which is exactly
the defect.

**New canary `strict_clean`.** It builds the minimal clean tree the auditor
described ("one VERIFIED claim, empty baseline, README/PLAN contain the
literal", evidence present) and asserts that `--strict` exits 0, prints
`RESULT: PASS`, does not print `RESULT: FAIL`, and that `--strict --json`
reports `ok: true`.

**Canary mutation.** `strict_clean` is a *positive* test, so it cannot fail
under the mutation that makes the checker always pass — a checker that agrees
with the expected answer on a clean tree necessarily passes it. It is caught by
the mutation that matters for its purpose (the C-7A6-1 defect). The transcript
records three mutations:

| mutation | canaries failing | note |
|---|---|---|
| force the exit code to 0 | 9 of 12 | the three survivors read the JSON (`baseline_is_exact`, `expired_baseline_entry`) or are positive tests (`strict_clean`) |
| always print `RESULT: FAIL` | 1 of 12 — **`strict_clean`** | this is the C-7A6-1 defect; the new canary catches it |
| the checker does nothing (no output, exit 0) | **12 of 12** | every canary, `strict_clean` included, fails |

## C-7A6-2 — QAQC probe log must match the run

The QAQC probe log was a **summary presented as a transcript**, with three
factual errors and a dangling filename reference.

**What was corrected** (in `audit/evidence/G1/7A-6/qaqc-probes/`):

1. `probe-commands.log` is now explicitly labelled a **summary**, with the
   results stated inline instead of "see earlier run", and it points to the
   full transcript.
2. **B2**: `exit: 0` → `exit: 1` (the strict mode really exits 1 on the real
   tree).
3. **A10**: `lines removed: 0` → `lines removed: 1`, and the findings are now
   stated completely: **5 stale-scope + 1 unresolved-literal = 6 findings**.
4. **A2–A9**: the "see earlier run" placeholders are replaced by the results
   themselves.
5. `qaqc-report.md`: the two references to the non-existent
   `final-probe-commands.log` now name the files that exist, so the sign-off,
   the log header and the directory contents agree.

**The full transcript.** QAQC's scratch tree (`/tmp/opencode/qaqc-76/`) was
ephemeral and is gone, so the transcript was **reproduced from scratch** at the
follow-up commit by `audit/evidence/G1/7A-6-followup/reproduce-probes.py`, and
is committed as `qaqc-probes/probe-commands-full.log`. Every probe runs against
a throw-away copy of the tree (`--root` isolation); the live probe restores
what it touches.

The reproduction agrees with the auditor's independent transcript
(`audit/evidence/G1/7A-6/audit-probes/probe-commands.log`) on every probe:
A2 fails at the injected line, A3 fails with 16 baselined, A4/A5 exit 2, A6
exits 1 with `invalid-status`, A7 exits 2, A9 gives 13 drift warnings and
exits 0, A10 removes 1 line and yields 6 findings, and the strict-clean probe
reproduces the C-7A6-1 defect exactly.

**Provenance.** The corrections were applied by the follow-up coder, not by
QAQC, and each one is itemised at the end of the corrected log. No probe
*result* changed: every corrected number is one the auditor had already
confirmed.

## C-7A6-3 — evidence provenance erratum

Recorded in `audit/evidence/G1/7A-6/PROVENANCE-ERRATUM.md`:

* `f6924ff` (named by the log headers) is a **pre-amend commit** of the same
  work; `candidate-sha.txt` names `994d629`. The restricted code/ledger/CI
  delta between them is **empty**; `git diff f6924ff..994d629` touches 9
  evidence files (+11/−10). `candidate-sha.txt` is authoritative.
* `diffstat.txt`'s summary line is corrected from 2661/23 to the true
  `4bcffeb..994d629` figure, **2691/24**. Its per-file diffstat was already
  correct and was not touched.
* `env.txt` repeats the `candidate:` line three times — a capture artifact of
  the successive amend cycles, not a discrepancy. `env.txt` was **not** edited
  (it is a captured log); the note is in the erratum.

No captured log was edited: `claims-check.log`, `canary-*.log`, `cpu-suite.log`,
`gpu-suite.log`, `gate-commands.log` and `env.txt` are as the 7A-6 candidate
produced them.

## Auditor evidence erratum (2026-11-02, QF-1/QF-2/QF-3)

Applied by the independent auditor after the follow-up QAQC pass; no product code or
checker behaviour changed.

* **QF-1 — reproducer crash.** `reproduce-probes.py` `probe_b()` B5 fell back to
  `out.strip().splitlines()[-1:]` (a list) when no `passed`/`failed` line existed, so a
  fresh clone without a built extension crashed with `TypeError` on the `18 skipped`
  path. Fixed to `(out.strip().splitlines() or [""])[-1]`; re-run from a clean clone with
  no extension and no `PYTHONPATH` (transcript in `reproduce-probes-audit.log`).
* **QF-2 — B9 stale line.** The committed `qaqc-probes/probe-commands-full.log` B9 was
  captured at an intermediate HEAD (`2 files changed, 141 insertions`). At the follow-up
  tip the same command is `22 files changed, 2014 insertions(+), 54 deletions(-)`
  (`b626c94..330fe70`). This is an informational line, not a probe result; the corrected
  reproducer writes the current value.
* **QF-3 — follow-up `env.txt` pre-amend SHAs.** `env.txt` names `bafcd9c` and `88cc19b`
  with no note. Both are pre-amend SHAs; `candidate-sha.txt` (`190c9e1`) is authoritative,
  the restricted code/ledger/CI delta is empty, and this follows the same
  `PROVENANCE-ERRATUM` convention used for 7A-6 (`f6924ff`↔`994d629`). `env.txt` was not
  edited because it is a captured log.

## C-7A6-4 — ID 3 literal

ID 3 ("GPU kernel/layer/E2E suites pass") is published **only** as a command
block in the README, so no prose phrase identifies it, and its literal
`PYTHONPATH=build` is a command token. The audit's complaint was that it was
labelled "claim-specific" when it is not a phrase.

The brief allows either replacing the literal or documenting the rule with a
removal test. The follow-up does the second, because the literal is in fact
exact for this claim:

* `PYTHONPATH=build` selects **README L85–L89** — the five GPU-suite
  invocations (`test_matmul.py`, `test_gguf_and_q4.py`, `test_layer.py`,
  `test_full_model.py`, `test_phase5_scale.py`) — and occurs **nowhere else**
  in either public document.
* Deleting those lines removes the literal, so the claim and its locator stand
  or fall together.

**What was changed in the ledger** (no status or flag changed):

* the Rules section now states the **VERIFIED-locator rule**: a VERIFIED row's
  *evidence path* is the proof; its literal is a *locator* that says where the
  claim is published, and it must stop resolving if the claim is removed
  (`unresolved-literal`). A claim published only as a command block has a
  command-shaped locator, acceptable only if it selects exactly that claim's
  lines and appears nowhere else;
* ID 3's row names the literal's role and the lines it selects;
* the 7A-6 verification section no longer calls ID 3's literal a
  claim-specific phrase.

**New canary `id3_claim_removed`.** It reads ID 3's literal from the ledger
(not a hard-coded line number), deletes every README line the literal selects,
and asserts the checker fails with `unresolved-literal`. The canary tracks the
ledger, so it stays meaningful if the literal changes.

**Why the literal was not changed.** A more specific literal would cover *less*
of the claim: `python3 tests/test_phase5_scale.py` selects one of the five
invocations, so deleting the other four would go undetected, whereas
`PYTHONPATH=build` selects all five. Changing it would have weakened the check
and would have contradicted the auditor's own example ("the specific GPU
test-suite command/file that would disappear if the claim were removed" — the
*set* of them, which is what `PYTHONPATH=build` selects).

## Also fixed: the ledger's stale line references

The auditor's prep commit `efe34fc` added one line to the README project tree
(`PHASE7_7A-6_FOLLOWUP_BRIEF.md`), shifting every README line from 27 onward
by +1. The 7A-6 ledger's scope annotations still named the old lines; the
checker reported **9 drift warnings** and the probes showed the effect (A2
reported two violations instead of one, because the drift re-anchored a site).

The nine stale README references (claims 8, 9, 10, 11, 12 and 21, both the
scope annotations and the prose) were refreshed to the current lines. The
checker's drift warnings are now zero apart from claim 21's wording note. This
is the checker's designed behaviour working: a document edit is a warning, and
the ledger is refreshed to match.

`IMPLEMENTATION_PLAN.md` was not touched by that commit, so its references were
already correct.

## Verification

| check | result |
|---|---|
| `check_claims.py` (default) | exit 0 — `PASS - 0 new violation(s), 17 baselined, 0 expired, 0 findings`, 1 warning (claim 21) |
| `check_claims.py --strict` (real tree) | exit 1 — `RESULT: FAIL - 17 unqualified occurrence(s)` |
| `check_claims.py --strict` (clean tree) | exit 0 — `RESULT: PASS - 0 unqualified occurrence(s)` |
| `check_claims.py --strict --json` (clean tree) | `ok: true` |
| `check_claims.py --json` (real tree) | `ok: true`, 30 claims, 17 violations (all baselined), 0 findings, 1 warning |
| `canary_claims.py` | **12/12** pass (10 existing + `strict_clean` + `id3_claim_removed`) |
| canary mutation | 9/12 fail when the exit code is forced to 0; `strict_clean` fails under the always-FAIL mutation; **12/12** fail when the checker is neutered to do nothing |
| `pytest -m "not gpu"` | 37 passed, 18 deselected |
| `pytest -m gpu` | 18 passed, 37 deselected |
| `test_cpu_only.py` / `-O` | 12/12 each |
| baseline | byte-identical (`git diff 994d629 -- audit/claims_baseline.txt` empty) |
| ledger statuses and flags | unchanged vs the 7A-6 candidate |
| QAQC probes | reproduced in full; agrees with the auditor's transcript on every probe |

**On the brief's "11/11".** The brief's acceptance list expects 11 canaries (the
10 existing plus `strict_clean`). C-7A6-4 asks for a removal test, and the
brief's allowed-files entry for `scripts/qa/canary_claims.py` names it
("new `strict_clean` canary; removal test if needed"), so the follow-up adds a
twelfth: `id3_claim_removed`. The "11/11 pass" criterion is met and exceeded —
**12/12** pass.

## Limitations and follow-ups

1. **The ledger's scope annotations are line-anchored.** A document edit above
   a scoped site produces a drift warning, not a failure; the ledger is
   refreshed to match. The auditor's prep commit is the first time this fired
   in anger, and it is the reason the follow-up refreshed nine references.
2. **`--strict` still fails on the real tree** — 17 baselined sites remain by
   design. It becomes the G6 release gate once the baseline is empty. It is
   advisory in CI until then.
3. **ID 21** is flagged `partial` with no unqualified site: the README mention
   is qualified in place, but the caveat is incomplete. The checker reports it
   as a wording task, not a ratchet item. 7D-1 owns the fix.
4. **Not implemented here:** the handoff's "fail if the ledger has not changed
   in a PR that changes a claim line" rule. That is a *release* check (7F-5
   diffs ledger + README + PLAN), not a CI-time check, and 7F-5 owns it.
5. **The GPU lane reused the G0 build artifact.** The follow-up changes no
   `src/` file, so a rebuild would not exercise anything new. The artifact is
   the repository's own `build/matmul_module.so`, byte-identical (sha256
   `c8f6b19b…`) to the `/tmp/opencode/g0-build` copy the 7A-6 bundle recorded;
   the `/tmp` copy was ephemeral and has since been cleaned, so the follow-up's
   `gpu-suite.log` uses `PYTHONPATH=build:src`, which a re-verifier can
   reproduce from the repository's build directory (a fresh clone must build
   it — 7A-8 owns the build entry point).

## Rollback

Revert the follow-up commit. The changes are confined to
`scripts/qa/check_claims.py`, `scripts/qa/canary_claims.py`,
`audit/CLAIMS_LEDGER.md`, the `audit/evidence/G1/7A-6/` bundle and the new
`audit/evidence/G1/7A-6-followup/` bundle. The product code, the CPU/GPU
suites and `audit/claims_baseline.txt` are unchanged. Reverting the ledger
restores the previous line references (which the prep commit had invalidated
anyway).

## Claims changed

None. No public claim was added, removed or re-qualified. The ledger's
*annotation* changed — ID 3's literal is now documented as a locator rather
than a claim-specific phrase, and nine stale line references were refreshed —
but every claim's status, wording and evidence pointer is unchanged.
