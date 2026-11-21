# Session handoff — 2026-11-22 (resume after the budget pause)

**Paste this file into a new session with the `architect` agent selected.**
Reading order: this file → `workflow/STATUS.md` → `workflow/DECISIONS.md` →
`workflow/MODEL_POLICY.md` → the signed approvals listed in §3.

---

## 1. Where the project is

gfx1150 only. The 780M is a separate project; MI25 deferred; gfx1100 future.
Strata is a pinned checkout at `baf16363` (`/home/kupipi/Documents/git/strata`);
this repo holds the workflow, evidence and the exported patches.

```text
main                    a06f66c   (PR #22 HO-010, #23 HO-011 merged)
open PR                 wp/strata-012-deepseek-s1 @ 135989a  (S1–S3 signed)
Strata checkout         bac859ef9 on local branch strata-012-deepseek-s1
signed binary           build-hip/strata  d58ee239…  (never rebuilt)
```

**Three-model set** (DEC-031): `qwen35moe` (Qwen3.6-35B-A3B, measured),
`deepseek` (DeepSeek-MoE-16B, recognition done, no run), `olmoe` (OLMoE-1B-7B,
oracle only).

## 2. What is proven

| Handoff | Result | State |
|---|---|---|
| HO-001 | build, support surface (`qwen4exp qwen35moe`), engine boundary | DONE, merged |
| HO-005 | Route 2 confirmed; Route 3 triggers T1–T5 | DONE, merged |
| HO-007 | Qwen3.6-35B-A3B generates 32 deterministic tokens, GTT ~26.2 GiB | DONE, merged |
| HO-008 | non-PLE families refused by the generic loader (probe) | DONE, merged |
| HO-010 | DeepSeek oracle: `gen: 8913 13 185 40619 317 …`, dumps, parity | DONE, merged |
| HO-011 | OLMoE oracle: `gen: 7785 15 187 187 510 …`; tokenizer gap found | DONE, merged |
| HO-012 | DeepSeek recognition + geometry + `--inspect`; named refusal | **DONE, PR open** |

## 3. Decisions in force (one line each)

| DEC | Meaning |
|---|---|
| 002 / 021 | Route 2 (pinned overlay) confirmed; T1–T5 are the Route 3 triggers |
| 008 / 033 | Strata checkout read-only, except per-handoff authorisation (012 used it) |
| 009 / WAIVER-001 | Auditor on DeepSeek (same family as architect) — **WAIVED, not PASS** |
| 016 | Family-support hold; S1–S3 was authorised by exception, S4 is **not** |
| 019 | Owner accepted HO-007 without a second owner audit |
| 024 | Hash immutable files; pin mutable ones by commit **with** the digest |
| 029 | The TheBloke Mixtral pack is the legacy tensor layout — Mixtral retired |
| 031 | Three-model set: qwen35moe, deepseek, olmoe |
| 032 | AC-3 may be satisfied by a recorded tokenizer refusal (OLMoE, `olmo` pre-tokenizer) |
| 034 | T2 fired at 6 files/234 lines; approved, metadata only; overlay measured cumulatively |
| 035 | Pause record + resume order |
| 036 | QAQC temporarily on `opencode/claude-sonnet-5-5` (Gemini billing cap) |
| 037 | S1–S3 accepted; S4 not authorised |

## 4. Resume checklist (in order)

1. **Merge `wp/strata-012-deepseek-s1`** (PR open, checks were green). Nothing else
   depends on it, but leaving it open makes `STATUS.md` lie again.
2. **Decide the QAQC seat** (DEC-036):
   - Gemini billing restored → revert `.opencode/agents/qaqc.md` to
     `opencode-go/gemini-4-argon#high` and delete DEC-036's substitution note;
   - stay on Sonnet → keep it, and record it as a deliberate choice (it is ~10×
     the cost, much stronger than Gemini).
3. **Sanity check the machine** (2 minutes):
   ```bash
   cd /home/kupipi/Documents/git/gfx1150-inference
   python3 workflow/check_model_policy.py --strict      # expect WAIVED, exit 0
   sha256sum /home/kupipi/Documents/git/strata/build-hip/strata   # d58ee239…
   ls /home/kupipi/Documents/models/gguf/               # packs under §6
   ```
4. **Rebuild the oracle if needed.** `/tmp/opencode/llama.cpp` is gone (tmp was
   cleared). Recipe in `workflow/evidence/HO-STRATA-010/manifest.md` §4: clone
   llama.cpp, checkout tag `b12527` (`78e05298…`), `cmake -B build -DLLAMA_CURL=OFF
   -DBUILD_SHARED_LIBS=ON`, build; the harness source is in
   `workflow/evidence/HO-STRATA-010/artifacts/oracle_harness.cpp`.
5. **Then** decide S4 (§5). Do not start it before 1–2 are done.

### 4.1 Live llama.cpp reference (verified 2026-11-21)

A llama.cpp server is running on this machine and serves the **same DeepSeek pack**
we are targeting, so S4 can use it as the parity reference instead of rebuilding
the CLI harness:

```text
endpoint   http://127.0.0.1:9931   (llama serve; /health 200, /v1/models 200)
model      Lucy-in-the-Sky/deepseek-moe-16b-base-Q4_K_M-GGUF:Q4_K_M  (lazy load)
```

**It reproduces the oracle exactly — but only with token input:**

```text
POST /completion  {"model":"…","prompt":[549,6077,280,7239,317],
                   "n_predict":16,"temperature":0}
  → tokens_evaluated 5, content " Paris.\nParis is the capital of France.\nParis is the capital of"
  → tokenize that content: 8913 13 185 40619 317 254 6077 280 7239 13 185 40619 317 254 6077 280
  → identical to HO-010's `gen:` line (16/16)
```

**Do not send text.** `/v1/completions` with a prompt string prepends a BOS
(`prompt_tokens: 6` for a 5-token prompt) and produces a different continuation
(`" a city of art, culture, and"`). The tokenizer itself is correct — `/tokenize`
returns the 5 IDs — the BOS is added by the completion path.

Notes: the server is a **router** (`--hf-repo`, lazy load) launched with
`--port 33739`; 9931 is where it is reachable, so ignore the args. The response
does not carry a `tokens` array — recover IDs with `/tokenize` on the content.

## 5. S4 — the forward pass (next, not yet authorised)

**Scope:** make DeepSeek-MoE-16B actually run, to the oracle's numbers.

What the pack needs, read from its metadata (HO-012 §2):

- 28 blocks, hidden 2048, **MHA 16/16** (no GQA), rope base 1e4, rms eps 1e-6;
- **block 0 is dense** (`leading_dense_block_count=1`, FF 10944), blocks 1–27 are
  **MoE**: 64 experts, top-6, **2 shared experts**, expert FF 1408;
- `model_family_runs()` must flip true **only** when parity passes — until then the
  named refusal is honest.

**Gates (from `planning/strata-engine/13-…` §4):**

- S4 layer parity against the HO-010 dumps, tolerance fixed **before** the run;
- S5 exact token parity: 3 prompts × 16 tokens, zero mismatches, plus KL;
- S6 baseline + envelope + the HO-007 regression (bit-identical);
- S7 QAQC → audit → signoff.

**Why this is expensive:** it is the first work that touches kernels, and the
first that can fail on numerics instead of structure. It also grows the overlay —
the T2 counter is at 6 files/234 lines, so a forward path will likely cross 300
and should be reviewed as such (DEC-034).

**Recommended first step before S4:** a `workflow/tools/check_bundle.py` that
runs the invariants reviewers keep finding by hand — hashes verify from the repo
root, no needed artifact is git-ignored, no untracked leftovers, fresh-clone
archive verifies, pins resolve with digests. Every rework so far (HO-008, 010,
011) was packaging, not engineering; this removes that class for the larger S4
bundles.

## 6. Environment facts

### Models (hashes in `workflow/MODELS.md`)

| Pack | Path | Size |
|---|---|---|
| Qwen3.6-35B-A3B UD-Q4_K_XL | `Documents/models/gguf/qwen3.6-35b-a3b/` | 21.28 GiB |
| DeepSeek-MoE-16B Q4_K_M | HF cache `models--Lucy-in-the-Sky--…-Q4_K_M-GGUF` | 10.10 GiB |
| DeepSeek-MoE-16B Q8_0 | HF cache `…-Q8_0-GGUF` | 16.22 GiB |
| OLMoE-1B-7B Q4_K_M | `Documents/models/gguf/olmoe-1b-7b/` | 3.92 GiB |
| Mixtral 8x7B Q3_K_M / Q4_K_M | HF cache `TheBloke--Mixtral-8x7B-v0.1-GGUF` | 18.96 / 24.63 GiB (retired, DEC-029) |
| Mistral 7B v0.2 / v0.3 | `Documents/models/gguf/Mistral-7b/` | 4.37 GiB each |

Disk: 153 GiB used, 292 GiB free. The `Deepseek-moe-16b/` and `Mixtral-8x7b/`
directories are empty — the packs live in the HF cache.

### Strata

- Pinned `baf16363`; this branch has the S1–S3 implementation and
  `build-deepseek/`.
- The patch is exported to `workflow/evidence/HO-STRATA-012/patches/` and applies
  cleanly to a fresh `baf16363` worktree — the local branch is *not* pushed anywhere
  (upstream is a third-party repo).
- **Never rebuild `build-hip/`**: it is the signed binary that all Qwen evidence
  depends on.

### Roles (MODEL_POLICY.md)

```text
architect        opencode-go/deepseek-v4-pro#max
coder-primary    opencode-go/kimi-k2.7-code
coder-secondary  opencode-go/qwen3.8-flash#low
qaqc             opencode/claude-sonnet-5-5     (temporary, DEC-036)
auditor          opencode-go/deepseek-v4.1-flash (WAIVED, WAIVER-001)
```

## 7. Carried findings (do not rediscover)

| From | Finding | Action |
|---|---|---|
| HO-010 | B-1: `test-output.txt` is a curated transcript labelled raw; B-2: lib digests are build-scoped; B-4: pins without digests | fix at the next bundle touch |
| HO-012 | F1: `model_family_not_supported` is family-generic — dropping the CUDA/HIP/SYCL suffix changed the `qwen35moe` guard text (accepted scope) | fix when that function is touched |
| HO-012 | F2: `check_architecture_deepseek` checks presence/numeric only; ranges live in `geometry_from_gguf` | verify at S4 |
| HO-011 | OLMoE needs an `olmo` pre-tokenizer **and** a family path | S1+ scope, T1 evidence |
| Audit | The auditor committed its own report (`86d02e6`) | tighten the write boundary in the process doc if revised |

## 8. Budget notes

- The last session stopped at ~7 % of the weekly cap. The unit of cost is a
  **gate cycle**: coder → QAQC → auditor, plus rework. Sonnet QAQC is ~10× Gemini.
- Cheapest useful order when budget is tight: coder run → architect verification
  of the raw artifacts (free-ish) → auditor (DeepSeek Flash) → QAQC (strong model)
  last, on a bundle already self-checked by `check_bundle.py`.
- Do not change a role model at the end of a budget window; decide it deliberately
  (that is what DEC-036 did, and it cost a beat).

## 9. First message (copy-paste)

```text
Resume the Strata project. Read workflow/SESSION_HANDOFF_2026-11-22.md, then
STATUS.md and DECISIONS.md. We are merging the HO-012 PR and deciding the QAQC
seat before anything else. Do not start S4 until I authorize it.
```
