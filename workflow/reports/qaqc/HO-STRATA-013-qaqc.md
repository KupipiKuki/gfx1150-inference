# QAQC report — HO-STRATA-013

| Field | Value |
|---|---|
| **Handoff** | HO-STRATA-013 (`check_bundle.py`: automate the evidence-packaging invariants), Rework `RW-HO-STRATA-013-1`, QAQC handoff `HO-STRATA-013-QAQC` |
| **Reviewer** | QAQC (`opencode-go/gemini-4-argon`, DEC-039) |
| **Date (UTC)** | 2026-11-22 |
| **Verdict** | **PASS** |
| **Scope reviewed** | Branch `wp/strata-013-check-bundle`, base `91eac12`, tip `2800d64` (23 files changed, 3538 insertions, 0 deletions): `workflow/tools/check_bundle.py`, `workflow/README.md`, `workflow/evidence/HO-STRATA-013/**`, `workflow/handoffs/HO-STRATA-013*.md`, `workflow/handoffs/RW-HO-STRATA-013-1.md` |

**Profile:** Host tooling only — Linux Mint 22.3 (Zena), kernel `7.0.0-42-generic`, Python `3.14.10`, git `2.43.0`. Hardware: AMD Radeon 890M (`gfx1150`) host (no GPU, model, quantization, or engine workload is invoked or claimed by this work package).

---

## 1. Acceptance criteria re-run

Every criterion in `HO-STRATA-013.md` §4 (AC-1…AC-8), `RW-HO-STRATA-013-1.md` §2 (F1–F5), and `HO-STRATA-013-QAQC.md` §4 was re-run independently on clean tree `2800d64`.

| # | Criterion | Command | Observed | Pass? |
|---|---|---|---|---|
| AC-1 | Runs on a real, signed bundle | `python3 workflow/tools/check_bundle.py workflow/evidence/HO-STRATA-012` | Exit `0`, `RESULT: PASS (22 checks, 3 warnings)`; 19 `PASS` (`B1-structure` ×3, `B2-hash-verify` ×10, `B3-hash-coverage`, `B4-tracked` ×2, `B5-not-ignored`, `B7-secrets`, `B8-read-only`), 3 `WARN B6-pins` on abbreviated/uncomparable commit pins (`66267d2`). Byte-identical to `artifacts/check-ho012.txt` (`f5534b8a…`). | **PASS** |
| AC-2 | Aggregate run over every bundle | `python3 workflow/tools/check_bundle.py --all` | Exit `1`; `RESULT: FAIL (313 checks, 111 warnings)`. Processes all 8 `workflow/evidence/HO-*` directories (`HO-STRATA-001`, `005`, `007`, `008`, `010`, `011`, `012`, `013`). **Exactly 2 FAIL lines**, both on `HO-STRATA-011`: `FAIL B3-unlisted workflow/evidence/HO-STRATA-011/artifacts/cmd-8.err.txt` and `FAIL B3-unlisted workflow/evidence/HO-STRATA-011/artifacts/cmd-8.out.txt`. Zero FAILs on `HO-001` (PASS, 43 warnings), `HO-005` (PASS, 1 warning: `WARN B1-structure no manifest.md; skipped`), `HO-007` (PASS, 32 warnings), `HO-008` (PASS, 31 warnings), `HO-010` (PASS, 0 warnings), `HO-012` (PASS, 3 warnings), `HO-013` (PASS, 0 warnings). Direct run on `workflow/evidence/DEC-039` exits `0` with `WARN B1-structure no manifest.md; skipped` (see F1). Fresh `--all` output is byte-identical (`diff` exit `0`, sha256 `b6515d5b…`) to `artifacts/check-all.txt`. | **PASS** |
| AC-3 | Negative controls (12 fixtures) | `python3 workflow/tools/check_bundle.py --self-test` | Exit `0`; 12/12 fixtures print `PASS` (`hash-edited`, `extra-artifact`, `untracked`, `ignored`, `bad-pin`, `secret`, `clean`, `bundle-relative` + `--strict`, `absolute-external`, `prose`, `basename-spelling`, `malformed-separator`), followed by `RESULT: PASS (all fixtures behaved as expected)`. Code inspection confirmed every fixture creates a real throwaway git repo and constructs the actual defect (tampered file post-hash, unlisted file, unadded file, `.gitignore` rule matching `*.log`, unresolvable `git show <commit>:missing.txt` pin, `ghp_` token, `./` path with normal+strict checks, external readable+missing absolute paths, prose lines, basename-only path for file under `artifacts/`, and ` *` binary-mode separator). | **PASS** |
| AC-4 | Stdlib only, isolated interpreter | `python3 -I workflow/tools/check_bundle.py --self-test`; `grep -nE '^(import\|from) ' workflow/tools/check_bundle.py`; `grep -nE 'socket\|urllib\|requests\|http' workflow/tools/check_bundle.py` | Exit `0` under `python3 -I` (12/12 fixtures pass). Imports are strictly stdlib (`__future__`, `argparse`, `hashlib`, `json`, `os`, `re`, `shutil`, `subprocess`, `sys`, `tempfile`, `pathlib`, `typing`). Grep for `socket\|urllib\|requests\|http` returned 0 matches. | **PASS** |
| AC-5 | Read-only | `git status --porcelain > before.txt`; run AC-1 and AC-2; `git status --porcelain > after.txt`; `diff -u before.txt after.txt` | `before.txt` and `after.txt` are both empty (0 bytes); `diff -u` exit `0`. | **PASS** |
| AC-6 | Works from a fresh clone | `git clone --branch wp/strata-013-check-bundle . /tmp/opencode/qaqc-013/cb-fresh`; run AC-1 in clone | Exit `0`; `RESULT: PASS (22 checks, 3 warnings)`; output is byte-identical (`diff -u` exit `0`) to AC-1 in the primary working tree. Temporary clone removed after verification. | **PASS** |
| AC-7 | Documented | `grep -n "check_bundle" workflow/README.md` | Section `## check_bundle.py` present at `workflow/README.md:36-49`, documenting both commands (`workflow/evidence/HO-STRATA-012` and `--all`) and the explicit rule: *"Before marking any handoff `CODER_DONE`, run the evidence-packaging checker"* and *"QAQC re-runs the same command(s) before its review."* | **PASS** |
| AC-8 | Deterministic output | Run AC-1 twice consecutively (`ac8-1.txt`, `ac8-2.txt`) and with `--json` twice (`ac8-json1.txt`, `ac8-json2.txt`); `diff -u` and `sha256sum` | Both text runs have sha256 `f5534b8afb1869263ca8671ddd9b63cf5a2db9dddac9bef9b7c752156185a527` (`diff` exit `0`); both `--json` runs are byte-identical (`diff` exit `0`), with no timestamps, durations, or absolute repo paths. | **PASS** |
| RW-1 F1 | Ordered B2 path resolution & no fallthrough on mismatch | Inspect `check_b2_hash_verify` (`workflow/tools/check_bundle.py:202-388`) + adversarial test Case A | Resolution order matches `RW-HO-STRATA-013-1.md` §2 F1: (a) repo-root relative (`PASS B2-hash-verify` or `FAIL B2-hash-mismatch`), (b) bundle-dir relative (`PASS B2-hash-verify` + `WARN B2-legacy-path` or `FAIL B2-hash-mismatch`), (c/c') external absolute (`PASS B2-hash-verify` + `WARN B2-external`, `FAIL B2-hash-mismatch`, or `WARN B2-external-unverifiable`), (d/d') basename fallback under bundle dir (`PASS B2-hash-verify` + `WARN B2-path-spelling` or `FAIL B2-hash-mismatch`), (e) `FAIL B2-missing`. Non-hash lines: `#` ignored, non-64-hex `WARN B2-prose`, 64-hex bad separator `FAIL B2-malformed`. `mismatch_at_exact_or_legacy = True` at (a) and (b) prevents fallthrough to (d) basename fallback. Verified via adversarial Case A (canonical `bundle/artifact.txt` tampered while decoy `bundle/sub/artifact.txt` has the listed digest): tool exited `1` with `FAIL B2-hash-mismatch bundle/artifact.txt` and did not fall through to the decoy. | **PASS** |
| RW-1 F2 | B3 coverage by normalized path | Inspect `check_b3_hash_coverage` (`workflow/tools/check_bundle.py:391-445`) + `--all` | Exact repo-relative match is covered silently; bundle-dir or basename match emits `WARN B3-path-spelling`; unlisted disk files emit `FAIL B3-unlisted`. `HO-STRATA-011/artifacts/cmd-8.{err,out}.txt` emit `FAIL B3-unlisted`. | **PASS** |
| RW-1 F3 | `--strict` mode upgrades | `python3 workflow/tools/check_bundle.py --all --strict` + adversarial test Case B | Exit `1`; `RESULT: FAIL (313 checks, 20 warnings)`, byte-identical (`diff` exit `0`, sha256 `5a9f802b…`) to `artifacts/check-all-strict.txt`. `STRICT_UPGRADE_CODES` upgrades exactly `B2-legacy-path`, `B2-external`, `B2-prose`, and `B3-path-spelling` from `WARN` to `FAIL`. Verified via `--all --strict` and adversarial Case B that `B6-pins` and `B7-secrets` (`allow-secret`) remain `WARN` under `--strict` (see F2). | **PASS** |
| RW-1 F4–F5 & Bundle Self-Check | Self-bundle check, `hashes.txt` hygiene, capture-bug fixes, legacy digest proof | `sha256sum -c workflow/evidence/HO-STRATA-013/hashes.txt`; `python3 workflow/tools/check_bundle.py workflow/evidence/HO-STRATA-013`; legacy proof script | `sha256sum -c` passes 17/17 `OK` (exit `0`). `hashes.txt` has zero `/home/` paths and zero empty-file hashes (`e3b0c442…`). Self-check on `HO-STRATA-013` exits `0` with `RESULT: PASS (29 checks, 0 warnings)`, including `PASS B6-pins` on `315030e:workflow/DECISIONS.md` and `315030e:workflow/README.md` and `PASS B7-secrets`. Independent Python verification of legacy digests reproduced `HO-007 verified from bundle dir: ok=17 problems=0` and `HO-001 verified with basename fallback: ok=21 mismatch=0 missing=0`. | **PASS** |

---

## 2. Commands run and verbatim key outputs

### 2.1 Diff and scope verification

```text
$ git rev-parse --short HEAD
2800d64

$ git diff 91eac12..2800d64 --stat
 workflow/README.md                                 |   14 +
 .../HO-STRATA-013/artifacts/check-all-strict.txt   |  330 ++++++
 .../evidence/HO-STRATA-013/artifacts/check-all.txt |  330 ++++++
 .../HO-STRATA-013/artifacts/check-ho012.txt        |   23 +
 .../HO-STRATA-013/artifacts/deterministic.txt      |    3 +
 .../HO-STRATA-013/artifacts/fresh-clone.txt        |   25 +
 .../HO-STRATA-013/artifacts/git-status-after.txt   |   12 +
 .../HO-STRATA-013/artifacts/git-status-before.txt  |   12 +
 .../HO-STRATA-013/artifacts/git-status-diff.txt    |    2 +
 .../HO-STRATA-013/artifacts/legacy-proof.txt       |    2 +
 .../HO-STRATA-013/artifacts/readme-section.txt     |    3 +
 .../evidence/HO-STRATA-013/artifacts/self-test.txt |   13 +
 .../HO-STRATA-013/artifacts/stdlib-imports.txt     |   12 +
 .../HO-STRATA-013/artifacts/stdlib-isolated.txt    |   13 +
 workflow/evidence/HO-STRATA-013/commands.log       |   73 ++
 workflow/evidence/HO-STRATA-013/hashes-notes.txt   |   21 +
 workflow/evidence/HO-STRATA-013/hashes.txt         |   21 +
 workflow/evidence/HO-STRATA-013/manifest.md        |  107 ++
 workflow/evidence/HO-STRATA-013/test-output.txt    |  806 ++++++++++++++
 workflow/handoffs/HO-STRATA-013-QAQC.md            |  114 ++
 workflow/handoffs/HO-STRATA-013.md                 |  246 +++++
 workflow/handoffs/RW-HO-STRATA-013-1.md            |  222 ++++
 workflow/tools/check_bundle.py                     | 1134 ++++++++++++++++++++
 23 files changed, 3538 insertions(+)

$ git diff 91eac12..2800d64 --stat -- workflow/evidence
(18 files changed, 1808 insertions(+), all under workflow/evidence/HO-STRATA-013/)
```

### 2.2 AC-1, AC-2, AC-3, AC-4, and Self-Bundle Check

```text
$ python3 workflow/tools/check_bundle.py workflow/evidence/HO-STRATA-012
PASS B1-structure manifest.md exists
PASS B1-structure hashes.txt exists
PASS B1-structure commands.log exists
PASS B2-hash-verify ok: workflow/evidence/HO-STRATA-012/manifest.md
PASS B2-hash-verify ok: workflow/evidence/HO-STRATA-012/hashes-notes.txt
PASS B2-hash-verify ok: workflow/evidence/HO-STRATA-012/commands.log
PASS B2-hash-verify ok: workflow/evidence/HO-STRATA-012/artifacts/gguf_geometry_test-output.txt
PASS B2-hash-verify ok: workflow/evidence/HO-STRATA-012/artifacts/inspect-deepseek.txt
PASS B2-hash-verify ok: workflow/evidence/HO-STRATA-012/artifacts/inspect-mismatch.txt
PASS B2-hash-verify ok: workflow/evidence/HO-STRATA-012/artifacts/model_family_test-output.txt
PASS B2-hash-verify ok: workflow/evidence/HO-STRATA-012/artifacts/native-deepseek-refusal.txt
PASS B2-hash-verify ok: workflow/evidence/HO-STRATA-012/artifacts/qwen-regression.txt
PASS B2-hash-verify ok: workflow/evidence/HO-STRATA-012/patches/0001-deepseek-family.patch
PASS B3-hash-coverage all files listed
PASS B4-tracked all files tracked
PASS B4-tracked git status clean
PASS B5-not-ignored no bundle file ignored
WARN B6-pins no comparable digest for 66267d2:workflow/handoffs/HO-STRATA-012.md
WARN B6-pins abbreviated digest for 66267d2:workflow/DECISIONS.md
WARN B6-pins abbreviated digest for 66267d2:planning/strata-engine/13-family-support-test-plan.md
PASS B7-secrets no credential-shaped strings
PASS B8-read-only git status unchanged
RESULT: PASS (22 checks, 3 warnings)
(exit: 0)

$ python3 workflow/tools/check_bundle.py --all > /tmp/opencode/qaqc-013/ac2.txt
(exit: 1)
$ grep -n "^FAIL " /tmp/opencode/qaqc-013/ac2.txt
266:FAIL B3-unlisted workflow/evidence/HO-STRATA-011/artifacts/cmd-8.err.txt
267:FAIL B3-unlisted workflow/evidence/HO-STRATA-011/artifacts/cmd-8.out.txt
$ grep -n "RESULT:" /tmp/opencode/qaqc-013/ac2.txt
73:HO-STRATA-001: RESULT: PASS (72 checks, 43 warnings)
76:HO-STRATA-005: RESULT: PASS (1 checks, 1 warnings)
135:HO-STRATA-007: RESULT: PASS (57 checks, 32 warnings)
193:HO-STRATA-008: RESULT: PASS (56 checks, 31 warnings)
219:HO-STRATA-010: RESULT: PASS (24 checks, 0 warnings)
273:HO-STRATA-011: RESULT: FAIL (52 checks, 1 warnings)
297:HO-STRATA-012: RESULT: PASS (22 checks, 3 warnings)
328:HO-STRATA-013: RESULT: PASS (29 checks, 0 warnings)
330:RESULT: FAIL (313 checks, 111 warnings)
$ diff -u /tmp/opencode/qaqc-013/ac2.txt workflow/evidence/HO-STRATA-013/artifacts/check-all.txt
(exit: 0 — byte-identical, sha256 b6515d5b79f772c868e91560e98e09560de2e1928a6174525a2130b5e044dca3)

$ python3 workflow/tools/check_bundle.py --all --strict > /tmp/opencode/qaqc-013/ac2-strict.txt
(exit: 1)
$ diff -u /tmp/opencode/qaqc-013/ac2-strict.txt workflow/evidence/HO-STRATA-013/artifacts/check-all-strict.txt
(exit: 0 — byte-identical, sha256 5a9f802b99a67fa9b56411f440dd72aa8aca39b3dccb5511785645bb37b13468)

$ python3 -I workflow/tools/check_bundle.py --self-test
PASS hash-edited
PASS extra-artifact
PASS untracked
PASS ignored
PASS bad-pin
PASS secret
PASS clean
PASS bundle-relative
PASS absolute-external
PASS prose
PASS basename-spelling
PASS malformed-separator
RESULT: PASS (all fixtures behaved as expected)
(exit: 0)

$ sha256sum -c workflow/evidence/HO-STRATA-013/hashes.txt
workflow/tools/check_bundle.py: OK
workflow/evidence/HO-STRATA-013/artifacts/check-all-strict.txt: OK
workflow/evidence/HO-STRATA-013/artifacts/check-all.txt: OK
workflow/evidence/HO-STRATA-013/artifacts/check-ho012.txt: OK
workflow/evidence/HO-STRATA-013/artifacts/deterministic.txt: OK
workflow/evidence/HO-STRATA-013/artifacts/fresh-clone.txt: OK
workflow/evidence/HO-STRATA-013/artifacts/git-status-after.txt: OK
workflow/evidence/HO-STRATA-013/artifacts/git-status-before.txt: OK
workflow/evidence/HO-STRATA-013/artifacts/git-status-diff.txt: OK
workflow/evidence/HO-STRATA-013/artifacts/legacy-proof.txt: OK
workflow/evidence/HO-STRATA-013/artifacts/readme-section.txt: OK
workflow/evidence/HO-STRATA-013/artifacts/self-test.txt: OK
workflow/evidence/HO-STRATA-013/artifacts/stdlib-imports.txt: OK
workflow/evidence/HO-STRATA-013/artifacts/stdlib-isolated.txt: OK
workflow/evidence/HO-STRATA-013/commands.log: OK
workflow/evidence/HO-STRATA-013/hashes-notes.txt: OK
workflow/evidence/HO-STRATA-013/manifest.md: OK
workflow/evidence/HO-STRATA-013/test-output.txt: OK
(exit: 0)
```

### 2.3 Adversarial tests (QAQC-constructed)

Two adversarial temporary git repositories were constructed under `/tmp/opencode/qaqc-013` (and deleted after the test):

1. **Case A — Canonical digest mismatch with a matching-basename decoy:** `bundle/artifact.txt` on disk had content `"tampered_canonical"`, while `bundle/sub/artifact.txt` had `"original_content"`, and `hashes.txt` listed `<sha256("original_content")>  bundle/artifact.txt`.
   - **Observed:** Exit `1`, `FAIL B2-hash-mismatch bundle/artifact.txt (actual: 522121ff8d88eeccaf7d0833fda015ce9d8a8f39599059a69133f091ecdfe3b8)`, `RESULT: FAIL (11 checks, 1 warnings)`. The checker did **not** fall through from step (a) to step (d) basename matching.
2. **Case B — Normal vs. `--strict` upgrade selectivity:** A bundle containing `B2-legacy-path` (`./manifest.md`), `B2-external`, `B2-prose` (`N/A — prose line`), `B3-path-spelling`, `B6-pins` (abbreviated digest `1234…5678`), and `B7-secrets` (with `# check_bundle: allow-secret test fixture`).
   - **Observed (normal):** Exit `0`, `RESULT: PASS (16 checks, 6 warnings)`.
   - **Observed (`--strict`):** Exit `1`, `RESULT: FAIL (16 checks, 2 warnings)` — `B2-legacy-path`, `B2-external`, `B2-prose`, and `B3-path-spelling` upgraded to `FAIL`; `WARN B6-pins` and `WARN B7-secrets` remained `WARN`.

---

## 3. Diff and guard-rail review

- [x] Diff is within scope; no unrelated files (`workflow/tools/check_bundle.py`, `workflow/README.md`, `workflow/evidence/HO-STRATA-013/**`, `workflow/handoffs/HO-STRATA-013*.md`, `workflow/handoffs/RW-HO-STRATA-013-1.md`).
- [x] No existing evidence bundle (`HO-001` through `HO-012` or `DEC-039`) was modified.
- [x] `workflow/DECISIONS.md`, `workflow/STATUS.md`, `.opencode/**`, and `.github/**` were not touched.
- [x] No new dependencies without approval (stdlib only, verified with `python3 -I` and import grep; no network calls).
- [x] No secrets/tokens in the diff, logs, or evidence (`PASS B7-secrets` on all bundles; self-test fixture uses a synthetic `ghp_1234…` dummy string).
- [x] Tests are meaningful; no skips hidden as passes (all 12 negative controls construct real defects in throwaway git repositories and assert specific check codes).
- [x] Evidence matches the commands that were run; both capture-ordering bugs from prior review (empty-file hash during live redirect and absolute `/home/` paths from `find`) are genuinely fixed in the committed artifacts (`artifacts/check-all.txt`, `artifacts/check-all-strict.txt`, `hashes.txt`).

---

## 4. Findings (severity order)

| # | Severity | Finding | File:line / evidence | Required action |
|---|---|---|---|---|
| F1 | Minor / Info | `--all` discovers bundles via `evidence_dir.glob("HO-*")` per `HO-STRATA-013.md` §1.1 line 60, so `workflow/evidence/DEC-039/` is skipped by the `HO-*` glob during `--all` rather than emitting a `DEC-039` section in `--all` stdout (`HO-STRATA-005`, which has no `manifest.md`, emits `WARN B1-structure no manifest.md; skipped` during `--all`, and running `check_bundle.py workflow/evidence/DEC-039` directly also emits `WARN B1-structure no manifest.md; skipped`, exit 0). This behavior was already accepted by the Architect in `RW-HO-STRATA-013-1.md` §1.3 and matches the required fixed-point `artifacts/check-all.txt`. | `workflow/tools/check_bundle.py:780`, `artifacts/check-all.txt` | None (documented for Auditor awareness). |
| F2 | Minor / Info | `STRICT_UPGRADE_CODES` upgrades `B2-legacy-path`, `B2-external`, `B2-prose`, and `B3-path-spelling` — matching `RW-HO-STRATA-013-1.md` §2 F3 verbatim. Note that `B2-path-spelling` is not in `STRICT_UPGRADE_CODES`, so on basename-only entries (such as in `HO-STRATA-001`) `--strict` leaves `WARN B2-path-spelling` as `WARN` while upgrading the paired `B3-path-spelling` to `FAIL` (causing the bundle to `FAIL` under `--strict` as intended). | `workflow/tools/check_bundle.py:52-57`, `artifacts/check-all-strict.txt:18,49` | None (conforms to `RW-HO-STRATA-013-1.md` §2 F3). |
| F3 | Minor (doc) | In `workflow/evidence/HO-STRATA-013/manifest.md` §3 (line 55), the summary table row for `HO-STRATA-013` states `2` warnings (`B6: 2 abbreviated commit pins for DECISIONS.md/README.md`), left over from before full 64-hex digests were recorded in `hashes-notes.txt`. The actual authoritative run in `artifacts/check-all.txt` (line 328) and `HO-STRATA-013.md` §11 (line 201) shows `HO-STRATA-013: RESULT: PASS (29 checks, 0 warnings)`. | `workflow/evidence/HO-STRATA-013/manifest.md:55` | None (non-blocking prose discrepancy; `artifacts/check-all.txt` is authoritative). |

No Blocker or Major findings.

---

## 5. Verdict and next state

- **PASS** → `AUDIT_REVIEW`; attach this report and the evidence path.

### QAQC_TO_AUDITOR (embedded per DEC-018)

| Field | Value |
|---|---|
| **ID** | HO-STRATA-013-AUDIT (embedded in `HO-STRATA-013-qaqc.md`) |
| **Type** | QAQC_TO_AUDITOR |
| **State** | AUDIT_REVIEW |
| **Date (UTC)** | 2026-11-22 |
| **From → To** | QAQC (`opencode-go/gemini-4-argon`) → Auditor |
| **Handoff** | `workflow/handoffs/HO-STRATA-013.md` (with `RW-HO-STRATA-013-1.md` and `HO-STRATA-013-QAQC.md`) |
| **Branch / commit** | `wp/strata-013-check-bundle` @ `2800d64` (base `91eac12`) |
| **QAQC report** | `workflow/reports/qaqc/HO-STRATA-013-qaqc.md` |
| **Evidence bundle** | `workflow/evidence/HO-STRATA-013/` (17/17 hashes verified via `sha256sum -c`; `check_bundle.py` self-check `RESULT: PASS (29 checks, 0 warnings)`) |
| **Summary** | All 8 acceptance criteria (AC-1…AC-8) and all 5 rework items (`RW-HO-STRATA-013-1` F1–F5) independently reproduced and verified. Three Minor/Informational findings (F1–F3), zero Blockers/Majors. |

---

## 6. Statement

I did not modify code, tests, docs, or configuration. This report (`workflow/reports/qaqc/HO-STRATA-013-qaqc.md`) is the only artifact I wrote.
