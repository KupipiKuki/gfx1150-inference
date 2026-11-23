# Architect approval — HO-STRATA-013

| Field | Value |
|---|---|
| **Handoff** | HO-STRATA-013 (`check_bundle.py`: evidence-packaging invariants) |
| **Architect** | `opencode-go/deepseek-v4-pro#max` |
| **Date (UTC)** | 2026-11-23 |
| **Decision** | **SIGNED** |
| **Merge commit** | pending — PR from `wp/strata-013-check-bundle` (branch-protected `main`, DEC-040) |
| **Evidence** | `workflow/evidence/HO-STRATA-013/` (21 hashed files, 21/21 OK) |

## 1. Criteria trace

| # | Criterion | Evidence | QAQC | Audit | Architect |
|---|---|---|---|---|---|
| AC-1 | Runs on a real signed bundle | `artifacts/check-ho012.txt`, exit 0 | PASS | PASS | PASS |
| AC-2 | Aggregate run over every bundle | `artifacts/check-all.txt`, exit 1, 2 FAILs both HO-011 | PASS | PASS | PASS |
| AC-3 | Negative controls | 16/16 fixtures, each constructing its defect | PASS | PASS | PASS |
| AC-4 | Stdlib only, `-I` | `artifacts/stdlib-isolated.txt`, `stdlib-imports.txt` | PASS | PASS | PASS |
| AC-5 | Read-only | status before/after identical | PASS | PASS | PASS |
| AC-6 | Fresh clone | `artifacts/fresh-clone.txt`; C17 re-probed in a clone | PASS | PASS | PASS |
| AC-7 | Documented | `workflow/README.md` section | PASS | PASS | PASS |
| AC-8 | Deterministic | `artifacts/deterministic.txt` | PASS | PASS | PASS |
| RW-1 F1–F5 | Legacy path classification | ordered B2 resolution; 12 fixtures | PASS | PASS | PASS |
| RW-2 A1 | B3 exempts only the bundle's own `hashes.txt` | unlisted `notes-hashes.txt` FAILs; four name variants | PASS | PASS | PASS |
| RW-2 A2 | B6 verifies every pin row | reworded command, wrong digest and `deadbeef` FAIL | PASS | PASS | PASS |
| RW-3 R2-1 | Logged capture commands run | C17 verbatim in a clone replaces the artifact | PASS | PASS | PASS |
| RW-3 R2-2 | `test-output.txt` matches final artifacts | 14/14 sections byte-identical | PASS | PASS | PASS |
| RW-3 R2-3 | Manifest claims only what the artifacts show | §1 generated from `commands.log` | PASS | PASS (minor) | PASS, carried |
| RW-3 R2-4 | File column authoritative in B6 | divergent cells WARN and verify `File` | PASS | PASS | PASS |

## 2. Gate evidence

- [x] QAQC report: `workflow/reports/qaqc/HO-STRATA-013-qaqc.md` — **PASS** (3 rounds; round 1 missed A1/A2, recorded in the report)
- [x] Audit report: `workflow/reports/audit/HO-STRATA-013-audit.md` — **PASS** (3 rounds; rounds 1 and 2 returned REWORK)
- [x] Evidence manifest complete, hashes verify (21/21), pins resolve with digests
- [x] Scope matches the handoff: 30 files since `91eac12`, all in `workflow/tools`, `workflow/README.md`, `workflow/evidence/HO-STRATA-013`, the HO-013/RW handoffs, the QAQC and audit reports
- [x] Guard rails respected: no other bundle touched, no `DECISIONS.md`/`STATUS.md` edit from the coder, no `.opencode`/`.github` change, no dependency, no network, Strata clean at `bac859ef9`, `build-hip/strata` still `d58ee239…`
- [x] No secrets; no unsupported claims
- [x] Seat: QAQC on `opencode-go/gemini-4-argon` (DEC-039); auditor on `opencode-go/deepseek-v4.1-flash` under **WAIVER-001** — a documented exception, not a model-separation PASS

## 3. Conditions / follow-ups (carried, not waived)

| ID | Finding | Disposition |
|---|---|---|
| R3-1 | manifest §1 has 24 of 25 rows (C24 missing) while claiming it "cannot drift" | Carried: C23 ≡ C24 byte-identical, and C23 reproduces the final `hashes.txt`; reproduction is unaffected. Fix at the next bundle touch |
| R3-2 | manifest §3/§5 mis-cite "C19"/"C14/C15" for the final rehash and fixed point | Carried: cosmetic, the artifacts are authoritative; fix with R3-1 |
| R3-3 | C17/C18 record the tool's rc 1 while the line exit is 0 | Carried: the entry states both; recorded as an erratum next touch |
| R3-4 | A pin row with an empty `File` cell is warned twice but not verified | Carried: latent, no signed bundle has such a row; the R2-4 rule covers the real case |
| R3-5 | `scripts/bypass_probe.py` embeds a throwaway commit id | Carried: it is a fixture id, regenerated per run |
| R3-6 | The architect materialised the QAQC report into git (QAQC cannot push) | Recorded in DEC-041; content verified by the auditor |
| R3-7 | Header/STATUS provenance of the round-3 state | Recorded in DEC-041 |
| R3-8 | `--all` is red because `HO-STRATA-011` has two unlisted artifacts | **Correct behaviour, do not tune.** Tracked with DEC-030's carried B-class; fix when that bundle is next touched |
| R3-9 | Round-1 audit assertion A3 (retried checks) | Superseded by round 3 |

None of these blocks the claim this handoff makes: *the checker detects packaging
defects, and cannot be satisfied without doing the work.* Every blocking finding
from two audit rounds and three QAQC rounds is closed and reproduced by the
reviewer who raised it.

## 4. Decision

**SIGNED.** State `DONE`. Merge authorized through a PR with a merge commit
(DEC-040), so the work-package SHAs stay reachable.

Adopted as the project's evidence gate: run `check_bundle.py <bundle>` before
`CODER_DONE`, and by QAQC before review (DEC-041). S4's bundle is the first to
use it.

| Role | Signature | Date |
|---|---|---|
| Architect | `opencode-go/deepseek-v4-pro#max` | 2026-11-23 |
