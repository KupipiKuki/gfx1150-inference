# Architect approval — HO-STRATA-007

| Field | Value |
|---|---|
| **Handoff** | HO-STRATA-007 — `qwen35moe` low-tier baseline (Qwen3.6-35B-A3B) |
| **Architect** | architect (DeepSeek session model, WAIVER-001 seat) |
| **Date (UTC)** | 2026-11-16 |
| **Decision** | **SIGNED** → state `DONE` |
| **Merge commit** | **Deferred** — see §3 C1; `wp/strata-007-qwen35moe-lowtier` is based on `research/strata-memo` (not on `main`), so the merge follows the DEC-015 selective-merge plan |
| **Evidence** | `workflow/evidence/HO-STRATA-007/` at `e066b09` (evidence commit `f03348d`, conditions `eae6a9e` + `e066b09`) |
| **Branch / base** | `wp/strata-007-qwen35moe-lowtier` / `afcc2096367cc8b17f72acd9708c886c9acc94bc` |

## 1. Criteria trace

| # | Criterion | Evidence | QAQC | Audit | Architect |
|---|---|---|---|---|---|
| 1 | Pack identified (`qwen35moe` / `Qwen3.6-35B-A3B`) | `artifacts/engine-families.txt`, `artifacts/control-plan-qwen36.json` | PASS | PASS | PASS |
| 2 | Pack hashes | `hashes.txt` (GGUF `55983c5a…`, 22,853,663,008 B = `setup.py:747`) | PASS | PASS | PASS |
| 3 | Model loads on signed binary | `test-output.txt` — 753 tensors, 4.40 GiB, 18.75 GiB experts, exit 0 | PASS | PASS | PASS |
| 4 | Generation (fixed prompt, greedy, 16–32 tokens, 512–2,048 context) | 32 token IDs + decoded text, reproduced 5× | PASS | PASS | PASS |
| 5 | Resources / stability | `/proc/meminfo`, `artifacts/amd-smi-gtt.txt` (GTT peak 26,798 MB), `dmesg` | PASS | PASS (A-2 closed by C1b) | PASS |
| 6 | Environment / binary hash | `manifest.md` §5, binary `d58ee239…`, ROCm 10.1 / hipBLASLt 100401 | PASS | PASS | PASS |
| 7 | No claims, one profile | no perf/support/quality claim; `gfx1150`/`qwen35moe` only | PASS | PASS | PASS |

## 2. Gate evidence

- [x] QAQC report: `workflow/reports/qaqc/HO-STRATA-007-qaqc.md` — **PASS** (`gemini-4-argon`; independent re-run, bit-identical token IDs; M1–M4 Minor).
- [x] Audit report: `workflow/reports/audit/HO-STRATA-007-audit.md` — **PASS (WAIVED — WAIVER-001)**; 4th independent run, 13 counter-hypothesis checks, cache/template hypothesis falsified by prompt probes.
- [x] Evidence manifest complete; `sha256sum -c hashes.txt` → 17/17 `OK`, exit 0, no format warnings.
- [x] Scope matches the handoff; no drift (diff `afcc2096..e066b09`: HO-007 evidence, handoffs, QAQC/audit reports, STATUS row).
- [x] Guard rails: no Strata source change (`git -C …/strata status --porcelain` empty, HEAD `baf16363…`); no new dependency; no model conversion; no secrets; no weights in git.
- [x] No unsupported claims: the engine `tok/s` line is raw output, explicitly disclaimed; no performance/support/quality statement in any artifact.

## 3. Conditions disposition

| # | Condition (audit) | Status | Closure evidence |
|---|---|---|---|
| **C1a** | Complete `hashes.txt` (6 auxiliary artifacts + `manifest.md`), machine-checkable | **CLOSED** | `eae6a9e`; `sha256sum -c` 17/17 `OK`, exit 0, no warnings |
| **C1b / A-2** | GTT / `amd-smi` evidence in the coder bundle | **CLOSED** | `artifacts/amd-smi-gtt.txt` — peak `USED_GTT 26,798 MB`; `rocm-smi` absent (`which` exit 1) recorded; output re-matched the 32 token IDs |
| **C1c / A-3** | `manifest.md` commit field: base + evidence | **CLOSED** | records base `afcc2096…`, evidence `f03348d…`, review head `a3da3d6…` |
| **C2 / A-1** | QAQC handoff state / write-boundary ruling | **CLOSED** | `HO-STRATA-007-QAQC.md` mirrored to `AUDIT_REVIEW` under DEC-018; QAQC report remains authoritative |
| **C3** | `GB`/`GiB` units; inline license | **CLOSED** | memory restated in exact kB + both units; GGUF restated `22,853,663,008 B; 21.28 GiB / 22.85 GB` (`e066b09`); `Apache 2.0: https://huggingface.co/Qwen/Qwen3.6-35B-A3B` inlined |
| **C4** | Python version | **CLOSED** | default `python3` = `3.14.10`; `/usr/bin/python3.12` not used; tokenizer interpreter named |
| **C5** | STATUS/OT move only after signoff | **CLOSED** | this document; `STATUS.md` and OT checkpoint 6 updated after this signature |
| **A-4** | Teardown CPU advisory | **NO ACTION** | observation only; no GPU fault/reset |

**Remaining follow-up (not a condition):** the branch merge is deferred to the DEC-015 selective-merge plan; merge only with the HO-001 split so the four workstreams are not fast-forwarded onto `main`.

## 4. Decision and limits of the claim

**SIGNED** → state `DONE`.

What this result establishes: on the signed gfx1150 build at `baf16363`, the
supported `qwen35moe` pack (`Qwen3.6-35B-A3B`, `UD-Q4_K_XL`, 22,853,663,008 B,
`55983c5a…`) loads and generates 32 tokens for one fixed prompt, deterministically
(greedy, 1024-cell context), with a measured peak of ~26.2 GiB GTT and no GPU
fault or reset.

What it does **not** establish: any performance, throughput, quality or support
claim; any other family (Mixtral, Qwen3-30B-A3B, DeepSeek) or model; any other
quantization, context length or prompt; the 780M, MI25 or gfx1100; the Control
server path (the signed feed has no gfx1150 engine package, so the engine
one-shot `--native` path is the tested path).

| Role | Signature | Date |
|---|---|---|
| Architect | architect (DeepSeek session model, WAIVER-001 seat) | 2026-11-16 |
