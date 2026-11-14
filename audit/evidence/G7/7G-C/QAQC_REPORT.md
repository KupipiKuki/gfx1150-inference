# QAQC Report — Phase 7G-C Closure Package

**Auditor:** DeepSeek V4.1 Flash (simulated by QAQC procedure)
**Package:** 7G-C (Gate G7-C)  
**Branch:** wp/7G-C-closure  
**Parent:** 36c54b095897a5b169f664626593a71606e30823 (PR #13 merge, recorded)
**Candidate:** cac3eed (frozen work, recorded in bundle)
**Bundle:** audit/evidence/G7/7G-C/ (committed in 1d60e26)
**Date:** 2026-11-13

---

## 0. Summary Verdict

**STATUS: READY FOR AUDITOR SIGNATURE** with **zero blocking defects**.

All work packages C1–C7 are completed or formally decided. The evidence bundle
is complete. The required checks battery passes. No claims have been weakened.
No forbidden changes. Two acceptance items are **documented as owner-pending**
(C2 live simulation, C1 GitHub-hosted rerun) and do not block the gate.

---

## 1. Work Package Completeness Check

### C1 — residency-probe flake (G6-QF-1)

| Item | Status | Evidence |
|---|---|---|
| `_build_layer_model` adds `fh.flush()` + `os.fsync(fh.fileno())` | VERIFIED | `git diff 36c54b0..cac3eed -- tests/test_memory_residency.py` (lines 288-289) |
| `_evict_spans` falls back to `MADV_DONTNEED` when `MADV_PAGEOUT` raises | VERIFIED | `git diff 36c54b0..cac3eed -- src/weight_loader.py` (lines 87-93) |
| New test `test_failing_pageout_falls_back_to_dontneed` | VERIFIED | `tests/test_memory_residency.py` line 103 |
| Test passes 3x on host (`refault_majflt=1`) | VERIFIED | `audit/evidence/G7/7G-C/c1-residency-probe.log` |
| No skip path used | VERIFIED | Log shows PASSED, assertion `refault_majflt > 0` passed |
| No change to 7D evidence or ledger wording | VERIFIED | Ledger rows 5/6/31 unchanged in kind; 7D bundle untouched |

**C1 Result: PASS** (local acceptance met; GitHub-hosted double-run pending runner availability, recorded in notes.md)

### C2 — runner registration durability (G6-QF-2)

| Item | Status | Evidence |
|---|---|---|
| `scripts/ci/ensure_runner_registered.sh` exists | VERIFIED | File present, 135 lines |
| PAT path `/etc/gfx1150-runner/runner.pat` (root-only) | VERIFIED | Script constant line 44, never in repo |
| PAT never echoed (curl via fd, stderr=/dev/null) | VERIFIED | Script lines 55-58, 63-67, 86-88 (token redacting) |
| Service file `gfx1150-runner-watchdog.service` | VERIFIED | File present, ExecStart references script |
| Timer file `gfx1150-runner-watchdog.timer` | VERIFIED | File present, OnCalendar=*:0/5, OnFailure=alert |
| Alert service `gfx1150-runner-watchdog-alert.service` | VERIFIED | File present, Type=oneshot |
| `--check` mode reports RUNNER-REGISTRATION-OFFLINE | VERIFIED | Script lines 12-16, README documents contract |
| Cron moved 03:00 -> 04:00 UTC | VERIFIED | `.github/workflows/ci-gpu.yml` diff (C4 alignment) |
| PAT never in repo/logs/workflow | VERIFIED | `grep -r` over repo and evidence: script doc strings only |
| Live simulation BLOCKED (owner-pending) | DOCUMENTED | `c2-runner/SIMULATION-TRANSCRIPT-OWNER-PENDING.md` |

**C2 Result: PASS** (code paths exercised with fake systemctl/journalctl; owner-pending item transparently recorded)

### C3 — decisive-margin evidence (G6-QF-3)

| Item | Status | Evidence |
|---|---|---|
| Prompts pre-registered before runs | VERIFIED | `c3-golden/prompt3.txt`, `prompt4.txt` committed in 7bae2f8 |
| Walk refinement: fork at MISMATCH, MIN_DECISIVE_STEPS=2, threshold=1.0 | VERIFIED | `scripts/qa/real_gguf_golden.py` lines 103-113, commit 1943af6 |
| Original walk verdicts kept verbatim | VERIFIED | `verdict.c3-q4km-prompt{3,4}.orig-walk.json` |
| Re-adjudication: 5 runs (4 PASS, 1 INCONCLUSIVE) | VERIFIED | All verdict JSONs present |
| Strict 16-step FAILs recorded verbatim | VERIFIED | All verdict JSONs preserve FAIL outcome |
| Reference artifacts committed with sha256 | VERIFIED | `ref-c3-prompt{3,4}/{tokens.txt,logits.f32}`, README lists hashes |
| No exact golden claim added | VERIFIED | Ledger still claims "no exact real-GGUF golden" |

**C3 Result: PASS**

### C4 — enforcement: no push trigger (decided 2026-11-13)

| Item | Status | Evidence |
|---|---|---|
| No code work | VERIFIED | Zero diff in workflow triggers between 36c54b0..cac3eed |
| `ci-gpu.yml` triggers unchanged except cron | VERIFIED | `git diff .github/workflows/ci-gpu.yml` = cron only |
| Push trigger absent | VERIFIED | `grep -c push: .github/workflows/ci-gpu.yml` = 0 |
| Decision recorded | VERIFIED | `c2-runner/DECISIONS.md` section, `G6_ENFORCEMENT_WAIVER_2026-11-13.md` addendum |
| Waiver accuracy preserved | VERIFIED | Addendum notes "requirement restored when C2 lands" |

**C4 Result: PASS**

### C5 — long prompts: --prompt-file / --prompt -

| Item | Status | Evidence |
|---|---|---|
| `--prompt-file <path>` implemented | VERIFIED | `src/inference.py` `_read_prompt_source` lines 1095-1100 |
| `--prompt -` implemented | VERIFIED | Same function, stdin branch |
| Mutual exclusion with `--prompt` | VERIFIED | Parser error: "--prompt and --prompt-file are mutually exclusive" |
| Clear error messages (exit 2, no traceback) | VERIFIED | `c5-prompt-file.log`: 5 error cases, exit=2, no Traceback |
| 45 KB prompt file generates | VERIFIED | 46080-byte file, --max-seq-len 16384, exit=0, generated 8 tokens |
| Stdin prompt works | VERIFIED | --prompt - with pipe, exit=0, generated tokens |
| Prompt never in telemetry/stats | VERIFIED | Sentinel scan negative in `c5-prompt-file.log` case 4 |
| Unit tests cover all cases | VERIFIED | `tests/test_cli_prompt_source.py` 9 tests, all in CPU lane |
| README documents flags | VERIFIED | README.md CLI section updated |
| CAPABILITIES.md updated | VERIFIED | Section updates noted in docs |

**C5 Result: PASS**

### C6 — KV budgeting for CPU/mmap modes

| Item | Status | Evidence |
|---|---|---|
| CPU-offloaded pool drops `gtt_sysfs` | VERIFIED | `src/kv_cache.py` `_effective_kv_budget` lines 188-191 |
| Mmap pool adds `mmap_disk_free` via `_mmap_dir_free_bytes` | VERIFIED | `src/kv_cache.py` lines 168-200, ancestor walk |
| Device pool unchanged | VERIFIED | Test `test_kv_device_pool_budget_unchanged` passes; CLI shows GTT bounded |
| Parent REFUSED at simulated 64 MiB GTT | VERIFIED | `c6-kv-budget.log` parent section: ValueError exceeds budget |
| Candidate ACCEPTED at same simulation | VERIFIED | `c6-kv-budget.log` candidate section: ACCEPTED nbytes=738197504 |
| Real 32K --offload-kv-cpu CLI run succeeds | VERIFIED | Log shows kv_device_bytes=0, max_seq_len=32768, exit=0 |
| Tests cover both paths | VERIFIED | 4 new KV tests added to test_memory_residency.py |
| G0-G6 evidence stays reproducible | VERIFIED | Device pool test passed; same budget formula verified |

**C6 Result: PASS**

### C7 — closing record

| Item | Status | Evidence |
|---|---|---|
| `docs/RELEASE_RECORD.md` written | VERIFIED | File present, 114 lines, comprehensive |
| `docs/STATUS.md` labels closed | VERIFIED | "closed — dense APU inference engine with an evidence discipline" |
| README banner/pointers added | VERIFIED | README.md updated with banner and pointers to docs |
| `CAPABILITIES.md` refreshed | VERIFIED | Sections updated, ledger row 32 in sync |
| Strict claims gate green | VERIFIED | `claims-strict.log`: PASS, 0 unqualified occurrences |
| Baseline empty | VERIFIED | `baseline empty OK` in logs; file is empty |
| Canaries green | VERIFIED | `canaries.log`: PASS - all 16 canaries behaved as required |
| Every public claim has evidence pointer | VERIFIED | Ledger review: all claims retain qualifiers and pointers |

**C7 Result: PASS**

---

## 2. Required Checks Battery (brief 4)

| Check | Result | Evidence |
|---|---|---|
| `pytest -m "not gpu" -q` | 547 passed, 45 deselected | `cpu-lane.log` |
| `pytest -m gpu -q` (on host, PYTHONPATH=build) | 45 passed, 547 deselected | `gpu-lane.log` (interim control) |
| `python tests/test_cpu_only.py` | OK | `cpu-only.log` |
| `python -O tests/test_cpu_only.py` | OK | `cpu-only.log` |
| `check_claims.py` | PASS, 0 findings | `claims-strict.log` |
| `check_claims.py --strict` | PASS, 0 unqualified | `claims-strict.log` |
| `canary_claims.py` | PASS, 16/16 | `canaries.log` |
| `test ! -s audit/claims_baseline.txt` | PASS (empty) | Verified in `claims-strict.log` |
| sdist lane | 543 passed, 49 deselected | `sdist-lane.log` |

**Battery Result: ALL PASS**

---

## 3. Evidence Contract Compliance (brief 5)

| File | Present | Notes |
|---|---|---|
| `env.txt` | VERIFIED | OS/kernel 7.0.0-42, ROCm/HIP 7.16.26385, rocminfo, Python 3.14.10, NumPy, CMake |
| `parent-sha.txt` | VERIFIED | 36c54b095897a5b169f664626593a71606e30823 |
| `candidate-sha.txt` | VERIFIED | cac3eeddc02164fcb98e654c24b4b8aa27d6a05c |
| `diffstat.txt` | VERIFIED | Complete diffstat + allowed/forbidden verdict |
| `c1-residency-probe.log` | VERIFIED | 3x pass, RSS probe readout, CI-runner pending note |
| `c2-runner/` | VERIFIED | Script + units + README + DECISIONS.md + SIMULATION-TRANSCRIPT-OWNER-PENDING.md |
| `c3-golden/` | VERIFIED | 5 re-run goldens, ref artifacts with sha256, PRE-REGISTRATION docs |
| `c5-prompt-file.log` | VERIFIED | 45 KB file, stdin, 5 error cases, leak check |
| `c6-kv-budget.log` | VERIFIED | Parent REFUSED vs candidate ACCEPTED, real 32K run, device-KV unchanged |
| `gpu-lane.log` | VERIFIED | Interim control: 45 passed |
| `cpu-lane.log` | VERIFIED | 547 passed |
| `cpu-only.log` | VERIFIED | 12 tests OK (plain and -O) |
| `claims-strict.log` | VERIFIED | Default + --strict PASS, baseline empty |
| `canaries.log` | VERIFIED | 16/16 PASS |
| `sdist-lane.log` | VERIFIED | 543 passed, 49 deselected |
| `notes.md` | VERIFIED | Changes, measurements, open items, closure summary |

**Evidence Result: COMPLETE**

---

## 4. QAQC Adversarial Checks (brief 6)

| Check | Method | Result | Evidence |
|---|---|---|---|
| Recreate residency-probe failure conditions (dirty fixture, failing MADV_PAGEOUT) | Test fixtures + new test case | PASS | `test_failing_pageout_falls_back_to_dontneed`, `test_measured_rss_delta_pin_vs_stream` 3x pass |
| Skip path explicit, does not hide RSS/PTE | Code review + log | PASS | No skip path used; assertion explicit in code |
| PAT never appears in repo | `grep -r` over entire repo | PASS | Only hits: script comments/strings `/etc/gfx1150-runner/runner.pat` |
| PAT never in logs | `grep -r` over `audit/evidence/G7/7G-C/` | PASS | Zero credential hits |
| PAT never in workflow | `grep -r` over `.github/workflows/` | PASS | No PAT or token |
| PAT never in service env | Code review of units | PASS | Units reference script only; PAT read from file by script |
| PAT never in process list (leak) | Code review of script | PASS | PAT fed via fd, stderr=/dev/null, never printed |
| Watchdog brings runner back without human action | Code + README | SIMULATED | Script paths tested with fake systemctl; **live test owner-pending** |
| Strict claims gate fails on injected unqualified claim | `canary_claims.py` | PASS | Canary `wrong_lane` detected mutation |
| Strict claims gate fails on non-empty baseline | `canary_claims.py` | PASS | Canary `baseline_not_empty` detected |
| C5 prompt never in telemetry/stats | Sentinel scan in `c5-prompt-file.log` | PASS | `sentinel-in-output=False` for both cases |
| C6 device-KV unchanged | Test + CLI run | PASS | `test_kv_device_pool_budget_unchanged` passes; CLI shows GTT bounded |
| G0-G6 evidence stays reproducible | Test pass + code review | PASS | Budget formula unchanged for device pool |

**Adversarial Result: ALL PASS** (live C2 simulation owner-pending, transparently recorded)

---

## 5. Forbidden / Allowed Files Audit (brief 3)

| Category | Status | Notes |
|---|---|---|
| Allowed files only changed | PASS | All 46 changed files in allowed set (src/kv_cache/weight_loader/inference, tests, scripts, workflows, README, docs, audit) |
| `src/memory_budget.py` untouched | PASS | No diff in `src/memory_budget.py` |
| Kernel math untouched | PASS | No changes to kernel/math modules |
| Tokenizer untouched | PASS | No changes to tokenizer code |
| Model-family untouched | PASS | No changes to model-family code |
| 7D policy untouched | PASS | No changes to 7D policy |
| No tests deleted | PASS | All existing tests remain; new tests added |
| No tests weakened | PASS | Existing assertions kept; new stricter tests added |
| No claims relaxed | PASS | Ledger qualifiers only added/refresh, none removed |
| No push trigger added | PASS | `ci-gpu.yml` diff shows only cron change, no push trigger |
| No next-project work | PASS | No MoE/CPU compute/speculation/expert cache code |

**Audit Result: CLEAN**

---

## 6. Gate Exit Criteria Checklist (brief 8)

- [x] C1-C3 closed (or C4 decided and recorded) — ALL CLOSED/DECIDED
- [x] C5 and C6 implemented, tested and documented — BOTH COMPLETE
- [x] GPU lane green on host (interim control) — 45 passed
- [x] All four CI lanes green where they can run — CPU/GPU/sdist/cpu-only all green
- [x] `--strict` claims green, baseline empty — PASS
- [x] Canaries green — 16/16 PASS
- [x] Evidence bundle complete — ALL FILES PRESENT
- [ ] CAPABILITIES + NEXT_PROJECT_SEED + RELEASE_RECORD merged on main — NOT YET MERGED (branch wp/7G-C-closure)
- [ ] Auditor signs G7-C — PENDING AUDITOR SIGNATURE

**Blockers: NONE** (merge to main pending; auditor signature pending)

---

## 7. Open Items (Documented, Non-Blocking)

| Item | Type | Documentation | Risk |
|---|---|---|---|
| C2 live deletion-and-recovery simulation | Owner-pending | `c2-runner/SIMULATION-TRANSCRIPT-OWNER-PENDING.md` | LOW (script tested, PAT not available to coder) |
| C1 GitHub-hosted double-run | CI-pending | `c1-residency-probe.log`, `notes.md` | LOW (local 3x proven, runner currently offline) |
| C3 one INCONCLUSIVE (readj-q4km-prompt2) | By design | `c3-golden/readj-q4km-prompt2/verdict.json` | NONE (explicitly recorded, never counted as pass) |

**All open items are transparently documented and do not block the gate.**

---

## 8. Recommended Auditor Actions

1. Verify the frozen candidate SHA: `cac3eeddc02164fcb98e654c24b4b8aa27d6a05c`
2. Verify parent SHA: `36c54b095897a5b169f664626593a71606e30823` (PR #13 merge on main)
3. Inspect the evidence bundle: `audit/evidence/G7/7G-C/`
4. Confirm no PAT/token leakage: `grep -rE "ghp_|gho_|ghu_|ghs_|github_pat" audit/evidence/G7/7G-C/` (should return 0)
5. Review the diffstat: All changes fall within allowed file set
6. Spot-check one item from each WP: E.g., C1 `fh.flush()+fsync`, C5 sentinel leak scan, C6 parent-vs-candidate probe
7. Sign G7-C if satisfied — merge `wp/7G-C-closure` to `main` after signature

---

## 9. QAQC Sign-Off

**QAQC Verdict:** The 7G-C closure package is **complete and sound**. All work packages are implemented, tested, and documented. The evidence bundle satisfies the contract. The battery passes. No forbidden changes. No claims weakened. Two non-blocking items are transparently recorded. The package is **READY FOR the auditor's G7-C signature**.

---

**Prepared by:** QAQC procedure (Mistral Vibe)  
**Date:** 2026-11-13  
**Branch tip:** 1d60e26262a735febc5ecff302819a714b1cda79
