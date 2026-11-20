# HO-STRATA-011 — OLMoE oracle extension (S0b)

| Field | Value |
|---|---|
| **ID** | HO-STRATA-011 |
| **Type** | ARCHITECT_TO_CODER |
| **State** | **READY** — DoR met (§8) |
| **Created / updated (UTC)** | 2026-11-19 |
| **From → To** | Architect → Primary Coder (`coder-primary`) |
| **Work package** | `strata-011-olmoe-oracle` |
| **Branch / base commit** | `wp/strata-011-olmoe-oracle` / `main` at the branch point (record the SHA) |
| **Priority / timebox** | P1 · 4 working hours |
| **Owner task** | OT-STRATA-001 (S0b authorized 2026-11-19, DEC-031) |
| **Plan** | `planning/strata-engine/13-family-support-test-plan.md` §4 (S0), §5 (three-model set) |

## 1. Purpose

Extend the S0 oracle to the third family, **OLMoE-1B-7B** (`olmoe`), so S1–S5 have
a reference for all three test models. No engine change: this is the same work as
HO-STRATA-010, on a smaller pack, with the three fidelity lessons from that
handoff built into the requirements.

## 2. Pack

| Field | Value |
|---|---|
| Repo | `allenai/OLMoE-1B-7B-0924-Instruct-GGUF` |
| File | `olmoe-1b-7b-0924-instruct-q4_k_m.gguf` |
| Size | 4,213,512,672 B (3.92 GiB) |
| SHA256 | `8c310f1435a1222338fd2d3d974975be9cd908180b644bab0c2a94da1ac32f3f` |
| Arch (`general.architecture`) | `olmoe` |
| Path | `/home/kupipi/Documents/models/gguf/olmoe-1b-7b/olmoe-1b-7b-0924-instruct-q4_k_m.gguf` |

The orchestrator verified size, the Hugging Face etag **and** the arch string
before writing this handoff. Re-verify all three; a mismatch is a stop.

## 3. Scope (in)

- Build the harness (reuse the committed `oracle_harness.cpp`; no logic change) at
  the pinned llama.cpp (`b12527`, `78e05298…`).
- **Tokenizer parity**: three fixed prompts (`The capital of France is`,
  `def add(a, b):\n    return`, `Three primary colors are`) — engine tokenizer vs
  `llama_tokenize` with `add_special=false`, side by side, zero differences.
  OLMoE uses a 50k tokenizer, so it is a genuinely new vocabulary.
- **Reference run**: P1 token IDs, 16 tokens greedy, twice, with the **normalized**
  comparison as the gate of record (`gen:` line only).
- **Dumps**: 4-token layer dump (all positions **and** all layers populated) and
  16-step top-2 logits, shapes printed as `[pos][layer][hidden]` and
  `[step][rank][(id, logit)]`.
- Evidence bundle mirroring HO-010.

## 4. Out of scope

- Any engine change; S1 and later stay held (DEC-016).
- Mixtral; the dense `llama` path; `qwen4exp`.
- Tolerance values or KL bounds (S4/S5).
- New model downloads; only the pack above.
- Performance or support claims.

## 5. Fidelity requirements (the HO-010 lessons, made explicit)

These are acceptance criteria, not advice — the first HO-010 bundle failed audit
on exactly these:

1. **Raw transcript.** Save each command's stdout/stderr to its own file
   (`artifacts/cmd-<n>.{out,err}.txt`) and record exit codes as observed. If a
   curated `test-output.txt` is kept, it must be labelled **"curated excerpt — the
   raw files are authoritative"** and must not contradict them. Never record a
   passing exit code for a command that exited non-zero.
2. **Normalization is the gate.** The two `gen:` outputs are compared after
   stripping timing; `stdout_diff` will exit 1 because `wall_s` differs. Record
   `raw_diff_exit=<observed>` and `normalized_diff_exit=<observed>` truthfully.
3. **Pins carry digests.** Where `workflow/MODELS.md`, `planning/strata-engine/13`
   or `DECISIONS.md` is pinned by commit (DEC-024), record the commit **and** the
   `git show <sha>:<path> | sha256sum` digest.
4. **Scope the provenance.** Library digests are **this host and this build**
   scoped; say so (B-2), and record `GGML_NATIVE`, cmake version, CPU and `nproc`.

## 6. Acceptance criteria

| # | Criterion | Check |
|---|---|---|
| 1 | Pack identity verified (size, SHA256, arch) | `sha256sum`, header read, both match §2 |
| 2 | Harness built at the pin; provenance recorded | tag/commit/flags/compiler/lib hashes |
| 3 | Tokenizer parity: 3 prompts, zero differences, BOS convention stated | side-by-side table |
| 4 | Reference tokens: P1, 16 greedy, reproducible across two runs | normalized diff empty; raw diff exit recorded truthfully |
| 5 | Layer dump `[4][L][H]` with **every** layer and position non-zero | shape line + non-degeneracy check |
| 6 | Logits/top-2 dump `[16][2][2]` with layout documented | shape line + file size |
| 7 | Evidence bundle complete; hashes verify; pins include digests | `sha256sum -c` clean |
| 8 | No engine change | Strata clean at `baf16363…`; binary `d58ee239…` |
| 9 | No claim | report review |

## 7. Evidence required

`workflow/evidence/HO-STRATA-011/`: `manifest.md`, `commands.log`, per-command raw
`artifacts/cmd-*.{out,err}.txt`, the parity table, `runs/` (gen outputs, dumps),
`hashes.txt` (immutable only), `hashes-notes.txt` (commit pins **with** digests).

## 8. Definition of Ready — MET

- [x] ID/type/from/to/title/work package
- [x] Branch/base named (record the SHA)
- [x] Scope/out-of-scope explicit
- [x] Inputs available and verified (pack hashed; oracle harness committed)
- [x] Every criterion has a check
- [x] Evidence requirements runnable
- [x] Guard rails explicit (§5)
- [x] Dependencies resolved
- [x] Priority/timebox set
- [x] No `NEEDS_INFO`
- [x] Authorized (DEC-031: S0b only)

## 9. Definition of Done

- [ ] Pack verified; harness built at the pin
- [ ] Tokenizer parity proven
- [ ] Reference tokens + dumps recorded, raw files authoritative
- [ ] Hashes clean; pins carry digests
- [ ] No engine change, no claim
- [ ] Manifest complete; `CODER_DONE`; QAQC handoff created

## 10. Signatures

| Role | Name/agent | Date | Decision |
|---|---|---|---|
| Sender (Architect) | architect | 2026-11-19 | READY |
| Receiver (Coder) | `coder-primary` | | |

## 11. Log

- 2026-11-19 Architect: created READY. OLMoE replaces Mixtral in the three-model
  set (DEC-029, DEC-031); the pack was downloaded and verified by the
  orchestrator (size, etag, arch `olmoe`).
