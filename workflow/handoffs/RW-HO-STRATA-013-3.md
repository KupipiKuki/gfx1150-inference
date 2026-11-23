# RW-HO-STRATA-013-3 — evidence consistency and B6 Command-cell precedence

| Field | Value |
|---|---|
| **ID** | RW-HO-STRATA-013-3 |
| **State** | OPEN |
| **Created (UTC)** | 2026-11-23 |
| **From → To** | Auditor (round-2 findings) → Architect (scope) → Primary Coder |
| **Original handoff** | `workflow/handoffs/HO-STRATA-013.md` |
| **Audit** | `workflow/reports/audit/HO-STRATA-013-audit.md` §8 |
| **Failed criteria** | AC-5/AC-6 (reproducibility of the log), RW-2 F3/F4 (evidence consistency), RW-2 A2 (residual) |
| **Re-check by** | QAQC, then Auditor |

## 1. Findings to close

### R2-1 — the logged capture command cannot work (blocking)

`commands.log` records `C9d`/`C9e` as:

```text
python3 workflow/tools/check_bundle.py --all --strict > /tmp/cas.txt 2>&1 && mv /tmp/cas.txt …/check-all-strict.txt
```

`--all --strict` exits **1** on the honest HO-011 failures, so `&&` short-circuits
and the `mv` never runs. Proven in a clean clone: the artifact's SHA is unchanged
and the output stays in `/tmp`. The artifact itself was produced with `;`; the
record is wrong, which makes the evidence unreproducible as written.

**Required:** every logged command must run to completion as recorded. Where the
tool is expected to exit non-zero, record `;` or capture the code first
(`… > /tmp/x 2>&1; rc=$?; mv /tmp/x …; echo "exit: $rc"`). **The record must
match what was actually executed** — no reconstructed commands.

### R2-2 — `test-output.txt` contradicts the final artifact (blocking)

`test-output.txt` still embeds the pre-`C9e` strict run, in which the bundle
FAILs on itself (`FAIL B2-hash-mismatch … check-all.txt (actual: e0063b4e…)`,
`B3-path-spelling`, `B4-tracked not clean`) at lines 672–691, while
`artifacts/check-all-strict.txt` now shows the bundle passing. The file has not
been rebuilt since `9be15de`.

**Required:** rebuild `test-output.txt` **after** the final capture of both
aggregate artifacts, from the final artifact files, in the fixed order. It is a
mechanical concatenation — no curation.

### R2-3 — manifest over-claims and its command column is wrong (blocking)

- §3 calls the aggregate capture a "clean tree" capture; the bundle's own
  `git-status-before.txt` lists 8 modified paths at capture time. Say what is
  true: the snapshots were taken mid-assembly and are identical before/after
  (AC-5 proves the tool wrote nothing, not that the tree was clean).
- §1 records wrong relative paths for C5/C8, omits `C9e` entirely, and elides
  C10–C12 with `...`.

**Required:** §1 lists every command actually run, verbatim and runnable, with
its cwd and exit code; §3 claims only what the artifacts show. No `...` anywhere
in the evidence.

### R2-4 — B6 lets the Command cell override the File column (latent, fix anyway)

`_parse_commit_pins_table` (`check_bundle.py:653-661`) prefers a
`<commit>:<path>` found in the **Command** cell over the `File`/`Path` column.
Variant proved by the auditor: Command says `git show <sha>:other.txt` while
`File` says `pinned.txt` — the row passes and `pinned.txt` is never verified; a
correct row with the same divergence falsely FAILs.

**Required:** the **File/Path** column is authoritative. If the Command cell
names a different path, emit `WARN B6-pins command path differs from File column`
and verify the File column. Never let the Command cell decide what is verified.
Add a negative control for the divergent-cells case (15 → 16 fixtures).

## 2. Make the probes reproducible by construction

The multi-line heredocs (`C10` legacy proof, `C11` bypass proof) cannot be
copy-pasted from the log. Move each into a committed helper:

- `workflow/evidence/HO-STRATA-013/scripts/legacy_proof.py`
- `workflow/evidence/HO-STRATA-013/scripts/bypass_probe.py`

Content: exactly what the current `C10`/`C11` heredocs do today, with the
docstring naming the claim it proves. `commands.log` then records
`python3 workflow/evidence/HO-STRATA-013/scripts/bypass_probe.py` — one line,
runnable. Both files are covered by `hashes.txt` and `B3`.

## 3. Capture procedure (order matters — this is where the last two rounds failed)

1. Code fix (R2-4) + fixture; `--self-test` must show **16/16**; commit.
2. Write the two `scripts/` helpers; commit.
3. Regenerate every non-aggregate artifact (`check-ho012`, `self-test`,
   `stdlib-isolated`, `stdlib-imports`, `git-status-*`, `fresh-clone`,
   `readme-section`, `deterministic`, `legacy-proof`, `bypass-proof`).
4. Capture the aggregates **last**, to `/tmp`, then move with `;` not `&&`:
   `python3 … --all > /tmp/ca.txt 2>&1; rc=$?; mv /tmp/ca.txt …`
5. **Then** rebuild `test-output.txt` from the final artifacts.
6. **Then** run the logged `C12` rehash block verbatim — it must reproduce
   `hashes.txt` (19+ entries, no `/home/`).
7. Commit; then prove the fixed point on the clean tree: `--all` and
   `--all --strict` reproduce both artifacts byte for byte and `git status`
   stays empty. Record that proof in commands.log **before** the final rehash,
   or in the handoff — not in a hashed file afterwards.

## 4. Expected numbers after the fix

- `--self-test`: **16/16**
- `--all`: exit 1, exactly 2 FAILs (both `HO-STRATA-011` `B3-unlisted`)
- `--all --strict`: exit 1, many FAILs (legacy upgrades) — the bundle itself PASSes
- `check_bundle.py workflow/evidence/HO-STRATA-013`: PASS
- `sha256sum -c hashes.txt`: all OK; entries = every bundle file + the tool

New FAILs on signed bundles attributable to R2-4 strictness are reported, not
tuned away; do not edit any signed bundle.

## 5. Guard rails

- Fix only R2-1…R2-4 and §2. No new checks, no refactor, no dependency.
- Do not edit any bundle except `HO-STRATA-013`; do not touch `DECISIONS.md`,
  `STATUS.md`, `.opencode/**`, `.github/**`, the Strata checkout.
- Commit on `wp/strata-013-check-bundle`; no PR, no `main`.
- If a check would need weakening to keep the old counts, stop and report.

## 6. Log

- 2026-11-23 Auditor: R2-1…R2-4, with a clean-clone proof that the logged `&&`
  command leaves the artifact untouched.
- 2026-11-23 Architect: confirmed R2-1 (`&&` after exit 1) and R2-2 (stale strict
  lines at `test-output.txt:672-691`) directly; scoped this rework; R2-4 fixed
  rather than deferred because "a check that can be satisfied without doing the
  work" is the exact defect this tool exists to prevent.
