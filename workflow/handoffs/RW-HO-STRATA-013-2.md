# RW-HO-STRATA-013-2 — B3 suffix bypass and B6 silent skip

| Field | Value |
|---|---|
| **ID** | RW-HO-STRATA-013-2 |
| **State** | CLOSED |
| **Created (UTC)** | 2026-11-22 |
| **From → To** | Auditor (finding) → Architect (scope) → Primary Coder |
| **Original handoff** | `workflow/handoffs/HO-STRATA-013.md` |
| **Failed criteria** | AC-1/AC-2 (tool correctness), AC-3 (fixtures do not cover the bypasses), RW-1 F1/F5 |
| **Audit** | `workflow/reports/audit/HO-STRATA-013-audit.md` |
| **Re-check by** | Architect, then QAQC, then Auditor |

## 1. Why this is blocking

The tool is the gate that is supposed to stop defective evidence. Right now two
checks can be satisfied **without doing the work**, which makes every future
bundle's "PASS" worth less. Both are confirmed in the committed source
(`workflow/tools/check_bundle.py` at `2800d64`), not merely reported.

### A1 — B3 exempts every file whose name ends in `hashes.txt`

```python
for current in sorted(bundle_dir.rglob("*")):
    ...
    fpath = rel_to_repo(current, root)
    if fpath.endswith("hashes.txt"):     # line 408
        continue
```

The intent is to exempt the bundle's own `hashes.txt` (a file cannot hash
itself). The effect is to exempt **any** file with that suffix. Probe: a bundle
with an unlisted `artifacts/notes-hashes.txt` returns
`RESULT: PASS (10 checks, 0 warnings)` — and still passes under `--strict`.
`HO-STRATA-010` already ships `artifacts/pack_hashes.txt`, so the hole is not
hypothetical.

**Required:** exempt exactly one path — the bundle's own `hashes.txt`
(normalized repo-relative comparison against `<bundle>/hashes.txt`). Every other
file, whatever its name, must be covered.

### A2 — B6 silently skips any pin row whose Command column does not match one regex

```python
if not re.search(r"git\s+show\s+[0-9a-fA-F]+:\S+\s*\\?\|\s*sha256sum", cmd):
    continue                          # line ~533
```

A pin row carrying a **wrong full 64-hex digest** with any other spelling of the
command (`git cat-file -p <sha>:<path> | sha256sum`, `git -C <repo> show …`,
a table built by hand) is never verified and the bundle reports PASS. An
**unresolvable commit** (`deadbeef`) with a non-matching Command also passes;
with the exact expected spelling it correctly FAILs. Verification must not
depend on how a human wrote the Command cell.

**Required:** verify every row of the `## Commit pins` table that has a
`<commit>:<path>` and a digest:

| Row state | Verdict |
|---|---|
| full 64-hex digest, commit and path resolve, digest matches | `PASS` |
| full 64-hex digest, digest differs | `FAIL B6-pins <path> (recorded <a>, actual <b>)` |
| commit does not resolve | `FAIL B6-pins unresolvable commit '<ref>' for <path>` |
| `<commit>:<path>` does not resolve | `FAIL B6-pins unresolvable <ref>:<path>` |
| abbreviated digest (`abc…def`) | `WARN B6-pins abbreviated digest` (unchanged) |
| table row with no commit/path (tree or binary pin) | `WARN B6-pins not a path pin` — **must not** be silently skipped |
| Repository not resolvable | `WARN B6-pins unknown repository` (unchanged) |

The Command column becomes documentation. Do not parse it for gating.

## 2. Also required (evidence reproducibility)

### F3 — `commands.log` must be copy-paste reproducible

The audit found: C2d/C9d record `artifacts/check-all.txt` as a relative path that
is wrong from the repo root, and C8/C10 elide the command with `...`. A reader
cannot reproduce them from the log.

**Required:** every entry records the exact command, verbatim, with the cwd;
no `...`; no relative path that cannot be resolved from the stated cwd. Where a
multi-line heredoc is used, record it in full (as C10 already does) or commit
the helper script inside the bundle and record the invocation.

### F4 — manifest corrections

- §3: the `HO-STRATA-013` row must read `0 warnings` (the authoritative
  `artifacts/check-all.txt` says `PASS (29 checks, 0 warnings)`; full 64-hex
  digests ended the two B6 warnings).
- §2 AC-2: state that `DEC-039` is `WARN skipped` only on a **direct**
  invocation; `--all` globs `HO-*` and does not visit it. Do not claim it appears
  in `--all`.

### F5 — three new negative controls (12 → 15)

| Fixture | Must report |
|---|---|
| unlisted `artifacts/notes-hashes.txt` | `FAIL B3-unlisted` (both default and `--strict`) |
| pin row, full wrong digest, command written as `git cat-file -p <sha>:<path> \| sha256sum` | `FAIL B6-pins` |
| pin row, unresolvable commit, command written as `git show …` but commit `deadbeef` | `FAIL B6-pins` |

## 3. Expected effect on the real archive — report, do not tune

After the fix, `--all` may report **new** FAILs on signed bundles whose pins were
never really verified (DEC-030 **B-4** recorded pins without digests). That is
the tool doing its job.

- Report the new per-bundle results verbatim in the manifest.
- **Do not edit any signed bundle.** Do not weaken a check to restore the old
  count.
- If HO-STRATA-012 (a signed, previously-PASS bundle) gains a FAIL, stop and
  report it to the architect before committing: that changes the acceptance
  baseline and the architect decides.

## 4. Evidence required

Regenerate per the capture rules established in RW-1 (output to `/tmp` then move;
log appended after the run; hashes last):

- `artifacts/check-ho012.txt`, `check-all.txt`, `check-all-strict.txt`,
  `self-test.txt` (15 fixtures), plus the existing set;
- `artifacts/bypass-proof.txt` — the two probes from §1 (unlisted
  `notes-hashes.txt`; wrong digest with a reworded command), showing they now
  FAIL, and the control probe still passing;
- `commands.log`, `test-output.txt`, `manifest.md`, `hashes.txt`,
  `hashes-notes.txt` refreshed; `hashes.txt` repo-relative, full 64-hex pins;
- fixed-point proof: a fresh `--all` reproduces `artifacts/check-all.txt` byte
  for byte and leaves `git status` empty.

## 5. Guard rails

- Fix only A1, A2, F3, F4, F5. No new checks, no new dependency, no refactor of
  unrelated code.
- Do not edit any bundle except `workflow/evidence/HO-STRATA-013`.
- Do not touch `workflow/DECISIONS.md`, `workflow/STATUS.md`, `.opencode/**`,
  `.github/**`, the Strata checkout.
- Commit on `wp/strata-013-check-bundle`; no PR, no `main`.
- Also correct the RW-1 §1.4 sentence that credits the **tool** with an "exit 4"
  on absolute paths — that guard lives in the evidence-generation script, not in
  `check_bundle.py`. A claim without an artifact is the defect this project keeps
  paying for.

## 6. Log

- 2026-11-22 Auditor: A1/A2 found with probes; F3 manifest/log defects; F3 report
  inconsistency ruled a must-fix inside the refresh.
- 2026-11-22 Architect: confirmed both bugs in the source (`:408`, `:~533`),
  scoped this rework, folded the auditor's A3/A4/A6 (log reproducibility,
  manifest wording) in.
- 2026-11-22 Primary Coder: A1/A2 fixed, F3/F4/F5 implemented, 15 self-test
  fixtures pass, evidence refreshed, fixed-point proof verified; state
  `CODER_DONE`.
