# Session handoff — 2026-11-23 (after HO-013)

**Paste this file into a new session with the `architect` agent selected.**
Reading order: this file → `workflow/STATUS.md` → `workflow/DECISIONS.md` →
`workflow/MODEL_POLICY.md` → `workflow/REFERENCE_SERVER.md`.

---

## 1. Where the project is

gfx1150 only. The 780M is a separate project; MI25 deferred; gfx1100 future.
Strata is a pinned checkout at `baf16363` (`/home/kupipi/Documents/git/strata`);
this repo holds the workflow, evidence and the exported patches.

```text
main                    d1a974d   (PR #24 HO-012, #25 resume, #26 HO-013, #27 STATUS)
open PR                 none
Strata checkout         bac859ef9 on local branch strata-012-deepseek-s1
signed binary           build-hip/strata  d58ee239…  (never rebuilt)
build-deepseek/         present (S1–S3 build, separate directory)
reference server        UP — 127.0.0.1:9931, pid varies, verified 16/16 today
```

**Three-model set** (DEC-031): `qwen35moe` (Qwen3.6-35B-A3B, measured),
`deepseek` (DeepSeek-MoE-16B, recognised + oracle, **does not run**), `olmoe`
(OLMoE-1B-7B, oracle only).

## 2. What is proven

| Handoff | Result | State |
|---|---|---|
| HO-001 | build, support surface (`qwen4exp qwen35moe`), engine boundary | DONE, merged #15 |
| HO-005 | Route 2 confirmed; Route 3 triggers T1–T5 | DONE, merged #19 |
| HO-007 | Qwen3.6-35B-A3B generates 32 deterministic tokens, GTT ~26.2 GiB | DONE, merged #15 |
| HO-008 | non-PLE families refused by the generic loader (probe) | DONE, merged #20 |
| HO-010 | DeepSeek oracle: `gen: 8913 13 185 40619 317 …`, dumps, parity | DONE, merged #22 |
| HO-011 | OLMoE oracle: `gen: 7785 15 187 187 510 …`; tokenizer gap found | DONE, merged #23 |
| HO-012 | DeepSeek recognition + geometry + `--inspect`; named refusal | **DONE, merged #24** (DEC-037) |
| HO-013 | `check_bundle.py` — the evidence gate; 8 codes, 16 fixtures | **DONE, merged #26** (DEC-041) |

## 3. Decisions in force (one line each)

| DEC | Meaning |
|---|---|
| 002 / 021 | Route 2 (pinned overlay) confirmed; T1–T5 are the Route 3 triggers |
| 008 / 033 | Strata checkout read-only, except per-handoff authorisation (012 used it) |
| 009 / WAIVER-001 | Auditor on DeepSeek (same family as architect) — **WAIVED, not PASS** |
| 016 | Family-support hold; S1–S3 was authorised by exception, **S4 is not** |
| 019 | Owner accepted HO-007 without a second owner audit |
| 024 | Hash immutable files; pin mutable ones by commit **with** the digest |
| 029 | The TheBloke Mixtral pack is the legacy tensor layout — Mixtral retired |
| 031 | Three-model set: qwen35moe, deepseek, olmoe |
| 032 | AC-3 may be satisfied by a recorded tokenizer refusal (OLMoE, `olmo` pre-tokenizer) |
| 034 | T2 fired at 6 files/234 lines; approved, metadata only; overlay measured cumulatively |
| 035 | Pause record (2026-11-20); superseded by this handoff's state |
| 036 | **CLOSED** by DEC-039 — the Sonnet substitution expired |
| 037 | S1–S3 accepted; S4 not authorised |
| 038 | The live llama.cpp server is a convenience reference; the CLI oracle is the authority |
| 039 | Gemini billing restored; QAQC back on `gemini-4-argon#high` |
| 040 | `main` is branch-protected: the architect merges via a `merge/*` PR with a merge commit |
| 041 | `check_bundle.py` is the evidence gate; **capture ordering is a rule** |

## 4. Resume checklist (in order)

1. **Machine sanity** (1 minute):
   ```bash
   cd /home/kupipi/Documents/git/gfx1150-inference
   git status --short --branch                      # expect: up to date with origin/main
   python3 workflow/check_model_policy.py --strict  # expect: RESULT: WAIVED, exit 0
   sha256sum /home/kupipi/Documents/git/strata/build-hip/strata   # expect d58ee239…
   python3 workflow/tools/check_bundle.py --all     # expect exit 1, exactly 2 FAILs (HO-011)
   ```
   The two `B3-unlisted` FAILs on `HO-STRATA-011` (`cmd-8.{out,err}.txt`) are
   **real and deliberately not fixed** — that bundle is signed. Anything else is new.

2. **Reference server** (DEC-038, `workflow/REFERENCE_SERVER.md`):
   ```bash
   curl -s -m 3 http://127.0.0.1:9931/health           # {"status":"ok"}
   curl -s http://127.0.0.1:9931/completion -H 'Content-Type: application/json' \
     -d '{"model":"Lucy-in-the-Sky/deepseek-moe-16b-base-Q4_K_M-GGUF:Q4_K_M",
          "prompt":[549,6077,280,7239,317],"n_predict":16,"temperature":0}'
   ```
   Expect `" Paris.\nParis is the capital of France.\nParis is the capital of"`,
   which tokenizes (16 IDs, `/tokenize` **with** the `model` field) to the HO-010
   `gen:` line. Verified 2026-11-23. If the port is dead, restart the server
   before rebuilding anything — it was down on 2026-11-22 and came back without a
   rebuild.

3. **Check GitHub Actions billing** before planning any merge — on 2026-11-23 the
   hosted runners were refused at the account level (§6). PR #28 may still be open
   for that reason alone.

4. **Decide S4** (§5). It is **not authorised**. Nothing in the last two sessions
   moved toward it.

5. **If S4 is authorised:** write `HO-STRATA-014` (ARCHITECT_TO_CODER) with the
   layer-parity gate, the tolerance fixed **before** the run, and DEC-041's
   capture rules. Then launch `coder-primary`.

## 5. S4 — the forward pass (next, still not authorised)

**Scope:** make DeepSeek-MoE-16B actually run, to the oracle's numbers.

What the pack needs, from its metadata (HO-012 §2):

- 28 blocks, hidden 2048, **MHA 16/16** (no GQA), rope base 1e4, rms eps 1e-6;
- **block 0 is dense** (`leading_dense_block_count=1`, FF 10944), blocks 1–27 are
  **MoE**: 64 experts, top-6, **2 shared experts**, expert FF 1408;
- `model_family_runs()` must flip true **only** when parity passes — until then
  the named refusal is honest.

**Gates** (`planning/strata-engine/13-…` §4):

- S4 layer parity against the HO-010 dumps, tolerance fixed **before** the run;
- S5 exact token parity: 3 prompts × 16 tokens, zero mismatches, plus KL;
- S6 baseline + envelope + the HO-007 regression (bit-identical);
- S7 QAQC → audit → signoff.

**Why this is expensive:** the first work that touches kernels, and the first
that can fail on numerics instead of structure. The T2 counter is at
**6 files / 234 lines**; a forward path will likely cross 300 and must be
reviewed as such (DEC-034). Budget it as a gate cycle per iteration, not one.

**What is now different from the last attempt:** the evidence gate exists.
Run `check_bundle.py` on the S4 bundle **before** `CODER_DONE`, and follow the
capture rules in DEC-041 (write to `/tmp`, move with `;`, rebuild derived files,
rehash last). Every packaging rework since HO-008 was avoidable this way.

## 6. Environment facts

### Models (hashes in `workflow/MODELS.md`)

| Pack | Path | Size |
|---|---|---|
| Qwen3.6-35B-A3B UD-Q4_K_XL | `Documents/models/gguf/qwen3.6-35b-a3b/` | 22 GiB |
| DeepSeek-MoE-16B Q4_K_M | HF cache `models--Lucy-in-the-Sky--…-Q4_K_M-GGUF` | 10.10 GiB |
| DeepSeek-MoE-16B Q8_0 | HF cache `…-Q8_0-GGUF` | 16.22 GiB |
| OLMoE-1B-7B Q4_K_M | `Documents/models/gguf/olmoe-1b-7b/` | 4.0 GiB |
| Mixtral 8x7B Q3_K_M / Q4_K_M | HF cache `TheBloke--Mixtral-8x7B-v0.1-GGUF` | retired (DEC-029) |
| Mistral 7B v0.2 / v0.3 | `Documents/models/gguf/Mistral-7b/` | 4.37 GiB each |

Disk: 215 GiB used, 231 GiB free. `Deepseek-moe-16b/` and `Mixtral-8x7b/` under
`gguf/` are empty — those packs live in the HF cache.

### Strata

- Pinned `baf16363`; the S1–S3 branch is `strata-012-deepseek-s1` at `bac859ef9`.
- The patch is exported to `workflow/evidence/HO-STRATA-012/patches/` and applies
  cleanly to a fresh `baf16363` worktree; the local branch is not pushed anywhere
  (upstream is a third-party repo).
- **Never rebuild `build-hip/`**: it is the signed binary all Qwen evidence
  depends on (`d58ee239…`). Use `build-deepseek/` for family work.

### Tooling added in HO-013

```bash
python3 workflow/tools/check_bundle.py <bundle>      # one bundle
python3 workflow/tools/check_bundle.py --all         # every HO-* bundle
python3 workflow/tools/check_bundle.py --all --strict # new bundles: legacy WARNs become FAILs
python3 workflow/tools/check_bundle.py --self-test    # 16 negative controls
```

### Roles (MODEL_POLICY.md)

```text
architect        opencode-go/deepseek-v4-pro#max
coder-primary    opencode-go/kimi-k2.7-code
coder-secondary  opencode-go/qwen3.8-flash#low
qaqc             opencode-go/gemini-4-argon#high   (restored, DEC-039)
auditor          opencode-go/deepseek-v4.1-flash   (WAIVED, WAIVER-001)
```

`gh` is authenticated (account `KupipiKuki`, SSH protocol), so PRs can be opened
and merged from the session. `main` requires **4 checks**; the clean-clone build
takes 9–14 min, so expect ~15 min per merge.

**GitHub Actions billing — check this first (2026-11-23 22:17 UTC).** The three
GitHub-hosted lanes refused to start:

```text
The job was not started because recent account payments have failed or your
spending limit needs to be increased. Please check the 'Billing & plans' section.
```

The **self-hosted GPU lane still passes** (18 s) — self-hosted minutes are free —
but 3 of the 4 required checks cannot run, so **nothing can be merged** while this
stands. It blocked PR #28 (this handoff). Fix it in Settings → Billing & plans,
then re-run the checks on the open PR; no code change is involved. This is GitHub
billing, not the Gemini cap of DEC-036/039.

## 7. Carried findings (do not rediscover)

| From | Finding | Action |
|---|---|---|
| HO-010 | B-1: `test-output.txt` is a curated transcript labelled raw; B-2: lib digests are build-scoped; B-4: pins without digests | fix at the next bundle touch |
| HO-011 | `artifacts/cmd-8.{out,err}.txt` exist and are listed in the manifest, but `hashes.txt` omits them — `--all` is red because of this, correctly | repair when that bundle is next touched; do not tune the tool |
| HO-011 | OLMoE needs an `olmo` pre-tokenizer **and** a family path | S1+ scope, T1 evidence |
| HO-012 | F1: `model_family_not_supported` is family-generic (accepted scope) | fix when that function is touched |
| HO-012 | F2: `check_architecture_deepseek` checks presence/numeric only; ranges live in `geometry_from_gguf` | verify at S4 |
| HO-013 | R3-1/R3-2 manifest citations; R3-3 exit-code wording; R3-4 empty-`File` pin row (latent); R3-5 fixture commit id; R3-6/R3-7 provenance | record-only, carried in the approval; fix with R3-1 at the next bundle touch |
| Audit | The auditor has twice written only its report (correct); the architect commits it verbatim (DEC-041) | keep the write boundary |
| Process | Three QAQC rounds and three audit rounds on HO-013; the failures were evidence packaging, not code | use the tool and DEC-041's rules before asking for review |

## 8. Budget notes

- The unit of cost is a **gate cycle**: coder → QAQC → auditor, plus rework.
  HO-013 cost three of them, because two "passes without doing the work" bugs
  survived a QAQC round. The tool now catches that class mechanically.
- Cheapest useful order: coder run → `check_bundle.py` → architect verification of
  the raw artifacts → QAQC → auditor.
- Do not change a role model at the end of a budget window (DEC-035, DEC-036).
- Local branches from merged work packages are still present; pruning them is
  safe but not required.

## 9. First message (copy-paste)

```text
Resume the Strata project. Read workflow/SESSION_HANDOFF_2026-11-23.md, then
STATUS.md and DECISIONS.md. Run the §4 sanity checks and the reference-server
16/16 call. Do not start S4 until I authorize it; if I do, write HO-STRATA-014
first and gate it with workflow/tools/check_bundle.py.
```
