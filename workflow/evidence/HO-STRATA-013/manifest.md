# Evidence manifest — HO-STRATA-013

| Field | Value |
|---|---|
| **Handoff** | HO-STRATA-013 |
| **Commit / branch** | `wp/strata-013-check-bundle` (RW-1 evidence commit; pin in `hashes-notes.txt`) |
| **Author / date (UTC)** | `coder-primary` / 2026-11-22 |
| **Environment** | Linux Mint 22.3 (Zena), kernel 7.0.0-42-generic, Python 3.14.10, git 2.43.0 |
| **Working directory** | `/home/kupipi/Documents/git/gfx1150-inference` |

## 1. Commands

Full transcript with cwd and exit codes: **`commands.log`**. Raw outputs: `artifacts/`.

| # | Command (copy-paste) | CWD | Exit | Output file |
|---|---|---|---|---|
| C1 | `python3 workflow/tools/check_bundle.py workflow/evidence/HO-STRATA-012` | repo root | 0 | `artifacts/check-ho012.txt` |
| C2 | `python3 workflow/tools/check_bundle.py --all` | repo root | 1 | `artifacts/check-all.txt` |
| C3 | `python3 workflow/tools/check_bundle.py --self-test` | repo root | 0 | `artifacts/self-test.txt` |
| C4 | `python3 -I workflow/tools/check_bundle.py --self-test` | repo root | 0 | `artifacts/stdlib-isolated.txt` |
| C5 | `git status --porcelain > /tmp/git-status-before.txt; run C1 and C2; git status --porcelain > /tmp/git-status-after.txt; diff` | repo root | 0 | `artifacts/git-status-before.txt`, `artifacts/git-status-after.txt` |
| C6 | `git clone --branch wp/strata-013-check-bundle . /tmp/cb-fresh; python3 /tmp/cb-fresh/workflow/tools/check_bundle.py /tmp/cb-fresh/workflow/evidence/HO-STRATA-012` | repo root | 0 | `artifacts/fresh-clone.txt` |
| C7 | `grep -n "check_bundle" workflow/README.md` | repo root | 0 | `artifacts/readme-section.txt` |
| C8 | `python3 workflow/tools/check_bundle.py workflow/evidence/HO-STRATA-012 > /tmp/ac8-run1.txt; ... > /tmp/ac8-run2.txt; diff` | repo root | 0 | `artifacts/deterministic.txt` |
| C9 | `python3 workflow/tools/check_bundle.py --all --strict` | repo root | 1 | `artifacts/check-all-strict.txt` |
| C10 | `python3 - <<'EOF' ... verify HO-STRATA-007 and HO-STRATA-001 ...` | bundle dirs | 0 | `artifacts/legacy-proof.txt` |

## 2. Acceptance criteria ↔ evidence

| # | Criterion | Command | Observed | Pass? |
|---|---|---|---|---|
| AC-1 | Runs on a real, signed bundle | C1 | exit 0, `RESULT: PASS` (22 checks, 3 warnings) | **PASS** |
| AC-2 | Aggregate run over every bundle | C2 | all `HO-*` processed; `DEC-039` WARN skipped; exactly 2 FAILs (`HO-STRATA-011` cmd-8 out/err); exit 1 | **PASS** |
| AC-3 | Negative controls | C3 | exit 0; all 12 fixtures behaved as expected | **PASS** |
| AC-4 | Stdlib only, isolated interpreter | C4 | exit 0 under `-I`; imports stdlib only | **PASS** |
| AC-5 | Read-only | C5 | no diff between before/after status | **PASS** |
| AC-6 | Works from a fresh clone | C6 | same exit code and verdict as AC-1 | **PASS** |
| AC-7 | Documented | C7 | README section present with both commands and rule | **PASS** |
| AC-8 | Deterministic output | C8 | two runs byte-identical | **PASS** |
| RW-1 F1–F5 | Legacy path classification fixed | C2, C9, C3, C10 | `--all` has 2 FAILs on `HO-STRATA-011`; `--all --strict` upgrades legacy warnings; self-test covers all new codes; legacy proof verifies digests | **PASS** |

## 3. Per-bundle verdict table (`--all`)

The pre-commit `--all` capture shows assembly-time FAILs for this bundle (stale
hashes, dirty tree); the post-commit re-run (C2b, `artifacts/check-all.txt`)
is the authoritative capture and shows exactly 2 FAILs, both HO-STRATA-011
`B3-unlisted`.

| Bundle | Result | Warnings | Findings |
|---|---|---|---|---|
| `HO-STRATA-001` | PASS | 43 | B2-legacy-path (3 top-level files), B2-path-spelling (16 artifact basenames), B2-external (2 absolute paths), B2-prose (3 lines), B3-path-spelling (19 files) |
| `HO-STRATA-005` | PASS | 1 | B1: no manifest.md; skipped |
| `HO-STRATA-007` | PASS | 32 | B2-legacy-path (15 `./` paths), B2-external (2 absolute paths), B3-path-spelling (15 files) |
| `HO-STRATA-008` | PASS | 31 | B2-legacy-path (14 `./` paths), B2-external (3 absolute paths), B3-path-spelling (14 files) |
| `HO-STRATA-010` | PASS | 0 | all checks pass |
| `HO-STRATA-011` | **FAIL** | 1 | B3-unlisted: `artifacts/cmd-8.err.txt` and `artifacts/cmd-8.out.txt`; B2-external (1 model file) |
| `HO-STRATA-012` | PASS | 3 | B6: 3 abbreviated/no-comparable commit pins |
| `HO-STRATA-013` | PASS | 2 | B6: 2 abbreviated commit pins for DECISIONS.md/README.md |

`DEC-039` is WARN skipped (no `manifest.md`), as required by the handoff.

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
| README section | `artifacts/readme-section.txt` | in `hashes.txt` |
| deterministic | `artifacts/deterministic.txt` | in `hashes.txt` |
| legacy proof | `artifacts/legacy-proof.txt` | in `hashes.txt` |
| commands log | `commands.log` | in `hashes.txt` |
| test output | `test-output.txt` | in `hashes.txt` |

## 5. Failures, skips, limits

- The `--all` run returns exit 1 because of two pre-existing packaging gaps in
  `HO-STRATA-011` (`artifacts/cmd-8.err.txt` and `artifacts/cmd-8.out.txt` are
  not listed in `hashes.txt`). These are **not fixed** per the handoff guard rail.
- `HO-STRATA-001`, `HO-STRATA-007`, and `HO-STRATA-008` now PASS with warnings
  only; every listed digest verifies under the bundle-dir or basename-fallback
  rule (proof in `artifacts/legacy-proof.txt`).
- `--all --strict` upgrades `B2-legacy-path`, `B2-external`, `B2-prose`, and
  `B3-path-spelling` warnings to FAILs, proving the strict mode works without
  changing `B6` or `B7`.
- `HO-STRATA-012` reports three B6 WARNs for abbreviated or text-only commit
  pins; this is expected and does not make the run FAIL.
- No model, pack, or engine run is involved; the only "profile" is the host
  toolchain.

## 6. Environment notes

- No environment variables altered behavior.
- Self-test creates throwaway git repositories under `/tmp/check_bundle_self_test_*`.
- Fresh-clone test uses `/tmp/cb-fresh`.

## 7. Statement

- [x] Commands are reproducible (cwd + exit code in `commands.log`).
- [x] Outputs are raw; no paraphrasing.
- [x] No secrets, tokens, or credentials anywhere in the bundle.
- [x] Every claim cites an artifact.
- [x] One profile only (host tooling; no hardware/model/quant claim).
- [x] No performance, support, or quality claim is made.
