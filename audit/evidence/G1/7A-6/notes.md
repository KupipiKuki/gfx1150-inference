# G1 / 7A-6 — claims checker

**Package:** 7A-6 — Claims checker
**Branch:** `wp/7A-6-claims-checker`
**Parent:** `4bcffeb35862c3d0b12fa54aac2f2d27bdc9ec60`
**Audit trace:** AUD-3 (G0 audit), T-7 (claims ledger had no enforcement), brief §3 items 1–6
**red/green:** **N/A** — this package adds tooling only. No `src/` change, no runtime
behaviour change, no product claim added or removed. The CPU and GPU suites are
unchanged from the 7A-1-followup baseline (37 passed / 18 deselected, 18 passed /
37 deselected).

## What was done

1. **`scripts/qa/check_claims.py`** (new, standard library only). Parses the **main**
   ledger table only (it stops at the first non-table line, so the ratchet
   sub-tables are prose, not claims), validates every row's status / public match /
   `Qualified in place?` flag, requires a `VERIFIED` row's evidence paths to exist,
   and enforces the qualification rule rather than mere literal presence.
2. **`scripts/qa/canary_claims.py`** (new). Ten canaries, each mutating a
   throw-away copy of the tree and asserting the checker notices.
3. **`audit/CLAIMS_LEDGER.md`** — the four generic literals replaced, and the
   "Qualified in place?" column now carries a machine-readable scope annotation.
4. **`audit/claims_baseline.txt`** — reviewed, **not modified**. The 15 seeded
   entries are exact, resolve, and are consistent with the ratchet section.
5. **`.github/workflows/ci-cpu.yml`** — default mode wired in as a blocking step,
   `--strict` wired in as advisory (`continue-on-error`) until G6.

## The enforcement model

The ledger row is the source of truth. A row's scope annotation inventories
**every** place the claim's literal occurs in `README.md` / `IMPLEMENTATION_PLAN.md`
and classifies each site:

| label | meaning | ratchet item? |
|---|---|---|
| `unqualified:` | asserted without a caveat | yes — needs a baseline entry |
| `qualified:` | asserted, and qualified in place | no |
| `context:` | planning/status prose that does not assert the claim | no |

The inventory must be **exhaustive**: an occurrence the ledger does not list is a
new, unreviewed assertion of the claim and fails the build. This is the part that
makes the ratchet *tighten* rather than merely record, and it is what lets the
canaries detect an injected claim.

- **Default mode** (CI): tolerates the exact baselined sites, fails on any new
  violation or finding, warns on expired baseline entries and on drifted line
  references.
- **`--strict`** (G6 release gate): ignores the baseline entirely and fails on
  every unqualified site. It is advisory in CI until G6, because the baseline is
  still populated.

### Why the scope annotation was needed

The seeded baseline is `(claim-id, path, literal)` — **path-level**, not
line-level. Without a line-level ledger annotation, a claim's literal appearing
*anywhere* in a baselined path is tolerated, so an injected claim cannot be
distinguished from the reviewed one. The G0 audit found exactly this: the manual
`claims-check.log` "only checks literal presence and evidence paths; it does not
apply the qualification rule", and reported "FINDINGS none" while nine unqualified
rows were live. The scope annotation restores the missing precision, and the
checker now reports all **12** unqualified rows (the 11 `no`-flag rows plus ID 13's
unqualified `IMPLEMENTATION_PLAN.md` L209 instance) instead of "none".

## Claim-specific literals (brief §3 item 3)

The four generic literals flagged by AUD-3 were replaced with phrases the claim
actually depends on:

| ID | was | now |
|---|---|---|
| 1 | `pip install` | `sdist` |
| 2 | `test_cpu_only.py` | `Self-contained CPU-only test suite` |
| 3 | `GPU` | `PYTHONPATH=build` |
| 4 | `llama-family` | `Q4_0`, `Q4_K`, `Q8_0` |

`check_claims.py` rejects a known-generic literal outright (`generic-literal`
finding), so these cannot silently come back. The `generic_literal` canary proves
the negative test AUD-3 asks for: a literal that does not match the claim cannot
enforce it, so the checker refuses it.

Note: `12 tests` (suggested in the brief as the CPU-suite literal) appears in the
audit documents but in **neither** public document, so it cannot be resolved and
would make the row permanently stale. `Self-contained CPU-only test suite` is the
phrase the CPU-suite claim actually depends on, and it resolves at
`IMPLEMENTATION_PLAN.md` L210.

## Baseline review (brief §3 item 2)

The seeded baseline was reviewed entry by entry and **left unchanged**. All 15
entries are exact `<claim-id> <path> <literal>` triples, each resolving to a live
unqualified site, with no wildcards and no allow-all. They cover exactly IDs 6,
10, 13, 14, 18, 19, 20, 26, 27, 28, 29, 30 — the 11 `no`-flag rows plus ID 13's
L209 instance. IDs 14, 18 and 19 have two entries each (one per file), which is
where 15 comes from.

No entry hides a cheaply-fixable claim: IDs 6 and 10 need README wording changes
(7B/7C, 7C-4), and IDs 13, 14, 18–20, 26–30 need 7D/7F to re-measure or remove
the figures. The `phi3`/`gemma` bullet needs **no** entry — the README qualifies
it inline at L109/L110. Every entry targets `G6`, where the file must be empty.

## Canaries (brief §3 item 6)

`python3 scripts/qa/canary_claims.py` — all ten pass; the working tree is never
modified (each canary copies the tree first).

| canary | mutation | expected |
|---|---|---|
| `not_yet_claim` | unqualified `chat special-token encoding` appended to README | fail |
| `unqualified_q4_k_m` | unqualified `Q4_K_M` appended to README | fail |
| `unqualified_qwen2` | unqualified `qwen2` appended to README | fail |
| `missing_evidence` | VERIFIED claim 1's `sdist-install.log` deleted | fail |
| `generic_literal` | claim 1's literal replaced by `GPU` | fail (generic-literal) |
| `strict_detects_baseline` | — | `--strict` fails on the seeded baseline |
| `baseline_is_exact` | — | 15 exact entries, all resolving |
| `expired_baseline_entry` | a stale entry appended | warn, exit 0 |
| `wrong_lane` | unqualified `qwen2` appended to `IMPLEMENTATION_PLAN.md` | fail |
| `nested_bullet` | unqualified `qwen2` nested under another bullet | fail |

The canaries were **mutation-tested**: neutering the checker (forcing exit 0)
makes eight of them fail, which proves they test the checker and not the harness.
`baseline_is_exact` and `expired_baseline_entry` read the JSON output rather than
the exit code, so they stay meaningful under that mutation.

## CI wiring

`.github/workflows/ci-cpu.yml` (`cpu-smoke` job) gains three steps:

1. `python3 scripts/qa/check_claims.py` — **blocking**. Default mode.
2. `python3 scripts/qa/canary_claims.py` — **blocking**.
3. `python3 scripts/qa/check_claims.py --strict` — **advisory**
   (`continue-on-error: true`) until G6, when the baseline must be empty.

The checker is standard-library only, so it runs in the CPU job, which installs
no pytest.

## Limitations and follow-ups

1. **The scope annotation is line-anchored.** If a public document is edited
   above a scoped site, the checker reports a drift warning and asks for the
   line reference to be refreshed; it does not fail, because a document edit is
   not a claim change. If a *new* occurrence appears, the count changes and the
   checker fails. This was verified explicitly: inserting a line at the top of
   README warns for 13 sites and still passes; inserting a new unqualified `qwen2`
   claim fails.
2. **The baseline remains path-level**, as the handoff specifies. Line-level
   precision lives in the ledger, not in `claims_baseline.txt`, so the file stays
   byte-identical to the auditor's seed.
3. **`--strict` cannot pass today** — it fails on the 17 baselined sites by
   design. It becomes the G6 release gate once the baseline is empty. It is
   advisory in CI until then.
4. **ID 21** (`MADV_DONTNEED` reclaims page-cache) is flagged `partial` with no
   unqualified site: the README mention *is* qualified in place, but the caveat is
   incomplete ("does not state that it does not bound RSS"). The checker reports
   it as a wording task, not a ratchet item. 7D-1 owns the fix.
5. **ID 13 and ID 27 share the `983` prefix.** ID 13's literal `983` also matches
   `983.4 tok/s` on the same line, so both rows see `IMPLEMENTATION_PLAN.md` L209.
   That is intended and matches the seeded baseline; the ledger records both
   sites per row.
6. **Not implemented here:** the handoff's "fail if the ledger has not changed in
   a PR that changes a claim line" rule. That is a *release* check (G6/7F-5
   compares `git diff` over ledger + README + PLAN), not a CI-time check, and
   7F-5 owns it.
7. **The GPU lane was not run against a fresh build.** The G0 baseline artifact
   was reused, exactly as in the 7A-1-followup package. This package changes no
   `src/` file, so a rebuild would not exercise anything new.

## Rollback

Revert the commit. Nothing outside `scripts/qa/`, `audit/CLAIMS_LEDGER.md`,
`.github/workflows/ci-cpu.yml` and this evidence directory is touched; the
product code, the CPU/GPU suites and `audit/claims_baseline.txt` are unchanged.
Reverting the ledger restores the previous prose (the scope annotations are
additive); reverting the workflow removes the three CI steps.

## Claims changed

None. No public claim was added, removed or re-qualified. The ledger's
*annotation* changed (scope annotations, and the four literals became
claim-specific), but every claim's status, wording and evidence pointer is
unchanged.
