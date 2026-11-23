# QAQC report — HO-STRATA-013 (Round 2)

| Field | Value |
|---|---|
| **Handoff** | HO-STRATA-013 (`check_bundle.py`: automate the evidence-packaging invariants), Reworks `RW-HO-STRATA-013-1` and `RW-HO-STRATA-013-2`, QAQC handoff `HO-STRATA-013-QAQC` |
| **Reviewer** | QAQC (`opencode-go/gemini-4-argon`, DEC-039) |
| **Date (UTC)** | 2026-11-22 |
| **Verdict** | **PASS** |
| **Scope reviewed** | Branch `wp/strata-013-check-bundle`, base `91eac12`, tip `429ad4d` (27 files changed, 4642 insertions, 0 deletions): `workflow/tools/check_bundle.py`, `workflow/README.md`, `workflow/evidence/HO-STRATA-013/**`, `workflow/handoffs/HO-STRATA-013*.md`, `workflow/handoffs/RW-HO-STRATA-013-{1,2}.md`, `workflow/reports/**` |

**Profile:** Host tooling only — Linux Mint 22.3 (Zena), kernel `7.0.0-42-generic`, Python `3.14.10`, git `2.43.0`. Hardware: AMD Radeon 890M (`gfx1150`) host (no GPU, model, quantization, or engine workload is invoked or claimed by this work package).

---

## 0. Round 1 outcome

Round 1 QAQC (`2800d64`) issued an erroneous **PASS** that missed two blocking tool-contract bypasses subsequently caught by the Auditor (`workflow/reports/audit/HO-STRATA-013-audit.md` §2.3, §4):

1. **A1 (`B3-hash-coverage` suffix bypass):** `check_bundle.py:408` used `if fpath.endswith("hashes.txt"): continue` instead of comparing against the bundle's own `hashes.txt`, allowing any unlisted file ending in `hashes.txt` (e.g., `artifacts/notes-hashes.txt`) to pass both default and `--strict` runs. **Which check would have caught it:** an adversarial boundary probe on the B3 self-exemption rule placing an unlisted `*hashes.txt` file inside `artifacts/` (now Check 1 below and self-test fixture `unlisted-hashes-suffix`).
2. **A2 (`B6-pins` silent skip on non-matching Command cell):** `check_bundle.py:533` gated pin verification on `re.search(r"git\s+show\s+[0-9a-fA-F]+:\S+\s*\\?\|\s*sha256sum", cmd)`, silently skipping any commit-pin row whose `Command` column used a different spelling (e.g., `git cat-file -p <sha>:<path> | sha256sum`) even when the row carried a wrong 64-hex digest or an unresolvable commit (`deadbeef`). **Which check would have caught it:** an adversarial B6 probe varying the `Command` phrasing on a wrong-digest and an unresolvable-commit row (now Check 2 below and self-test fixtures `pin-wrong-digest-reworded` / `pin-unresolvable-commit-reworded`).

Round 1 also misstated `sha256sum -c` as `17/17` instead of `18/18` (omitting the `workflow/tools/check_bundle.py` entry; in Round 2 the bundle has **19/19** entries including `artifacts/bypass-proof.txt`) and treated the `commands.log` path/elision defects (A6) and `manifest.md` warning-count/DEC-039 wording discrepancies (A4) as non-blocking without requiring an evidence refresh.

---

## 1. Round 2 checks and acceptance criteria re-run

All seven required Round 2 checks (covering `RW-HO-STRATA-013-2` A1, A2, F3, F4, F5 and `HO-STRATA-013` AC-1…AC-8) were executed independently on clean tree `429ad4d`.

| # | Check / Criterion | Command / Probe | Observed | Pass? |
|---|---|---|---|---|
| **1 (A1)** | **B3 suffix bypass** | Temp git repo `/tmp/opencode/qaqc-r2/repo_a1` with tracked `bundle/{manifest.md,commands.log,hashes.txt}` (covering `manifest.md` and `commands.log`) and UNLISTED `bundle/artifacts/notes-hashes.txt`; run `check_bundle.py` default and `--strict` | Default: exit `1`, `FAIL B3-unlisted bundle/artifacts/notes-hashes.txt`, `RESULT: FAIL (11 checks, 0 warnings)`. `--strict`: exit `1`, `FAIL B3-unlisted bundle/artifacts/notes-hashes.txt`, `RESULT: FAIL (11 checks, 0 warnings)`. The bundle's own `bundle/hashes.txt` is **not** reported as unlisted (`check_bundle.py:404,409` compares `fpath == own_hashes`). | **PASS** |
| **2 (A2)** | **B6 silent skip** | Temp git repos `/tmp/opencode/qaqc-r2/repo_a2{a,b,c}` with `pinned.txt` at HEAD (`6f3be4af…`, actual sha256 `dd432658…`) and `hashes-notes.txt` `## Commit pins` row using `git cat-file -p <sha>:pinned.txt \| sha256sum`: (2a) wrong 64-hex digest `a`×64; (2b) unresolvable commit `deadbeef`; (2c) control with correct 64-hex digest | **2a (wrong digest):** exit `1`, `FAIL B6-pins pinned.txt (recorded aaaa…aaaa, actual dd4326581f6b940a68f39de43cf25d594476d1a825573ffb5aaf7b24f6348cac)`. **2b (`deadbeef`):** exit `1`, `FAIL B6-pins unresolvable commit 'deadbeef' for pinned.txt`. **2c (control):** exit `0`, `PASS B6-pins pin ok: 6f3be4afc10bf7168fcffd1be8f62c2f4ffa1fae:pinned.txt`, `RESULT: PASS (13 checks, 0 warnings)`. | **PASS** |
| **3 (AC-3 / F5)** | **Fixtures (15 negative controls)** | `python3 workflow/tools/check_bundle.py --self-test` (`and python3 -I ...`) + code inspection of `check_bundle.py:1054-1151` | Exit `0` under default and `-I`; 15/15 fixtures print `PASS`, `RESULT: PASS (all fixtures behaved as expected)`. `fixture_unlisted_hashes_suffix` and `fixture_pin_unresolvable_commit_reworded` construct the exact defects and assert `FAIL B3-unlisted` and `FAIL B6-pins` (default + `--strict`). See Minor finding **F1** regarding `fixture_pin_wrong_digest_reworded`. | **PASS** |
| **4 (AC-1 / AC-2)** | **Regression (`HO-STRATA-012`, `--all`, `HO-STRATA-013`)** | `python3 workflow/tools/check_bundle.py workflow/evidence/HO-STRATA-012`; `python3 workflow/tools/check_bundle.py --all`; `python3 workflow/tools/check_bundle.py workflow/evidence/HO-STRATA-013` | **AC-1 (`HO-STRATA-012`):** exit `0`, `RESULT: PASS (25 checks, 6 warnings)` (3 abbreviated/no-comparable pin warnings + 3 `WARN B6-pins not a path pin` on tree/binary rows), byte-identical to `artifacts/check-ho012.txt`. **AC-2 (`--all`):** exit `1`, `RESULT: FAIL (317 checks, 114 warnings)`, byte-identical to `artifacts/check-all.txt`; **exactly 2 FAIL lines**, both `B3-unlisted` on `HO-STRATA-011` (`artifacts/cmd-8.err.txt`, `artifacts/cmd-8.out.txt`); `HO-STRATA-012` and all other `HO-*` bundles `PASS`. **Self-bundle (`HO-STRATA-013`):** exit `0`, `RESULT: PASS (30 checks, 0 warnings)`. (See Minor finding **F3** on `artifacts/check-all-strict.txt`.) | **PASS** |
| **5** | **Evidence integrity (`hashes.txt` & C12)** | `sha256sum -c workflow/evidence/HO-STRATA-013/hashes.txt`; `grep -n '/home/' workflow/evidence/HO-STRATA-013/hashes.txt`; run C12 script from `commands.log` into `/tmp` and `diff -u` against `hashes.txt` | `sha256sum -c`: **19/19 OK**, exit `0` (0 failures). `grep '/home/'`: 0 matches. C12 script output diff against `workflow/evidence/HO-STRATA-013/hashes.txt`: exit `0` (**byte-identical**). | **PASS** |
| **6 (F3)** | **Reproducibility (`commands.log`)** | Inspect `workflow/evidence/HO-STRATA-013/commands.log` (`lines 1-289`) | Zero `...` elisions anywhere in `commands.log`; `C8`, `C10`, `C11`, and `C12` are recorded in full. `C2d` (`line 8`) and `C9d` (`line 13`) move `/tmp/check-all*.txt` to `workflow/evidence/HO-STRATA-013/artifacts/check-all*.txt`, which resolves directly from `cwd: /home/kupipi/Documents/git/gfx1150-inference` (repo root). | **PASS** |
| **7 (F4)** | **Documentation & manifest accuracy** | Inspect `manifest.md` §2, §3 and `RW-HO-STRATA-013-1.md` §1.4 | `manifest.md` §3 (`line 63`) row for `HO-STRATA-013` states `PASS | 0 | all checks pass after the fixed-point rehash`. `manifest.md` §2 AC-2 (`line 37`) and §3 (`line 65`) state `DEC-039` is `WARN skipped` only on a direct invocation and `--all` globs `HO-*` and never visits it. `RW-HO-STRATA-013-1.md` §1.4 (`lines 78-80`) attributes the exit-4 absolute-path guard to the evidence-generation script, not `check_bundle.py`. | **PASS** |

---

## 2. Probe commands and verbatim outputs

### 2.1 Check 1 (A1 — B3 suffix bypass) and Check 2 (A2 — B6 silent skip)

```text
$ python3 - <<'PY'
import hashlib, shutil, subprocess, sys
from pathlib import Path

tool = Path("workflow/tools/check_bundle.py").resolve()
base = Path("/tmp/opencode/qaqc-r2")
shutil.rmtree(base, ignore_errors=True)
base.mkdir(parents=True, exist_ok=True)

def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)

def git_init(repo):
    repo.mkdir(parents=True, exist_ok=True)
    run(["git", "init"], cwd=repo)
    run(["git", "config", "user.email", "qaqc@example.com"], cwd=repo)
    run(["git", "config", "user.name", "QAQC"], cwd=repo)

def commit_all(repo, msg):
    run(["git", "add", "-A"], cwd=repo)
    run(["git", "commit", "-m", msg], cwd=repo)

def sha256_file(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

# CHECK 1: A1 B3 suffix bypass
repo_a1 = base / "repo_a1"
git_init(repo_a1)
bundle_a1 = repo_a1 / "bundle"
(bundle_a1 / "artifacts").mkdir(parents=True)
(bundle_a1 / "manifest.md").write_text("# Manifest\ncommands.log\n")
(bundle_a1 / "commands.log").write_text("cmd\n")
(bundle_a1 / "artifacts" / "notes-hashes.txt").write_text("unlisted notes\n")
(bundle_a1 / "hashes.txt").write_text(
    f"{sha256_file(bundle_a1/'manifest.md')}  bundle/manifest.md\n"
    f"{sha256_file(bundle_a1/'commands.log')}  bundle/commands.log\n"
)
commit_all(repo_a1, "a1 setup")

r_a1_def = run([sys.executable, str(tool), str(bundle_a1)], cwd=repo_a1)
r_a1_str = run([sys.executable, str(tool), "--strict", str(bundle_a1)], cwd=repo_a1)
print("=== CHECK 1 (A1 default) exit:", r_a1_def.returncode)
print(r_a1_def.stdout.strip())
print("=== CHECK 1 (A1 --strict) exit:", r_a1_str.returncode)
print(r_a1_str.stdout.strip())

# CHECK 2: A2 B6 silent skip
def make_a2_bundle(repo, commit_val, digest_val):
    b = repo / "bundle"
    b.mkdir(parents=True, exist_ok=True)
    (b / "manifest.md").write_text("# Manifest\ncommands.log\n")
    (b / "commands.log").write_text("cmd\n")
    (b / "hashes-notes.txt").write_text(
        "## Commit pins\n\n"
        "| File | Repository | Commit | Command | Digest |\n"
        "|---|---|---|---|---|\n"
        f"| pinned.txt | gfx1150-inference | {commit_val} | git cat-file -p {commit_val}:pinned.txt \\| sha256sum | {digest_val} |\n"
    )
    (b / "hashes.txt").write_text(
        f"{sha256_file(b/'manifest.md')}  bundle/manifest.md\n"
        f"{sha256_file(b/'commands.log')}  bundle/commands.log\n"
        f"{sha256_file(b/'hashes-notes.txt')}  bundle/hashes-notes.txt\n"
    )
    commit_all(repo, "bundle")
    return b

repo_a2a = base / "repo_a2a"
git_init(repo_a2a)
(repo_a2a / "pinned.txt").write_text("real file content\n")
commit_all(repo_a2a, "initial file")
sha_head = run(["git", "rev-parse", "HEAD"], cwd=repo_a2a).stdout.strip()
real_digest = sha256_file(repo_a2a / "pinned.txt")
b_a2a = make_a2_bundle(repo_a2a, sha_head, "a" * 64)
r_a2a = run([sys.executable, str(tool), str(b_a2a)], cwd=repo_a2a)
print("\n=== CHECK 2a (A2 wrong digest, git cat-file -p) exit:", r_a2a.returncode)
print(r_a2a.stdout.strip())

repo_a2b = base / "repo_a2b"
git_init(repo_a2b)
(repo_a2b / "pinned.txt").write_text("real file content\n")
commit_all(repo_a2b, "initial file")
b_a2b = make_a2_bundle(repo_a2b, "deadbeef", real_digest)
r_a2b = run([sys.executable, str(tool), str(b_a2b)], cwd=repo_a2b)
print("\n=== CHECK 2b (A2 unresolvable commit deadbeef) exit:", r_a2b.returncode)
print(r_a2b.stdout.strip())

repo_a2c = base / "repo_a2c"
git_init(repo_a2c)
(repo_a2c / "pinned.txt").write_text("real file content\n")
commit_all(repo_a2c, "initial file")
sha_head_c = run(["git", "rev-parse", "HEAD"], cwd=repo_a2c).stdout.strip()
b_a2c = make_a2_bundle(repo_a2c, sha_head_c, real_digest)
r_a2c = run([sys.executable, str(tool), str(b_a2c)], cwd=repo_a2c)
print("\n=== CHECK 2c (A2 control: correct digest, git cat-file -p) exit:", r_a2c.returncode)
print(r_a2c.stdout.strip())
PY
=== CHECK 1 (A1 default) exit: 1
PASS B1-structure manifest.md exists
PASS B1-structure hashes.txt exists
PASS B1-structure commands.log exists
PASS B2-hash-verify ok: bundle/manifest.md
PASS B2-hash-verify ok: bundle/commands.log
FAIL B3-unlisted bundle/artifacts/notes-hashes.txt
PASS B4-tracked all files tracked
PASS B4-tracked git status clean
PASS B5-not-ignored no bundle file ignored
PASS B7-secrets no credential-shaped strings
PASS B8-read-only git status unchanged
RESULT: FAIL (11 checks, 0 warnings)
=== CHECK 1 (A1 --strict) exit: 1
PASS B1-structure manifest.md exists
PASS B1-structure hashes.txt exists
PASS B1-structure commands.log exists
PASS B2-hash-verify ok: bundle/manifest.md
PASS B2-hash-verify ok: bundle/commands.log
FAIL B3-unlisted bundle/artifacts/notes-hashes.txt
PASS B4-tracked all files tracked
PASS B4-tracked git status clean
PASS B5-not-ignored no bundle file ignored
PASS B7-secrets no credential-shaped strings
PASS B8-read-only git status unchanged
RESULT: FAIL (11 checks, 0 warnings)

=== CHECK 2a (A2 wrong digest, git cat-file -p) exit: 1
PASS B1-structure manifest.md exists
PASS B1-structure hashes.txt exists
PASS B1-structure commands.log exists
PASS B2-hash-verify ok: bundle/manifest.md
PASS B2-hash-verify ok: bundle/commands.log
PASS B2-hash-verify ok: bundle/hashes-notes.txt
PASS B3-hash-coverage all files listed
PASS B4-tracked all files tracked
PASS B4-tracked git status clean
PASS B5-not-ignored no bundle file ignored
FAIL B6-pins pinned.txt (recorded aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa, actual dd4326581f6b940a68f39de43cf25d594476d1a825573ffb5aaf7b24f6348cac)
PASS B7-secrets no credential-shaped strings
PASS B8-read-only git status unchanged
RESULT: FAIL (13 checks, 0 warnings)

=== CHECK 2b (A2 unresolvable commit deadbeef) exit: 1
PASS B1-structure manifest.md exists
PASS B1-structure hashes.txt exists
PASS B1-structure commands.log exists
PASS B2-hash-verify ok: bundle/manifest.md
PASS B2-hash-verify ok: bundle/commands.log
PASS B2-hash-verify ok: bundle/hashes-notes.txt
PASS B3-hash-coverage all files listed
PASS B4-tracked all files tracked
PASS B4-tracked git status clean
PASS B5-not-ignored no bundle file ignored
FAIL B6-pins unresolvable commit 'deadbeef' for pinned.txt
PASS B7-secrets no credential-shaped strings
PASS B8-read-only git status unchanged
RESULT: FAIL (13 checks, 0 warnings)

=== CHECK 2c (A2 control: correct digest, git cat-file -p) exit: 0
PASS B1-structure manifest.md exists
PASS B1-structure hashes.txt exists
PASS B1-structure commands.log exists
PASS B2-hash-verify ok: bundle/manifest.md
PASS B2-hash-verify ok: bundle/commands.log
PASS B2-hash-verify ok: bundle/hashes-notes.txt
PASS B3-hash-coverage all files listed
PASS B4-tracked all files tracked
PASS B4-tracked git status clean
PASS B5-not-ignored no bundle file ignored
PASS B6-pins pin ok: 6f3be4afc10bf7168fcffd1be8f62c2f4ffa1fae:pinned.txt
PASS B7-secrets no credential-shaped strings
PASS B8-read-only git status unchanged
RESULT: PASS (13 checks, 0 warnings)
```

### 2.2 Check 3 (Self-test), Check 4 (Regression), and Check 5 (Hashes & C12)

```text
$ python3 workflow/tools/check_bundle.py --self-test
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
PASS unlisted-hashes-suffix
PASS pin-wrong-digest-reworded
PASS pin-unresolvable-commit-reworded
RESULT: PASS (all fixtures behaved as expected)
(exit: 0)

$ python3 workflow/tools/check_bundle.py workflow/evidence/HO-STRATA-012 > /tmp/opencode/qaqc-r2/ho012.txt
(exit: 0)
$ diff -u /tmp/opencode/qaqc-r2/ho012.txt workflow/evidence/HO-STRATA-013/artifacts/check-ho012.txt
(exit: 0 — byte-identical; RESULT: PASS (25 checks, 6 warnings))

$ python3 workflow/tools/check_bundle.py --all > /tmp/opencode/qaqc-r2/all.txt
(exit: 1)
$ diff -u /tmp/opencode/qaqc-r2/all.txt workflow/evidence/HO-STRATA-013/artifacts/check-all.txt
(exit: 0 — byte-identical)
$ grep -n "^FAIL " /tmp/opencode/qaqc-r2/all.txt
266:FAIL B3-unlisted workflow/evidence/HO-STRATA-011/artifacts/cmd-8.err.txt
267:FAIL B3-unlisted workflow/evidence/HO-STRATA-011/artifacts/cmd-8.out.txt
$ grep -n "RESULT:" /tmp/opencode/qaqc-r2/all.txt
73:HO-STRATA-001: RESULT: PASS (72 checks, 43 warnings)
76:HO-STRATA-005: RESULT: PASS (1 checks, 1 warnings)
135:HO-STRATA-007: RESULT: PASS (57 checks, 32 warnings)
193:HO-STRATA-008: RESULT: PASS (56 checks, 31 warnings)
219:HO-STRATA-010: RESULT: PASS (24 checks, 0 warnings)
273:HO-STRATA-011: RESULT: FAIL (52 checks, 1 warnings)
300:HO-STRATA-012: RESULT: PASS (25 checks, 6 warnings)
332:HO-STRATA-013: RESULT: PASS (30 checks, 0 warnings)
334:RESULT: FAIL (317 checks, 114 warnings)

$ sha256sum -c workflow/evidence/HO-STRATA-013/hashes.txt
workflow/evidence/HO-STRATA-013/artifacts/bypass-proof.txt: OK
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
workflow/tools/check_bundle.py: OK
(exit: 0 — 19/19 OK; grep '/home/' returns 0 matches; C12 output into /tmp diffs byte-identical to hashes.txt)
```

---

## 3. Diff and guard-rail review

- [x] Diff (`git diff 91eac12..429ad4d --stat`) is within scope; no unrelated files.
- [x] No existing signed evidence bundle (`HO-001` through `HO-012` or `DEC-039`) was modified.
- [x] `workflow/DECISIONS.md`, `workflow/STATUS.md`, `.opencode/**`, `.github/**`, and `/home/kupipi/Documents/git/strata` were not touched.
- [x] No new dependencies without approval (stdlib only, verified with `python3 -I` and import grep; no network calls).
- [x] No secrets/tokens in the diff, logs, or evidence (`PASS B7-secrets` across all bundles).
- [x] Both blocking defects from `RW-HO-STRATA-013-2` (A1 B3 suffix bypass and A2 B6 silent skip) are genuinely fixed in `workflow/tools/check_bundle.py` and verified by independent probes.

---

## 4. Findings (severity order)

| # | Severity | Finding | File:line / evidence | Required action |
|---|---|---|---|---|
| F1 | Minor | In `fixture_pin_wrong_digest_reworded` (`workflow/tools/check_bundle.py:1079-1100`), the file is committed in the throwaway repo at `bundle/artifact.txt`, but the `## Commit pins` table row writes `File` as `artifact.txt` (`git cat-file -p <commit>:artifact.txt \| sha256sum`). Consequently, inside `--self-test`, that fixture triggers `FAIL B6-pins unresolvable <commit>:artifact.txt` (`check_bundle.py:568`) before reaching the digest-mismatch branch (`check_bundle.py:578`). Note that: (1) the fixture still proves the reworded `git cat-file -p` row is no longer silently skipped by `_parse_commit_pins_table`, and (2) the wrong-digest branch at `check_bundle.py:578` works properly and is verified both by `commands.log` C11 (`artifacts/bypass-proof.txt` Probe 2, which uses `bundle/artifact.txt`) and by QAQC Check 2a above. Also, `_write_hashes` is omitted in `fixture_pin_wrong_digest_reworded` and `fixture_pin_unresolvable_commit_reworded` (just as in `fixture_bad_pin`). | `workflow/tools/check_bundle.py:1085-1100` | None required for gate (the production B6 check at `:577-579` and `artifacts/bypass-proof.txt` Probe 2 are both verified). |
| F2 | Minor | In `_parse_commit_pins_table` (`workflow/tools/check_bundle.py:652-664`), the parser checks `re.search(r"git\s+show\s+([0-9a-fA-F]+):(\S+)", cmd)` first and falls back to the `Commit` and `File`/`Path` columns when `Command` is not `git show <hex>:<path>`. This satisfies all `HO-*` tables and all A2 probes, though if a future row had a `git show` command whose `<sha>:<path>` disagreed with the `Commit`/`File` columns, `cmd` would take precedence. | `workflow/tools/check_bundle.py:652-664` | None (documented for Auditor awareness). |
| F3 | Minor | While `artifacts/check-all.txt` was re-verified after the final C12 rehash (`C2f`) and is a byte-exact fixed point on clean tree `429ad4d`, `artifacts/check-all-strict.txt` (and `artifacts/git-status-before.txt` / `after.txt`) was captured during the pre-commit refresh sequence (`C9d`/`C5`), so the `HO-STRATA-013` section inside `artifacts/check-all-strict.txt` records the pre-rehash state of `check-all.txt` (`FAIL B2-hash-mismatch`, `FAIL B3-path-spelling`, `FAIL B4-tracked`). Running `check_bundle.py --all --strict` on the committed clean tree `429ad4d` produces identical results for `HO-001`..`HO-012` and `HO-STRATA-013: RESULT: PASS (30 checks, 0 warnings)`. | `workflow/evidence/HO-STRATA-013/artifacts/check-all-strict.txt:307-332` | None (authoritative `--all` fixed point `artifacts/check-all.txt` and `sha256sum -c` 19/19 are clean). |

No Blocker or Major findings.

---

## 5. Verdict and next state

- **PASS** → `AUDIT_REVIEW`; attach this report and the evidence path.

### QAQC_TO_AUDITOR (embedded per DEC-018)

| Field | Value |
|---|---|
| **ID** | HO-STRATA-013-AUDIT-R2 (embedded in `HO-STRATA-013-qaqc.md`) |
| **Type** | QAQC_TO_AUDITOR |
| **State** | AUDIT_REVIEW |
| **Date (UTC)** | 2026-11-22 |
| **From → To** | QAQC (`opencode-go/gemini-4-argon`) → Auditor (`opencode-go/deepseek-v4.1-flash`, WAIVER-001) |
| **Handoff** | `workflow/handoffs/HO-STRATA-013.md` (with `RW-HO-STRATA-013-1.md`, `RW-HO-STRATA-013-2.md`, and `HO-STRATA-013-QAQC.md`) |
| **Branch / commit** | `wp/strata-013-check-bundle` @ `429ad4d` (base `91eac12`) |
| **QAQC report** | `workflow/reports/qaqc/HO-STRATA-013-qaqc.md` |
| **Evidence bundle** | `workflow/evidence/HO-STRATA-013/` (19/19 hashes verified via `sha256sum -c`; C12 rehash script reproduces `hashes.txt` byte-identically; `check_bundle.py` self-check `RESULT: PASS (30 checks, 0 warnings)`) |
| **Summary** | All 7 Round 2 verification checks (A1 B3 suffix bypass probe, A2 B6 silent skip probes + control, 15 `--self-test` fixtures, AC-1/AC-2 regression + `--all` fixed-point diff, 19/19 `sha256sum -c` + C12 reproduction, `commands.log` copy-paste reproducibility, and `manifest.md`/`RW-1` doc corrections) passed on clean tree `429ad4d`. Three Minor findings (F1–F3), zero Blockers/Majors. |

---

## 6. Statement

I did not modify code, tests, docs, evidence, handoffs, or configuration. This report (`workflow/reports/qaqc/HO-STRATA-013-qaqc.md`) is the only file I wrote in the repository.
