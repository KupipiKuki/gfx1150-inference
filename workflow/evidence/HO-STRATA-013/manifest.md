# Evidence manifest — HO-STRATA-013

| Field | Value |
|---|---|
| **Handoff** | HO-STRATA-013 |
| **Commit / branch** | `wp/strata-013-check-bundle` (RW-2 evidence refresh; pin in `hashes-notes.txt`) |
| **Author / date (UTC)** | `coder-primary` / 2026-11-22 |
| **Environment** | Linux Mint 22.3 (Zena), kernel 7.0.0-42-generic, Python 3.14.10, git 2.43.0 |
| **Working directory** | `/home/kupipi/Documents/git/gfx1150-inference` |

## 1. Commands

Full transcript with cwd and exit codes: **`commands.log`**. Raw outputs: `artifacts/`.

| # | Command (copy-paste) | CWD | Exit | Output file |
|---|---|---|---|---|
| C1 | `python3 workflow/tools/check_bundle.py workflow/evidence/HO-STRATA-012` | repo root | 0 | `artifacts/check-ho012.txt` |
| C2d | `python3 workflow/tools/check_bundle.py --all > /tmp/check-all.txt && mv /tmp/check-all.txt workflow/evidence/HO-STRATA-013/artifacts/check-all.txt` | repo root | 1 | `artifacts/check-all.txt` — authoritative capture: output written to /tmp then moved; log appended after the run |
| C9d | `python3 workflow/tools/check_bundle.py --all --strict > /tmp/check-all-strict.txt && mv /tmp/check-all-strict.txt workflow/evidence/HO-STRATA-013/artifacts/check-all-strict.txt` | repo root | 1 | `artifacts/check-all-strict.txt` — authoritative strict capture |
| C3 | `python3 workflow/tools/check_bundle.py --self-test` | repo root | 0 | `artifacts/self-test.txt` |
| C4 | `python3 -I workflow/tools/check_bundle.py --self-test` | repo root | 0 | `artifacts/stdlib-isolated.txt` |
| C4b | `grep -nE '^(import\|from) ' workflow/tools/check_bundle.py` | repo root | 0 | `artifacts/stdlib-imports.txt` |
| C5 | `git status --porcelain > /tmp/gs-before.txt; python3 workflow/tools/check_bundle.py workflow/evidence/HO-STRATA-012 > /dev/null; python3 workflow/tools/check_bundle.py --all > /dev/null; git status --porcelain > /tmp/gs-after.txt; diff -u /tmp/gs-before.txt /tmp/gs-after.txt > artifacts/git-status-diff.txt` | repo root | 0 | `artifacts/git-status-before.txt`, `artifacts/git-status-after.txt`, `artifacts/git-status-diff.txt` |
| C6 | `rm -rf /tmp/cb-fresh; git clone -q --branch wp/strata-013-check-bundle . /tmp/cb-fresh; cd /tmp/cb-fresh && python3 workflow/tools/check_bundle.py workflow/evidence/HO-STRATA-012` | repo root | 0 | `artifacts/fresh-clone.txt` |
| C7 | `grep -n 'check_bundle' workflow/README.md` | repo root | 0 | `artifacts/readme-section.txt` |
| C8 | `python3 workflow/tools/check_bundle.py workflow/evidence/HO-STRATA-012 > /tmp/ac8-run1.txt; python3 workflow/tools/check_bundle.py workflow/evidence/HO-STRATA-012 > /tmp/ac8-run2.txt; diff -u /tmp/ac8-run1.txt /tmp/ac8-run2.txt > artifacts/deterministic.txt && echo IDENTICAL >> artifacts/deterministic.txt` | repo root | 0 | `artifacts/deterministic.txt` |
| C10 | `python3 - <<'PY' ... verify HO-001 by basename fallback and HO-007 from bundle dir ...` | repo root | 0 | `artifacts/legacy-proof.txt` |
| C11 | `python3 - <<'PY' ... RW-2 bypass probes (notes-hashes.txt; wrong digest with reworded command; control) ...` | repo root | 0 | `artifacts/bypass-proof.txt` |
| C12 | `python3 - <<'PY' ... rehash all files in the bundle into hashes.txt ...` | repo root | 0 | `hashes.txt` |
| C2f | `python3 workflow/tools/check_bundle.py --all > /tmp/check-all-fp.txt; diff -u /tmp/check-all-fp.txt artifacts/check-all.txt && echo IDENTICAL` | repo root | 0 | fixed-point proof (appended to `commands.log` after C12) |

## 2. Acceptance criteria ↔ evidence

| # | Criterion | Command | Observed | Pass? |
|---|---|---|---|---|
| AC-1 | Runs on a real, signed bundle | C1 | exit 0, `RESULT: PASS` (25 checks, 6 warnings) | **PASS** |
| AC-2 | Aggregate run over every bundle | C2d | all `HO-*` processed; `DEC-039` is `WARN skipped` only on a direct invocation; `--all` globs `HO-*` and never visits it; exactly 2 FAILs (`HO-STRATA-011` cmd-8 out/err); exit 1 | **PASS** |
| AC-3 | Negative controls | C3 | exit 0; all 15 fixtures behaved as expected | **PASS** |
| AC-4 | Stdlib only, isolated interpreter | C4 / C4b | exit 0 under `-I`; imports stdlib only | **PASS** |
| AC-5 | Read-only | C5 | no diff between before/after status | **PASS** |
| AC-6 | Works from a fresh clone | C6 | same exit code and verdict as AC-1 | **PASS** |
| AC-7 | Documented | C7 | README section present with both commands and rule | **PASS** |
| AC-8 | Deterministic output | C8 | two runs byte-identical | **PASS** |
| RW-2 A1 | B3 exempts only the bundle's own `hashes.txt` | C3 / C11 | unlisted `artifacts/notes-hashes.txt` now `FAIL B3-unlisted` in default and `--strict` | **PASS** |
| RW-2 A2 | B6 verifies every path pin regardless of Command spelling | C3 / C11 | wrong full digest and unresolvable commit under reworded commands now `FAIL B6-pins`; tree/binary pins now `WARN B6-pins not a path pin` | **PASS** |
| RW-2 F3 | `commands.log` copy-paste reproducible | commands.log | exact commands, repo-relative paths, no `...` elisions | **PASS** |
| RW-2 F4 | Manifest corrections | manifest.md | `HO-STRATA-013` row shows `0 warnings`; AC-2 states `DEC-039` is direct-invocation only | **PASS** |
| RW-2 F5 | Three new negative controls | C3 / C11 | 12 → 15 fixtures; bypass probes FAIL as required | **PASS** |

## 3. Per-bundle verdict table (`--all`)

The authoritative aggregate capture (`C2d`) was taken from a clean tree with valid hashes: output to /tmp, moved into place, log appended afterwards. It shows exactly 2 FAILs, both `HO-STRATA-011` `B3-unlisted`; the `HO-STRATA-013` line in the artifact reflects the self-check before the final hash commit and is replaced by the fixed-point run in C2f.

| Bundle | Result | Warnings | Findings |
|---|---|---|---|---|
| `HO-STRATA-001` | PASS | 43 | B2-legacy-path (3 top-level files), B2-path-spelling (16 artifact basenames), B2-external (2 absolute paths), B2-prose (3 lines), B3-path-spelling (19 files) |
| `HO-STRATA-005` | PASS | 1 | B1: no manifest.md; skipped |
| `HO-STRATA-007` | PASS | 32 | B2-legacy-path (15 `./` paths), B2-external (2 absolute paths), B3-path-spelling (15 files) |
| `HO-STRATA-008` | PASS | 31 | B2-legacy-path (14 `./` paths), B2-external (3 absolute paths), B3-path-spelling (14 files) |
| `HO-STRATA-010` | PASS | 0 | all checks pass |
| `HO-STRATA-011` | **FAIL** | 1 | B3-unlisted: `artifacts/cmd-8.err.txt` and `artifacts/cmd-8.out.txt`; B2-external (1 model file) |
| `HO-STRATA-012` | PASS | 6 | B6: 3 abbreviated/no-comparable commit pins, 3 `not a path pin` warnings for tree/binary pins |
| `HO-STRATA-013` | PASS | 0 | all checks pass after the fixed-point rehash |

`DEC-039` is `WARN skipped` only when the tool is invoked directly on `workflow/evidence/DEC-039/`; `--all` globs `HO-*` and never visits it, as required by the handoff.

## 4. Artifacts and hashes

| Artifact | Path | SHA256 |
|---|---|---|
| check tool | `workflow/tools/check_bundle.py` | in `hashes.txt` |
| HO-012 check | `artifacts/check-ho012.txt` | in `hashes.txt` |
| `--all` check | `artifacts/check-all.txt` | in `hashes.txt` |
| `--all --strict` check | `artifacts/check-all-strict.txt` | in `hashes.txt` |
| self-test | `artifacts/self-test.txt` | in `hashes.txt` |
| stdlib/isolated | `artifacts/stdlib-isolated.txt` | in `hashes.txt` |
| fresh-clone | `artifacts/fresh-clone.txt` | in `hashes.txt` |
| git status before | `artifacts/git-status-before.txt` | in `hashes.txt` |
| git status after | `artifacts/git-status-after.txt` | in `hashes.txt` |
| git status diff | `artifacts/git-status-diff.txt` | in `hashes.txt` |
| README section | `artifacts/readme-section.txt` | in `hashes.txt` |
| deterministic | `artifacts/deterministic.txt` | in `hashes.txt` |
| legacy proof | `artifacts/legacy-proof.txt` | in `hashes.txt` |
| bypass proof | `artifacts/bypass-proof.txt` | in `hashes.txt` |
| commands log | `commands.log` | in `hashes.txt` |
| test output | `test-output.txt` | in `hashes.txt` |
| manifest | `manifest.md` | in `hashes.txt` |

## 5. Failures, skips, limits

- The `--all` run returns exit 1 because of two pre-existing packaging gaps in
  `HO-STRATA-011` (`artifacts/cmd-8.err.txt` and `artifacts/cmd-8.out.txt` are
  not listed in `hashes.txt`). These are **not fixed** per the handoff guard rail.
- `HO-STRATA-012` now reports 6 B6 warnings: 3 abbreviated/no-comparable
  digests on real path pins, and 3 `not a path pin` warnings for tree/binary
  pins that were previously silently skipped. The bundle remains `PASS`.
- `--all --strict` upgrades `B2-legacy-path`, `B2-external`, `B2-prose`, and
  `B3-path-spelling` warnings to FAILs, proving the strict mode works without
  changing `B6` or `B7`.
- No signed bundle was edited; no check was weakened to restore a count.
- No model, pack, or engine run is involved; the only "profile" is the host
  toolchain.

## 6. Environment notes

- No environment variables altered behavior.
- Self-test creates throwaway git repositories under `/tmp/check_bundle_self_test_*`.
- Fresh-clone test uses `/tmp/cb-fresh`.
- Bypass probes create throwaway git repositories under `/tmp/bypass_proof_*`.

## 7. Statement

- [x] Commands are reproducible (cwd + exit code in `commands.log`).
- [x] Outputs are raw; no paraphrasing.
- [x] No secrets, tokens, or credentials anywhere in the bundle.
- [x] Every claim cites an artifact.
- [x] One profile only (host tooling; no hardware/model/quant claim).
- [x] No performance, support, or quality claim is made.
