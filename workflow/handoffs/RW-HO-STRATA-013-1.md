# RW-HO-STRATA-013-1 — B2/B3 misclassify legacy hashes.txt path spellings

| Field | Value |
|---|---|
| **ID** | RW-HO-STRATA-013-1 |
| **State** | OPEN |
| **Created (UTC)** | 2026-11-22 |
| **From → To** | Architect (reviewer) → Primary Coder |
| **Original handoff** | `workflow/handoffs/HO-STRATA-013.md` @ `7715f68` |
| **Failed criteria** | AC-2 (aggregate run), AC-3 (negative controls are incomplete) |
| **Re-check by** | Architect, then QAQC per `HO-STRATA-013-QAQC.md` |

## 1. What failed, exactly

`--all` reports **32 FAILs that are not defects**. Three bundles hash with
path spellings the tool cannot resolve, and every digest is correct.

### 1.1 HO-STRATA-001 — 15 "missing" files + 3 "malformed" lines

```text
FAIL B2-hash-verify missing: boundary-layout.txt
FAIL B2-hash-verify missing: manifest.md
FAIL B2-hash-verify missing: commands.log
… (15 in total, all under artifacts/)
FAIL B2-hash-verify malformed hashes.txt line: 'strata HEAD     baf16363b4…   (git -C … rev-parse HEAD; DEC-007)'
FAIL B2-hash-verify malformed hashes.txt line: 'workflow base commit  a6166f7e…   (wp/strata-001-gfx1150-build, base)'
FAIL B2-hash-verify malformed hashes.txt line: 'N/A — no model, dataset or prompt was used in this handoff …'
```

The listed spellings are **bundle-relative without the `artifacts/` prefix**
(`boundary-layout.txt` for `artifacts/boundary-layout.txt`). Proof that the
digests are right:

```console
$ cd workflow/evidence/HO-STRATA-001 && python3 - <<'EOF'
# verify each listed digest, falling back to the file with the same basename
EOF
with basename fallback: ok=21 mismatch=0 missing=0
```

The three "malformed" lines are a **pin record** and an explicit **`N/A — …`**
prose line. They are not hash lines and never were.

### 1.2 HO-STRATA-007 and HO-STRATA-008 — 15 + 14 "missing" files

```text
FAIL B2-hash-verify missing: ./artifacts/amd-smi-gtt.txt
```

Those paths are bundle-relative with a `./` prefix (GNU `sha256sum` output run
from the bundle directory). Verified:

```console
$ cd workflow/evidence/HO-STRATA-007 && python3 # hash each listed path from the bundle dir
verified from bundle dir: 17 | problems: 0
```

### 1.3 What the tool got right (keep it)

- `HO-STRATA-012` PASS with 3 B6 warnings — correct.
- `HO-STRATA-011` FAIL on `artifacts/cmd-8.err.txt` and `artifacts/cmd-8.out.txt` —
  **a real gap**: both files exist, the manifest lists them (command 8), and
  `hashes.txt` omits them. Report it, do not fix it (the bundle is signed).
- `HO-STRATA-010` PASS, `HO-STRATA-005`/`DEC-039` skipped — correct.
- The seven existing negative controls — correct.

## 2. Required fix (and nothing else)

### F1 — B2 path resolution, in this order

For each `<sha256>  <path>` line, resolve in exactly this order and report which
one matched. Only `e` is a FAIL.

| # | Resolution | Verdict |
|---|---|---|
| a | path exists relative to the **repo root** | `PASS B2-hash-verify` (canonical) |
| b | path exists relative to the **bundle dir** | `PASS` + `WARN B2-legacy-path <path>` |
| c | **absolute** path, outside the repo, readable | `PASS` + `WARN B2-external <path>` |
| c' | absolute path, not readable | `WARN B2-external-unverifiable <path>` |
| d | no exact match, but a file with the **same basename** exists under the bundle, and its digest matches | `PASS` + `WARN B2-path-spelling <listed> -> <actual>` |
| d' | same basename exists, digest **differs** | `FAIL B2-hash-mismatch <listed> (actual: <actual>)` |
| e | none of the above | `FAIL B2-missing <path>` |

Non-hash lines:

- line starts with `#` → silent (comment);
- first token is not 64 hex → `WARN B2-prose <line>` (pin records, `N/A — …`);
- first token is 64 hex but the separator/format is wrong → `FAIL B2-malformed <line>`.

### F2 — B3 coverage by normalized path

- Exact match → covered.
- A listed path whose **basename** matches a disk file but whose spelling
  differs → `WARN B3-path-spelling <disk> (listed as <listed>)`.
- A disk file with no listing by exact path or basename → `FAIL B3-unlisted <disk>`.
  `HO-STRATA-011/artifacts/cmd-8.{out,err}.txt` MUST stay `FAIL B3-unlisted`.

### F3 — `--strict` mode

Add `--strict`: upgrades `B2-legacy-path`, `B2-external`, `B2-prose`,
`B3-path-spelling` from WARN to FAIL. Rationale: the signed archive stays green
on legacy spellings, while **new** bundles can be gated strictly. `--strict`
must not change `B6` (abbreviated digests stay WARN) or `B7`.

### F4 — Negative controls for the new classifications

Extend `--self-test` from 7 to **12 fixtures**; each must assert the exact code:

| Fixture | Expected |
|---|---|
| hash edited after `hashes.txt` was written | `FAIL B2-hash-mismatch` |
| extra artifact not listed | `FAIL B3-unlisted` |
| file written but never added | `FAIL B4-tracked` |
| artifact matched by `.gitignore` | `FAIL B5-not-ignored` |
| pin to a commit that does not contain the path | `FAIL B6-pins` |
| `ghp_`-shaped string | `FAIL B7-secrets` |
| clean bundle | `RESULT: PASS` |
| **bundle-relative path (with `./`)** | `PASS` + `WARN B2-legacy-path`; under `--strict` → `FAIL` |
| **absolute external path** | `PASS` + `WARN B2-external`; unreadable → `WARN B2-external-unverifiable` |
| **pin / `N/A —` prose line** | `WARN B2-prose`, exit 0 |
| **listed basename, actual file under `artifacts/`** | `PASS` + `WARN B2-path-spelling` + `WARN B3-path-spelling` |
| **64-hex line with a broken separator** | `FAIL B2-malformed` |

### F5 — New expected `--all` result

After the fix, `--all` must exit **1** with **exactly two FAIL lines**, both
`B3-unlisted` on `HO-STRATA-011`:

```text
workflow/evidence/HO-STRATA-011/artifacts/cmd-8.err.txt
workflow/evidence/HO-STRATA-011/artifacts/cmd-8.out.txt
```

and zero FAILs for HO-001, HO-007, HO-008, HO-010, HO-012. If your run differs,
stop and report the difference — do not adjust bundles or expectations to match.

## 3. Evidence required

Re-run AC-1 … AC-8 from `HO-STRATA-013.md` §4 and refresh the bundle:

- `artifacts/check-all.txt` — the new `--all` output (2 FAILs, as above);
- `artifacts/check-all-strict.txt` — `--all --strict` (every legacy warning becomes a FAIL, proving the mode works);
- `artifacts/self-test.txt` — 12 fixtures;
- `artifacts/legacy-proof.txt` — the two verification runs quoted in §1.1 and §1.2, raw, showing the digests match;
- `commands.log`, `test-output.txt`, `hashes.txt`, `hashes-notes.txt` refreshed; `manifest.md` §1 command table and the per-bundle verdict table updated.

## 4. Guard rails

- Fix only F1–F5. No scope expansion, no new checks, no new dependency.
- **Do not edit any bundle under `workflow/evidence/HO-*`.** HO-011's gap is reported, not repaired; HO-001's spelling is reported, not repaired.
- Do not weaken B2/B3 in the other direction: a genuinely missing file must still FAIL. That is why F4's fixtures are mandatory.
- Do not touch `workflow/DECISIONS.md`, `workflow/STATUS.md`, `.opencode/**`, `.github/**`, the Strata checkout.
- Commit on `wp/strata-013-check-bundle` only. No PR, no `main`.

## 5. Re-check

| Step | Who | What |
|---|---|---|
| 1 | Coder | Fix F1–F5, refresh evidence, state `CODER_DONE`, push |
| 2 | Architect | Verify the 12 fixtures, the 2-FAIL `--all`, and `--all --strict` |
| 3 | QAQC (Gemini Argon, DEC-039) | Full independent review per `HO-STRATA-013-QAQC.md` |

A second failure on the **same** criterion (B2/B3 classification) escalates per
`HANDOFF_CONTRACT.md` §9.

### Coder completion (2026-11-22)

Fixed and pushed to `wp/strata-013-check-bundle`. Evidence in
`workflow/evidence/HO-STRATA-013/`.

Commands that prove F1–F5 (run from a clean tree after the RW-1 evidence
commits):

- F1/F2/F5: `python3 workflow/tools/check_bundle.py --all`
  - exit 1
  - exactly 2 FAIL lines:
    - `FAIL B3-unlisted workflow/evidence/HO-STRATA-011/artifacts/cmd-8.err.txt`
    - `FAIL B3-unlisted workflow/evidence/HO-STRATA-011/artifacts/cmd-8.out.txt`
  - zero FAILs for HO-001, HO-007, HO-008, HO-010, HO-012
  - output saved in `workflow/evidence/HO-STRATA-013/artifacts/check-all.txt`
- F3: `python3 workflow/tools/check_bundle.py --all --strict`
  - exit 1
  - every `B2-legacy-path`, `B2-external`, `B2-prose`, and `B3-path-spelling` warning upgraded to FAIL
  - `B6` and `B7` remain WARN
  - output saved in `workflow/evidence/HO-STRATA-013/artifacts/check-all-strict.txt`
- F4: `python3 workflow/tools/check_bundle.py --self-test`
  - exit 0
  - 12/12 fixtures PASS:
    - `hash-edited`, `extra-artifact`, `untracked`, `ignored`, `bad-pin`, `secret`, `clean`, `bundle-relative`, `absolute-external`, `prose`, `basename-spelling`, `malformed-separator`
  - output saved in `workflow/evidence/HO-STRATA-013/artifacts/self-test.txt`
- Self-bundle verification: `python3 workflow/tools/check_bundle.py workflow/evidence/HO-STRATA-013`
  - exit 0, `RESULT: PASS` (45 checks, 17 warnings)
- Legacy digest proof: `workflow/evidence/HO-STRATA-013/artifacts/legacy-proof.txt`
  - HO-STRATA-007: 17 verified, 0 problems from bundle dir
  - HO-STRATA-001: 21 ok, 0 mismatch, 0 missing with basename fallback

## 6. Log

- 2026-11-22 Architect: raised. AC-2 produced 32 false-positive FAILs across three
  signed bundles; all digests verify under the bundle-dir or basename rule. The
  tool's true positives (HO-011, 2 unlisted artifacts) are kept.
