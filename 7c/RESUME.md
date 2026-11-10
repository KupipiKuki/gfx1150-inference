# 7C RESUME LOG — COMPLETE (work + evidence committed, stopped at G3)

Branch: wp/7C-model-families

## Final state

- 20f1165 — work commit: ModelSpec/tensor map, Phi-3 fused paths, Gemma graph,
  compat matrix, claims rows 10/11/12 (12 files, +2184/-124).
- 4b930ec — evidence-bundle commit: full audit/evidence/G3/7C/ per README.md
  contract, incl. candidate-sha.txt = 20f1165.
- Final battery re-run green immediately before the work commit:
  CPU lane 461 passed / GPU lane 34 passed / test_cpu_only OK in both modes /
  check_claims.py PASS. Lane logs in the evidence bundle were refreshed to
  that final run (timings: CPU 48.98s, GPU 1.88s, cpu-only 0.692/0.690s).
- Parent red worktree /tmp/7c-parent removed (git worktree list is clean of it;
  /tmp/opencode/qaqc-76fu/tree is a separate pre-existing prunable worktree,
  left alone).
- Working tree is clean apart from this 7c/ notes directory (untracked by design).

## Next owner: QAQC / auditor (per PHASE7_7C_MODEL_FAMILY_BRIEF.md §7–§8 and
audit/evidence/G3/7C/README.md)

- G3 verdict on candidate 20f1165; auditor merges to vibe/phase7-220201 only
  after signoff.
- 7D is NOT authorized. Do not reopen the 7B tokenizer. Real-GGUF Phi-3/Gemma
  goldens belong to 7F-2.

## Gotchas (unchanged, kept for reference)

- Q4_K/Q6_K matmul kernel requires K multiple of 256 — quantized family fixtures
  use hidden=256/inter=256.
- check_claims scope grammar: groups separated by `;`, sites `PATH:LINE`,
  comma-separated; case-sensitive substring literals.
- README line references in ledger rows point at exact lines; re-verify with
  grep if README shifts.
- evidence *.log files are gitignored (`.gitignore: *.log`) — prior bundles
  (G2/7B) force-add them; 7C did the same.
