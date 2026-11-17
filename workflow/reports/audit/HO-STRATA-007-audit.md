# Audit report — HO-STRATA-007

| Field | Value |
|---|---|
| **Handoff** | HO-STRATA-007 (`ARCHITECT_TO_CODER`, state `AUDIT_REVIEW`); reviewed via `CODER_TO_QAQC` `HO-STRATA-007-QAQC` and the embedded `QAQC_TO_AUDITOR` record |
| **Reviewer** | Auditor (`auditor`), runtime model `opencode-go/deepseek-v4.1-flash` (family `deepseek`) — **reported as WAIVED under WAIVER-001 / DEC-009**, not as a clean independent-family PASS (see §2.5) |
| **Date (UTC)** | 2026-11-16T03:42Z (host uptime ≈ 124,700 s) |
| **Verdict** | **PASS (WAIVED — WAIVER-001)** → `ARCHITECT_APPROVAL`, with bookkeeping conditions C1–C5 that must be closed before `DONE` |
| **Evidence reviewed** | `workflow/evidence/HO-STRATA-007/` (`manifest.md`, `commands.log` 34,500 B, `test-output.txt` 12,895 B, `hashes.txt`, `artifacts/` × 10) at commit `f03348d` on `wp/strata-007-qwen35moe-lowtier` |
| **QAQC report** | `workflow/reports/qaqc/HO-STRATA-007-qaqc.md` (QAQC `opencode-go/gemini-4-argon#high`, family `gemini`, verdict PASS) |
| **Scope reviewed** | Diff `afcc2096367cc8b17f72acd9708c886c9acc94bc..bd823f52fc1482c349169f72e9f49c3d0a8828d7` — 18 files, all HO-007 workflow artifacts; Strata checkout `/home/kupipi/Documents/git/strata` at `baf16363b4403ef0ed4f538f5d5ed11c43fb9535`, `git status --porcelain` empty |
| **Profile (one only)** | gfx1150 (Radeon 890M, Ryzen AI 9 HX 370, 92 GiB RAM, 2 GiB VRAM carveout + 45.97 GiB GTT) · ROCm `/opt/rocm/core-10.1`, HIP `7.16.26385`, hipBLASLt `1.4` (`100401`), kernel `7.0.0-42-generic` · `Qwen3.6-35B-A3B` (`qwen35moe`, catalog family `qwen36`), `UD-Q4_K_XL` · workload: one-shot greedy (`temperature=0`), 5-token prompt, 32 new tokens, 1024 context cells |

---

## 1. Evidence verification

- [x] **Manifest complete; commands reproducible.** `manifest.md` records 7 commands with CWD and exit codes; I re-ran the acceptance command, the pack identification, the tokenizer encode/decode, and the control plan in this session — all reproduced (§1.1).
- [x] **Outputs raw; failures/skips kept verbatim.** `test-output.txt` holds the pre-run meminfo, pre-run `dmesg`, engine output, `exit:0`, post-run meminfo, post-run `dmesg`, with no paraphrase. The one refusal in the work — `./build-hip/strata generate` → `unknown argument: generate`, exit `2` — is documented both as raw artifact (`artifacts/engine-generate-help.txt`) and as a scope note (`manifest.md:52`, `HO-STRATA-007.md:112-126`); I reproduced it (`exit=2`). No skip is presented as a pass.
- [x] **Artifacts/hashes match the manifest.** `sha256sum -c hashes.txt` → **8/8 `OK`**, exit `0`. The model (`55983c5a…`) and the signed binary (`d58ee239…`) both verify; the GGUF is 22,853,663,008 B and its digest equals the catalog pin at `/home/kupipi/Documents/git/strata/setup.py:747`. Six auxiliary `artifacts/` files plus `manifest.md` are not listed in `hashes.txt` (QAQC M1); I recomputed all 15 digests and they match QAQC's §1.2 table. Non-blocking — see §3 and condition C1. `sha256sum -c` also prints `WARNING: 8 lines are improperly formatted` because `hashes.txt` interleaves label lines with digest lines; cosmetic, folded into M1.
- [x] **Environment recorded.** OS/kernel/ROCm/HIP/hipBLASLt/amd-smi/binary hash present and independently confirmed (`rocminfo` Agent `gfx1150`; HIP `7.16.26385-0000000`; `libhipblaslt.so.1.4`; kernel `7.0.0-42-generic`; `HSA_OVERRIDE_GFX_VERSION` unset). One field is wrong: `manifest.md:8` says `Python 3.12`, while the interpreter actually used (`python3` in `PATH`) is `3.14.10`; `/usr/bin/python3.12` exists but is not the default (QAQC M4). Deterministic outputs reproduce under `3.14.10` (§1.1), so this is a record defect, not a reproducibility failure — condition C4.
- [x] **No secrets.** Pattern scan over the bundle and both handoffs (`hf_*`, `ghp_*`, `api_key=`, `token=`/`Bearer`, 16+ char values) returned zero matches. No model weights in git: the largest committed file is `commands.log` (34,500 B); the 22.85 GB GGUF lives outside the repo at `/tmp/opencode/qwen36/`.

### 1.1 Independent re-run (this audit)

```text
$ cd /home/kupipi/Documents/git/strata
$ LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib ./build-hip/strata \
    --native /tmp/opencode/qwen36/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf \
    --tokens 760,6511,314,9338,369 --n 32 --max-context 1024
strata-q36: /tmp/opencode/qwen36/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf: 753 tensors (layout checked), 4.40 GiB on the GPU in 1.0 s (the routed experts are placed after the engine's buffers)
strata-q36: prompt experts: 0 of 41 layers on the fused int8 kernels, 41 on our int8 kernels, 0 on MMQ (int8)
strata-q36: context 1024 cells, prompt chunk 4096, MTP block loaded, 38.72 GiB of VRAM free
strata-q36: every routed expert in VRAM (18.75 GiB) in 3.3 s
strata-q36: warmed up in 3.7 s (one prompt chunk, a decode step)
gen: 11751 11 264 3177 34756 364 1141 25438 57902 1680 430 279 242476 300 21262 11 279 9440 46890 15849 11 321 279 42027 9141 368 54832 13 11751 369 1048 10919
strata-q36: prompt 5 tokens in 88.3 ms (56.6 tok/s), 32 generated in 1621.7 ms (19.7 tok/s)
exit=0
```

- **Token IDs:** 32/32 identical to `artifacts/generated-token-ids.txt` (and to the QAQC re-run). Fourth independent execution on this host.
- **Decoded text:** independently re-derived from the GGUF tokenizer —
  `' Paris, a city renowned for its iconic landmarks such as the Eiffel Tower, the Louvre Museum, and the Notre-Dame Cathedral. Paris is also famous'` — byte-identical to `artifacts/generated-text.txt`.
- **Prompt encode:** `Tokenizer.from_gguf(...).encode('The capital of France is')` → `[760, 6511, 314, 9338, 369]`, identical to `artifacts/prompt-token-ids.txt` and to the `--tokens` argument.
- **Timing line** is reproduced as a raw observation only (88.3 ms / 1,621.7 ms here vs 88.8 / 1,601.5 coder, 90.7 / 1,630.7 QAQC). It is preserved verbatim and is **not** used as a performance claim by anyone.
- **Resource envelope, in-run sampling** (0.5 s interval, `amd-smi metric -g 0 -m` + `/proc/meminfo`): peak `GPUActive 27,457,580 kB` (`26.19 GiB` / `27.46 GB`) and peak `USED_GTT 26,814 MB`; pre-run `GPUActive 118,620 kB`, `USED_GTT 109–115 MB` across the three sessions; after exit `GPUActive 108,380 kB`, `USED_GTT 105 MB` — the model is fully released, no leak. Immediate post-run `GPUActive 27,224,412 kB`, `MemFree 15,480,520 kB`. These bracket the coder's `27,238,816 kB` / `14,446,844 kB` and QAQC's `27,222,244 kB` / `15,554,856 kB`: the envelope claim is corroborated by three independent sessions.

---

## 2. Claim and scope audit

- [x] **Every claim cites a command and an output.** Pack identity → `artifacts/engine-families.txt` (`qwen4exp qwen35moe`) + `artifacts/control-plan-qwen36.json`; pack hash → `hashes.txt` + `setup.py:747`; load → engine output in `test-output.txt`; 32 tokens → `gen:` line + `generated-token-ids.txt` + `generated-text.txt`; envelope → `test-output.txt` pre/post blocks; environment → `commands.log` + `hashes.txt`. All verified.
- [x] **One profile per claim.** `gfx1150` / `Qwen3.6-35B-A3B` / `UD-Q4_K_XL` / greedy / 1024 cells only. No Mixtral, Qwen3-30B-A3B or DeepSeek run; no 780M, MI25 or gfx1100 data; no cross-profile transfer.
- [x] **No performance, throughput, quality or support claim.** The words `faster`, `speedup`, `outperform`, `beats`, `SOTA`, `production` do not appear in any HO-007 artifact. `supported` appears only as pre-existing scope language for the catalog pack (HO-001/DEC-016), not as a result of this run. The engine's self-printed `tok/s` line is raw output, explicitly disclaimed at `manifest.md:54`, and is not restated in the handoff, the QAQC report's conclusions, or `STATUS.md`.
- [x] **Scope matches the handoff; no silent expansion.** Diff `afcc2096..bd823f5` = 18 files: 14 evidence files, `HO-STRATA-007.md`, `HO-STRATA-007-QAQC.md`, `workflow/reports/qaqc/HO-STRATA-007-qaqc.md`, and one `STATUS.md` row + one project-state paragraph. Nothing else. The two path adaptations (Control server path unusable, `generate` subcommand rejected) are recorded in-scope adaptations with raw backing, not scope change.
- [x] **Guard rails respected.** No Strata source change: `git -C /home/kupipi/Documents/git/strata status --porcelain` empty, HEAD `baf16363b4403ef0ed4f538f5d5ed11c43fb9535`, `build-hip/strata` `d58ee239…` (the signed HO-001 build). No new dependency (no `pip`/`apt`/ROCm change). No model conversion — the engine reads the catalog GGUF directly. No secrets. Evidence committed once at `f03348d` and never mutated afterwards (git log of `workflow/evidence/HO-STRATA-007/` shows only `f03348d`), so QAQC stayed read-only.
- [x] **Rework history is closed or named.** No `RW-HO-STRATA-007-*` exists; none is required by this audit. The HO-001 rework (`RW-HO-STRATA-001-1`) is closed and unrelated.
- [x] **DoR / DoD.** DoR: all ten items marked; the base commit is named in the log (`afcc2096…`, `HO-STRATA-007.md:140`) though the field itself says "this branch's start" — a wording nit, not an unmet gate. The added DoR line recording the pack/quant confirmed at execution is a clarification inside the authorized pack, not new scope. DoD: all seven items marked; the manifest gaps are M1/A-2/A-3 below, none of which defeats an acceptance criterion.

### 2.5 Process and model separation

- **Coder vs QAQC (R4/R5): satisfied.** `coder-primary` = `opencode-go/kimi-k2.7-code` (family `kimi`), `qaqc` = `opencode-go/gemini-4-argon#high` (family `gemini`) — different families, so Gemini did not check Kimi's own work. `python3 workflow/check_model_policy.py` lists exactly these.
- **Auditor (R2/R5): WAIVED, not PASS.** I am `opencode-go/deepseek-v4.1-flash` (family `deepseek`), the architect's family. Under **WAIVER-001 / DEC-009** this is an accepted exception, so this report's verdict is a **WAIVED audit**: the evidence is sound, but the family independence that R2 wants is absent and the architect's own review plus the owner remain the compensating checks. Do not read this as a clean independent-family PASS.
- **Policy state: PENDING.** `python3 workflow/check_model_policy.py --strict` exits `2` (architect model unset — the session model is DeepSeek and DEC-013 forbids writing an agent file mid-session). Not introduced by HO-007; recorded as checkpoint 1a in `OT-STRATA-001`.
- **No per-call model override: no contrary evidence.** Each of the four assigned role files carries an explicit `model:` line, and the QAQC report records Argon usage consistent with `qaqc.md`, and my own runtime matches `auditor.md`. **Verification limit:** the artifacts cannot prove the negative (that the orchestrator passed no `model` override to `subagent`); that rests on DEC-013 compliance by the architect. Same limit applies to the coder's `kimi` attribution, which is asserted by QAQC and by the agent file, not by an in-repo artifact.
- **State chain:** `READY` (architect, `HO §12` + `afcc2096` commit) → `IN_PROGRESS` (coder, base `afcc2096`) → `CODER_DONE` (`f03348d`) → `QAQC_REVIEW` → `AUDIT_REVIEW` (QAQC PASS, `bd823f5`, `HO-STRATA-007.md:7`, `STATUS.md:16`). One bookkeeping defect: `HO-STRATA-007-QAQC.md` still reads `State: PROPOSED` with an unticked DoD and a blank receiver signature, because QAQC treated itself as read-only outside `reports/qaqc/` and embedded the `QAQC_TO_AUDITOR` record in its report instead — new finding A-1, condition C2.

---

## 3. Findings / rework

### 3.1 QAQC findings M1–M4 — dispositions

| # | QAQC severity | My disposition | Reasoning |
|---|---|---|---|
| **M1** | Minor | **Upheld as Minor — non-blocking; close as C1.** | `hashes.txt` covers the 8 artifacts the claims rest on and all verify. The 6 unlisted auxiliary files (`control-plan-qwen36.json`, `engine-families.txt`, `engine-generate-help.txt`, `control-launch-help.txt`, `engine-geometry.txt`, `decode-command.txt`) plus `manifest.md` are still pinned by commit `f03348d`, and I independently re-derived their contents by re-running the plan (`engine_missing true`, `engine_usable false`) and `--families` (`qwen4exp qwen35moe`). No claim depends on an unhashed file's integrity alone, so this does not hide a wrong claim — but `ENGINEERING_WORKFLOW.md` §8 ("artifacts have a path and a SHA256") is not fully met, so it must be completed, not just noted. |
| **M2** | Minor | **Upheld as Minor — non-blocking; close as C3.** | The label conflates decimal `GB` with binary `GiB`: `GPUActive 27,238,816 kB` = `27.24 GB` decimal but `25.98 GiB` binary, so `27.2 GiB` overstates by ~4.7 %. The error is conservative (it overstates memory use, so it cannot make "it fits" look better than it is), and the raw kB in `test-output.txt` are exact. My sample confirms peak `27,457,580 kB` = `27.46 GB` / `26.19 GiB`. Restate in kB (or correct GiB) before DONE. |
| **M3** | Minor | **Upheld as Minor — non-blocking; close as C3.** | `HANDOFF_CONTRACT` requires license/provenance; provenance URL (`unsloth/Qwen3.6-35B-A3B-MTP-GGUF`) and the catalog pin are recorded, and the pin carries `"license": "Apache 2.0: https://huggingface.co/Qwen/Qwen3.6-35B-A3B"` (verified at `setup.py:758` by me). The requirement is met by a citation into a pinned file, which is auditable, so the criterion does not fail; inlining the string is a readability fix. |
| **M4** | Minor | **Upheld as Minor — non-blocking; close as C4.** | The environment field is **wrong as written**: default `python3` is `3.14.10`, not `3.12` (`/usr/bin/python3.12` exists but was not the interpreter in `PATH`). This is the one M-finding that is a factual error rather than a labeling choice. It does not defeat reproducibility: I re-ran the encode and the decode under `3.14.10` and got the exact recorded values, and the tokenizer is GGUF-driven. Correct the manifest and name the interpreter that produced the tokenizer artifacts. |

No M-finding was inflated into a blocker: each is a record/format defect whose underlying datum is independently reproducible. None is dismissed either — each has a named close condition.

### 3.2 New findings from this audit

| # | Severity | Finding | Required action | Owner |
|---|---|---|---|---|
| **A-1** | Minor (process) | `workflow/handoffs/HO-STRATA-007-QAQC.md` still says `State: PROPOSED`, its DoD §9 is unticked, and the Receiver signature is blank, while the QAQC PASS is recorded in `HO-STRATA-007.md:7,142-145`, `STATUS.md:16` and the report's embedded `QAQC_TO_AUDITOR` block. The transition is traceable, but the handoff file contradicts it — `HO-STRATA-007-QAQC.md:7,87-98`. | Complete the QAQC handoff (state `AUDIT_REVIEW`, DoD ticked, QAQC signature/date) or file the embedded `QAQC_TO_AUDITOR` as `workflow/handoffs/HO-STRATA-007-AUDIT.md`. The architect should also resolve the write-boundary ambiguity (workflow §4 vs the QAQC transition duty) in `DECISIONS.md`. | Architect / QAQC (C2) |
| **A-2** | Minor (evidence) | AC-5 names `GTT` and `rocm-smi`; the coder's bundle records `/proc/meminfo` (`GPUActive`) and `dmesg` but **no GTT and no `rocm-smi`/`amd-smi` output**. `rocm-smi` is not installed on this host (verified), and no `amd-smi` output exists in the bundle. The GTT datum exists only in the QAQC report (`USED_GTT 26,814 MB`), which I reproduced (§1.1). | Either add the `amd-smi metric -g 0 -m` command + output to the bundle, or have the architect record explicitly that the reviewer-measured GTT is the evidence of record for AC-5. | Coder / Architect (C1) |
| **A-3** | Minor (record) | `manifest.md:6` labels `afcc2096…` as "Commit / branch" — that is the **base** commit; the evidence commit is `f03348d` (the handoff and QAQC report both use it). A reader re-checking the manifest against HEAD would diff the wrong interval. | Record both: base `afcc2096…`, evidence `f03348d` (and branch head `bd823f5` at review). | Coder (C1) |
| **A-4** | Observation (no action on the claim) | The whole kernel log contains no `amdgpu` ring timeout, no GPU reset and no page fault — consistent with the recorded "no resets/errors". However, my repeated audit re-runs induced three new lines `workqueue: kfd_process_wq_release [amdgpu] hogged CPU for >13333us …` (uptimes 124497/124634/124686) on process teardown. These are CPU-scheduling advisories, not GPU faults; the coder's recorded run (uptime ≈ 115,864) produced zero new kernel messages, so `test-output.txt`'s pre/post `dmesg` identity is genuine for that run. | No rework. For future envelope logs, sample `amd-smi` during the run and note teardown CPU hogs separately from GPU errors. | Architect (informational) |

### 3.3 Counter-hypotheses tested

| Hypothesis | Test | Result |
|---|---|---|
| The `gen:` output is a template/cache rather than model output | Two unprompted probes on the same binary/profile: `"The capital of Germany is"` → `760,6511,314,9564,369` → `gen: 19241 13 19241 369 264 3177 20105 11`; `"def add(a, b):\n    return"` → `727,884,2784,11,292,1590,198,262,460` → `gen: 264 478 292 271 727 31192 2784 11` | **Falsified.** Output tracks the prompt; a cache/template would be invariant. Only the recorded baseline prompt is used as evidence; the probes are audit falsification, not a new claim. |
| Token IDs and decoded text disagree (post-hoc text invention) | Re-derive decode from the GGUF tokenizer; re-derive encode of the prompt | **Agree exactly** — 32 IDs → the recorded sentence; prompt → the recorded 5 IDs. |
| The model was never really loaded (numbers quoted from another session) | Timestamp/uptime correlation, four independent executions, in-run sampling, full release after exit | **Consistent.** Identical engine load lines (`753 tensors`, `4.40 GiB`, `18.75 GiB` experts), peak GPU memory ~27.46 GB during the run and ~0 afterwards, no process left holding memory. |
| The resource envelope contradicts the load claim | In-run `amd-smi`/`meminfo` sampling (§1.1) | **Supports it**: 26.19 GiB of GTT in use at peak, `dmesg` free of GPU faults, full release. |
| `engine_missing: true` is being misused to excuse a Control path that actually works | Re-ran `strata.py launch --plan --model UD-Q4_K_XL --family qwen36 --output json`; re-ran `strata generate` | **Documented reason stands** — plan returns `engine_missing true` / `engine_usable false`, and the binary rejects the `generate` word with `unknown argument: generate` (exit `2`) while its usage text advertises `strata generate --pack DIR …`. The `--native` one-shot path is the only working path on this build; the refusal is quoted verbatim in the bundle. |

---

## 4. Verdict

- **PASS (WAIVED — WAIVER-001)** → `ARCHITECT_APPROVAL`. Attach this report and `workflow/evidence/HO-STRATA-007/` to the architect's review. No `RW-HO-STRATA-007-*` is opened: every acceptance criterion is reproduced and no claim is unsupported, so a rework handoff would be scope-free bureaucracy against a correct result.
- The PASS is **conditional on bookkeeping closure before `DONE`** (nothing here changes a measurement or a claim):

| # | Condition | Owner | Why it is a condition, not rework |
|---|---|---|---|
| **C1** | Add the 6 auxiliary `artifacts/` digests + `manifest.md` to `hashes.txt` (and drop the label-line format warnings); add the GTT/`amd-smi` command + output to the bundle; fix the `manifest.md:6` commit field | Coder, on the same work-package branch | Contract-completeness defects; the underlying data is independently reproducible and already verified by QAQC and by this audit |
| **C2** | Bring `HO-STRATA-007-QAQC.md` in line with the PASS (state, DoD, signature) or file the embedded `QAQC_TO_AUDITOR`; rule on the write-boundary ambiguity in `DECISIONS.md` | Architect / QAQC | Process record; the chain is already visible in `HO-STRATA-007.md`, `STATUS.md` and the QAQC report |
| **C3** | Correct the `GB`/`GiB` labels in `manifest.md:31,61`; inline the Apache-2.0 license string | Coder | Wording, raw data exact |
| **C4** | Correct the Python version in `manifest.md:8` (default `python3` = `3.14.10`) and name the interpreter that produced the tokenizer artifacts | Coder | Factual record error with no effect on determinism |
| **C5** | Move `STATUS.md:16` and the `OT-STRATA-001` checkpoint-6 row forward only after the architect signs; merge only after signoff (DEC-015 selective-merge rule) | Architect | State hygiene; the auditor does not final-approve |

**Not signed by the auditor.** The architect decides `DONE` and merges; my role ends at this verdict and the evidence pointer.

---

## 5. Owner-task oversight

- Owner task: `OT-STRATA-001` (DEC-017 authorized this run as checkpoint 6).
- Checkpoints met: **6 — qwen35moe low-tier (007)** is met at the evidence level — one supported family loaded and generated on gfx1150 with hashes, envelope and limits recorded, no claims. Still open and unaffected: 1a (model policy `--strict`, architect-only), 2/3/4 (blocked by DEC-016), 5 (Route 2 vs 3, needs a signed baseline).
- Owner-facing statement that is now supportable: *on gfx1150 with the signed `baf16363` build and ROCm 10.1, the catalog `qwen35moe` pack (`Qwen3.6-35B-A3B`, `UD-Q4_K_XL`, 22.85 GB) loads, peaks at ~27.5 GB of GPU-visible memory (GTT) and produces 32 deterministic greedy tokens from a fixed prompt, reproducibly.* Nothing about speed, quality or support breadth.
- Owner acceptance: **pending** — checkpoint 6 is not recorded as accepted in `OT-STRATA-001` until the architect signs and the auditor reports it (C5).

---

## 6. Statement

I did not modify code, tests, docs, configuration, evidence, handoffs, or the Strata checkout. My only writes were this report and a scratch run log under `/tmp/opencode/`. My executions used the signed binary read-only: one baseline re-run, one resource-sampled re-run, two prompt-sensitivity probes (falsification only, no new claim), plus read-only verification commands (`sha256sum`, `git`, `rocminfo`, `hipcc --version`, tokenizer encode/decode, `strata.py launch --plan`).
