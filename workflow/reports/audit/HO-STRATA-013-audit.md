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

---

> **Round 2 (final-state re-audit) is in §8 below.** Round 1 above is kept as
> written; its verdict applied to `0b3ad61` and is superseded. The governing
> verdict for `9b85e33` is **REWORK** — read §8.

## 8. Round 2 — re-audit of the final state (2026-11-23)

| Field | Value |
|---|---|
| **Handoff** | HO-STRATA-013, rework `RW-HO-STRATA-013-2`, QAQC report round 2 |
| **Reviewer seat** | Auditor, runtime model `opencode-go/deepseek-v4.1-flash` (family `deepseek`). The architect seat is `opencode-go/deepseek-v4-pro#max` — **same family under WAIVER-001**. DEC-006 requires different base families; this is a documented exception, **not a model-separation PASS**, and I do not treat it as one. |
| **Date (UTC)** | 2026-11-23 |
| **Verdict** | **REWORK (FAIL)** → `RW-HO-STRATA-013-3` (definition in §8.10) |
| **State** | `AUDIT_REVIEW` → **`REWORK`** |
| **Tree audited** | `wp/strata-013-check-bundle` @ `9b85e33` (`9b85e33db1c228bcb0845c65508a53e8a2a88ccd`), base `91eac12`; `git status --porcelain` empty before and after every probe |
| **Evidence reviewed** | `workflow/evidence/HO-STRATA-013/` (19 hashed entries + `hashes.txt`) at `9b85e33`, not the `0b3ad61` bundle round 1 saw |
| **QAQC** | `workflow/reports/qaqc/HO-STRATA-013-qaqc.md` (round 2, `opencode-go/gemini-4-argon`, PASS at `429ad4d`) |
| **Profile (one only)** | Host tooling: Linux Mint 22.3, kernel `7.0.0-42-generic`, Python `3.14.10`, git `2.43.0`. No GPU, model, quant, engine, or dataset is invoked or claimed. |
| **Scratch** | `/tmp/opencode/audit-r2/` (probe repos, `probes.py`, a clone of the branch). Nothing in the repo was modified by the probes. |

### 8.1 Delta since round 1 — what is actually different

```text
$ git log --oneline 0b3ad61..HEAD
9b85e33 HO-STRATA-013: AUDIT_REVIEW — QAQC round 2 PASS, F3 fixed, final artifacts
76892c2 HO-STRATA-013: QAQC round 2 PASS; fix its F3 (stale strict capture)
429ad4d HO-STRATA-013: RW-2 — rehash over the corrected C12 log entry
0ebcd0a HO-STRATA-013: RW-2 manifest wording fix and rehash
07ec82e HO-STRATA-013: RW-2 handoff closure — state CODER_DONE, log entries
... (RW-2 implementation commits)

$ git diff 429ad4d..HEAD --stat          # the post-QAQC changes only
 .../HO-STRATA-013/artifacts/check-all-strict.txt   |   8 +-
 workflow/evidence/HO-STRATA-013/commands.log       |   5 +
 workflow/evidence/HO-STRATA-013/hashes.txt         |   4 +-
 workflow/handoffs/HO-STRATA-013.md                 |  23 ++
 workflow/reports/qaqc/HO-STRATA-013-qaqc.md        | 352 ++++++++++++-------
 5 files changed, 266 insertions(+), 126 deletions(-)
```

The tool itself did not change after `429ad4d` (`git diff 429ad4d..HEAD --
workflow/tools/check_bundle.py` is empty), so QAQC's behavioural PASS on the
tool still applies to the audited tip. The post-QAQC change is evidence-only,
which is what makes the process ruling in §8.8 possible — and also what makes
the defects in §8.5 checkable.

The RW-2 fix itself is the minimal, correct change (verified in the diff
`2800d64..HEAD`): `fpath == own_hashes` replaces `fpath.endswith("hashes.txt")`
at `check_bundle.py:409`; the `git show … | sha256sum` gate at `:~533` is gone,
every parsed row is now verified, and non-path rows emit
`WARN B6-pins not a path pin`. Three fixtures were added; the strict variant
was generalised to `STRICT_FIXTURES`. No new check, no new dependency, no
unrelated refactor.

### 8.2 A1 — is the B3 suffix bypass closed?

Probes built from scratch in `/tmp/opencode/audit-r2/probes/` (throwaway git
repo, `bundle/{manifest.md,commands.log,artifact.txt,hashes.txt}`, one extra
unlisted file committed), then `python3 workflow/tools/check_bundle.py [--strict] bundle`.

| Probe (unlisted file) | Default | `--strict` |
|---|---|---|
| `artifacts/notes-hashes.txt` (the round-1 probe) | `FAIL B3-unlisted bundle/artifacts/notes-hashes.txt`; `RESULT: FAIL (12 checks, 0 warnings)`; exit 1 | identical, exit 1 |
| `my-hashes.txt` (variant) | `FAIL B3-unlisted bundle/my-hashes.txt`; exit 1 | identical, exit 1 |
| `artifacts/hashes.txt` (variant: a *different* file literally named `hashes.txt`) | `FAIL B3-unlisted bundle/artifacts/hashes.txt`; exit 1 | identical, exit 1 |
| `hashes.txt.bak` (variant) | `FAIL B3-unlisted bundle/hashes.txt.bak`; exit 1 | identical, exit 1 |
| **control:** clean bundle, own `hashes.txt` unlisted | `PASS B3-hash-coverage all files listed`; `RESULT: PASS (12 checks, 0 warnings)` | `RESULT: PASS`, exit 0 |

**A1: FIXED.** The exemption is now an exact repo-relative comparison with the
bundle's own `hashes.txt`, so it neither over- nor under-exempts. The nested
`artifacts/hashes.txt` case — the one a suffix test would still miss — is
caught, which is the strongest available confirmation.

### 8.3 A2 — is the B6 silent skip closed?

Same fixture pattern: a committed `pinned.txt`/`artifact.txt` plus a
`hashes-notes.txt` `## Commit pins` table, varying only the Command spelling
and the digest.

| Probe | Row shape | Observed | Required | Verdict |
|---|---|---|---|---|
| A2-a | full 64-hex **wrong** digest; Command `git cat-file -p <sha>:bundle/artifact.txt \| sha256sum` | exit 1; `FAIL B6-pins bundle/artifact.txt (recorded 000…000, actual 6667b2d1…)` | `FAIL B6-pins` | **PASS** |
| A2-b | commit `deadbeef`; Command `git show deadbeef:… \| sha256sum` | exit 1; `FAIL B6-pins unresolvable commit 'deadbeef' for bundle/artifact.txt` | `FAIL B6-pins` | **PASS** |
| A2-c | **correct** digest; reworded `git cat-file -p` Command | exit 0; `PASS B6-pins pin ok: 7bc5db8b…:bundle/artifact.txt`; `RESULT: PASS (14 checks, 0 warnings)` | `PASS` | **PASS** (control) |
| A2-d | tree pin: `File / tree = Strata source tree`, `Commit = —` | exit 0; `WARN B6-pins not a path pin`; `RESULT: PASS (14 checks, 1 warnings)` | `WARN`, never silent | **PASS** |
| A2-e | **no Command column at all**, full wrong digest | exit 1; `FAIL B6-pins bundle/artifact.txt (recorded 000…, actual 6667b2d1…)` | `FAIL B6-pins` | **PASS** (round-1 probe 5 is closed) |
| **A2-f** (my variant) | `File = bundle/pinned.txt`, `Commit = <sha>`, Command `git show <sha>:bundle/other.txt \| sha256sum`, digest = **other.txt's** | exit 0; `PASS B6-pins pin ok: b7d8f2ea…:bundle/other.txt`; `RESULT: PASS (15 checks, 0 warnings)` | the File column's `commit:path` and digest must decide | **FAIL (R2-4)** |
| **A2-g** (same variant, other digest) | same row, digest = **pinned.txt's** (the row is correct for its `File` column) | exit 1; `FAIL B6-pins bundle/other.txt (recorded c3d3c29e…, actual 960e611b…)` | `PASS` | **FAIL (R2-4)**, a false FAIL |

**A2: the specified cases are fixed; one residual bypass remains.** The Command
column is supposed to be documentation (`RW-HO-STRATA-013-2.md` §1: "The
Command column becomes documentation. Do not parse it for gating."), but
`_parse_commit_pins_table` still prefers a `git show <hex>:<path>` found in the
Command cell over the `Commit`/`File` columns
(`check_bundle.py:653-661`). A row can therefore declare
`File = pinned.txt` while the verified path is `other.txt`; A2-f passes a row
whose declared file's digest was never checked, and A2-g fails a row that is
correct in its columns. No signed bundle is affected today (only HO-012 and
HO-013 have pin tables, and both have Command path == File in every row — I
checked every row), so this is latent, but it is the same defect class A2 was
opened for, reached through a different cell. QAQC saw the mechanism and
graded it "None" (F2); with A2-f/A2-g in hand it is a real contract deviation,
not merely a note.

### 8.4 Fixed points, hashes, and the empty-file question

On the clean committed tree (`9b85e33`, `git status` empty before and after):

```text
$ python3 workflow/tools/check_bundle.py --all > /tmp/opencode/audit-r2/final/all.txt        # exit 1
$ python3 workflow/tools/check_bundle.py --all --strict > /tmp/…/all-strict.txt             # exit 1
$ diff -u workflow/evidence/HO-STRATA-013/artifacts/check-all.txt        /tmp/…/all.txt        # exit 0 (identical)
$ diff -u workflow/evidence/HO-STRATA-013/artifacts/check-all-strict.txt /tmp/…/all-strict.txt  # exit 0 (identical)
$ sha256sum workflow/evidence/HO-STRATA-013/artifacts/check-all.txt /tmp/…/all.txt
e0063b4edebc3a843b0592cb7a63ba12e6989973f5828706adf7421033b7a0bb  …/check-all.txt
e0063b4edebc3a843b0592cb7a63ba12e6989973f5828706adf7421033b7a0bb  /tmp/…/all.txt
$ sha256sum workflow/evidence/HO-STRATA-013/artifacts/check-all-strict.txt /tmp/…/all-strict.txt
b25abcd142527e801b34ac4bac80d7049df283a697053a6df182cbaa399d665b  …/check-all-strict.txt
b25abcd142527e801b34ac4bac80d7049df283a697053a6df182cbaa399d665b  /tmp/…/all-strict.txt
$ git status --porcelain | wc -l
0
```

Both aggregate artifacts are **fixed points**, including the recaptured strict
file (the value QAQC recorded as `e0063b4e…` mismatch is now the accepted
`check-all.txt` digest, and the strict block shows `HO-STRATA-013: RESULT: PASS
(30 checks, 0 warnings)`). The `--all` baseline is unchanged from round 1:
exactly two `B3-unlisted` FAILs, both HO-STRATA-011:

```text
$ grep -n "^FAIL " /tmp/opencode/audit-r2/final/all.txt
266:FAIL B3-unlisted workflow/evidence/HO-STRATA-011/artifacts/cmd-8.err.txt
267:FAIL B3-unlisted workflow/evidence/HO-STRATA-011/artifacts/cmd-8.out.txt
$ grep "^FAIL " …/all-strict.txt | awk '{print $2}' | sort | uniq -c
      8 B2-external
     32 B2-legacy-path
      3 B2-prose
     48 B3-path-spelling
      2 B3-unlisted
```

`hashes.txt` is repo-relative, 19 entries (3 comment lines + 19 digests), no
`/home/`, and `sha256sum -c` is clean:

```text
$ sha256sum -c workflow/evidence/HO-STRATA-013/hashes.txt   # exit 0
19/19 entries OK, exit 0
$ grep -n '/home/' workflow/evidence/HO-STRATA-013/hashes.txt
none
```

**Empty-file digest — one, explained, benign but ambiguous (R2-5).** The
re-audit check "no `e3b0c442…`" now fails literally:

```text
$ grep -n 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855' workflow/evidence/HO-STRATA-013/hashes.txt
12:e3b0c442…  workflow/evidence/HO-STRATA-013/artifacts/git-status-diff.txt
```

`artifacts/git-status-diff.txt` is 0 bytes because C5 diffs two identical
status snapshots. That is a legitimate empty output, not the RW-1 capture bug
(the digest of an empty file is correctly the empty-string digest). It is still
a bad signal in a bundle whose history contains an empty-hash incident:
`diff … > file` and a failed capture are indistinguishable at a glance. The
fix is one line (`[ -s file ] || echo 'IDENTICAL (no status change)' > file`, as
`deterministic.txt` already does) or a manifest sentence. Minor, non-blocking.

### 8.5 Evidence reproducibility — where the rework is not finished

**R2-1 (Blocker). The three capture commands cannot produce their artifacts.**
C2d, C9d and C9e are all written as `<tool> … > /tmp/x && mv /tmp/x <artifact>`.
The tool exits **1** when a bundle FAILs, and the log records `exit: 1` for each
of them, so `&&` short-circuits and `mv` never runs. Run verbatim in a clean
clone of the audited tip:

```text
$ cd /tmp/opencode/audit-r2/clone   # clone of wp/strata-013-check-bundle @ 9b85e33
$ sha256sum workflow/evidence/HO-STRATA-013/artifacts/check-all.txt        # before: e0063b4e…
$ python3 workflow/tools/check_bundle.py --all > /tmp/check-all.txt && mv /tmp/check-all.txt workflow/evidence/HO-STRATA-013/artifacts/check-all.txt
$ echo $?
1
$ sha256sum workflow/evidence/HO-STRATA-013/artifacts/check-all.txt        # after:  e0063b4e…  (UNCHANGED)
$ ls -l /tmp/check-all.txt
-rw-r--r-- 1 kupipi kupipi 21755 … /tmp/check-all.txt          # output left in /tmp; mv skipped
$ git status --porcelain
(empty)                                                        # looks like nothing happened

# same result for C9d (/tmp/check-all-strict.txt, 21752 bytes left behind, exit 1)
# same result for C9e (/tmp/cas.txt, 21752 bytes left behind, exit 1)
```

The command as logged, run by a reviewer, leaves the tree clean, the exit code
at 1, and the output in `/tmp` — indistinguishable from "the artifact was
already correct". That is exactly the trap that let QAQC's F3 stale capture
survive: the artifact is only correct because someone moved it by hand, not
because the logged command did. The artifact contents reproduce (I copied
`/tmp/check-all.txt` over a scratch copy and diffed: identical), so this is a
defect in the **log**, not a fabricated artifact — but `HANDOFF_CONTRACT.md` §7
makes copy-paste reproducibility a MUST, and RW-2 F3 (the criterion this rework
was opened to fix) explicitly required every entry to record the exact
command. C2d/C9d carried this from round 1; C9e **introduced** it in the
post-QAQC fix. Blocking.

**R2-2 (Blocker). `test-output.txt` still embeds the pre-fix strict run and
contradicts the final artifact.** `test-output.txt` (last touched at `9be15de`,
untouched by the F3 fix) contains a `=== C9d … --all --strict ===` section whose
`HO-STRATA-013` block is the stale one:

```text
$ python3 … extract the C9d section from test-output.txt; diff against artifacts/check-all-strict.txt
 FAIL B2-hash-mismatch …/artifacts/check-all.txt (actual: e0063b4e…)
 FAIL B3-path-spelling …/artifacts/check-all.txt
 FAIL B4-tracked git status not clean for bundle
-HO-STRATA-013: RESULT: PASS (30 checks, 0 warnings)
+HO-STRATA-013: RESULT: FAIL (30 checks, 0 warnings)
(8 changed lines; the six other command sections I compared are byte-identical to their artifacts)
```

QAQC F3 was "a stale strict capture". The architect recaptured
`artifacts/check-all-strict.txt` and rehashed, but did not regenerate the
aggregate transcript, so the bundle now contains two mutually contradictory
records of the same run, and `manifest.md` §5 does not mention it. The
EVIDENCE_MANIFEST requirement is that `test-output.txt` is the raw output;
a reader diffing it against the artifact sees a FAIL that the project says is a
PASS. Blocking.

**R2-3 (Blocker). Claims in `manifest.md` that no artifact supports.**

- §3: "The authoritative aggregate capture (`C2d`) was taken from a **clean
  tree** …". `artifacts/git-status-before.txt` (the C5 snapshot from the same
  refresh session) lists eight modified paths, including
  `workflow/tools/check_bundle.py` and `workflow/handoffs/RW-HO-STRATA-013-1.md`:

  ```text
   M workflow/evidence/HO-STRATA-013/artifacts/check-all-strict.txt
   M workflow/evidence/HO-STRATA-013/artifacts/check-all.txt
   … (8 lines)
  ```

  The tool was already modified at C2d (C2d exercised the RW-2 code) and no
  commit occurs between C2d and C5, so the session was dirty throughout. The
  **substance** is fine — I verified both artifacts are fixed points on the
  clean tip (§8.4) — but the sentence is a claim the bundle's own artifact
  contradicts. This is round 1's A7, still open and now stated more strongly.
- §1 is headed "Command (copy-paste)" but C5 and C8 write
  `> artifacts/git-status-diff.txt` / `> artifacts/deterministic.txt` from the
  **repo root** — i.e. `<repo>/artifacts/…`, not the bundle (the `commands.log`
  entries are correct; the manifest's copies are not). `C9e` — the command that
  actually produced the audited strict artifact — is missing from §1 entirely,
  while `C9d` is still labelled "authoritative strict capture". C10/C11/C12 are
  elided with `...` in that same "copy-paste" column, which contradicts §2
  RW-2 F3's "no `...` elisions" and §7's "Commands are reproducible".
- The A7 capture is not annotated anywhere: §2 AC-5 says "no diff between
  before/after status" (true) and nothing records that the snapshot was taken
  on a dirty tree.

**Verified reproducible (not findings):** `commands.log` has no `...`; C10,
C11 and C12 are recorded as complete heredocs; the logged C12 block reproduces
`hashes.txt` byte for byte from the clean tip:

```text
$ python3 /tmp/opencode/audit-r2/c12.py > /tmp/opencode/audit-r2/hashes-regen.txt
$ diff -u workflow/evidence/HO-STRATA-013/hashes.txt /tmp/opencode/audit-r2/hashes-regen.txt
(exit 0)
$ sha256sum workflow/evidence/HO-STRATA-013/hashes.txt /tmp/opencode/audit-r2/hashes-regen.txt
e232ea8658a8373c1f09d459c502cce6f0f51a6d2375912345bf62ee9bcc8a14  (both)
```

### 8.6 Regression, stdlib, determinism

| Check | Command | Observed |
|---|---|---|
| AC-1 | `… workflow/evidence/HO-STRATA-012` | exit 0; `RESULT: PASS (25 checks, 6 warnings)`; byte-identical to `artifacts/check-ho012.txt` |
| AC-2 | `… --all` | exit 1; `RESULT: FAIL (317 checks, 114 warnings)`; exactly 2 FAILs, both HO-011; identical to `artifacts/check-all.txt` |
| AC-2 strict | `… --all --strict` | exit 1; `RESULT: FAIL (317 checks, 23 warnings)`; upgrades only `B2-legacy-path`/`B2-external`/`B2-prose`/`B3-path-spelling`; identical to the artifact |
| AC-3 | `… --self-test` | exit 0; 15 fixture lines `PASS` (`hash-edited … pin-unresolvable-commit-reworded`); `RESULT: PASS (all fixtures behaved as expected)`; identical to `artifacts/self-test.txt` |
| AC-4 | `python3 -I … --self-test` | exit 0; 15/15; identical to `artifacts/stdlib-isolated.txt` |
| AC-4 | imports / network | `__future__, argparse, hashlib, json, os, re, shutil, subprocess, sys, tempfile, pathlib, typing`; `grep -E 'socket|urllib|requests|http|urlopen'` → none |
| AC-8 | two text runs, two `--json` runs | text byte-identical; JSON byte-identical; no `/home/`, no timestamps |

A3 from round 1 (the `absolute-external` fixture still asserts only
`B2-external` and not `B2-external-unverifiable`; `basename-spelling` asserts
only `B2-path-spelling`) was **not** in RW-2's scope list and remains open as a
carried Minor (R2-6). The pipeline is unchanged: `--all` is red only on the
signed HO-011 bundle, which must not be edited (R2-9).

### 8.7 Scope and guard rails

```text
$ git diff 91eac12..HEAD --stat
 27 files changed, 4782 insertions(+), 0 deletions(-)
 (workflow/tools/check_bundle.py, workflow/README.md, HO-013 evidence,
  HO-013/RW-1/RW-2 handoffs, QAQC + audit reports only)

$ git diff --name-only 91eac12..HEAD | grep -vE '^(workflow/tools/check_bundle\.py|workflow/README\.md|workflow/handoffs/|workflow/reports/|workflow/evidence/HO-STRATA-013/)'
none
$ git diff --name-only 91eac12..HEAD -- workflow/DECISIONS.md workflow/STATUS.md .opencode .github
(empty)
$ git diff --name-only 91eac12..HEAD -- workflow/evidence | grep -v '^workflow/evidence/HO-STRATA-013/'
none
$ git -C /home/kupipi/Documents/git/strata status --porcelain ; git -C … rev-parse --short HEAD
(empty) bac859ef9
$ sha256sum /home/kupipi/Documents/git/strata/build-hip/strata
d58ee2398596d1a100c15d5b9459e24bd86854cb5e5fb7ce88dbc6c7ed9f5858
```

No dependency (stdlib only), no secret (`ghp_`/`github_pat_`/`sk-`/`AKIA`/
`xox…`/`PRIVATE KEY` appear only as the tool's detection regex and its fixture
string), no `.opencode/**`/`.github/**`/`DECISIONS.md`/`STATUS.md` change, no
other bundle touched, Strata checkout and signed binary unchanged. `git status`
was empty before my probes and empty after them.

### 8.8 Ruling on the post-QAQC F3 fix (architect, `76892c2`)

**The mechanism is acceptable; this execution of it is not.**

Acceptable, and not a break in the review chain:

1. It is evidence-only. The tool hash is unchanged (`git diff 429ad4d..HEAD --
   workflow/tools/check_bundle.py` empty), so QAQC's behavioural PASS at
   `429ad4d` still covers the code that will be signed.
2. It regenerates a deterministic artifact from the committed tree and rehashes
   with the same logged, reproducible C12 block — verified byte-identical here
   (§8.5), not merely asserted.
3. It is recorded in `commands.log` (C9e) and handoff §15, so the change is
   visible to the next reviewer.
4. The QAQC → audit order means the auditor reviews the final state anyway; a
   documented evidence-only repair between the two gates is exactly what the
   audit gate exists to legitimise, provided the auditor re-derives the
   evidence rather than trusting the architect's summary. I re-derived it.

Not acceptable, and why the verdict is REWORK rather than PASS:

1. The repair is **incomplete**: it fixed `check-all-strict.txt` but left the
   superseded strict run inside `test-output.txt` (R2-2), so the bundle
   contradicts itself.
2. The repair is **not reproducible as recorded**: C9e's `&& mv` cannot run
   after exit 1 (R2-1). The artifact is right; the audit trail is not.
3. It **adds a claim its artifacts contradict**: "taken from a clean tree"
   (R2-3).
4. The same commit rewrote `workflow/reports/qaqc/HO-STRATA-013-qaqc.md`
   (352 lines changed) in the architect's commit. The workflow reserves that
   directory for QAQC (`ENGINEERING_WORKFLOW.md` §4). I found no fabricated
   QAQC claim — everything I could re-run matched — so I treat this as
   materialisation of QAQC's report (DEC-018-style), not tampering, but the
   provenance is unattested and should be noted (R2-8, Minor).

Precedent for the architect: a post-review fix is legitimate when it is
evidence-only, reproducible, complete (every file that embeds the superseded
output is regenerated), and recorded. Three of four failed here. If the
architect decides instead to sign without a third round, that decision must be
recorded in `DECISIONS.md` with these three defects carried explicitly — but I
cannot recommend it: the bundle would certify a transcript that disagrees with
its own artifact.

### 8.9 Findings

| # | Severity | Finding | Evidence | Blocking | Owner |
|---|---|---|---|---|---|
| **R2-1** | **Blocker** | C2d/C9d/C9e use `<tool> … && mv …`; the tool exits 1, so `mv` never runs. The logged command cannot produce the artifact; output stays in `/tmp`, `git status` stays clean. F3 is therefore not met, and C9e introduced the defect in the F3 fix. | clean clone `@9b85e33`: artifact sha unchanged after running C2d verbatim; `/tmp/check-all.txt` (21755 B) and `/tmp/cas.txt` (21752 B) left behind; exit 1 | **Yes** | Coder |
| **R2-2** | **Blocker** | `test-output.txt` embeds the pre-C9e strict run in which `HO-STRATA-013` FAILs (`B2-hash-mismatch`, `B3-path-spelling`, `B4-tracked`), contradicting `artifacts/check-all-strict.txt` (`PASS (30 checks, 0 warnings)`). File untouched since `9be15de`. | 8-line diff between the C9d section and the artifact; no manifest note | **Yes** | Architect/Coder |
| **R2-3** | **Blocker** | `manifest.md` §3 claims the C2d capture came from a "clean tree"; `git-status-before/after.txt` (same session) list 8 modified paths including the tool. §1's "copy-paste" column writes C5/C8 outputs to `<repo>/artifacts/…` (wrong directory), omits C9e, and elides C10–C12 with `...` while §2 F3 claims "no `...` elisions". | `git-status-before.txt`; `manifest.md:23,26,27-29,30,46,52` | **Yes** | Coder (manifest) |
| **R2-4** | **Blocker (latent)** | `B6-pins` still prefers a `git show <hex>:<path>` found in the Command cell over the `Commit`/`File` columns. A2-f passes a row whose declared `File` digest was never checked; A2-g falsely FAILs a row that is correct in its columns. Contradicts RW-2 A2 ("The Command column becomes documentation. Do not parse it for gating"). No signed bundle currently has divergent cells (HO-012/HO-013 checked row by row). | probe A2-f `RESULT: PASS (15 checks, 0 warnings)`, `pin ok: …:bundle/other.txt`; A2-g `FAIL B6-pins bundle/other.txt`; `check_bundle.py:653-661` | **Yes** (tool contract; second-round A2 issue — escalated per §9) | Coder |
| **R2-5** | Minor | `artifacts/git-status-diff.txt` is 0 bytes, so `hashes.txt` carries the empty-string digest `e3b0c442…`. Legitimate (C5 diff of identical snapshots) but indistinguishable from a failed capture in a bundle with that history. | `hashes.txt:12`; `wc -c` = 0 | No | Coder (one-line marker) or manifest note |
| **R2-6** | Minor (carried) | Round-1 A3 still open: `absolute-external` asserts only `B2-external`, not `B2-external-unverifiable`; `basename-spelling` asserts only `B2-path-spelling`. A regression in either branch would not fail the self-test. | `FIXTURES` table; `fixture_absolute_external`, `fixture_basename_spelling` | No | Architect to schedule |
| **R2-7** | Minor | `RW-HO-STRATA-013-1.md:78` now blames "the evidence-generation script … exits 4 if `hashes.txt` contains an absolute path". No such script or behaviour exists in the repo (the captures are inline heredocs; the tool's exits are 0/1/2). The attribution moved; the claim is still unsupported. | `grep -rn 'exit 4' workflow/` → only the audit/RW/QAQC prose | No | Architect |
| **R2-8** | Minor (process) | The QAQC round-2 report was written into the repo by the architect's commit `76892c2`, not by QAQC; the workflow gives `workflow/reports/qaqc/` to QAQC only. Content re-verified independently; no false QAQC claim found. | `git show --name-only 76892c2`; 352-line diff | No | Architect (record the materialisation) |
| **R2-9** | Carried | `--all` exits 1 on HO-STRATA-011's two unlisted artifacts. Correct; must not be tuned; only a bundle supersession repairs it. | `grep -n '^FAIL '` → 2 lines | No | Architect |

No blocker was found in A1, and no blocker in the specified A2 rows: the RW-2
fixes are real and I reproduced them. The blockers are in the **evidence trail
around** the fix (R2-1–R2-3) and in the one B6 cell the fix still trusts
(R2-4).

### 8.10 Verdict and `RW-HO-STRATA-013-3`

**REWORK (FAIL).** The tool's two audited bypasses are closed; the final
artifacts are fixed points; hashes and C12 verify. But the evidence bundle is
not internally consistent (R2-2), its capture commands do not reproduce their
artifacts (R2-1), one manifest claim is contradicted by the bundle's own
artifact (R2-3), and B6 still lets a self-inconsistent pin row pass (R2-4).
Signing now would certify a bundle whose transcript disagrees with its artifact
and whose "authoritative capture" line does nothing.

Scope for `RW-HO-STRATA-013-3` (bounded; no new feature, no new dependency):

1. **R2-1** — rewrite C2d/C9d/C9e so the move runs on the recorded exit code
   (`> /tmp/x; [ $? -eq 1 ] && mv …`, or `… > /tmp/x || true; mv …`), re-run
   them, and record the real exit code of each line. Prove it by running the
   logged line verbatim in a clean clone and showing the artifact hash change
   (or that it is already the fixed point and the output file is consumed).
2. **R2-2** — regenerate `test-output.txt` from the final run **after** the
   strict recapture, so its C9d section matches the artifact; or drop the
   strict section from `test-output.txt` and say so in §5. Rehash.
3. **R2-3** — correct `manifest.md` §3 (no "clean tree" claim without an
   artifact; state that the AC-5 capture is a dirty-tree comparison, or
   recapture on a clean tree), fix §1's C5/C8 commands to the bundle path, add
   C9e, and either expand C10–C12 or stop claiming "no `...` elisions" for the
   manifest table.
4. **R2-4** — `_parse_commit_pins_table`: make `Commit` + `File`/`Path` columns
   authoritative; use the Command's `<sha>:<path>` only when the corresponding
   column is empty; when both are present and disagree, `FAIL B6-pins
   inconsistent pin row`. Add a fixture (divergent Command path → `FAIL`) and
   one (no Command column, correct digest → `PASS`) to the self-test. Re-run
   `--self-test` (16 fixtures), `--all`, the fixed points, and rehash.
5. **R2-5** (optional) — make the empty diff self-describing.
6. **Not in scope:** R2-6, R2-7, R2-8, R2-9 (architect/carried).

Evidence required: the same capture rules as RW-2 (`/tmp` then move, log after
the run, hashes last, clean-tree fixed point for both aggregate artifacts); a
verbatim re-run of C2d/C9d/C9e proving the artifact is written; `sha256sum -c`
clean; C12 byte-identical to `hashes.txt`; `--all` still exactly two HO-011
FAILs; `--self-test` and `-I` exit 0; `git status` empty; no bundle edit, no
protected path, no dependency.

**Re-check:** Auditor (this seat) first, then QAQC. R2-1 is a second failure on
F3 and R2-4 a second-round A2 deviation — per `HANDOFF_CONTRACT.md` §9 both are
escalated to the architect, who may decide to fix them in this rework (my
recommendation) or record a `DECISIONS.md` deferral with the risk accepted.
The auditor does not decide that, and does not sign.

### 8.11 Statement

I did not modify code, tests, docs, configuration, evidence, handoffs,
`workflow/DECISIONS.md`, `workflow/STATUS.md`, `.opencode/**`, or `.github/**`,
and I did not merge or approve the release. My only write is this report; all
probes ran on throwaway repos and a clone under `/tmp/opencode/audit-r2/`. The
Strata checkout was read only (`bac859ef9`, clean; binary `d58ee239…`). My seat
is `opencode-go/deepseek-v4.1-flash`, which shares a family with the architect
(`deepseek-v4-pro#max`) under **WAIVER-001**; that is a documented exception to
DEC-006 and **not** a model-separation PASS.

---

### AUDITOR_TO_ARCHITECT — Round 2 (supersedes the round-1 record above)

| Field | Value |
|---|---|
| **Type** | `AUDITOR_TO_ARCHITECT` |
| **From → To** | Auditor (`opencode-go/deepseek-v4.1-flash`, WAIVER-001 — family exception, not a PASS) → Architect |
| **Handoff** | HO-STRATA-013, `RW-HO-STRATA-013-2`, QAQC round 2 |
| **State** | `AUDIT_REVIEW` → **`REWORK`** |
| **Report** | `workflow/reports/audit/HO-STRATA-013-audit.md` §8 |
| **Evidence** | `workflow/evidence/HO-STRATA-013/` @ `9b85e33`: 19/19 hashes OK; C12 byte-identical; both aggregate artifacts reproduce byte for byte on the clean tip; `git status` empty |
| **Verdict** | **REWORK (FAIL)** — A1 fixed, the specified A2 rows fixed, artifacts sound; evidence trail and one B6 cell not |
| **Closed** | A1 (B3 exact `hashes.txt` exemption; 4 unlisted-name variants incl. nested `hashes.txt`, default and `--strict`); A2-a/b/c/d/e (wrong digest, `deadbeef`, control, non-path WARN, no-Command-column); 15/15 fixtures; fixed points; 19/19 + C12; scope/guard rails |
| **Blocking** | R2-1 C2d/C9d/C9e cannot write their artifacts (`&&` after exit 1) — proven in a clean clone; R2-2 `test-output.txt` embeds the pre-fix strict FAIL, contradicting the artifact; R2-3 manifest "clean tree" claim contradicted by `git-status-before.txt` + wrong/omitted §1 commands; R2-4 `B6-pins` still trusts the Command cell's path (A2-f passes, A2-g false-FAILs) |
| **Minor** | R2-5 empty `git-status-diff.txt` digest; R2-6 round-1 A3 assertions; R2-7 RW-1 "exit 4" sentence; R2-8 QAQC report materialised by the architect |
| **Carried** | R2-9 HO-011 red (correct; do not tune) |
| **Process ruling** | Post-QAQC evidence-only repair is acceptable in principle (tool unchanged, reproducible rehash, logged, auditor re-derives the final state); this execution is incomplete and non-reproducible, so it does not close the review |
| **Rework** | `RW-HO-STRATA-013-3`, definition in §8.10; materialise `workflow/handoffs/RW-HO-STRATA-013-3.md` (this seat writes only the audit report) |
| **Next** | Architect materialises RW-3 and decides the §9 escalation for R2-1/R2-4; coder fixes R2-1–R2-4 only; Auditor re-checks; QAQC after. No `ARCHITECT_APPROVAL` before that |

---

> **Round 3 (final-state re-audit after RW-3) is in §9 below.** Rounds 1–2 are
> kept as written; their verdicts applied to `0b3ad61` and `9b85e33` and are
> superseded. The governing verdict for `2541bec` is **PASS** — read §9.

## 9. Round 3 — re-audit after RW-3 (2026-11-23)

| Field | Value |
|---|---|
| **Handoff** | HO-STRATA-013, rework `RW-HO-STRATA-013-3`, QAQC report round 3 |
| **Reviewer seat** | Auditor, runtime model `opencode-go/deepseek-v4.1-flash` (family `deepseek`). The architect seat is `opencode-go/deepseek-v4-pro#max` — **same family under WAIVER-001**. DEC-006 requires different base families; this is a documented exception, **not** a model-separation PASS, and I do not treat it as one. |
| **Date (UTC)** | 2026-11-23 |
| **Verdict** | **PASS** → `ARCHITECT_APPROVAL` |
| **State** | `AUDIT_REVIEW` → **`ARCHITECT_APPROVAL`** (the architect signs or rejects; I do not) |
| **Tree audited** | `wp/strata-013-check-bundle` @ `2541becb11eefec8063ca37d23873d269c6eb54a`, base `91eac12`; `git status --porcelain` empty before and after every probe |
| **Evidence reviewed** | `workflow/evidence/HO-STRATA-013/` at `2541bec` — 21 entries, `sha256sum -c` **21/21 OK** (exit 0), no `/home/` |
| **QAQC** | `workflow/reports/qaqc/HO-STRATA-013-qaqc.md` (round 3, `opencode-go/gemini-4-argon`, PASS at `830b6bf`) |
| **Profile (one only)** | Host tooling: Linux Mint 22.3, kernel `7.0.0-42-generic`, Python `3.14.10`, git `2.43.0`. No GPU, model, quantization, engine, or dataset is invoked or claimed. |
| **Scratch** | `/tmp/opencode/audit-r3/` (two clones, R2-4 probe repo, re-derivations). Nothing in the repo was modified by me. |

### 9.1 Delta since round 2 and the frozen tool

```text
$ git log --oneline 9b85e33..HEAD
2541bec HO-STRATA-013: AUDIT_REVIEW — QAQC round 3 PASS, F1/F2 closed
fd4bb85 HO-STRATA-013: close QAQC round-3 findings F1/F2
830b6bf HO-STRATA-013: RW-3 closed — R2-1..R2-4 fixed, artifacts are fixed points
cc0eeeb HO-STRATA-013: RW-3 — convergence pass on the strict artifact (C21-C23)
d48466a HO-STRATA-013: RW-3 — clean-tree recapture, log, test-output and rehash (C17-C20)
c59a4db HO-STRATA-013: RW-3 — evidence refresh (coder), step cap at the recapture
e91d901 HO-STRATA-013: RW-3 — regenerate non-aggregate and aggregate artifacts
cad4c85 HO-STRATA-013: RW-3 — probes moved into committed scripts
679b774 HO-STRATA-013: RW-3 — B6 verifies the File column, not the Command cell
...

$ git log --oneline 9b85e33..HEAD -- workflow/tools/check_bundle.py
679b774 HO-STRATA-013: RW-3 — B6 verifies the File column, not the Command cell
$ git diff --stat 830b6bf..HEAD -- workflow/tools/check_bundle.py
(empty)
$ git diff --name-only 679b774..HEAD | grep -vE '^workflow/(evidence/HO-STRATA-013/|handoffs/|reports/)'
none
```

The tool that would be signed is byte-identical to the tool QAQC exercised at
`830b6bf`; every later change is evidence, handoff, or report. That is what
makes the architect's evidence-only completion (§9.8) checkable — and I
re-derived it rather than trusting the summary.

### 9.2 R2-1 — the logged capture command now writes its artifact (Blocker → **closed**)

C17 taken **verbatim** from `commands.log:133`:

```text
python3 workflow/tools/check_bundle.py --all > /tmp/ca.txt 2>&1; rc=$?; mv /tmp/ca.txt workflow/evidence/HO-STRATA-013/artifacts/check-all.txt
```

**Sentinel test** — fresh clone of the tip, sentinel written into the artifact:

```text
$ git clone --branch wp/strata-013-check-bundle . /tmp/opencode/audit-r3/clone   # HEAD 2541bec, status 0
$ echo "SENTINEL probe" > workflow/evidence/HO-STRATA-013/artifacts/check-all.txt
$ sha256sum …/check-all.txt
7448f1a9bfc820e9…                                    # the sentinel
$ rm -f /tmp/ca.txt; ls /tmp/ca.txt
ls: cannot access '/tmp/ca.txt': No such file or directory
$ <C17 verbatim>
$ echo $?                                            # line exit (mv is last)
0
$ sha256sum …/check-all.txt
beba38ed483db158c0d6602475bb159534b09d6ec000fea517f62b500eddfaa8
$ ls /tmp/ca.txt
ls: cannot access '/tmp/ca.txt': No such file or directory
$ git status --porcelain
 M workflow/evidence/HO-STRATA-013/artifacts/check-all.txt
$ tail -2 …/check-all.txt
HO-STRATA-013: RESULT: FAIL (32 checks, 1 warnings)

RESULT: FAIL (319 checks, 115 warnings)
```

The replacement is not cosmetic: the tool **read the sentinel**, so the
freshly written file contains
`FAIL B2-hash-mismatch …/check-all.txt (actual: 7448f1a9…)`,
`WARN B3-path-spelling`, `FAIL B4-tracked git status not clean for bundle`,
and `HO-STRATA-013: RESULT: FAIL (32 checks, 1 warnings)` — a dirty-tree run,
exactly as the sentinel implies. The sentinel is gone and `/tmp/ca.txt` is
consumed. **The command now does the work it claims.**

**Clean-clone control** — no sentinel:

```text
clone HEAD 2541bec, git status 0
pre  sha 61f34497111985cb4bef2a18e8ee4c02819fe1e31c91e064f6e4ba708cb2b9bd  inode 4597080
rc=1  mv-exit=0
post sha 61f34497111985cb4bef2a18e8ee4c02819fe1e31c91e064f6e4ba708cb2b9bd  inode 2097267
/tmp/ca.txt ABSENT
git status lines: 0
```

Inode changes while the digest is stable: the artifact was **rewritten with the
same bytes**, not skipped. Round 2 proved the opposite (digest unchanged, file
left in `/tmp`, tree clean); the defect is gone.

### 9.3 R2-2 — `test-output.txt` is the final artifacts (Blocker → **closed**)

```text
$ python3 (split on "===== artifacts/<name>.txt =====" and compare byte-wise)
segments: 14
artifacts/check-ho012.txt: identical (1457 bytes incl. trailing)
artifacts/check-all.txt: identical (21913 bytes incl. trailing)
artifacts/check-all-strict.txt: identical (21910 bytes incl. trailing)
artifacts/self-test.txt: identical (375 bytes incl. trailing)
artifacts/stdlib-isolated.txt: identical (375 bytes incl. trailing)
artifacts/stdlib-imports.txt: identical (271 bytes incl. trailing)
artifacts/git-status-before.txt: identical (668 bytes incl. trailing)
artifacts/git-status-after.txt: identical (668 bytes incl. trailing)
artifacts/git-status-diff.txt: identical (1 bytes incl. trailing)
artifacts/fresh-clone.txt: identical (1457 bytes incl. trailing)
artifacts/readme-section.txt: identical (145 bytes incl. trailing)
artifacts/deterministic.txt: identical (169 bytes incl. trailing)
artifacts/legacy-proof.txt: identical (118 bytes incl. trailing)
artifacts/bypass-proof.txt: identical (2262 bytes incl. trailing)
all_ok: True
artifacts on disk: 14
missing from transcript: []
'actual: e0063b4e' -> False
'B4-tracked git status not clean' -> False
'HO-STRATA-013: RESULT: FAIL' -> False
```

All 14/14 sections are byte-identical to their final files (the 1-byte
`git-status-diff.txt` is the generator's injected trailing newline around an
empty artifact, consistent with `print(p.read_text())`). The stale strict run
that round 2 caught — `actual: e0063b4e`, `B4-tracked git status not clean`,
`HO-STRATA-013: RESULT: FAIL` — appears nowhere. The self-bundle block in the
transcript now reads `RESULT: PASS (32 checks, 0 warnings)`, agreeing with
`artifacts/check-all-strict.txt`.

### 9.4 R2-3 — manifest vs record (Blocker → **closed in substance**, two doc residuals)

**§1 ↔ `commands.log`, entry for entry.** Parsed, not spot-checked:

```text
log ids  : C1 C2 C3 C4 C5 C6 C7 C8 C9 C10 C11a C11b C12 C13 C14 C15 C16 C17
           C18 C19 C20 C21 C22 C23 C24            (25 entries)
manifest : C1 … C23                                (24 rows)
log - manifest: ['C24']
manifest - log: []
```

Spot-checks: C1 (ordinary row), C17 (the probe in §9.2) and C19 (heredoc) are
verbatim; the heredoc rows are first line + `*(full block: commands.log Cn)*`,
and `commands.log` itself has **zero** `...` (`grep -c '\.\.\.'` → 0). C21 is
recorded as one merged runnable line covering the log's two commands, with
exit `1` (the second command's `mv`). The substantive table is correct; the
one omission is **C24**, the final rehash appended in the same F1/F2 commit
(see R3-1). No `...` appears in `commands.log`; the two `...` in `manifest.md`
are prose (`no \`...\`` and `/home/...`), not elided commands.

**C16 erratum — present and honest.** `commands.log:102-104`:

```text
=== C16 (rehash after test-output and manifest updates) ===
# ERRATUM (recorded 2026-11-23): this block is incomplete in the historical record
# (the closing PY delimiter is missing) and is SUPERSEDED by C20/C23. Do not run it.
```

Verified: the C16 block has **0** closing `PY` lines (`sed … | grep -c '^PY$'` →
0), C20/C23 are complete, and C24's body is byte-identical to C23's
(`diff` exit 0). The erratum tells the truth about the defect and the
supersession.

**§3 and §5 — the two doc residuals.** §3 (`manifest.md:63`) still says the
C17 capture was taken "after the final rehash (`C19`)" and was "verified
byte-identical by the fixed-point runs (`C14`/`C15`)". C19 rebuilds
`test-output.txt` (not a rehash) and postdates C17; the rehash after C17 is
C20/C24; C14/C15 predate C17. The **clean-tree** half of the sentence is now
supported by the bundle's own artifact — `check-all.txt:328` carries
`PASS B4-tracked git status clean` for HO-STRATA-013, and the round-2
contradiction (`git-status-before.txt` with 8 modified paths) is correctly
re-labelled in §2/§5 as a **mid-assembly** comparison. §5
(`manifest.md:118-119`) calls `C12/C16/C19` "superseded rehash attempts";
C19 is a transcript rebuild. These are R3-1/R3-2: documentation accuracy, not
evidence integrity.

### 9.5 R2-4 — `File` column authoritative (Blocker → **closed**)

Throwaway repo, `pinned.txt` sha256 `60e5f7a5…`, `other.txt` `e6bd09f4…`,
`Commit` = HEAD `efde7568…`; six row shapes (the tool run in the repo root):

| Case | Row | Default run | Verdict |
|---|---|---|---|
| **A — divergent Command cell, correct `File` digest** | `File=pinned.txt`, `Command=git show …:other.txt \| sha256sum`, digest `60e5f7a5…` | exit 0; `WARN B6-pins command path differs from File column`; `PASS B6-pins pin ok: efde7568…:pinned.txt`; `RESULT: PASS (14 checks, 1 warnings)` | **PASS** (required behaviour) |
| **B — divergent Command cell, wrong `File` digest** | same row, digest `e6bd09f4…` (other's) | exit 1; WARN as above; `FAIL B6-pins pinned.txt (recorded e6bd09f4…, actual 60e5f7a5…)`; `RESULT: FAIL (14 checks, 1 warnings)` | **PASS** |
| **C — Command cell has no path, correct digest** | `Command=sha256sum pinned.txt`, digest `60e5f7a5…` | exit 0; `PASS B6-pins pin ok: efde7568…:pinned.txt`; `RESULT: PASS (13 checks, 0 warnings)` | **PASS** |
| **C2 — Command cell has no path, wrong digest** | `Command=sha256sum pinned.txt`, digest `e6bd09f4…` | exit 1; `FAIL B6-pins pinned.txt (recorded e6bd09f4…, actual 60e5f7a5…)`; `RESULT: FAIL (13 checks, 0 warnings)` | **PASS** |
| **D — `File` column empty, Command names a path, wrong digest** | empty File cell, `Command=git show …:pinned.txt`, digest `e6bd09f4…` | exit 0; `WARN … command path differs from File column`; `WARN B6-pins not a path pin`; `RESULT: PASS (14 checks, 2 warnings)` | warned, not verified — R3-4 |
| **E — `File` column empty, Command names a path, correct digest** | same, digest `60e5f7a5…` | identical to D | warned, not verified — R3-4 |

The Command cell no longer decides what is verified: the divergent row passes
only when the **File** digest is right (A) and fails when it is wrong (B); a
command with no path still verifies the File column (C/C2). The 16th fixture
`pin-divergent-cells` (`check_bundle.py:1207`) asserts exactly A/B, and the
self-test is 16/16. An empty `File` cell is not verified but is **warned twice**
and is not silent; no signed bundle has such a row (I checked every row in
`HO-STRATA-012`/`013`). That residual is R3-4, not a reopen of R2-4.

### 9.6 Fixed points, hashes, reproducibility

Clean tree `2541bec`, `git status` empty before and after:

```text
$ python3 workflow/tools/check_bundle.py --all > /tmp/opencode/audit-r3/all.txt 2>&1; echo $?
1
$ python3 workflow/tools/check_bundle.py --all --strict > …/all-strict.txt 2>&1; echo $?
1
$ diff -q …/all.txt        workflow/evidence/HO-STRATA-013/artifacts/check-all.txt;        echo $?
0
$ diff -q …/all-strict.txt workflow/evidence/HO-STRATA-013/artifacts/check-all-strict.txt; echo $?
0
61f34497111985cb4bef2a18e8ee4c02819fe1e31c91e064f6e4ba708cb2b9bd  artifacts/check-all.txt
61f34497111985cb4bef2a18e8ee4c02819fe1e31c91e064f6e4ba708cb2b9bd  /tmp/…/all.txt
d94c30243b2a0fab241d16ac631a08c28f75ba89faaa9e12812a5c8f5dbc9ebe  artifacts/check-all-strict.txt
d94c30243b2a0fab241d16ac631a08c28f75ba89faaa9e12812a5c8f5dbc9ebe  /tmp/…/all-strict.txt
$ git status --porcelain | wc -l
0
```

Both aggregates are **fixed points**. Census in the stored `--all`:

```text
$ grep '^FAIL ' artifacts/check-all.txt
FAIL B3-unlisted workflow/evidence/HO-STRATA-011/artifacts/cmd-8.err.txt
FAIL B3-unlisted workflow/evidence/HO-STRATA-011/artifacts/cmd-8.out.txt
# strict census
  8 B2-external
 32 B2-legacy-path
  3 B2-prose
 48 B3-path-spelling
  2 B3-unlisted          # 93 FAILs, RESULT: FAIL (319 checks, 23 warnings)
```

`HO-STRATA-013` inside the artifact: `RESULT: PASS (32 checks, 0 warnings)`;
total `319 checks, 114 warnings`, matching the per-bundle table
(72+1+57+56+24+52+25+32 = 319; 43+1+32+31+0+1+6+0 = 114).

Hashes and derivation:

```text
$ sha256sum -c workflow/evidence/HO-STRATA-013/hashes.txt
… 21 lines: OK
(exit 0)
$ grep -c '/home/' workflow/evidence/HO-STRATA-013/hashes.txt
0
$ grep -c '\.\.\.' workflow/evidence/HO-STRATA-013/commands.log
0
$ <C23 block verbatim from commands.log> > /tmp/opencode/audit-r3/hashes-c23.txt
$ diff -q hashes.txt /tmp/…/hashes-c23.txt; echo $?
0
727cbea9b77477504f7e6d6dc4df6f6a75f7893653f0ef5a654dc32a5b06b539  both
$ diff <(C23 body) <(C24 body); echo $?
0                                        # C24 repeats C23; omitted from §1 (R3-1)
```

The two pins still resolve with the recorded digests
(`315030e:workflow/DECISIONS.md` → `600d123a…7b05`,
`315030e:workflow/README.md` → `3bfcf2aa…4674e`, both unchanged after
`315030e`). The committed probe scripts exist and run: `legacy_proof.py`
reproduces `artifacts/legacy-proof.txt` byte for byte; `bypass_probe.py` exits
0 and reproduces every assertion, differing only in the throwaway repo's
commit id (`d19d446e…` recorded vs `d00d88cd…` on re-run) — R3-5.

### 9.7 Regression, scope, guard rails

| Check | Command | Observed |
|---|---|---|
| AC-1 | `… workflow/evidence/HO-STRATA-012` | exit 0; `RESULT: PASS (25 checks, 6 warnings)`; byte-identical to `artifacts/check-ho012.txt` |
| AC-2 | `… --all` | exit 1; `RESULT: FAIL (319 checks, 114 warnings)`; exactly the 2 HO-011 FAILs; identical to the artifact |
| AC-3 | `… --self-test` | exit 0; 16/16 fixture lines; `RESULT: PASS (all fixtures behaved as expected)`; identical to `artifacts/self-test.txt` |
| AC-4 | `python3 -I … --self-test` | exit 0; identical to `artifacts/stdlib-isolated.txt` |
| AC-4 | imports / network | `__future__, argparse, hashlib, json, os, re, shutil, subprocess, sys, tempfile, pathlib, typing`; `grep -E 'socket\|urllib\|requests\|http.client\|urlopen'` → none |
| AC-5 | read-only | `git status` empty before/after every run; `B8-read-only … unchanged` in both aggregates |
| AC-6 | fresh clone | §9.2 clean clone: same exit code, same verdict, byte-identical artifact |
| AC-7 | README | `README.md:36-49`; both commands; "Before marking any handoff `CODER_DONE`…"; "QAQC re-runs…" |
| AC-8 | determinism | two runs sha `2604843c0ed08e3a74d2d6428a3929df51b5c184dd5bfe5cf77e72f2bc355bee` both; `deterministic.txt` matches the fresh runs exactly |
| Self-bundle | `… workflow/evidence/HO-STRATA-013` | exit 0; `RESULT: PASS (32 checks, 0 warnings)` |

```text
$ git diff --shortstat 91eac12..HEAD
 30 files changed, 5716 insertions(+)
$ git diff --name-only 91eac12..HEAD | grep -vE '^(workflow/tools/check_bundle\.py|workflow/README\.md|workflow/handoffs/|workflow/reports/|workflow/evidence/HO-STRATA-013/)'
none
$ git diff --name-only 91eac12..HEAD -- workflow/DECISIONS.md workflow/STATUS.md .opencode .github
(empty)
$ git diff --name-only 91eac12..HEAD -- workflow/evidence | grep -v '^workflow/evidence/HO-STRATA-013/'
none
$ git -C /home/kupipi/Documents/git/strata status --porcelain
(empty)   HEAD bac859ef9
$ sha256sum /home/kupipi/Documents/git/strata/build-hip/strata
d58ee2398596d1a100c15d5b9459e24bd86854cb5e5fb7ce88dbc6c7ed9f5858
```

No dependency, no network, no secret (`B7-secrets` PASS; the only
credential-shaped strings are the tool's own regexes and fixture), no other
bundle edited, no protected path touched, Strata and the signed binary
unchanged. (Two process docs are stale — see R3-7.)

### 9.8 Process ruling — architect completion C17–C24 and the post-QAQC F1/F2 fix

**Ruling: the chain holds.** The architect completed the recapture after the
coder's step cap and then closed QAQC's F1/F2 after QAQC's PASS. That is
acceptable *here* because each condition I set in round 2 is met and was
verified, not accepted on the summary:

1. **The tool is frozen.** `9b85e33..HEAD` changes
   `workflow/tools/check_bundle.py` only in the coder's `679b774`;
   `830b6bf..HEAD` changes it not at all. The code QAQC tested at `830b6bf` is
   the code at `2541bec`.
2. **Every post-coder commit is evidence, handoff, or report.**
   `git diff --name-only 679b774..HEAD` outside
   `workflow/evidence/HO-STRATA-013/`, `workflow/handoffs/`,
   `workflow/reports/` is empty.
3. **It is logged and re-derivable, not merely asserted.** C17–C24 record cwd
   and exit in `commands.log`; I re-derived C17/C18 (fixed points, clean clone,
   sentinel), C19/C22 (14/14 transcript sections), C20/C23 (byte-identical
   `hashes.txt`), C21 (both aggregates), and the non-aggregate C1–C4, C7–C10
   artifacts. Every one reproduces except the inherently run-scoped C5 status
   snapshot (now honestly labelled mid-assembly) and the throwaway commit id in
   R3-5.
4. **The F1/F2 closure is evidence-only.** `fd4bb85` changes `manifest.md`
   (documentation), `commands.log` (C24 + erratum), `hashes.txt` (C24 rehash)
   and the QAQC report; the tool is untouched, the aggregates and transcript are
   unchanged and still fixed points, and `sha256sum -c` is 21/21. Conditions:
   evidence-only ✔, reproducible ✔, recorded ✔, evidence-complete ✔; the
   **documentation** of it is not fully complete (R3-1/R3-2), which is why they
   are findings and not a chain failure.

Two caveats the architect must record, not silently normalise:

- **R3-6** — the QAQC round-3 report was written into `workflow/reports/qaqc/`
  by the architect's `fd4bb85` (a 317-line replacement of the round-2 report).
  `ENGINEERING_WORKFLOW.md` §4 reserves that directory for QAQC. This is the
  second occurrence (R2-8 was the first). Its content checks out against my own
  runs — every number and probe I re-ran matched — so I find no fabricated QAQC
  claim, but the final-tip QAQC gate has no independently authored artifact.
- **R3-1/R3-2** — the manifest's own provenance sentences are now the least
  accurate part of the bundle.

The mechanism may be used to finish an evidence-only cycle; it should not be
used to author a reviewer's report. I recommend a `DECISIONS.md` note at
signoff recording the architect's completion of C17–C24 and the materialisation
of both QAQC reports.

### 9.9 Findings (round 3)

| # | Severity | Finding | Evidence | Blocking | Owner |
|---|---|---|---|---|---|
| **R3-1** | Minor (documentation) | `manifest.md` §1 claims "Generated by parsing `commands.log`, so it cannot drift from the record", yet it has 24 rows for 25 log entries: **C24 is missing** (the final rehash, appended in the same F1/F2 commit). §5 then calls `C12/C16/C19` "superseded **rehash** attempts" — C19 rebuilds `test-output.txt`. §1's `C16` row points at a block the log says "Do not run it", with no marker in the table. | `manifest.md:13-15,17-42,118-119`; `commands.log:102-104,236-261`; `log - manifest = ['C24']`; C23/C24 bodies `diff` 0 | No — the omitted row is a byte-identical duplicate of the included C23, which reproduces the final `hashes.txt` | Architect (doc-only; any edit needs a C25 rehash and a re-check) |
| **R3-2** | Minor (documentation) | §3 says C17 was taken "after the final rehash (`C19`)" and "verified byte-identical by the fixed-point runs (`C14`/`C15`)". C19 is a transcript rebuild and postdates C17; the rehash after C17 is C20/C24; C14/C15 predate C17. The clean-tree half **is** supported by `PASS B4-tracked git status clean` in the artifact; the byte-identity is proved by C21 line 1 and this audit. | `manifest.md:63`; `commands.log:93-101,131-139,158-191` | No | Architect |
| **R3-3** | Minor (log wording) | `commands.log` records `exit: 1` for C17/C18, but the logged line's own exit status is **0** (it ends with `mv`); `1` is the tool's rc. RW-3 asked for "the real exit code of each line". Reproduction is unaffected and proven. | C17/C18 run verbatim: line exit 0, rc 1 | No | Coder/Architect (one-word label) |
| **R3-4** | Minor (latent) | A pin row with an **empty `File` column** is not verified: `WARN command path differs…` + `WARN not a path pin`, `RESULT: PASS`, even with a wrong 64-hex digest. Warned twice, not silent; no signed bundle has such a row (`HO-012`/`HO-013` checked row by row). | probes D/E in §9.5; `check_bundle.py:543-559` | No (latent) | Architect to schedule |
| **R3-5** | Minor | `scripts/bypass_probe.py` cannot reproduce its artifact byte-for-byte: the throwaway repo's commit id differs per run (`d19d446e…` vs `d00d88cd…`). The assertions and exit code reproduce; the recorded id is unverifiable by design. | `diff artifacts/bypass-proof.txt /tmp/…/bypass.txt` = one line | No | Coder (note) or accept as inherent |
| **R3-6** | Minor (process) | QAQC's round-3 report was committed by the architect (`fd4bb85`), replacing the round-2 report in a directory the workflow reserves for QAQC; the report's "this is the only file I wrote" is therefore not attributable. Content re-verified; no false QAQC claim found. Second occurrence after R2-8. | `git show --stat fd4bb85`; `git diff 830b6bf fd4bb85 -- workflow/reports/qaqc/…` (317 lines) | No | Architect (record in `DECISIONS.md`; QAQC owns its report henceforth) |
| **R3-7** | Minor (process) | `HO-STRATA-013` has no row in `workflow/STATUS.md` ("a handoff without a status row is invisible"), and the handoff header still reads `CODER_DONE` while §13/§17 log `AUDIT_REVIEW`/QAQC PASS. | `grep 'HO-STRATA-013' workflow/STATUS.md` → no match; `HO-STRATA-013.md:7` | No | Architect |
| **R3-8** | Carried | `--all` exits 1 on `HO-STRATA-011`'s two unlisted artifacts. Correct; must not be tuned; only a bundle supersession repairs it. | 2 `B3-unlisted` lines | No | Architect |
| **R3-9** | Carried | Round-1 A3 / R2-6 still open: `absolute-external` asserts only `B2-external`; `basename-spelling` only `B2-path-spelling`. Explicitly outside RW-3. | `FIXTURES`, `check_bundle.py:1200-1202` | No | Architect to schedule |

**Per-finding closure:**

| Finding (round 2) | Status | Proof in this audit |
|---|---|---|
| **R2-1** — `&&` after exit 1 leaves the artifact untouched | **CLOSED** | §9.2: sentinel replaced, `/tmp/ca.txt` consumed, clean-clone inode change with stable digest |
| **R2-2** — transcript embeds the pre-fix strict run | **CLOSED** | §9.3: 14/14 sections byte-identical; the three stale strings absent |
| **R2-3** — manifest over-claims / wrong `§1` commands / `...` | **CLOSED in substance** | §9.4: 24/25 rows verbatim, C16 erratum honest, no `...` in the log, mid-assembly snapshots correctly labelled; residuals R3-1/R3-2 |
| **R2-4** — Command cell overrides the `File` column | **CLOSED** | §9.5: A/B/C/C2 behave as specified; 16th fixture; empty-File residual R3-4 |
| QAQC F1 — §1 drift / C16 block | **CLOSED** (the §1 regeneration is real and the erratum is honest); the regeneration is one row short — R3-1 | §9.4 |
| QAQC F2 — §3 check counts | **CLOSED** | 32/319 and the per-bundle rows match the artifact exactly |

### 9.10 Verdict and statement

**PASS → `ARCHITECT_APPROVAL`.** The four round-2 blockers are closed in
substance and by direct probe on `2541bec`: the logged capture now writes its
artifact (R2-1), the transcript is the final artifacts (R2-2), the manifest no
longer contradicts the record on the capture and no `...` remains (R2-3), and
the `File` column decides B6 (R2-4). The bundle verifies 21/21, both aggregates
and the transcript are fixed points, `--all` is red only on the signed
`HO-STRATA-011` bundle, and the tool is the one QAQC exercised.

The residual defects are documentation and process, not evidence: the §1 table
omits the final, byte-identical duplicate rehash row (R3-1), §3 mis-cites the
rehash and fixed-point entries (R3-2), the C17/C18 exit label reports the
tool's rc rather than the line's (R3-3), an empty-`File` pin row is warned but
not verified (R3-4), the probe artifact embeds a throwaway commit id (R3-5),
and the QAQC report/status board were maintained by the architect (R3-6/R3-7).
No claim about the tool's behaviour or the artifacts' contents is unsupported.
I do not block on these because the evidence itself is complete and
independently re-derivable, and the one omitted row is the same command as the
row that is present.

**What the architect must do at the signature:** either carry R3-1/R3-2
explicitly in the approval (the cleanest option — this verdict applies to
`2541bec`), or correct them in a doc-only commit with a C25 rehash and a
re-check; a post-audit manifest edit changes the hashed state and is **not**
covered by this verdict. Record the C17–C24 completion and the QAQC report
materialisation in `DECISIONS.md` (R3-6). Do not tune `--all` green on
`HO-STRATA-011` (R3-8).

**Statement.** I did not modify code, tests, docs, configuration, evidence,
handoffs, `workflow/DECISIONS.md`, `workflow/STATUS.md`, `.opencode/**`, or
`.github/**`; I did not merge, sign, or approve a release. My only write is this
report; every probe ran under `/tmp/opencode/audit-r3/`. The Strata checkout was
read only (`bac859ef9`, clean; `build-hip/strata` `d58ee239…`). My seat is
`opencode-go/deepseek-v4.1-flash`, which shares a family with the architect
(`deepseek-v4-pro#max`) under **WAIVER-001** — a documented exception to
DEC-006 and **not** a model-separation PASS.

---

### AUDITOR_TO_ARCHITECT — Round 3 (governs `2541bec`)

| Field | Value |
|---|---|
| **Type** | `AUDITOR_TO_ARCHITECT` |
| **From → To** | Auditor (`opencode-go/deepseek-v4.1-flash`, WAIVER-001 — family exception, not a PASS) → Architect (`opencode-go/deepseek-v4-pro#max`) |
| **Handoff** | HO-STRATA-013, `RW-HO-STRATA-013-3`, QAQC round 3 |
| **State** | `AUDIT_REVIEW` → **`ARCHITECT_APPROVAL`** |
| **Report** | `workflow/reports/audit/HO-STRATA-013-audit.md` §9 |
| **Evidence** | `workflow/evidence/HO-STRATA-013/` @ `2541bec` — 21 entries, `sha256sum -c` 21/21 OK (exit 0), no `/home/`; both aggregates reproduce byte for byte; `git status` empty |
| **Verdict** | **PASS** — R2-1…R2-4 closed; tool and evidence meet the handoff |
| **Closed** | R2-1 (C17 verbatim in a fresh clone: sentinel replaced, `/tmp/ca.txt` consumed, inode change on a clean clone); R2-2 (14/14 transcript sections byte-identical, no stale FAIL strings); R2-3 (24/25 §1 rows verbatim, C16 erratum honest, zero `...` in the log, mid-assembly snapshots correctly labelled); R2-4 (File column authoritative; divergent cell → WARN + PASS, wrong File digest → FAIL; 16/16 fixtures); QAQC F1/F2 (erratum + 32/319 counts) |
| **Minor** | R3-1 §1 omits C24 and §5 mislabels C19 as a rehash; R3-2 §3 mis-cites C19/C14/C15; R3-3 C17/C18 exit label; R3-4 empty-`File` pin row warned not verified; R3-5 probe artifact embeds a throwaway commit id; R3-6 QAQC round-3 report materialised by the architect; R3-7 no STATUS row, stale handoff header |
| **Carried** | R3-8 HO-011 red (correct; do not tune); R3-9 round-1 A3 assertions |
| **Process ruling** | **Chain holds.** Tool frozen at `679b774`; every later change is evidence/handoff/report; C17–C24 logged and independently re-derived (aggregates, transcript, hashes, sentinel probe); post-QAQC F1/F2 is evidence-only and re-verified. Caveat: the architect authored QAQC's round-3 report — record it in `DECISIONS.md` and stop the practice (R3-6). |
| **Next** | Architect: sign `ARCHITECT_APPROVAL` at `2541bec` and carry R3-1/R3-2 explicitly, or fix them doc-only with a C25 rehash and request a re-check; record the completion/materialisation in `DECISIONS.md`; then merge (the merge commit cites HO-STRATA-013 and this evidence directory). No code or evidence change in the approval commit. |
