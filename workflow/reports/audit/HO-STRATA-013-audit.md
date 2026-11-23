# Audit report — HO-STRATA-013

| Field | Value |
|---|---|
| **Handoff** | HO-STRATA-013 (`check_bundle.py`: automate the evidence-packaging invariants), with `RW-HO-STRATA-013-1` and the QAQC report |
| **Reviewer** | Auditor (`auditor`), runtime model `opencode-go/deepseek-v4.1-flash` (family `deepseek`) — **shares the architect's family under WAIVER-001; this is a documented exception, not a clean independent-family PASS** (DEC-006 separation; DEC-039 records the auditor seat as `deepseek`, waived) |
| **Date (UTC)** | 2026-11-22 |
| **Verdict** | **REWORK (FAIL)** → `RW-HO-STRATA-013-2` (definition in §5; see the note on materialization) |
| **Evidence reviewed** | `workflow/evidence/HO-STRATA-013/` (18 hashed entries) on `wp/strata-013-check-bundle` @ `0b3ad61`; QAQC-verified tree `2800d64` |
| **QAQC report** | `workflow/reports/qaqc/HO-STRATA-013-qaqc.md` (`opencode-go/gemini-4-argon`, PASS, F1–F3) |
| **Scope reviewed** | `git diff 91eac12..HEAD` — 24 files, 3779 insertions, 0 deletions; only `check_bundle.py`, `README.md`, the HO-013 evidence, and the HO/RW/QAQC handoff+report artifacts |
| **Profile (one only)** | Host tooling: Linux Mint 22.3, kernel `7.0.0-42-generic`, Python `3.14.10`, git `2.43.0`. No GPU, model, quant, or engine workload is invoked or claimed. |
| **Decisions read** | DEC-024 (hash immutable / pin mutable), DEC-030 (curated-transcript precedent), DEC-039 (QAQC/auditor seats), DEC-040 (`main` via PR, no merge here) |

---

## 1. Evidence verification

- [x] **Manifest complete; acceptance commands reproducible.** AC-1…AC-8 and RW-1 F1–F5 were re-run independently (§1.1). Two `commands.log` entries are not copy-paste exact (A6), but the criteria themselves re-run from the manifest.
- [x] **Outputs raw; failures/skips kept verbatim.** `test-output.txt` is a byte-exact concatenation of the 13 artifacts; every artifact reproduces byte-identically (§1.3). The two FAILs on `HO-STRATA-011` are preserved, not hidden.
- [x] **Artifacts/hashes match.** `sha256sum -c` → **18/18 OK, exit 0**; paths are repo-relative (§1.2).
- [x] **Environment recorded and true.** The manifest's OS/kernel/Python/git match this host exactly.
- [x] **No secrets.** Pattern scan over the bundle for `ghp_`, `github_pat_`, `sk-`, `AKIA`, `xox[baprs]-`, `PRIVATE KEY` → none. The `/home/…` strings present are documented external paths, not credentials.
- [x] **Pins carry digests and resolve.** `315030e:workflow/DECISIONS.md` → `600d123a…7b05`; `315030e:workflow/README.md` → `3bfcf2aa…4674e`; both match `hashes-notes.txt`, and neither file changed after `315030e`.
- [x] **RW-1 §1.4 capture bugs are gone from the committed artifacts.** No `e3b0c442…` empty-file digest; no `/home/` in `hashes.txt`; no self-bundle absolute path in `check-all.txt` (§1.4).
- [x] **Read-only.** `git status --porcelain` was empty before and after my runs; the tool wrote nothing in the repo.
- [x] **Scope/guard rails.** No existing bundle, `DECISIONS.md`, `STATUS.md`, `.opencode/**`, `.github/**`, Strata checkout, or built binary was modified (§2.4).

### 1.1 Independent re-run (this audit)

| # | Command | Observed | Verdict |
|---|---|---|---|
| AC-1 | `python3 workflow/tools/check_bundle.py workflow/evidence/HO-STRATA-012` | exit 0; `RESULT: PASS (22 checks, 3 warnings)`; `diff` against `artifacts/check-ho012.txt` **identical** | PASS |
| AC-2 | `python3 workflow/tools/check_bundle.py --all` | exit 1; `RESULT: FAIL (313 checks, 111 warnings)`; **exactly 2 FAILs**, both `HO-STRATA-011` `B3-unlisted` (`artifacts/cmd-8.err.txt`, `.out.txt`); byte-identical to `artifacts/check-all.txt` | PASS |
| AC-3 | `python3 workflow/tools/check_bundle.py --self-test` | exit 0; 12 `PASS` fixture lines; `RESULT: PASS (all fixtures behaved as expected)`; identical to `artifacts/self-test.txt` | PASS |
| AC-4 | `python3 -I workflow/tools/check_bundle.py --self-test`; `grep -nE '^(import\|from) ' …` | exit 0 under `-I`; 12/12; imports are stdlib only (`__future__, argparse, hashlib, json, os, re, shutil, subprocess, sys, tempfile, pathlib, typing`); no network imports | PASS |
| AC-5 | `git status --porcelain` before/after AC-1+AC-2+AC-3 | empty before, empty after; committed before/after artifacts identical (`snapshot_cmp_exit: 0`) | PASS (see A7) |
| AC-6 | `git clone --branch wp/strata-013-check-bundle . /tmp/opencode/audit-fresh`; run AC-1 in clone | clone `0b3ad61`; exit 0; byte-identical to AC-1 | PASS (committed artifact is from `d00da6f`) |
| AC-7 | `grep -n "check_bundle" workflow/README.md` | section at `README.md:36-49`; both commands; “Before marking any handoff `CODER_DONE` …”; “QAQC re-runs …” | PASS |
| AC-8 | two AC-1 runs; two `--json` runs; `diff`/`sha256sum` | text: `f5534b8a…a527` both runs, `diff` exit 0; JSON byte-identical; no timestamps/absolute paths in JSON | PASS |
| RW-1 F1/F2/F5 | `--all` (+ inspection of `check_b2_hash_verify`, `check_b3_hash_coverage`) | ordered resolution (repo-root → bundle-dir → external → basename → missing); no fallthrough from a canonical mismatch (probe 1, §2.3); 2 FAILs only | PASS |
| RW-1 F3 | `--all --strict` | exit 1; `RESULT: FAIL (313 checks, 20 warnings)`; exactly `B2-external` (8), `B2-legacy-path` (32), `B2-prose` (3), `B3-path-spelling` (48) upgraded, plus the 2 `B3-unlisted`; `B6-pins` remains WARN (3); identical to `artifacts/check-all-strict.txt` | PASS |
| RW-1 F4 | `--self-test` + code read | 12 fixtures each create a throwaway git repo and a real defect; fixtures assert a specific code | PASS, with assertion gaps in A3 |
| Self-bundle | `python3 workflow/tools/check_bundle.py workflow/evidence/HO-STRATA-013` | exit 0; `RESULT: PASS (29 checks, 0 warnings)`; `PASS B6-pins` on both pins | PASS |

### 1.2 Hashes and pins

```text
$ sha256sum -c workflow/evidence/HO-STRATA-013/hashes.txt
… 18 lines: OK
(exit 0)

$ git show 315030e:workflow/DECISIONS.md | sha256sum
600d123a7cef8ea1e54bcdb81ac019a036297d9e6ccada925136058a341f7b05  -
$ git show 315030e:workflow/README.md | sha256sum
3bfcf2aa3ee2e55acfd69313b136e895a1176a71e58317b7c698f67b4d46874e  -
$ git diff --stat 315030e..HEAD -- workflow/README.md workflow/DECISIONS.md
(empty)
```

`hashes.txt` has 18 entries (17 bundle files + `workflow/tools/check_bundle.py`), all repo-root relative; none begins with `/`. The QAQC report's “17/17” omits the tool entry (A8).

### 1.3 Raw, not curated (DEC-030 B-1)

`test-output.txt` is a faithful concatenation, not a rewrite. I split it on its `===== artifacts/<name> =====` headers and compared every section with the corresponding artifact:

```text
check-ho012.txt: embedded=23 artifact=23 identical=True
check-all.txt: embedded=330 artifact=330 identical=True
check-all-strict.txt: embedded=330 artifact=330 identical=True
self-test.txt: embedded=13 artifact=13 identical=True
stdlib-isolated.txt: embedded=13 artifact=13 identical=True
stdlib-imports.txt: embedded=12 artifact=12 identical=True
git-status-before.txt: embedded=12 artifact=12 identical=True
git-status-after.txt: embedded=12 artifact=12 identical=True
git-status-diff.txt: embedded=2 artifact=2 identical=True
fresh-clone.txt: embedded=25 artifact=25 identical=True
readme-section.txt: embedded=3 artifact=3 identical=True
deterministic.txt: embedded=3 artifact=3 identical=True
legacy-proof.txt: embedded=2 artifact=2 identical=True
```

All 13/13 sections are byte-identical. The committed `check-all.txt` and `check-all-strict.txt` also reproduce byte-for-byte from the current tree.

### 1.4 The two capture bugs from RW-1 §1.4

```text
$ grep -rn 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855' workflow/evidence/HO-STRATA-013/
none
$ grep -n '/home/' workflow/evidence/HO-STRATA-013/hashes.txt
none
$ grep -n '/home/kupipi/Documents/git/gfx1150-inference' workflow/evidence/HO-STRATA-013/artifacts/check-all.txt
none
```

`check-all.txt` does contain `/home/…` paths, but they are the **external model/binary pins of HO-001/007/008/011** echoed by `B2-external`, not the self-bundle path and not the capture redirect leak. The self-bundle absolute path is absent. Both capture bugs are fixed in the committed artifacts.

---

## 2. Claim and scope audit

### 2.1 Claims verified

- **“AC-1…AC-8 reproduce on a clean tree.”** Verified §1.1; the artifacts are raw and byte-identical.
- **“`--all` has exactly two genuine FAILs.”** Verified: `HO-STRATA-011/artifacts/cmd-8.{err,out}.txt` exist (0 and 2529 bytes), the manifest lists command 8 as writing them, and `HO-STRATA-011/hashes.txt` does not list them. Genuine packaging gap; correct find.
- **“`--all --strict` upgrades exactly the F3 codes.”** Verified by code (`STRICT_UPGRADE_CODES`, `check_bundle.py:52-57`) and by the strict output's FAIL/WARN code census. `B6` and `B7` are unchanged.
- **“Legacy bundles verify under bundle-dir/basename rules.”** Verified by the committed `legacy-proof.txt` counts and by the `--all` zero-FAIL state for HO-001/007/008; the digests are checked by B2.
- **“Pins resolve with the recorded digests.”** Verified §1.2.
- **“Both capture bugs are fixed.”** Verified §1.4.
- **“Scope is limited to the tool, README, handoff, and HO-013 evidence.”** Verified §2.4.

### 2.2 Claims that do not hold, or are not supported by a committed artifact

- **False claim (A5).** `RW-HO-STRATA-013-1.md:78` says “the tool now exits 4 if `hashes.txt` contains an absolute path.” The tool has no exit 4 anywhere (`grep -nE 'exit.?4'` finds nothing; exit codes are 0/1/2), and B2 step (c/c′) deliberately **accepts** absolute external paths with `WARN B2-external`. The sentence contradicts the tool's own contract and must be corrected in the record (architect), not implemented.
- **Unsupported as worded (A4).** `manifest.md:57` says “`DEC-039` is WARN skipped … as required by the handoff” under AC-2, but `--all` globs `HO-*` and never emits a DEC-039 section. A direct run does emit `WARN B1-structure no manifest.md; skipped` (I ran it: exit 0, 1 check, 1 warning), so the behaviour is right but the AC-2 artifact does not show it.
- **Not reproducible from the bundle (A6).** `commands.log` C8 uses `python3 ...`; C10 shows `python3 - <<'PY'` with the body absent; C2d/C9d `mv /tmp/ca.txt artifacts/check-all.txt` with `cwd: repo root` would write to `<repo>/artifacts/`, not the bundle. The manifest §7 claim “Commands are reproducible” is therefore overstated, even though the outputs themselves were reproduced (by QAQC and by me).

### 2.3 Tool honesty — adversarial probes (this audit)

The tool must not let a wrong bundle pass. I built throwaway git repos under `/tmp/opencode/audit-probe*` and ran the committed tool against them. Two contract violations surfaced, plus one confirmation of the QAQC adversarial result.

**Probe 1 — canonical mismatch with a matching-basename decoy (QAQC Case A reproduced).**

```text
FAIL B2-hash-mismatch bundle/artifact.txt (actual: 522121ff…)
RESULT: FAIL
```

No fallthrough from step (a) to the basename decoy. The F1 fix is real.

**Probe 2 — unlisted artifact named `artifacts/notes-hashes.txt` (A1, blocker).**

```text
bundle/a.txt, bundle/manifest.md listed; bundle/artifacts/notes-hashes.txt NOT listed
PASS B3-hash-coverage all files listed
RESULT: PASS (10 checks, 0 warnings)          # --strict also PASS (10 checks, 0 warnings)
```

`check_bundle.py:408` is `if fpath.endswith("hashes.txt"): continue`. That exempts **every** path ending in `hashes.txt`, not only the bundle's own `hashes.txt` as B3 requires. This is a live class: `HO-STRATA-010/artifacts/pack_hashes.txt` already has that suffix (it happens to be listed, so no current damage). An artifact can be smuggled into a bundle unhashed and the tool reports PASS, even under `--strict`. This is exactly the “weaken a check to make it pass” failure the handoff guard rail forbids.

**Probe 3 — full 64-hex wrong pin digest with a nonstandard command; Probe 4 — the same row with the standard command (A2, blocker).**

```text
Probe 3 (command: `git show <c>:pinned.txt > /tmp/x; sha256sum /tmp/x`):
RESULT: PASS (11 checks, 0 warnings)

Probe 4 (control, command: `git show <c>:pinned.txt \| sha256sum`):
FAIL B6-pins digest mismatch for 9b6d10ee…:pinned.txt
RESULT: FAIL (12 checks, 0 warnings)
```

**Probe 5 — pin row with `File`+`Repository`+`Commit`+full wrong digest and no `Command` column.**

```text
RESULT: PASS (11 checks, 0 warnings)
```

**Probe 6 — unresolvable commit `deadbeef` with a nonstandard command.**

```text
RESULT: PASS (11 checks, 0 warnings)
```

`check_bundle.py:533` only verifies rows whose `Command` cell matches `git show <hex>:<path> | sha256sum`; everything else is silently skipped. B6 says rows that record a commit pin must have the commit and `commit:path` resolve, and a full 64-hex digest must match. Probes 3/5/6 show both a wrong digest and an unresolvable commit passing as `RESULT: PASS`. The control (Probe 4) shows the check is correct only for the exact phrasing the project happens to use today.

**Self-test realism (A3).** The 12 fixtures are real: each builds a throwaway git repo, constructs the defect (tampered file, unlisted file, unadded file, `.gitignore` match, missing `commit:path`, `ghp_` string, clean bundle, `./` path, external absolute + missing, prose, basename spelling, ` *` separator), and asserts a specific code. Two F4 sub-cases are constructed but not asserted: `fixture_absolute_external` creates the missing external path but only asserts `WARN B2-external`, not `WARN B2-external-unverifiable`; `fixture_basename_spelling` asserts only `WARN B2-path-spelling`, not the paired `WARN B3-path-spelling`. A regression in either branch would not fail the self-test.

### 2.4 Scope and guard rails

```text
$ git diff 91eac12..HEAD --stat
 workflow/README.md                                 |   14 +
 .../HO-STRATA-013/artifacts/… (13 files)            |  …
 workflow/evidence/HO-STRATA-013/{manifest.md,commands.log,test-output.txt,hashes.txt,hashes-notes.txt} | …
 workflow/handoffs/HO-STRATA-013.md                 |  264 ++++
 workflow/handoffs/HO-STRATA-013-QAQC.md            |  114 ++
 workflow/handoffs/RW-HO-STRATA-013-1.md            |  222 ++++
 workflow/reports/qaqc/HO-STRATA-013-qaqc.md        |  223 ++++
 workflow/tools/check_bundle.py                     | 1134 ++++++++++++++++++++
 24 files changed, 3779 insertions(+)

$ git diff --name-only 91eac12..HEAD -- workflow/DECISIONS.md workflow/STATUS.md .opencode .github
(empty)
$ git diff 91eac12..HEAD --stat -- workflow/evidence
(only workflow/evidence/HO-STRATA-013/**)
$ git -C /home/kupipi/Documents/git/strata status --porcelain
(empty; HEAD bac859ef9)
$ sha256sum /home/kupipi/Documents/git/strata/build-hip/strata
d58ee2398596d1a100c15d5b9459e24bd86854cb5e5fb7ce88dbc6c7ed9f5858  (mtime Nov 15, unchanged)
```

No existing bundle was edited; no protected path changed; the Strata checkout and signed binary are untouched; no dependency was added (stdlib-only, `-I` passes); no network code. The only out-of-scope-looking entries (QAQC handoff/report, RW file) are architect/QAQC artifacts, not coder edits. `git status` after my runs is empty.

---

## 3. QAQC findings — disposition, and the `--all` red state

| QAQC | Finding | Ruling |
|---|---|---|
| **F1** | `--all` globs `HO-*`, so `DEC-039` appears only on a direct run | **Accept, record-only.** HO-013 §1.1 literally specifies `HO-*`; the direct run gives `WARN B1-structure no manifest.md; skipped`, exit 0. No tool change. Fix the *wording* in manifest §2 (A4) so the evidence does not claim `--all` printed it. |
| **F2** | `--strict` upgrades exactly the F3 four; `B2-path-spelling` stays WARN while the paired `B3-path-spelling` fails | **Accept, record-only.** `STRICT_UPGRADE_CODES` matches RW-1 §2 F3 verbatim; my strict run confirms it. A bare `B2-path-spelling` without a B3 partner is a correctly listed file plus a redundant wrong spelling — not an integrity gap. |
| **F3** | `manifest.md:55` says HO-013 has 2 warnings; `check-all.txt:328` says `0 warnings` | **Require correction, but only inside the evidence refresh — not as a standalone edit now.** The manifest is a hashed artifact; hand-editing it today would break the QAQC-verified 18/18 chain for a warning-count typo and force a re-gate with no tool change. Because A1/A2 already require a rework and a refreshed bundle, correct §3 to `0` (and the §2 DEC-039 wording) in that same pass, regenerate `hashes.txt`, and re-verify 18/18 + self-bundle PASS. If the architect were to override the tool findings and sign off without rework, F3 would be a carried Minor per the DEC-030 precedent, not a gate. It is not acceptable as a permanent contradiction *after* a refresh. |

**`--all` exit 1 is correct behaviour, not a defect.** `HO-STRATA-011/artifacts/cmd-8.err.txt` (0 bytes) and `cmd-8.out.txt` (2529 bytes) exist, `HO-STRATA-011/manifest.md:23` records command 8 writing them, and `HO-STRATA-011/hashes.txt` omits both. The tool must not be tuned green; the bundle is signed and HO-013 §2 forbids editing it. The project should **carry** this as a tracked finding (DEC-030 “carried, not waived” style), not suppress it. A future supersession of the HO-011 bundle is the only legitimate repair.

---

## 4. Findings / rework

| # | Severity | Finding | Required action | Owner |
|---|---|---|---|---|
| **A1** | **Blocker** | `B3-hash-coverage` exempts any file whose path `endswith("hashes.txt")` (`check_bundle.py:408`), not just the bundle's own `hashes.txt`. Probe 2: an unlisted `artifacts/notes-hashes.txt` → `RESULT: PASS`, normal **and** `--strict`. Violates B3 and the guard rail “do not make a check pass by weakening it”. | Compare the bundle-relative path exactly with the bundle's own `hashes.txt` (e.g. `current == bundle_dir / "hashes.txt"`); add a fixture that creates an unlisted `*hashes.txt` artifact and asserts `FAIL B3-unlisted` in both modes. | Coder |
| **A2** | **Blocker** | `B6-pins` silently skips every pin row whose `Command` cell is not exactly `git show <hex>:<path> \| sha256sum` (`check_bundle.py:533`) and every row with no `Command` column. Probes 3/5/6: a **full 64-hex wrong digest** → `RESULT: PASS`; an **unresolvable commit** → `RESULT: PASS`. Contract B6 says rows that record a commit pin must resolve and a full digest must match. | Treat every row with a `Commit` + file/path as a pin: require the commit and `commit:path` to resolve; when the row records a full 64-hex digest (Digest column), compare it to `git show <commit>:<path> \| sha256sum` regardless of the Command phrasing; keep genuinely non-repo pins (tree/binary) informational **as a WARN**, never a silent skip. Add fixtures: nonstandard-command wrong digest → `FAIL B6-pins`; nonstandard-command unresolvable commit → `FAIL B6-pins`. | Coder |
| **A3** | Minor | Self-test constructs but does not assert two F4 sub-cases: `B2-external-unverifiable` and `B3-path-spelling` (the `absolute-external` and `basename-spelling` fixtures assert only the first code). | Add the two assertions in the same pass. | Coder |
| **A4** | Minor | `manifest.md` §3 line 55: HO-013 row says 2 warnings; authoritative `check-all.txt:328` says 0. §2 AC-2 also claims `DEC-039` is skipped **in `--all`**, which never includes it. | Correct both in the refresh; regenerate `hashes.txt`; re-verify 18/18 and self-bundle PASS; QAQC re-checks the delta. | Coder; QAQC re-check |
| **A5** | Minor | RW-1 §1.4 line 78 claims “the tool now exits 4 if `hashes.txt` contains an absolute path.” No exit 4 exists; B2 c/c′ intentionally accepts absolute external paths. | Correct the RW record; do **not** implement exit 4 (it would contradict B2). | Architect |
| **A6** | Minor | `commands.log` C2d/C9d write `artifacts/…` from repo-root cwd (wrong directory); C8/C10 elide the command body. The manifest §7 “commands are reproducible” claim is overstated. | Record exact commands/paths; include the C10 verification script in the refresh. | Coder |
| **A7** | Minor | AC-5's committed `git-status-before/after.txt` were captured on the dirty RW-1 assembly tree (`M`/`D`/`??` lines). They are raw and identical, so the claim holds, but a clean-tree capture is stronger. | Recapture on a clean tree in the refresh, or annotate the artifact. | Coder |
| **A8** | Minor | QAQC report says `sha256sum -c` is “17/17”; it verifies **18** entries (17 bundle files + the tool). | Correct the count in the QAQC report. | QAQC |
| **A9** | Carried | `--all` exits 1 on `HO-STRATA-011`'s two unlisted artifacts. Genuine; correct; must not be tuned. | Record as a carried finding; no bundle edit. | Architect |

QAQC F1 and F2 are accepted as record-only (§3). No Blocker/Major was found in the *evidence* itself: every claim reproduces and every hash verifies. The blockers are in the **delivered tool's contract**, not in the recorded run.

---

## 5. Verdict

- **REWORK (FAIL)** → `RW-HO-STRATA-013-2`. The evidence and claims pass; the tool does not yet meet its own B3/B6 contract, and the handoff exists precisely to stop “a check can be satisfied without doing the work.”
- The rework is bounded: two code fixes (A1, A2), two self-test assertions (A3), and an evidence refresh that also closes A4 and A6 (and optionally A7). No new checks, no new dependency, no bundle edits.

**Note on materialization.** The auditor's session constraint for this review is one written file (this report). The authoritative `RW-HO-STRATA-013-2` definition is embedded below; the architect/session must materialize `workflow/handoffs/RW-HO-STRATA-013-2.md` from it before the coder accepts. The reviewer named in it is this audit seat (Auditor, `opencode-go/deepseek-v4.1-flash`, WAIVER-001), with QAQC re-check after.

### Embedded rework definition — `RW-HO-STRATA-013-2`

| Field | Value |
|---|---|
| **ID / Type** | `RW-HO-STRATA-013-2` / `REWORK` |
| **From → To** | Auditor (`opencode-go/deepseek-v4.1-flash`, WAIVER-001) → Primary Coder |
| **Original** | `workflow/handoffs/HO-STRATA-013.md` @ `0b3ad61` (with `RW-HO-STRATA-013-1.md`) |
| **Failed criteria** | B3 `B3-hash-coverage` (A1), B6 `B6-pins` (A2); evidence/self-test gaps A3, A4, A6 |
| **Exact evidence** | A1: `check_bundle.py:408`; probe 2 output `RESULT: PASS (10 checks, 0 warnings)` with unlisted `artifacts/notes-hashes.txt`, identical under `--strict`. A2: `check_bundle.py:533`; probes 3/5/6 `RESULT: PASS` with a full wrong pin digest / unresolvable commit; control probe 4 `FAIL B6-pins digest mismatch`. A3: `check_bundle.py:964-984` and `1003-1014` assert only one code each. A4: `manifest.md:55` vs `check-all.txt:328`. A6: `commands.log:48,53,66,71`. |
| **Required fix** | A1: exempt only the bundle's own `hashes.txt`. A2: verify every commit-pin row; full 64-hex digest must match `git show <commit>:<path> \| sha256sum`; unresolvable commit/path FAILs; non-repo pins are WARN, never silent. A3: add the two assertions. A4/A6: correct the manifest and command log in the refreshed bundle. |
| **Guard rails** | Fix only A1–A4/A6; no new checks, no new dependency (stdlib only), no network; do **not** edit any `workflow/evidence/HO-*` bundle other than HO-013; do not tune the tool green on HO-011; no `DECISIONS.md`/`STATUS.md`/`.opencode`/`.github` edits; branch `wp/strata-013-check-bundle` only; no merge. |
| **Evidence required** | New fixtures for A1/A2/A3; `--self-test` exit 0 with the expanded fixture set; `--all` still exit 1 with **exactly** the two HO-011 `B3-unlisted` FAILs and zero elsewhere; `--all --strict` unchanged in intent; self-bundle `RESULT: PASS`; `sha256sum -c` 18/18 on the refreshed bundle; clean-tree `git status`; corrected `manifest.md` §3 and §2; exact `commands.log`. Raw outputs, no curation (DEC-030 B-1). |
| **Re-check** | Auditor (this seat), then QAQC (`opencode-go/gemini-4-argon`). A second failure on B3 or B6 escalates to the architect per `HANDOFF_CONTRACT.md` §9. |

---

## 6. Owner-task oversight

- Owner task: none specific to HO-013. This is enabling tooling for `OT-STRATA-001`; **checkpoint 4 (DeepSeek baseline) is unaffected** — no model/engine claim is made here.
- Checkpoints met: not applicable to this handoff.
- Owner acceptance: not recorded; the architect signs, not the auditor.

---

## 7. Statement

I did not modify code, tests, docs, configuration, evidence, handoffs, `DECISIONS.md`, `STATUS.md`, `.opencode/**`, or `.github/**`. I did not touch the Strata checkout or `build-hip/` (Strata clean at `bac859ef9`; binary `d58ee239…` unchanged). My only write is this report; scratch probes are under `/tmp/opencode/`. I did not merge or approve the release. My seat is `opencode-go/deepseek-v4.1-flash`, sharing the architect's family under **WAIVER-001** — reported as a documented exception, not a model-separation PASS.

---

### AUDITOR_TO_ARCHITECT (embedded per DEC-018)

| Field | Value |
|---|---|
| **Type** | `AUDITOR_TO_ARCHITECT` |
| **From → To** | Auditor (`opencode-go/deepseek-v4.1-flash`, WAIVER-001) → Architect |
| **Handoff** | HO-STRATA-013 (with RW-1 and QAQC report) |
| **State** | `AUDIT_REVIEW` → **`REWORK`** |
| **Report** | `workflow/reports/audit/HO-STRATA-013-audit.md` |
| **Evidence** | `workflow/evidence/HO-STRATA-013/` — 18/18 hashes OK at `0b3ad61`; self-bundle `RESULT: PASS (29 checks, 0 warnings)` |
| **Verdict** | **REWORK (FAIL)** — evidence and ACs reproduce; tool contract B3/B6 violated |
| **Blocking** | A1 `B3` exempts every `*hashes.txt` (unlisted artifact passes, even strict); A2 `B6` silently skips nonstandard pin rows (wrong full digest and unresolvable commit both PASS) |
| **Minor** | A3 self-test assertions; A4 manifest §3/§2; A5 RW “exit 4” claim; A6 command reproducibility; A7 dirty-tree AC-5 snapshot; A8 QAQC 17/18 count |
| **Carried** | A9 `--all` red on HO-011 (correct; track, do not tune) |
| **Rework** | `RW-HO-STRATA-013-2`, definition in §5; materialize the file, then coder → Auditor → QAQC |
| **Next** | Architect creates `RW-HO-STRATA-013-2.md` from §5 and sends it to the coder; no `ARCHITECT_APPROVAL` until the refreshed evidence passes this audit seat and QAQC |
