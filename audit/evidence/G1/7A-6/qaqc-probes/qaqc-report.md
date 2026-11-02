# QAQC Report — Work package 7A-6 (Claims checker) + review of the Gemini preliminary QAQC

**Role:** QAQC (independent session, per handoff §1 and the coder brief §3)
**Date:** 2026-11-02
**Tree tested:** candidate `994d62922af7ed9f5b9546d787d8c05606cdb8f1` on `wp/7A-6-claims-checker`
(tip `f0a73a1` = the candidate-SHA follow-up; parent `4bcffeb`). Live runs on the branch;
adversarial probes on throwaway tree copies via the checker's own `--root` isolation.
**Probes:** `probe-commands.log` (this directory) — the summary — and
`probe-commands-full.log` (this directory) — the full transcript.
**Preliminary report reviewed:** `gemini-qaqc-report.md` (same directory) — see §5.

---

## Verdict

**PASS.** The implementation meets every task and acceptance criterion in the brief, every
coder-report claim reproduces exactly, and all eleven of my adversarial probes behave
correctly — including the two that substantiate the package's core design claim (a **new**
unqualified occurrence cannot hide behind the path-level ratchet baseline) and the canary
mutation-test the coder reported. No stop condition triggered. Three evidence-hygiene
findings (§4) are non-blocking and none requires re-running the package.

## 1. Acceptance criteria — all reproduced

| Criterion (brief §3) | Claimed | QAQC result |
|---|---|---|
| Default mode green on the seeded baseline | PASS, 0 new / 17 baselined / 0 expired | ✅ exact — `RESULT: PASS - 0 new violation(s), 17 baselined, 0 expired baseline entry(ies), 0 finding(s)`, exit 0 (+1 warning on claim 21) |
| `--strict` fails on every violation | exit 1, 17 occurrences | ✅ exact — exit 1, "17 unqualified occurrence(s)" |
| `--json` | valid JSON | ✅ `ok=true`, 30 claims, 17 violations (all baselined), 0 unaccounted, 0 findings |
| 15 baseline entries exact, resolve, no wildcards | yes | ✅ 15 `(claim-id, path, literal)` triples over 12 claims (6, 10, 13, 14, 18–20, 26–30; 14/18/19 double-entered); **byte-identical to the parent** (`git diff` empty) |
| ID 6 and 10 `no`/`partial`, consistent with the ratchet | both `no` | ✅ both `no`; ledger ratchet section agrees |
| Claim-specific literals; no generic literal can return | 4 replaced | ✅ IDs 1–4: `pip install`→`sdist`, `test_cpu_only.py`→`Self-contained CPU-only test suite`, `GPU`→`PYTHONPATH=build`, `llama-family`→`Q4_0`/`Q4_K`/`Q8_0`; `generic-literal` finding fires (my probe A6-class canary + the committed canary) |
| Reports the unqualified rows, not "none" | 12 rows, 17 sites | ✅ verified in human and JSON output |
| Canaries (10) | 10/10 | ✅ all 10 pass, exit 0 |
| CI wiring | default+canaries blocking, strict advisory | ✅ 3 steps in `cpu-smoke`, `continue-on-error: true` on strict, valid YAML; jobs-only change |
| No `src/`, tests, packaging, README/PLAN change | empty | ✅ 17 files, all in the allowed set; ledger **statuses and flags unchanged** vs parent (only literals + scope annotations added) |

Suites unchanged: `pytest -m "not gpu"` 37 passed / 18 deselected; `-m gpu` 18 passed /
37 deselected; full `pytest -q` 55 passed; `test_cpu_only.py` 12/12 normal and `-O`.

## 2. Adversarial probes (mine)

| # | Probe | Result |
|---|---|---|
| A1 | **Handoff §7 mandated canary**: unqualified `NOT YET` claim injected into the *live* README → default fails (1 NEW VIOLATION); restored → green; README byte-identical after restore | ✅ exit 1 → exit 0 |
| A2 | **Line-precision attack**: a *second* unqualified `qwen2` appended to README despite the path-level baseline entry `10 README.md qwen2` | ✅ **fails** as `NEW VIOLATION (not inventoried in the ledger)` at README:114 — the path-level baseline cannot hide a new occurrence; the core design claim holds |
| A3 | **Baseline is load-bearing**: delete entry `10 README.md qwen2` | ✅ L109 becomes a NEW violation → exit 1 (16 baselined) |
| A4 | Wildcard baseline entry (`q*en2`) | ✅ exit 2, "wildcard entries are not allowed" |
| A5 | Malformed baseline entry | ✅ exit 2 |
| A6 | Invalid status (`SOMETIMES`) in a ledger row | ✅ `invalid-status` finding → default fails |
| A7 | Duplicate claim ID | ✅ exit 2 |
| A8 | Escaped-pipe (`\|`) literal cell | ✅ parses to 7 columns; the split honours the escape |
| A9 | Drift: line inserted at README top | ✅ exactly **13** drifted-site warnings, exit 0 (matches the coder's claim) |
| A10 | Qualifier-bullet deletion in a copy | ✅ **5 stale-scope findings** (claims 8–12), exit 1 — a removed qualifier is caught |
| A11 | `claims-check.log` vs live output | ✅ identical after its 5-line header |
| C | **Canary mutation-test** (coder's claim I verified): neuter the checker (force exit 0) | ✅ exactly **8 of 10** canaries fail; the 2 that survive (`baseline_is_exact`, `expired_baseline_entry`) read JSON, as designed; restored → 10/10 |

## 3. The design decision — assessed

The seeded baseline is path-level (`<claim-id> <path> <literal>`); line precision comes from
the ledger's new scope annotations (`unqualified:`/`qualified:`/`context:` inventories that
must be exhaustive). Probes A2/A3/A9/A10 confirm the geometry: a new occurrence fails
(unaccounted), a deleted qualifier fails (stale-scope), pure line shifts only warn, and the
baseline entries are load-bearing. **Model boundary, disclosed in notes §limitations 1 and
restated for the auditor:** an in-place *rewording* at a qualified site (same line, same
count) is invisible to the checker by design — the checker enforces geometry, not wording;
wording changes are governed by the same-PR ledger rule and 7F-5's ledger-vs-docs diff.
This is acceptable, but G6 sign-off should cite 7F-5 as the wording backstop.

## 4. Findings (non-blocking)

1. **Evidence provenance names an unreachable commit.** Every log header and `env.txt` say
   `candidate: f6924ff…`, but `candidate-sha.txt` says `994d629…`. Per the reflog,
   `f6924ff` is a **pre-amend commit** (message identical, parent `4bcffeb`), amended to
   `994d629` with only evidence-file edits (+11/−10, all in `audit/evidence/G1/7A-6/`);
   the **code/ledger/CI delta between the two is zero** (verified). So the evidence is
   valid for the candidate — but `f6924ff` is unreachable from any branch and will
   eventually be garbage-collected, and the bundle never explains the relationship.
   **Action:** document the `f6924ff`↔`994d629` equivalence in `notes.md` (or a follow-up
   commit); quote the verified zero substantive delta.
2. **`diffstat.txt` numbers predate the final commit**: it records 2661 insertions/23
   deletions; the true `4bcffeb..994d629` figure is 2691/24 (the file list itself is
   correct and scope-compliant). Same root cause as finding 1; fold the correction into
   the same note.
3. **`env.txt` formatting glitch:** the `candidate:` line appears three times with
   different spacing. Cosmetic; fix alongside finding 1.

## 5. Comparison with the Gemini preliminary QAQC (`gemini-qaqc-report.md`)

**Where we agree (and I verified):** the recommendation (approve), scope/file isolation
(no `src/`/tests/packaging changes), baseline preservation (0 diffs), the 12-claims /
17-sites / 15-entries structure, default/strict/JSON/canary/pytest results, the three CI
steps with `--strict` advisory, and the generic-literal rejection. Gemini's overall
judgment is sound.

**Gemini's factual errors — none changes the verdict, but the report must not be relied
on as-is:**

| # | Gemini says | Actual (verified) |
|---|---|---|
| 1 | "17 files changed, **2520 insertions(+), 18 deletions(-)**" | **2691 insertions(+), 24 deletions(-)** (`git diff --shortstat 4bcffeb..994d629`) |
| 2 | Status enum "{VERIFIED, NOT_YET, UNVERIFIED, **CONTEXT**}" | `{VERIFIED, PARTIAL, NOT YET, UNVERIFIED, REMOVED}`. "context" is a **scope label**, not a status; PARTIAL and REMOVED are missing from Gemini's list |
| 3 | "Column 7 (**Public?**) enforces {yes, no}" | No such column. The 7th column is "Scope / limit" (free text); the flag column (5th) validates `yes/no/partial/n-a` |
| 4 | Baseline entries are "(claim_id, path, **line_no**) triples" | `(claim-id, path, **literal**)` — line numbers live in the ledger scope annotations, not the baseline |
| 5 | Literal replacements on claims **10, 18, 19, 27** | Claims **1, 2, 3, 4** (per the ledger itself and the notes) |
| 6 | Bundle contains `pytest-cpu.log`, `pytest-gpu.log`, `git-diff.patch`, `git-status.txt` | None of those exist; the actual files are `cpu-suite.log`, `gpu-suite.log`, `diffstat.txt` (and no patch/status artifacts) |
| 7 | The 1 warning is on claim 21 "(**ci-cpu.yml missing link to workflow run**)" | The actual warning: "claim 21: flag is 'partial' with no unqualified site; the caveat wording is incomplete (a wording task, not a ratchet item)" |
| 8 | Canary 9 = "Claim in an **unauthorized file** fails"; Canary 10 = "**Unterminated/malformed table parsing** fails" | Canary 9 (`wrong_lane`): an unqualified claim appended to `IMPLEMENTATION_PLAN.md` must be detected (both public docs are scanned). Canary 10 (`nested_bullet`): an unqualified assertion nested under a qualified parent bullet must be detected |
| 9 | env.txt mismatch is "captured during staging prior to commit finalization… no functional impact" | Understated: the mismatch is a **dangling pre-amend commit** (`f6924ff`) referenced as "candidate" in every log, unreachable from the branch and gc-able — findings 1–3 above. I verified the substantive tree is byte-identical, so the *evidence* is valid; the *provenance record* needs the documenting note |
| 10 | "10/10 canaries passed in 0.28s" | 10/10 confirmed; 0.71s on this run (immaterial) |
| 11 | Parser "terminates… (e.g. `### Summary of Non-Verified Claims`)" | The stop-at-first-non-table-line behavior is real, but no section of that name exists — the first non-table line is `**Last updated:**` |

**What Gemini's review did not do (covered here):** verify the canary mutation-test
(8/10 fail under a neutered checker — the coder's claim holds exactly); probe the
line-precision design (A2) and the load-bearing baseline (A3); confirm ledger
statuses/flags are unchanged vs the parent (only literals + annotations changed); confirm
`claims-check.log` matches the live run byte-for-byte; and resolve the `f6924ff`
provenance rather than note it as cosmetic.

## 6. Disposition

**7A-6 passes QAQC** and is recommended to the auditor for acceptance, with findings 1–3
(document the `f6924ff` capture-provenance; fix the `diffstat.txt`/`env.txt` records) as a
small documentation follow-up inside the 7A-6 evidence set. The Gemini preliminary report
is **directionally correct (approve) but factually unreliable in detail** — §5 above is
the corrected record; the auditor should treat my §5 table as the reconciliation. G1
remains unsigned pending 7A-2..7A-5 (and 7A-7/7A-8 per the brief).

**QAQC sign-off:** 2026-11-02. Probes: `probe-commands.log` (summary) and
`probe-commands-full.log` (full transcript), both in this directory.

> **Follow-up correction (7A-6 follow-up, condition C-7A6-2).** The original sign-off named a
> `final-probe-commands.log`, which did not exist; the directory holds `probe-commands.log`,
> a summary rather than a transcript, whose `--strict` exit code and A10 removal count were
> wrong. The summary has been corrected (B2 exit 1; A10: 1 line removed, 5 stale-scope +
> 1 unresolved-literal = 6 findings) and is now explicitly labelled a summary; the full
> transcript is `probe-commands-full.log`, reproduced at the follow-up commit because
> QAQC's scratch tree was ephemeral. The corrections were applied by the follow-up coder,
> not by QAQC, and are itemised at the end of `probe-commands.log`. No probe *result*
> changed: every corrected number is the one the auditor already confirmed.
Scratch retained at `/tmp/opencode/qaqc-76/`.
