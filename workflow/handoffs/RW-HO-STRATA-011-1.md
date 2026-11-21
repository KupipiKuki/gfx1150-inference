# RW-HO-STRATA-011-1 — the oracle is right; the bundle is not shippable

| Field | Value |
|---|---|
| **ID** | RW-HO-STRATA-011-1 |
| **Type** | REWORK |
| **State** | **CLOSED** — all four findings resolved; QAQC re-pass `c73b424`; fresh-clone 41/41 |
| **Created (UTC)** | 2026-11-19 |
| **From → To** | QAQC (`qaqc`) → Primary Coder (`coder-primary`) |
| **Original handoff** | HO-STRATA-011, commit `bc93b56` |
| **Re-checker** | QAQC (`qaqc`), then auditor |

## Summary

Every measured value reproduces bit-for-bit (pack identity, `gen:` line, both
dump digests, parity table). The failures are **bundle integrity**: two
artifacts were never committed, the hash list does not verify from the stated
working directory, one helper still carries the previous family's constants, and
the commit pins predate the change they are meant to pin.

## 1. Failed criteria

| # | Criterion | Evidence |
|---|---|---|
| **F1** | AC-7 — evidence bundle complete; hashes verify | `olmoe_p1_4_layers.bin` (`3c72636a…`) and `olmoe_p1_logits.bin` (`a73e3eae…`) are **ignored by git** (`git status --ignored`): `.gitignore` matches `*.bin`. `git ls-tree bc93b56 workflow/evidence/HO-STRATA-011/artifacts/runs/` lists only the four `.txt` files. The bundle cannot be verified from a fresh clone. |
| **F2** | AC-7 — hashes verify from the stated CWD | `sha256sum -c workflow/evidence/HO-STRATA-011/hashes.txt` from the repo root exits 1 with 37/38 files unread: the list uses bundle-relative paths (`artifacts/…`) while `manifest.md` and `commands.log` declare `CWD: repo root`. HO-010 uses repo-root-relative paths. |
| **F3** | AC-5/AC-7 — helper reproducibility | `artifacts/check_layers.py` hardcodes `n_layer = 28` (DeepSeek) and crashes on OLMoE: `ValueError: cannot reshape array of size 131072 into shape (4,28,2048)`. Commands `[0]` and `[7]` are recorded as `python3 - <path>` with the stdin script absent, so neither can be re-run. |
| **F4** | AC-7 — pins carry the right commit and digest | `hashes-notes.txt` pins `workflow/MODELS.md`, `planning/strata-engine/13-…` and `DECISIONS.md` at `8ce28c4e`, which predates the OLMoE row and DEC-031 (`6679e938`). `manifest.md` §3 writes "(in hashes.txt)" for 11 rows instead of the digest. `cmd-9.out.txt` prints a relative `build-hip/strata`. |

## 2. Required fix

1. **F1.** Add `!workflow/evidence/**/*.bin` to `.gitignore` beside the existing
   `!workflow/evidence/**/*.log` negation (DEC-008), then `git add` the layer and
   logits dumps normally. Delete the transient `olmoe_p1_logits_run2.bin` after
   the comparison — one logits file is the artifact, the second is a check input.
2. **F2.** Rewrite `hashes.txt` with repo-root-relative paths
   (`workflow/evidence/HO-STRATA-011/…`), then run
   `sha256sum -c workflow/evidence/HO-STRATA-011/hashes.txt` **from the repo root**
   and record `exit=0`. Update the manifest's §1 command to match.
3. **F3.** Make `artifacts/check_layers.py` family-agnostic: read the layer count
   from the file size and a `--layers` argument, or from a shape sidecar; no
   hardcoded 28. Use it as the recorded command `[7]`. Replace `python3 - <path>`
   in command `[0]` with a committed script or a complete `python3 -c "…"` line
   that includes the code.
4. **F4.** Pin `MODELS.md`, `13-…` and `DECISIONS.md` at the commit that carries
   the OLMoE row and DEC-031 (`6679e938`), recording both the commit and the
   `git show <sha>:<path> | sha256sum` digest. Replace "(in hashes.txt)" with the
   actual digest in the manifest §3. Re-run command `[9]` so it prints the
   absolute binary path.

## 3. Guard rails

- Do not re-measure or regenerate the dumps; if a re-run produces a different
  digest, stop and report it as a deviation.
- Fix only F1–F4 plus the recomputed hashes. No engine change, no downloads, no
  tolerance, no new claim.
- If `.gitignore` changes, keep the two negations adjacent with a one-line reason
  each.

## 4. Evidence to prove the fix

- `git ls-tree -r HEAD workflow/evidence/HO-STRATA-011/artifacts/runs/` lists both
  dumps.
- `sha256sum -c workflow/evidence/HO-STRATA-011/hashes.txt` from the repo root →
  all OK, exit 0, with the new count.
- `python3 artifacts/check_layers.py … --layers 16` → shape `(4,16,2048)`,
  `[(0,16),(1,16),(2,16),(3,16)]`, no nan/inf.
- `hashes-notes.txt` pins with both commit and digest at `6679e938`.
- Fresh-clone test: `git archive HEAD | tar -x -C /tmp/…` then `sha256sum -c`
  passes (proves nothing depends on ignored or untracked files).

## 5. Acknowledgment

| Role | Date | Note |
|---|---|---|
| Coder | 2026-11-20 | F1–F4 fixed; bundle verifies from repo root and fresh clone; state remains `CODER_DONE`. |
| QAQC (re-pass) | 2026-11-19 | PASS |
| Auditor | 2026-11-19 | PASS (WAIVED) |

**Escalation:** a second failure on the same criterion goes to the architect.
