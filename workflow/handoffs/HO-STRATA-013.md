# HO-STRATA-013 — `check_bundle.py`: automate the evidence-packaging invariants

| Field | Value |
|---|---|
| **ID** | HO-STRATA-013 |
| **Type** | ARCHITECT_TO_CODER |
| **State** | CODER_DONE (RW-HO-STRATA-013-2 completed) |
| **Created / updated (UTC)** | 2026-11-22 / 2026-11-22 |
| **From → To** | Architect → Primary Coder (`coder-primary`) |
| **Work package** | `check-bundle` |
| **Branch / base commit** | `wp/strata-013-check-bundle` / `91eac12` (`workflow/resume-2026-11-22`; remote `workflow/resume-2026-11-22`) |
| **Priority / timebox** | P1 · 1 working day |

## 0. Why this exists

Every rework in this project so far has been **packaging, not engineering**:
HO-008 (`--n` vs `--native` flag), HO-010 (curated transcript labelled raw,
build-scoped lib digests, pins without digests), HO-011 (bundle completeness).
Each was found by a human running the same handful of checks by hand at the
gate. S4 is the largest bundle yet; the class must be removed before it.

This handoff builds the checker. It changes **no engine code, no evidence
bundle, and no existing evidence**.

## 1. Scope (in)

Add one stdlib-only Python tool, its negative-control self-test, and a short
README section.

### 1.1 `workflow/tools/check_bundle.py`

CLI:

```text
python3 workflow/tools/check_bundle.py <bundle-dir> [--json]
python3 workflow/tools/check_bundle.py --all [--json]
python3 workflow/tools/check_bundle.py --self-test
```

Exit codes: `0` no FAIL, `1` at least one FAIL, `2` usage error. Output: one
`PASS|WARN|FAIL <code> <message>` line per finding, then a summary
`RESULT: PASS|FAIL (n checks, m warnings)`. `--json` emits a stable object
(`{"bundle": ..., "checks": [{"code","status","message","path"}], "result": ...}`)
with **no timestamps, durations, or absolute paths** so two runs are
byte-identical.

Checks (codes are part of the contract; keep these names):

| Code | Check |
|---|---|
| `B1-structure` | `manifest.md` and `hashes.txt` exist. When the manifest declares commands, `commands.log` exists. A directory without `manifest.md` is `WARN skipped`, not FAIL (it may be a decision artifact such as `workflow/evidence/DEC-039/`). |
| `B2-hash-verify` | Every `<sha256>  <path>` line in `hashes.txt` verifies against the working tree, paths resolved from the **repo root**, not the bundle dir. |
| `B3-hash-coverage` | Every file under the bundle dir is listed in `hashes.txt`, except `hashes.txt` itself. Extra listed paths that do not exist are already `B2` failures. |
| `B4-tracked` | Every file in the bundle is known to git (`git ls-files`), and `git status --porcelain <bundle>` is empty. |
| `B5-not-ignored` | No bundle file matches `git check-ignore` — proves the DEC-008 negations (`!workflow/evidence/**/*.log`, `*.bin`) still work. |
| `B6-pins` | Rows in `hashes-notes.txt` that record a commit pin are verified: the commit and `commit:path` must resolve, and when a full 64-hex digest is recorded it must match `git show <commit>:<path> \| sha256sum`. Abbreviated digests (`abc123…def`) are `WARN`, unresolvable pins are `FAIL`. |
| `B7-secrets` | No credential-shaped strings in any bundle file: `ghp_`, `github_pat_`, `sk-`, `AKIA`, `xox[baprs]-`, `-----BEGIN … PRIVATE KEY-----`, or `(?i)(api[_-]?key\|token\|secret)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{20,}`. A line carrying an explicit `check_bundle: allow-secret <reason>` marker is downgraded to `WARN`. |
| `B8-read-only` | `git status --porcelain` is identical before and after the run. The tool writes nothing inside the repo. |

`--all` iterates `workflow/evidence/HO-*` directories in sorted order and
aggregates; exit `1` if any bundle FAILs. Repo root is discovered with
`git rev-parse --show-toplevel`.

### 1.2 `--self-test` — negative controls

The positive case alone proves nothing: a checker that never fails is worse
than none. `--self-test` creates throwaway git repos under a temp directory and
asserts each code **fires** on a purpose-built defect:

| Fixture | Must report |
|---|---|
| hash edited after `hashes.txt` was written | `B2-hash-verify` FAIL |
| extra artifact not listed in `hashes.txt` | `B3-hash-coverage` FAIL |
| file written but never added | `B4-tracked` FAIL |
| artifact matched by `.gitignore` | `B5-not-ignored` FAIL |
| pin to a commit that does not contain the path | `B6-pins` FAIL |
| `ghp_`-shaped string in a log | `B7-secrets` FAIL |
| clean bundle | `RESULT: PASS` |

It must also assert the **positive** case: a clean fixture passes. Self-test
exits `0` only when every expectation holds, and prints one line per fixture.

### 1.3 `workflow/README.md`

Add a short section under the loop: what the tool checks, the two commands
(`<bundle>`, `--all`), and when to run it (**before `CODER_DONE`**, and by QAQC
before its review). No other README edits.

## 2. Out of scope

- No edits to any existing bundle under `workflow/evidence/` — signed evidence is immutable.
- No edits to `workflow/handoffs/` other than `HO-STRATA-013.md`; QAQC and audit reports belong to other roles.
- No edits to `workflow/DECISIONS.md`, `workflow/STATUS.md`, `.opencode/**`, `.github/**`.
- No CI wiring (a follow-up handoff decides whether `--all` becomes a required check).
- No engine, Strata-checkout, tokenizer, kernel or model work. **Nothing in this handoff may make DeepSeek run.**
- No fixing of defects the tool finds in HO-001/005/007/008/010/011/012 — report only.

## 3. Inputs

| Input | Path / hash | Status |
|---|---|---|
| Contract | `workflow/HANDOFF_CONTRACT.md` §7 (evidence contract) | available |
| Hash rule | `workflow/DECISIONS.md` DEC-024 (immutable hashed, mutable pinned by commit) | available |
| Packaging rule | DEC-008 (evidence in this repo; `.gitignore` negations) | available |
| Known defects to reproduce | DEC-030 B-1/B-2/B-4 (HO-010), DEC-037 F1 (HO-012) | available |
| Reference bundle | `workflow/evidence/HO-STRATA-012/` (10 files, 10 hashes) | available |
| Target path | `workflow/tools/check_bundle.py` (new directory) | to create |
| Base commit | `91eac12` | available |

## 4. Acceptance criteria

| # | Criterion | Command / check | Expected |
|---|---|---|---|
| AC-1 | Runs on a real, signed bundle | `python3 workflow/tools/check_bundle.py workflow/evidence/HO-STRATA-012` | exit `0`, `RESULT: PASS`, every code `PASS`. If a check legitimately FAILs on this bundle, **do not edit the bundle**: record the finding and raise it to the architect (`NEEDS_INFO`) — the signed bundle is evidence, the tool is new |
| AC-2 | Aggregate run over every bundle | `python3 workflow/tools/check_bundle.py --all` | Processes every `workflow/evidence/HO-*` dir; exit code equals `0` iff zero FAIL lines; `workflow/evidence/DEC-039/` is `WARN skipped`. Raw output committed. Pre-existing defects are reported, not fixed |
| AC-3 | Negative controls | `python3 workflow/tools/check_bundle.py --self-test` | exit `0`; one line per fixture; all seven fixtures above demonstrated, including the clean PASS |
| AC-4 | Stdlib only, isolated interpreter | `python3 -I workflow/tools/check_bundle.py --self-test` and `grep -nE '^(import\|from) ' workflow/tools/check_bundle.py` | exit `0` under `-I`; imports are stdlib only (no pip installs, no network) |
| AC-5 | Read-only | `git status --porcelain > /tmp/before.txt`; run AC-1 and AC-2; `git status --porcelain > /tmp/after.txt`; `diff /tmp/before.txt /tmp/after.txt` | no diff |
| AC-6 | Works from a fresh clone | `git clone --branch wp/strata-013-check-bundle . /tmp/cb-fresh`; run AC-1 there | same exit code and same verdict as AC-1 (proves no dependence on untracked working-tree state) |
| AC-7 | Documented | `grep -n "check_bundle" workflow/README.md` | section present with both commands and the "run before CODER_DONE" rule |
| AC-8 | Deterministic output | run AC-1 twice, `diff` the two outputs | identical (no timestamps, absolute paths, or ordering drift) |

## 5. Evidence required

- `workflow/evidence/HO-STRATA-013/manifest.md` (filled `templates/EVIDENCE_MANIFEST.md`; §4 environment: OS, kernel, `python3 --version`, `git --version`).
- `commands.log` — every command with cwd, exit code, verbatim.
- `test-output.txt` — raw output of AC-1, AC-2, AC-3, AC-4, AC-6, AC-8; failures kept verbatim.
- `artifacts/` — `check-ho012.txt`, `check-all.txt`, `self-test.txt`, `fresh-clone.txt`, `git-status-before.txt`, `git-status-after.txt`.
- `hashes.txt` (SHA256 of the immutable files in the bundle) and `hashes-notes.txt` (commit pins per DEC-024; pin `workflow/DECISIONS.md` and `workflow/README.md` by commit, do not hash them).
- A per-bundle verdict table for `--all` in the manifest, including any pre-existing defect found, with the code and the file.

## 6. Guard rails

- Do not touch: any existing `workflow/evidence/**` bundle, `workflow/DECISIONS.md`, `workflow/STATUS.md`, `.opencode/**`, `.github/**`, the Strata checkout, `build-hip/`, `build-deepseek/`.
- Do not add dependencies. Stdlib only. No network at runtime.
- Do not change acceptance criteria or scope. Ambiguity → `NEEDS_INFO` to the architect, not a local reinterpretation.
- Do not merge or push to `main`. Commit and push only `wp/strata-013-check-bundle`.
- Do not make a check pass by weakening it: if a bundle is wrong, the tool is right. The only permitted tuning is a false positive demonstrated with a fixture.
- No secrets in the repo, logs, or handoff.
- Evidence must be raw. A curated transcript labelled "raw" is a failed handoff (DEC-030 B-1).

## 7. Dependencies / blockers

| Dependency | Owner | Status | Needed by |
|---|---|---|---|
| `git` ≥ 2.x, `python3` ≥ 3.11 | environment | available | start |
| `workflow/evidence/HO-STRATA-012` as the positive control | Architect | available | AC-1 |
| Bases `91eac12` not yet on `origin/main` (DEC-040, PR pending) | Architect | open | at merge time, rebase onto `origin/main` if it moved |

## 8. Definition of Ready

- [x] ID/type/from/to/title/work package present
- [x] Branch and base commit named (`wp/strata-013-check-bundle` @ `91eac12`)
- [x] Scope and out-of-scope explicit
- [x] Inputs linked and available
- [x] Every criterion has a command/check
- [x] Evidence requirements runnable
- [x] Guard rails explicit
- [x] Dependencies resolved or owned
- [x] Priority/timebox set (P1, 1 day)
- [x] No open `NEEDS_INFO`

## 9. Definition of Done

- [x] `workflow/tools/check_bundle.py` committed on `wp/strata-013-check-bundle` — `git log --oneline wp/strata-013-check-bundle`
- [x] AC-1…AC-8 run; raw output in the manifest — see `workflow/evidence/HO-STRATA-013/test-output.txt`
- [x] The twelve negative controls pass; the clean fixture passes — `python3 workflow/tools/check_bundle.py --self-test` exit 0
- [x] No out-of-scope edits, no new dependencies — `git diff --stat 91eac12..HEAD` shows only `workflow/tools/check_bundle.py`, `workflow/README.md`, `workflow/handoffs/HO-STRATA-013.md`, `workflow/evidence/HO-STRATA-013/`
- [x] No secrets in the bundle — `python3 workflow/tools/check_bundle.py workflow/evidence/HO-STRATA-013` reports `PASS B7-secrets`
- [x] Evidence manifest complete, hashes verify, pins resolve with digests — `python3 workflow/tools/check_bundle.py workflow/evidence/HO-STRATA-013` after commit
- [x] Handoff updated to `CODER_DONE`; `CODER_TO_QAQC` record attached — see §11/§12
- [x] Rework `RW-HO-STRATA-013-1` completed: F1–F5 implemented and evidenced

## 10. Signatures

| Role | Name/agent | Date | Decision |
|---|---|---|---|
| Sender | Architect (`opencode-go/deepseek-v4-pro#max`) | 2026-11-22 | READY |
| Receiver | Primary Coder (`opencode-go/kimi-k2.7-code`) | 2026-11-22 | accepted (IN_PROGRESS) → CODER_DONE |

## 11. Log

- 2026-11-22 Architect: created, `READY`. Predecessor recommendation was
  `SESSION_HANDOFF_2026-11-22.md` §5; scope widened from "hash + ignore checks"
  to the eight codes above because B-1 (curated transcript) and B-6 (pins) were
  both gate findings.
- 2026-11-22 Primary Coder: accepted, `IN_PROGRESS`.
- 2026-11-22 Primary Coder: implemented `workflow/tools/check_bundle.py`, README
  section, evidence bundle; `CODER_DONE`.
- 2026-11-22 Architect: review verdict `REWORK` (`RW-HO-STRATA-013-1`); AC-2
  reported 32 false-positive FAILs on legacy path spellings in HO-001/007/008.
- 2026-11-22 Primary Coder: implemented F1–F5 of `RW-HO-STRATA-013-1`: ordered
  B2 path resolution (repo root → bundle dir → absolute/external → basename
  fallback), B3 coverage by normalized path, `--strict` upgrade mode, 12
  self-test fixtures, and refreshed evidence; `CODER_DONE`.
- 2026-11-22 Primary Coder: RW-1 verification from a clean tree:
  - `python3 workflow/tools/check_bundle.py workflow/evidence/HO-STRATA-013` → `RESULT: PASS` (45 checks, 17 warnings)
  - `python3 workflow/tools/check_bundle.py --all` → exit `1`, exactly 2 FAILs (`B3-unlisted` on `HO-STRATA-011/artifacts/cmd-8.err.txt` and `.out.txt`)
  - `python3 workflow/tools/check_bundle.py --self-test` → `RESULT: PASS` (all 12 fixtures behaved as expected)
- 2026-11-22 Primary Coder: RW-1 closure — fixed-point evidence verified and pushed:
  - `python3 workflow/tools/check_bundle.py workflow/evidence/HO-STRATA-013` → `RESULT: PASS` (29 checks, 0 warnings)
  - `python3 workflow/tools/check_bundle.py --all` → exit `1`, exactly 2 FAILs both `HO-STRATA-011` (`B3-unlisted workflow/evidence/HO-STRATA-011/artifacts/cmd-8.err.txt` and `cmd-8.out.txt`)
  - `python3 workflow/tools/check_bundle.py --self-test` → `RESULT: PASS` (12/12 fixtures)
  - Fixed-point proof: `python3 workflow/tools/check_bundle.py --all` output is byte-identical to `workflow/evidence/HO-STRATA-013/artifacts/check-all.txt`; `git status --porcelain` empty before and after.
- 2026-11-22 Primary Coder: RW-2 closure — A1 (B3 exact `hashes.txt` exemption) and
  A2 (B6 verifies every path pin) fixed; three new negative controls added
  (15/15 fixtures); `commands.log` and `manifest.md` made reproducible/correct;
  evidence refreshed and fixed-point verified:
  - `python3 workflow/tools/check_bundle.py --self-test` → `RESULT: PASS` (15/15 fixtures)
  - `python3 workflow/tools/check_bundle.py --all` → exit `1`, exactly 2 FAILs
    (`HO-STRATA-011` `B3-unlisted`); `HO-STRATA-012` remains `PASS`
  - `python3 workflow/tools/check_bundle.py workflow/evidence/HO-STRATA-013` → `RESULT: PASS` (30 checks, 0 warnings)
  - Fixed-point proof: fresh `--all` output byte-identical to `artifacts/check-all.txt`; `git status --porcelain` empty.

## 12. CODER_TO_QAQC

**Branch:** `wp/strata-013-check-bundle` (tip is the RW-1 CODER_DONE commit).
**Evidence:** `workflow/evidence/HO-STRATA-013/`.
**Rework:** `RW-HO-STRATA-013-1` completed.

What QAQC must re-run:
1. `python3 workflow/tools/check_bundle.py workflow/evidence/HO-STRATA-012` — expect exit 0, `RESULT: PASS`.
2. `python3 workflow/tools/check_bundle.py --all` — expect exit 1 with **exactly 2 FAILs**: `B3-unlisted workflow/evidence/HO-STRATA-011/artifacts/cmd-8.err.txt` and `B3-unlisted workflow/evidence/HO-STRATA-011/artifacts/cmd-8.out.txt`; zero FAILs for HO-001/007/008/010/012; `DEC-039` WARN skipped.
3. `python3 workflow/tools/check_bundle.py --all --strict` — expect exit 1; every `B2-legacy-path`, `B2-external`, `B2-prose`, and `B3-path-spelling` warning becomes a FAIL; `B6` and `B7` warnings remain WARN.
4. `python3 workflow/tools/check_bundle.py --self-test` — expect exit 0, all 12 fixtures pass.
5. `python3 -I workflow/tools/check_bundle.py --self-test` — expect exit 0.
6. `git status --porcelain` before and after (2) + (4) — expect no diff.
7. `grep -n "check_bundle" workflow/README.md` — expect section with both commands and the CODER_DONE rule.

Notes:
- Do not edit existing bundles; the tool is right if it FAILs a bundle.
- The per-bundle verdict table is in `workflow/evidence/HO-STRATA-013/manifest.md` §3.

## 12. Architect review of CODER_DONE (2026-11-22)

Verdict: **REWORK** — see `RW-HO-STRATA-013-1.md`.

Verified good: AC-1 (HO-012 PASS), AC-3 (7 fixtures), AC-4, AC-5, AC-6, AC-7,
AC-8; the tool's own bundle passes 25 checks; `HO-STRATA-011`'s two unlisted
artifacts are a genuine find.

Failed: **AC-2** — `--all` reports 32 FAILs that are path-spelling artifacts of
three legacy bundles (HO-001, HO-007, HO-008). All their digests verify from the
bundle dir or by basename (proof in the rework §1). AC-3 is also incomplete: it
has no fixture for the legacy spellings it misclassifies.

### Coder reply to architect review (2026-11-22)

`RW-HO-STRATA-013-1` completed. The B2/B3 classification now handles
bundle-relative `./` prefixes, absolute external paths, basename-only spellings,
and prose/pin lines without treating them as defects. `--strict` upgrades the
legacy warnings to FAILs for new bundles, and the self-test covers all 12
classifications. The two remaining FAILs on `--all` are the genuine
`HO-STRATA-011` cmd-8 artifact gaps identified in the original review; no
legacy bundle was edited.

## 13. QAQC review (architect mirrors the transition, DEC-018)

| Field | Value |
|---|---|
| Reviewer | QAQC, `opencode-go/gemini-4-argon`, DEC-039 |
| Verdict | **PASS** |
| Report | `workflow/reports/qaqc/HO-STRATA-013-qaqc.md` |
| Reproduced | 8/8 ACs, 5/5 RW-1 criteria, on clean tree `2800d64` |
| Findings | F1 `--all` globs `HO-*` so DEC-039 is only reachable per-directory (accepted); F2 `--strict` matches F3 verbatim; F3 manifest §3 lists 2 warnings where the authoritative artifact shows 0 (non-blocking, see below) |

State `CODER_DONE → QAQC_REVIEW → AUDIT_REVIEW`, recorded here because QAQC
writes only its report (DEC-018). Next: auditor review.

Carried to the auditor, not fixed: `manifest.md` §3's HO-STRATA-013 row still
lists 2 B6 warnings; `artifacts/check-all.txt` is authoritative and shows
`PASS (29 checks, 0 warnings)` after the digests became full 64-hex. Editing the
manifest now would invalidate the hashes QAQC verified.

## 14. Audit verdict (2026-11-22) — REWORK

`workflow/reports/audit/HO-STRATA-013-audit.md` reproduced AC-1…AC-8 and the
RW-1 fixes, confirmed 18/18 hashes, raw (not curated) evidence, clean scope, and
the seat waiver (WAIVER-001). It then found two blocking defects that QAQC did
not: **B3** (`check_bundle.py:408`) exempts every `*hashes.txt`, not only the
bundle's own file, and **B6** (`:~533`) silently skips any pin row whose Command
cell is not spelled exactly — so a wrong full digest and an unresolvable commit
both PASS. The architect confirmed both in the source and scoped
`RW-HO-STRATA-013-2`. The audit's other findings (commands.log not copy-paste
reproducible; manifest §3 warning count; the AC-2 DEC-039 wording) are folded in
as F3/F4.

## 15. QAQC round 2 and the F3 fix (2026-11-22)

QAQC re-ran the work on the fixed tip and returned **PASS**, reproducing the
auditor's two probes as now-failing (unlisted `notes-hashes.txt` → `B3-unlisted`;
wrong full digest and `deadbeef` under a reworded command → `B6-pins`) and the
control as passing. Regression: HO-012 PASS, `--all` 2 FAILs (both HO-011),
15/15 fixtures, 19/19 hashes, C12 reproduces `hashes.txt`.

Its finding **F3** was real and is fixed by the architect, not the coder:
`artifacts/check-all-strict.txt` had been captured mid-refresh and showed this
bundle dirty (`e0063b4e…` mismatch, `B3-path-spelling`, `B4 not clean`).
Recaptured from the clean tree (`C9e`), hashes regenerated by the logged `C12`
block verbatim. Both aggregate artifacts are now fixed points: a fresh
`--all` and `--all --strict` reproduce them byte for byte with an empty
`git status`.

The auditor should verify the *final* artifacts (`429ad4d`→this commit), not the
ones its first audit saw. Two QAQC findings are record-only: F1 (one fixture
fails at the unresolvable-path branch before reaching the digest comparison —
it still proves the row is not skipped, and `bypass-proof.txt` covers the
digest branch directly) and F2 (the pin parser prefers `<commit>:<path>` from
the Command cell when present).

## 16. RW-3 closure (2026-11-23)

R2-4 is fixed: B6 verifies the **File/Path** column and never lets the Command
cell decide what is verified; divergent cells emit
`WARN B6-pins command path differs from File column`. `--self-test` is **16/16**.

The probes moved into `workflow/evidence/HO-STRATA-013/scripts/`
(`legacy_proof.py`, `bypass_probe.py`), so `commands.log` records one runnable
line per probe instead of an un-copyable heredoc.

Capture ordering, which failed twice, is now explicit: aggregates are captured
to `/tmp` and moved with `;` (the tool exits 1 — `&&` would skip the move, cause
of R2-1), `test-output.txt` is rebuilt **after** the final capture (cause of
R2-2), and the rehash runs last. Entries C17–C23 record the cycle verbatim.

Final state, verified on a clean tree:

```text
--all              exit 1, 2 FAILs (both HO-STRATA-011 B3-unlisted)   IDENTICAL to stored artifact
--all --strict     exit 1, 93 FAILs (legacy upgrades), bundle PASSes  IDENTICAL to stored artifact
--self-test        16/16
--all on HO-STRATA-012  PASS
hashes.txt         21 entries, 21/21 OK, no absolute path
```

**Process note:** the coder hit its step budget at the recapture; the architect
completed C17–C20 and the convergence pass C21–C23, logged verbatim, with no
tool change. The auditor ruled such an evidence-only completion acceptable *if*
reproducible, logged and re-derived — that condition is what QAQC and the
auditor now test.

## 17. QAQC round 3 (2026-11-23) — PASS

Reproduced R2-1 (the logged `C17` command now actually moves the artifact from a
fresh clone — inode changes, `/tmp/ca.txt` gone) and R2-4 (File column verified;
divergent Command cell WARNs; wrong File digest FAILs). Fixed points hold for
both aggregates; `test-output.txt` matches every artifact section; 21/21 hashes;
C23 reproduces `hashes.txt`.

Two doc findings closed before the audit: QAQC F1 (manifest §1 abbreviated the
rehash heredocs and stopped at C19 — the table is now **generated from
`commands.log`**, and the historical `C16` block carries an erratum because its
closing `PY` was missing and it is superseded by `C20`/`C23`) and F2 (§3 check
counts corrected to 32/319).

## 18. Architect signoff (2026-11-23)

**SIGNED** — `workflow/handoffs/HO-STRATA-013-APPROVAL.md`. Audit round 3 PASS
with no blocking findings; the seven record-only minors (R3-1…R3-9) are carried
in the approval with owners, none touching the claim. Merge via PR with a merge
commit (DEC-040). Adopted as the evidence gate (DEC-041): run before
`CODER_DONE`, and by QAQC before review.
