# HO-STRATA-006 — model-family support investigation (read-only)

| Field | Value |
|---|---|
| **ID** | HO-STRATA-006 |
| **Type** | ARCHITECT_TO_CODER |
| **State** | **DEFERRED** — owner hold (DEC-016); not cancelled, DoR kept for restart |
| **Created / updated (UTC)** | 2026-11-16 / 2026-11-16 |
| **From → To** | Architect → Primary Coder (`coder-primary`) |
| **Work package** | `strata-006-model-support` |
| **Priority / timebox** | P1 · 1 working day when reopened |
| **Owner task** | OT-STRATA-001 (checkpoint 1a/2); decision DEC-010 |

## 0. Repositories, branches and base commits

| Checkout | Path | Branch | Base commit | What may change |
|---|---|---|---|---|
| **Workflow repo** (`gfx1150-inference`) | `/home/kupipi/Documents/git/gfx1150-inference` | `wp/strata-006-model-support` (created by the architect) | `750dd2f` (HO-STRATA-001 SIGNED) | `workflow/evidence/HO-STRATA-006/**`, `workflow/handoffs/HO-STRATA-006.md` |
| **Strata checkout** | `/home/kupipi/Documents/git/strata` | **no branch, no commits** | `baf16363b4403ef0ed4f538f5d5ed11c43fb9535` (DEC-007) | nothing — read-only, `git status --porcelain` empty at CODER_DONE |

## 1. Scope (in)

Answer, with file/line evidence from the pinned tree, what it takes to make this
engine run **one** additional model class, and what each class costs. This is an
**investigation**: the output is a decision document, not code.

1. **Family registration.** Where the compiled family list comes from
   (`src/program/generate.cpp:3566-3574`, `STRATA_HAVE_QWEN35`,
   `cmake/strata_gpu_engine.cmake`), and what an entry actually controls: GGUF
   `general.architecture` string, pack layout, tensor-name map, chat template,
   tokenizer, Control-side acceptance (`strata_control/feed.py`,
   `retired.py`, `runtime.py`).
2. **Family descriptor.** Which per-family fields exist and must be supplied:
   layer count, hidden size, expert count / active experts, routing (top-k,
   groups), attention (GQA/MQA/MLA, sliding window), RoPE variant, tokenizer
   (BPE vs SentencePiece), chat template, MTP/drafter, quantization hooks.
3. **Reuse analysis per candidate**, one row each, with the code path named:
   - **Mixtral 8x7B** — can it reuse the existing MoE routing and grouped GEMM?
     Where does its 8x7B shape differ from `qwen35moe` (Qwen3.6-35B-A3B)?
   - **Qwen3-30B-A3B** — is it shape-close to `qwen35moe`, and if so what
     actually differs (attention, RoPE, tokenizer, chat template)? **It is not
     the same model as Qwen3.6-35B-A3B.**
   - **DeepSeek-V2-Lite / DeepSeek-MoE-16B** — does it need MLA / a new attention
     path that neither supported family has? If yes, say so and estimate the
     size of the work.
4. **Effort and risk table**, cheapest-first, with a recommendation for the
   first family to support as a proof of concept, and the smallest model file
   that would test it (name the *class* and quant target — **do not download**).
5. **What a low-tier test would need** per class (per `planning/strata-engine/11-model-support-investigation.md` §2): smallest quant, 512–2,048-token context, 16–64 deterministic tokens, correctness check, the memory a run needs on this host (91 GB RAM, `ttm.pages_limit` 12,050,777 pages ≈ 46 GiB GTT).

## 2. Out of scope

- **Any code change to Strata.** This handoff adds and patches nothing.
- **Downloading or running any model.** No `strata launch` without `--plan`, no
  `setup.sh`, no huggingface/curl, no pack assembly.
- Implementing support (that is the handoff after this one, as a deviation,
  because HO-STRATA-001 kept Strata read-only).
- Baseline measurements (HO-STRATA-002/003/004, blocked on this).
- The Route 2 vs Route 3 decision (HO-STRATA-005, which consumes this result).
- 780M, MI25, gfx1100, gfx1151, gfx1201; performance or support claims.

## 3. Inputs

| Input | Path / source | Status |
|---|---|---|
| HO-STRATA-001 evidence | `workflow/evidence/HO-STRATA-001/` (`families.txt`, `engine-boundary.md`, `help.txt`) | available |
| HO-STRATA-001 approval | `workflow/handoffs/HO-STRATA-001-APPROVAL.md` | available |
| Pinned Strata tree | `/home/kupipi/Documents/git/strata` @ `baf16363b4…` | available, read-only |
| Engine docs | Strata `docs/HOW_IT_WORKS.md`, `AGENTS.md`, `docs/MODELS.md`, `docs/QUANTS.md` | available |
| Family list source | `src/program/generate.cpp:3566-3574`; `cmake/strata_gpu_engine.cmake` (`STRATA_HAVE_QWEN35`) | available |
| Control-side policy | `strata_control/feed.py`, `feed_models.py`, `retired.py`, `runtime.py`, `shape_engine.py` | available |
| Prior investigation plan | `planning/strata-engine/11-model-support-investigation.md` | available (questions 1–3 are the core) |
| Decision | DEC-010 (support first, then low-tier tests on all classes) | adopted |

## 4. Acceptance criteria

| # | Criterion | Command / check | Expected |
|---|---|---|---|
| 1 | Branch/base and pin verified | `git rev-parse HEAD` in both checkouts; `git -C …/strata status --porcelain` | workflow repo at `750dd2f`+ on `wp/strata-006-model-support`; Strata `baf16363b4…`, porcelain empty |
| 2 | Registration map | `grep -n` of the family list, `STRATA_HAVE_QWEN35`, and the Control-side family tables | `artifacts/family-registration.md`: every place a family name is decided, with file:line, and a one-line statement of what changes when one is added |
| 3 | Descriptor map | reading `src/` + `include/` for per-family fields | `artifacts/family-descriptor.md`: the field list, where each is consumed, and which are mandatory vs defaulted |
| 4 | Reuse matrix | per-candidate reading, one row each | `artifacts/reuse-matrix.md`: Mixtral 8x7B, Qwen3-30B-A3B, DeepSeek-V2-Lite/MoE-16B — reuse / adapt / new-path, with the file:line that decides it, and **no** guessing where the code does not answer |
| 5 | Effort/risk + recommendation | synthesis of 2–4 | `artifacts/recommendation.md`: cheapest-first table (effort in days, risk, what breaks if wrong), the recommended first family, and the smallest test model per class |
| 6 | Low-tier run requirements | memory arithmetic against this host | in `recommendation.md`: per class, the RAM/GTT a low-tier run needs vs 91 GB RAM and ≈46 GiB GTT, and whether it fits |
| 7 | No unsupported claim | read your own output | every sentence that asserts engine behaviour cites a file:line or a command; "not determinable from the code" is an acceptable, expected answer |
| 8 | Evidence bundle | `ls -R workflow/evidence/HO-STRATA-006/` | `manifest.md`, `commands.log`, `test-output.txt`, `artifacts/`, `hashes.txt`; no secrets; no weights; no downloads |

## 5. Evidence required

- `workflow/evidence/HO-STRATA-006/manifest.md` (from `templates/EVIDENCE_MANIFEST.md`)
- `commands.log`, `test-output.txt`, `hashes.txt` (incl. the pinned SHA and the STRATA_HAVE_QWEN35 build flag)
- `artifacts/family-registration.md`, `family-descriptor.md`, `reuse-matrix.md`, `recommendation.md`
- No model files, no tokens, no secrets. **No network fetches of model metadata
  beyond what the pinned tree already contains** — if a fact needs the internet,
  write "not determinable offline" and move on.

## 6. Guard rails

- Strata stays read-only: no edit, no patch, no commit, `git status --porcelain` empty. `build-hip/` already exists from 001 and may be used read-only.
- **No model download, no model run, no `setup.sh`, no package installs.**
- Write only under `workflow/evidence/HO-STRATA-006/**` and this handoff in the workflow repo.
- No merge, no push to `main`; commit only on `wp/strata-006-model-support`.
- No performance, throughput, quality or support claims. A family is "supported" only after a low-tier test in a later handoff — never after an investigation.
- No 780M / MI25 / gfx1100 / gfx1151 / gfx1201 comparisons.
- No secrets.

## 7. Dependencies / blockers

| Dependency | Owner | Status | Needed by |
|---|---|---|---|
| HO-STRATA-001 SIGNED | Architect | **resolved** (2026-11-16) | start |
| Strata pin | Architect | resolved (DEC-007) | all |
| Branch `wp/strata-006-model-support` | Architect | **resolved** @ `750dd2f` | before READY |
| Owner decision: accept DEC-010 (support-first) vs descope to the two supported Qwen families | Owner via Auditor | **open** | before the *implementation* handoff, not this one |
| A model file per class (later) | Owner | open (OT decisions 2–4) | HO-002/003/004 |

## 8. Definition of Ready

- [x] ID/type/from/to/title/work package present
- [x] Branch and base commit named and existing (`wp/strata-006-model-support` @ `750dd2f`; Strata pinned)
- [x] Scope and out-of-scope explicit
- [x] Inputs linked and available
- [x] Every criterion has a command/check
- [x] Evidence requirements runnable
- [x] Guard rails explicit
- [x] Dependencies resolved or owned
- [x] Priority/timebox set
- [x] No open `NEEDS_INFO` (owner decisions block the *implementation*, not this investigation)

## 9. Definition of Done

- [ ] AC-1…AC-8 run; raw output in the bundle
- [ ] Registration and descriptor maps complete, with file:line for every claim
- [ ] Reuse matrix covers the three candidate classes and names the blocking code path where one exists
- [ ] Recommendation: cheapest-first table + the first family + the smallest test model + the memory arithmetic
- [ ] Strata checkout clean; nothing written outside the evidence dir and this handoff
- [ ] No claims beyond the code; "not determinable offline" used where true
- [ ] Evidence manifest complete; handoff `CODER_DONE`; `CODER_TO_QAQC` created
- [ ] Committed on `wp/strata-006-model-support` (no merge, no push)

## 10. Signatures

| Role | Name/agent | Date | Decision |
|---|---|---|---|
| Sender (Architect) | architect | 2026-11-16 | READY — DoR complete |
| Receiver (Primary Coder) | `coder-primary` | | |

## 11. Log

- 2026-11-16 Architect: created after HO-STRATA-001 SIGNED, per DEC-010
  (support-first). HO-STRATA-002/003/004 are `DEFERRED` on this handoff: the
  pinned engine implements `qwen4exp` and `qwen35moe` only, so those three
  baselines have nothing to run yet. Branch based on the signed state `750dd2f`.
- 2026-11-16 Architect: `READY`. This is the cheapest possible next step — it
  costs reading, not building, and it decides whether the owner's three test
  beds are a day of work or a kernel project.
- 2026-11-16 Architect: **DEFERRED by owner decision (DEC-016).** The owner chose to keep
  DEC-003 unchanged and block the three test beds rather than accept the support-first path
  (DEC-010), and to hold technical work until OT-STRATA-001 decisions 2–5 are answered. No
  coder is launched. The DoR checklist above stays valid, so restarting this handoff later is a
  state change, not a rewrite. Nothing was executed under this ID.
