# HO-STRATA-007 — qwen35moe low-tier baseline (Qwen3.6-35B-A3B)

| Field | Value |
|---|---|
| **ID** | HO-STRATA-007 |
| **Type** | ARCHITECT_TO_CODER |
| **State** | **ARCHITECT_APPROVAL** — READY → IN_PROGRESS → CODER_DONE → QAQC_REVIEW (PASS) → AUDIT_REVIEW (PASS, WAIVED) → **ARCHITECT_APPROVAL** (conditions C1–C5 open) |
| **Created / updated (UTC)** | 2026-11-16 / 2026-11-16 |
| **From → To** | Architect → Primary Coder (`coder-primary`, Kimi K2.7 Code) |
| **Work package** | `strata-007-qwen35moe-lowtier` |
| **Branch / base commit** | `wp/strata-007-qwen35moe-lowtier` / this branch’s start; record the parent SHA in the log |
| **Priority / timebox** | P0 · 1 working day |
| **Owner task** | OT-STRATA-001 (DEC-017) |

## 1. Scope (in)

- Install or verify the **supported** `qwen35moe` pack — model family
  `qwen3.6-35b-a3b` — from the Strata Control/catalog, smallest practical quant
  that fits the gfx1150.
- Run **one** low-tier generation on the signed gfx1150 build at
  `baf16363` (`build-hip/strata`).
- Record the exact command, the raw output, the model/pack hashes, the resource
  envelope, and the limits.
- Use the Control’s local server path (`python3 strata.py launch …`) or the
  engine’s one-shot `generate` with a tokenized prompt; record which.
- No source changes; no family-support work; no other models.

## 2. Out of scope

- Mixtral 8x7B, Qwen3-30B-A3B, DeepSeek; adding families; changing the engine.
- Performance, throughput, quality or support claims.
- The 780M, MI25, gfx1100.
- Model conversion or custom packs beyond the supported catalog pack.

## 3. Inputs

| Input | Path / source | Status |
|---|---|---|
| Signed gfx1150 build | `build-hip/strata` at `baf16363` | available |
| Engine boundary / CLI | `workflow/evidence/HO-STRATA-001/artifacts/engine-boundary.md`, `help.txt` | available |
| Family mapping | `serve/server.py:9695` — `qwen35moe = qwen3.6-35b-a3b` | verified |
| Installable family | `strata_control/feed.py:155` — `("qwen4exp","qwen35moe")` | verified |
| Model pack | Strata Control catalog, `qwen35moe`, smallest practical quant | owner-authorized (DEC-017) |
| Toolchain | ROCm `/opt/rocm/core-10.1`, hipBLASLt `100401` | recorded in HO-001 |

## 4. Acceptance criteria

| # | Criterion | Command / check | Expected |
|---|---|---|---|
| 1 | Pack identified | `python3 strata.py launch --help`; `python3 strata.py launch --plan --family qwen` | the `qwen35moe` pack (`qwen3.6-35b-a3b`); pack name, quant, size recorded |
| 2 | Pack hashes | `sha256sum` of the pack files/shard(s) | hashes in the evidence; no conversion |
| 3 | Model loads | the documented Control/engine command | load completes; no crash; no source change |
| 4 | Generation | one fixed prompt, `temperature=0`, 16–32 new tokens, 512–2,048 context | ≥16 tokens; raw output saved verbatim |
| 5 | Resources / stability | `/proc/meminfo`, GTT, `dmesg`, `rocm-smi` | peak RAM/GTT recorded; no resets/errors |
| 6 | Environment | `rocminfo`, `hipcc --version`, binary SHA256 | ROCm 10.1, hipBLASLt 100401, signed binary |
| 7 | No claims | the report | one profile (`gfx1150`/`qwen35moe`); no perf/support/quality claim |

## 5. Evidence required

`workflow/evidence/HO-STRATA-007/`:

- `manifest.md` (from `templates/EVIDENCE_MANIFEST.md`), `commands.log`,
  `test-output.txt`, `artifacts/`, `hashes.txt`.
- The model/pack name, quant, size, file hashes, license/provenance.
- The prompt, the request/response (or token IDs), the raw output.
- RAM/GTT peak, `dmesg`, `rocm-smi`, and the exact environment.
- No model weights in git; hashes only.

## 6. Guard rails

- No Strata source changes; the checkout is pinned/read-only.
- No family-support work; no Mixtral/Qwen3-30B-A3B/DeepSeek.
- No performance/support/quality claim; this is a load-and-generate check.
- One profile only; no cross-profile transfer.
- No secrets; no model weights in the repo.
- If the pack does not fit or the engine refuses it, record the refusal
  verbatim and stop; do not substitute a different family.

## 7. Dependencies / blockers

| Dependency | Owner | Status | Needed by |
|---|---|---|---|
| Model pack install (catalog) | Coder/Owner | owner-authorized; coder records it | execution |
| Signed build + toolchain | Coder | available | execution |

## 8. Definition of Ready

- [x] ID/type/from/to/title/work package present
- [x] Branch and base named; coder records the parent SHA
- [x] Scope and out-of-scope explicit
- [x] Inputs linked
- [x] Every criterion has a command/check
- [x] Evidence requirements runnable
- [x] Guard rails explicit
- [x] Dependencies named
- [x] Priority/timebox set
- [x] Owner authorization (DEC-017)
- [x] Pack name/quant confirmed at execution: `qwen36` family / `UD-Q4_K_XL` quant, file `Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf`

## 9. Definition of Done

- [x] Pack identified and hashed
- [x] Model loads on the signed binary
- [x] ≥16 tokens generated; raw output saved
- [x] Resource envelope and `dmesg` recorded
- [x] Environment and binary hash recorded
- [x] No source changes, no other family, no claims
- [x] Evidence manifest complete; `CODER_DONE` and the QAQC handoff created

## 10. Test shape (record the exact command)

Executed path: the engine’s one-shot path, with a tokenized prompt. The Control’s
local server path could not be used because the signed update feed has no pre-built
HIP engine package for `gfx1150`; the locally-built signed binary was used directly.

```bash
cd /home/kupipi/Documents/git/strata
LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib ./build-hip/strata \
  --native /tmp/opencode/qwen36/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf \
  --tokens 760,6511,314,9338,369 --n 32 --max-context 1024
```

The `qwen35moe` file was detected from the GGUF header and routed to `strata-q36`.
The prompt was tokenized with `tools/strata_tokenizer.py`; the generated token IDs
and decoded text are in the evidence bundle. Record the exact command, raw output,
and any refusal.

## 11. Signatures

| Role | Name/agent | Date | Decision |
|---|---|---|---|
| Sender (Architect) | architect | 2026-11-16 | READY |
| Receiver (Coder) | `coder-primary` | 2026-11-16 | accepted |
| QAQC | `qaqc` (`gemini-4-argon`) | 2026-11-16 | **PASS** → `AUDIT_REVIEW` |
| Auditor | `auditor` (`deepseek-v4.1-flash`, WAIVED) | 2026-11-16 | **PASS (WAIVED)** → `ARCHITECT_APPROVAL`, conditions C1–C5 |

## 12. Log

- 2026-11-16 Architect: READY after DEC-017; owner accepted HO-001 and
  authorized the supported `qwen35moe` low-tier test.
- 2026-11-16 Coder: IN_PROGRESS; base SHA `afcc2096367cc8b17f72acd9708c886c9acc94bc`.
- 2026-11-16 Coder: CODER_DONE; `qwen35moe` (`qwen36` family / `UD-Q4_K_XL`) loaded on the signed `baf16363` build and generated 32 tokens; evidence in `workflow/evidence/HO-STRATA-007/`; commit `f03348d`.
- 2026-11-16 QAQC: **PASS** → `AUDIT_REVIEW`; independent re-run on `gemini-4-argon`
  reproduced bit-identical token IDs and the resource envelope; 4 Minor
  non-blocking observations (M1–M4) recorded for the auditor in
  `workflow/reports/qaqc/HO-STRATA-007-qaqc.md`.
- 2026-11-16 Auditor: **PASS (WAIVED — WAIVER-001)** → `ARCHITECT_APPROVAL`;
  4th independent re-run reproduced 32/32 token IDs and the decode; 13 counter-
  hypothesis checks; M1–M4 upheld Minor; new findings A-1 (QAQC handoff state),
  A-2 (no GTT/amd-smi in the coder bundle), A-3 (manifest commit field),
  A-4 (teardown CPU advisory, no action). Conditions C1–C5 are bookkeeping only.
  Report: `workflow/reports/audit/HO-STRATA-007-audit.md`.
- 2026-11-16 Coder: closed audit bookkeeping conditions C1a–C4 on the same
  work-package branch. Rewrote `hashes.txt` in pure `sha256sum` format covering
  every evidence file plus the external model and signed binary, verified with
  `sha256sum -c` (exit 0, no warnings). Added `artifacts/amd-smi-gtt.txt` from a
  repeat of the accepted generation command, with `amd-smi metric -g 0 -m`
  sampled before/during/after; token IDs matched `generated-token-ids.txt`;
  peak `USED_GTT` = 26,798 MB. Updated `manifest.md` commit field (base/evidence/
  review head), corrected Python version and tokenizer interpreter, restated
  memory in exact kB with decimal/binary units, and inlined the Apache-2.0
  license string from `setup.py:758`. State remains `ARCHITECT_APPROVAL`; C5
  (status/merge) is still for the architect.
