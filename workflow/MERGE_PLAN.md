# Merge plan — HO-STRATA-001 + HO-STRATA-007 → `main`

**Status:** ready to execute · **Author:** architect · **Date:** 2026-11-16
**Decisions:** DEC-015 (selective merge), DEC-017 (007 authorized), DEC-019 (owner accepts 007 without a second audit)

---

## 1. Why a plan rather than a plain merge

Audit finding **P1** flagged that the work-package branches sit on
`research/strata-memo`, so a naive merge would fast-forward four workstreams
onto `main` without review. This plan verifies what actually lands and confirms
that nothing is an unreviewed change.

## 2. Verified state

| Item | Value |
|---|---|
| Target | `origin/main` (`c68cb27`) |
| Source | `wp/strata-007-qwen35moe-lowtier` (`776b6ff`, contains HO-001 @ `750dd2f`) |
| Merge base | `a6166f7` (`research/strata-memo` tip) |
| Files changed | **107** (106 added, 1 modified) |
| Insertions | 78,810 |
| Conflicts | **none** — `git merge-tree --write-tree origin/main HEAD` returned a clean tree (`bf4235f`), exit 0 |
| `.gitignore` on `main` since the base | unchanged (empty diff), so the only modification applies cleanly |

`main` tracks **zero** files under `workflow/`, `planning/` or `research/`, so the
merge is a pure union: no existing project file is replaced, deleted or
rewritten.

## 3. What lands, by workstream

| Workstream | Paths | Reviewed by |
|---|---|---|
| **HO-001** build/support | `workflow/evidence/HO-STRATA-001/` (19 artifacts + manifest/hashes), `HO-STRATA-001*.md`, QAQC + audit reports | QAQC (Gemini), auditor, Mistral 4 owner audit (grade A, 8/8, 19/19 hashes) |
| **HO-007** qwen35moe baseline | `workflow/evidence/HO-STRATA-007/` (17 hashes OK), `HO-STRATA-007*.md`, QAQC + audit reports, approval | QAQC (Gemini), auditor (WAIVED), architect SIGNED |
| **Process** | `workflow/ENGINEERING_WORKFLOW.md`, `HANDOFF_CONTRACT.md`, `MODEL_POLICY.md`, `OWNER_AUDIT_CHECKLIST.md`, `STATUS.md`, `DECISIONS.md`, `check_model_policy.py`, `templates/`, `handoffs/OT-STRATA-001.md` | architect + auditor |
| **Planning** | `planning/strata-engine/00–12` | plan audit (document 07) |
| **Research** | `research/strata-memo/` | Mistral pilot + auditor memo (prior project) |
| **Agent config** | `.opencode/agents/`, `.opencode/opencode.json`, `.opencode/skills/` | architect |
| **`.gitignore`** | `!workflow/evidence/**/*.log` negation (DEC-008) | HO-001 rework |

Nothing in the list is unreviewed: the only handoff content without a QAQC pass
is `HO-STRATA-005`/`HO-STRATA-006`, which are `PROPOSED`/`DEFERRED` planning
documents and carry no result.

## 4. The `.gitignore` change (must land)

```diff
 # Logs
 *.log
+# …except the evidence bundle's raw command output, which the handoff contract
+# requires as a tracked artifact (HANDOFF_CONTRACT.md §7; DEC-008).
+!workflow/evidence/**/*.log
```

Verified behaviour on the merge result:

- `workflow/evidence/**/commands.log` → **tracked** (`!…` rule wins).
- `build.log` at repo root → **still ignored** (`*.log`).
- No parent directory is excluded, so the negation is effective.

Without this hunk the evidence logs would be ignored on a fresh clone.

## 5. Merge steps

```bash
cd /home/kupipi/Documents/git/gfx1150-inference
git fetch origin
git switch main && git reset --hard origin/main     # local main is 41 behind
git merge --no-ff wp/strata-007-qwen35moe-lowtier \
  -m "merge: HO-STRATA-001 build/support + HO-STRATA-007 qwen35moe baseline

HO-001: gfx1150 build, support surface (qwen4exp qwen35moe), engine boundary.
SIGNED 2026-11-16; Mistral 4 owner audit grade A, 8/8 criteria, 19/19 hashes.
HO-007: Qwen3.6-35B-A3B UD-Q4_K_XL loads and generates 32 deterministic tokens.
SIGNED 2026-11-16; QAQC (Gemini) PASS, auditor (WAIVED) PASS.
Evidence: workflow/evidence/HO-STRATA-001/, workflow/evidence/HO-STRATA-007/.
No performance, support or quality claim; one profile each."

git push origin main
```

Then verify:

```bash
git log --oneline -3
git ls-files workflow/evidence | wc -l          # expect 36
git check-ignore build.log                       # still ignored
cd workflow/evidence/HO-STRATA-007 && sha256sum -c hashes.txt
cd ../HO-STRATA-001 && sha256sum -c hashes.txt
```

## 6. Rollback

Before the push: `git reset --hard origin/main`.
After the push: `git revert -m 1 <merge-sha>` (a documented revert, not a force-push).

## 7. Not in this merge

- **HO-002/003/004** — blocked (DEC-016); no content to merge.
- **HO-005** — route decision; starts after this merge.
- **HO-006** — deferred; its planning file is included, its investigation is not.
- **Architect model config** — `MODEL_POLICY.md` lands with the architect role
  still unset; `--strict` continues to exit 2 under WAIVER-001. Closing that is a
  separate session/model change, not a merge blocker.

## 8. Executed (2026-11-16)

- **Merge commit:** `fe54d79` (`--no-ff`), tree identical to the verified
  `merge-tree` result; pushed as `origin/merge/strata-001-007`.
- **Local `main`:** reset to `origin/main` (`eccdc39`) after the merge, so the
  only copy of the merge commit is the remote branch.
- **`main` is protected:** the direct push was rejected —
  `GH013: 3 of 4 required status checks have not succeeded`. The repo's history
  is PR-based (`Merge pull request #12/#14`), so this merge must land as a PR
  from `merge/strata-001-007` → `main`. The architect cannot open or merge the
  PR from this session (no `gh` auth, no `GH_TOKEN`); the owner completes it.
- **Verification on the merge tree:**
  - `git ls-files workflow/evidence | wc -l` → **36**.
  - `.gitignore`: `build.log` still ignored; `workflow/evidence/**/commands.log`
    tracked.
  - HO-001: **19/19** bundle hashes OK (`hashes.txt` is a documented mixed
    format; verify by joining basenames with `artifacts/`).
  - HO-007: **15/15** bundle hashes OK; the signed binary hash still verifies.

### Reproducibility note (non-blocking)

`/tmp/opencode/qwen36/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf` is **no longer present**
on this host — temporary storage was cleaned. The recorded SHA256
(`55983c5a…3fe9f1`) and byte count pin it, and `setup.py:747` carries the same
digest, so the run is reproducible after a re-download. For future handoffs,
keep the GGUF on persistent storage (or record the re-download step in the
evidence manifest) so the model hash can be re-verified without network access.
