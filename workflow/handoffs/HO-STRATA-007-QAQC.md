# HO-STRATA-007-QAQC — qwen35moe low-tier baseline: QAQC review

| Field | Value |
|---|---|
| **ID** | HO-STRATA-007-QAQC |
| **Type** | CODER_TO_QAQC |
| **State** | PROPOSED |
| **Created / updated (UTC)** | 2026-11-16 / 2026-11-16 |
| **From → To** | Primary Coder (`coder-primary`) → QAQC (`qaqc`) |
| **Work package** | `strata-007-qwen35moe-lowtier` |
| **Branch / base commit** | `wp/strata-007-qwen35moe-lowtier` / `679a3ea` on top of `afcc2096367cc8b17f72acd9708c886c9acc94bc` |
| **Priority / timebox** | P0 · 1 working day |
| **Original handoff** | `workflow/handoffs/HO-STRATA-007.md` |

## 1. Scope (in)

- Verify the coder's evidence for HO-STRATA-007.
- Re-run the acceptance commands independently.
- Confirm the pack identification, hashes, model load, generation, resource envelope, environment, and guard rails.

## 2. Out of scope

- Do not modify code, tests, docs, or the Strata checkout.
- Do not install or run other model families (Mixtral, Qwen3-30B-A3B, DeepSeek).
- Do not make new performance/support/quality claims.

## 3. Inputs

| Input | Path / hash | Status |
|---|---|---|
| Original handoff | `workflow/handoffs/HO-STRATA-007.md` | CODER_DONE |
| Evidence bundle | `workflow/evidence/HO-STRATA-007/` | complete |
| Signed gfx1150 build | `/home/kupipi/Documents/git/strata/build-hip/strata` @ `baf16363` | available |
| Model pack | `/tmp/opencode/qwen36/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf` (sha256 `55983c5a…`) | available on host |
| Toolchain | ROCm `/opt/rocm/core-10.1` | available |

## 4. Acceptance criteria

| # | Criterion | Command / check | Expected |
|---|---|---|---|
| 1 | Evidence bundle is complete | `ls workflow/evidence/HO-STRATA-007/` | `manifest.md`, `commands.log`, `test-output.txt`, `artifacts/`, `hashes.txt` |
| 2 | Pack identification matches scope | Inspect `artifacts/control-plan-qwen36.json` and `artifacts/engine-families.txt` | family `qwen36` / `UD-Q4_K_XL`, engine lists `qwen35moe` |
| 3 | Pack hash matches the signed pin | `sha256sum /tmp/opencode/qwen36/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf` | `55983c5a75a1ab969824077b3bb3de4146e82a9234072b48ad4e8f92ad3fe9f1` |
| 4 | Model loads and generates on the signed binary | `LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib ./build-hip/strata --native /tmp/opencode/qwen36/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf --tokens 760,6511,314,9338,369 --n 32 --max-context 1024` | exit 0; ≥16 generated tokens; no crash |
| 5 | Resource envelope is recorded | Inspect `test-output.txt` | pre/post `/proc/meminfo`, `dmesg` tail; no reset/error |
| 6 | Environment recorded | Inspect `commands.log` | `rocminfo`, `hipcc --version`, binary SHA256, GPU info |
| 7 | Guard rails respected | Review diff and evidence | No Strata source changes; no other family; no claims beyond the single profile |

## 5. Evidence required

- `workflow/evidence/HO-STRATA-007/manifest.md`
- `workflow/evidence/HO-STRATA-007/commands.log`
- `workflow/evidence/HO-STRATA-007/test-output.txt`
- `workflow/evidence/HO-STRATA-007/hashes.txt`
- `workflow/evidence/HO-STRATA-007/artifacts/`

## 6. Guard rails

- Do not modify the Strata source or the gfx1150-inference repo outside `workflow/handoffs/`, `workflow/evidence/HO-STRATA-007/`, and this handoff file.
- Do not add dependencies.
- Do not change acceptance criteria or scope.
- Do not merge or push to `main`.
- No secrets in the repo, logs, or handoff.

## 7. Dependencies / blockers

| Dependency | Owner | Status | Needed by |
|---|---|---|---|
| Model pack present on host | Coder | downloaded | command re-run |
| Signed build + ROCm 10.1 | Coder/Owner | available | command re-run |

## 8. Definition of Ready

- [x] ID/type/from/to/title/work package present
- [x] Branch and base commit named
- [x] Scope and out-of-scope explicit
- [x] Inputs linked and available
- [x] Every criterion has a command/check
- [x] Evidence requirements runnable
- [x] Guard rails explicit
- [x] Dependencies resolved or owned
- [x] Priority/timebox set
- [x] No open `NEEDS_INFO`

## 9. Definition of Done

- [ ] QAQC report written to `workflow/reports/qaqc/HO-STRATA-007-qaqc.md`
- [ ] Every acceptance criterion re-run; raw output recorded
- [ ] Diff reviewed against scope and guard rails
- [ ] PASS or FAIL verdict recorded
- [ ] Evidence manifest reviewed for completeness and secrets

## 10. Signatures

| Role | Name/agent | Date | Decision |
|---|---|---|---|
| Sender (Coder) | `coder-primary` | 2026-11-16 | CODER_DONE |
| Receiver (QAQC) | `qaqc` | | |

## 11. Log

- 2026-11-16 Coder: created CODER_TO_QAQC handoff; evidence path `workflow/evidence/HO-STRATA-007/`; commit `679a3ea`.
