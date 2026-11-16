# QAQC report — HO-STRATA-007

| Field | Value |
|---|---|
| **Handoff** | HO-STRATA-007 (`ARCHITECT_TO_CODER`) → reviewed via `CODER_TO_QAQC` `HO-STRATA-007-QAQC` |
| **Reviewer** | QAQC (`qaqc` subagent), runtime model `Gemini 4 Argon` (`opencode-go/gemini-4-argon`, family `gemini` — distinct from `coder-primary` `opencode-go/kimi-k2.7-code` and `auditor` `opencode-go/deepseek-v4.1-flash`) |
| **Date (UTC)** | 2026-11-16 |
| **Verdict** | **PASS** → `AUDIT_REVIEW` |
| **Scope reviewed** | Branch `wp/strata-007-qwen35moe-lowtier` at `f6ee3556d1e546607fe0fe5f5a72aa0e7c29b52a` (commits `f03348d` + `f6ee355`) vs base `afcc2096367cc8b17f72acd9708c886c9acc94bc` (17 files: 14 under `workflow/evidence/HO-STRATA-007/`, `workflow/handoffs/HO-STRATA-007.md`, `workflow/handoffs/HO-STRATA-007-QAQC.md`, `workflow/STATUS.md`); pinned Strata checkout `/home/kupipi/Documents/git/strata` at `baf16363b4403ef0ed4f538f5d5ed11c43fb9535` (read-only) |
| **Profile (one only)** | AMD Radeon 890M (`gfx1150`) / Ryzen AI 9 HX 370 (92 GiB RAM, 2 GiB VRAM carveout + 45.97 GiB GTT), ROCm `/opt/rocm/core-10.1`, hipBLASLt `100401`, model `Qwen3.6-35B-A3B` (`qwen35moe` / catalog family `qwen36`), quant `UD-Q4_K_XL` (`Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf`), workload: one-shot greedy (`temperature=0`), 5-token prompt (`"The capital of France is"`), 32 new tokens (`--n 32`), 1024 context cells (`--max-context 1024`) |

---

## 1. Acceptance criteria re-run

Every acceptance criterion in `HO-STRATA-007.md` (§4) and `HO-STRATA-007-QAQC.md` (§4) was re-run independently in this session from `/home/kupipi/Documents/git/strata` and `/home/kupipi/Documents/git/gfx1150-inference`.

| # | Criterion | Command (re-run by QAQC) | Observed (QAQC independent run) | Pass? |
|---|---|---|---|---|
| 1 | Pack identified (`qwen35moe` / `Qwen3.6-35B-A3B`) | `cd /home/kupipi/Documents/git/strata && LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib ./build-hip/strata --families && LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib python3 strata.py launch --plan --model UD-Q4_K_XL --family qwen36 --output json` | `--families` prints `qwen4exp qwen35moe` (exit `0`). `--plan --model UD-Q4_K_XL --family qwen36 --output json` prints `"ok": true`, `"family": "qwen36"`, `"model": "UD-Q4_K_XL"`, `"title": "qwen36 UD-Q4_K_XL"`, `"engine_missing": true` (exit `0`). (Bare `python3 strata.py launch --plan --family qwen --no-tui` without `--model` exits `2` with the catalog's default-fit refusal.) In `setup.py:746-774`, `OWN_PATH_FAMILIES["qwen36"]` maps `"arch": "qwen35moe"`, `"name": "qwen3.6-35b-a3b"`, smallest quant `UD-Q4_K_XL`, file `Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf`, size `22,853,663,008` B (`21.28 GiB` / `22.85 GB`), HF source `unsloth/Qwen3.6-35B-A3B-MTP-GGUF`, license `Apache 2.0: https://huggingface.co/Qwen/Qwen3.6-35B-A3B`. | **PASS** |
| 2 | Pack hashes | `stat -c '%s %n' /tmp/opencode/qwen36/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf && sha256sum /tmp/opencode/qwen36/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf && grep -n "55983c5a" /home/kupipi/Documents/git/strata/setup.py` | Size `22853663008` bytes; SHA256 `55983c5a75a1ab969824077b3bb3de4146e82a9234072b48ad4e8f92ad3fe9f1` — exact match to `setup.py:747` (`"Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf": (22853663008, "55983c5a75a1ab969824077b3bb3de4146e82a9234072b48ad4e8f92ad3fe9f1")`) and `hashes.txt:3`. No conversion performed; engine reads the GGUF directly. | **PASS** |
| 3 | Model loads on signed binary | `cd /home/kupipi/Documents/git/strata && LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib ./build-hip/strata --native /tmp/opencode/qwen36/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf --tokens 760,6511,314,9338,369 --n 32 --max-context 1024` | `strata` reads the GGUF header (`qwen35moe`) at `src/program/generate.cpp:3647-3658` and switches to `strata-q36` (`src/qwen35/q36_engine.cu`). Loads `753 tensors (layout checked), 4.40 GiB on the GPU in 1.0 s`, places `every routed expert in VRAM (18.75 GiB) in 3.1 s` with `38.72 GiB of VRAM free`, warms up in `3.8 s`, exits `0`. No crash; no source change (`git -C /home/kupipi/Documents/git/strata status --porcelain` empty). Also verified `./build-hip/strata generate` exits `2` (`unknown argument: generate`), confirming why the `--native` flag path is required. | **PASS** |
| 4 | Generation (1 fixed prompt, `temperature=0`, 16–32 tokens, 512–2,048 context) | Same one-shot command above, plus `Tokenizer.from_gguf(...)` encode/decode verification via `/home/kupipi/Documents/git/strata/tools/strata_tokenizer.py` | Prompt `"The capital of France is"` encodes to `[760, 6511, 314, 9338, 369]`. `--tokens` in `strata-q36` is unconditionally greedy (`temperature=0`, `src/qwen35/q36_engine.cu:3897`). Context `1024` cells, `--n 32`. Generated 32 token IDs bit-identical to the coder's run: `11751 11 264 3177 34756 364 1141 25438 57902 1680 430 279 242476 300 21262 11 279 9440 46890 15849 11 321 279 42027 9141 368 54832 13 11751 369 1048 10919`. Decodes to `" Paris, a city renowned for its iconic landmarks such as the Eiffel Tower, the Louvre Museum, and the Notre-Dame Cathedral. Paris is also famous"`. | **PASS** |
| 5 | Resources / stability (`/proc/meminfo`, GTT, `dmesg`, `amd-smi`) | Pre/post `/proc/meminfo`, `amd-smi metric -g 0 -m`, `dmesg \| tail -n 10`, plus 0.5 s in-run sampling of `/proc/meminfo` and `amd-smi metric -g 0 -m` | Pre-run: `MemFree: 43118780 kB`, `GPUActive: 110428 kB`, `USED_GTT: 109 MB`. In-run peak: `GPUActive: 27457580 kB` (`26.19 GiB` / `27.46 GB`), `USED_GTT: 26814 MB` (`26.19 GiB`). Immediate post-run (before asynchronous KFD page reclaim): `MemFree: 15554856 kB`, `GPUActive: 27222244 kB` (corroborating the coder's immediate post-run `GPUActive: 27238816 kB` and `MemFree: 14446844 kB`). `dmesg` tail identical before and after the run: zero new kernel messages, no amdgpu/KFD faults or resets. | **PASS** |
| 6 | Environment & binary SHA256 | `sha256sum /home/kupipi/Documents/git/strata/build-hip/strata`, `rocminfo`, `hipcc --version`, `amd-smi static`, `git -C /home/kupipi/Documents/git/strata rev-parse HEAD` | Strata HEAD `baf16363b4403ef0ed4f538f5d5ed11c43fb9535` (porcelain empty); `build-hip/strata` `39,736,088` B, SHA256 `d58ee2398596d1a100c15d5b9459e24bd86854cb5e5fb7ce88dbc6c7ed9f5858` (matches signed `HO-STRATA-001` build); `rocminfo` Agent 2 `gfx1150` (`AMD Radeon 890M Graphics`, 16 CUs, wave32); HIP `7.16.26385-0000000` (`/opt/rocm/core-10.1`); hipBLASLt `1.4` (`100401`); kernel `7.0.0-42-generic`. | **PASS** |
| 7 | No claims / single profile / bundle integrity | Review of `manifest.md`, `HO-STRATA-007.md`, `HO-STRATA-007-QAQC.md`, `sha256sum -c` against `hashes.txt`, secret scan | Single profile only (`gfx1150` / `qwen35moe` / `UD-Q4_K_XL` / greedy / `1024` context). No performance, throughput, quality, or support claims made; the engine's self-printed timing line is preserved verbatim as raw output without interpretation. All 8 entries in `hashes.txt` verify (`OK`); see Minor finding M1 on the 6 additional `artifacts/` files. | **PASS** |

### 1.1 Exact re-run output (QAQC session)

```text
$ cd /home/kupipi/Documents/git/strata
$ LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib ./build-hip/strata \
    --native /tmp/opencode/qwen36/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf \
    --tokens 760,6511,314,9338,369 --n 32 --max-context 1024
strata-q36: /tmp/opencode/qwen36/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf: 753 tensors (layout checked), 4.40 GiB on the GPU in 1.0 s (the routed experts are placed after the engine's buffers)
strata-q36: prompt experts: 0 of 41 layers on the fused int8 kernels, 41 on our int8 kernels, 0 on MMQ (int8)
strata-q36: context 1024 cells, prompt chunk 4096, MTP block loaded, 38.72 GiB of VRAM free
strata-q36: every routed expert in VRAM (18.75 GiB) in 3.1 s
strata-q36: warmed up in 3.8 s (one prompt chunk, a decode step)
gen: 11751 11 264 3177 34756 364 1141 25438 57902 1680 430 279 242476 300 21262 11 279 9440 46890 15849 11 321 279 42027 9141 368 54832 13 11751 369 1048 10919
strata-q36: prompt 5 tokens in 90.7 ms (55.1 tok/s), 32 generated in 1630.7 ms (19.6 tok/s)
exit=0
```

### 1.2 Independent SHA256 verification of all bundle files and external inputs

All 8 entries in `workflow/evidence/HO-STRATA-007/hashes.txt` were verified with `sha256sum -c`:

| File | SHA256 | In `hashes.txt`? |
|---|---|---|
| `/tmp/opencode/qwen36/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf` | `55983c5a75a1ab969824077b3bb3de4146e82a9234072b48ad4e8f92ad3fe9f1` | Yes (`OK`) |
| `/home/kupipi/Documents/git/strata/build-hip/strata` | `d58ee2398596d1a100c15d5b9459e24bd86854cb5e5fb7ce88dbc6c7ed9f5858` | Yes (`OK`) |
| `workflow/evidence/HO-STRATA-007/manifest.md` | `e52e40eac3eb29d57197c2b2ed3d0b53764a3c612ad39aed34b2b4308df77a13` | No (M1) |
| `workflow/evidence/HO-STRATA-007/commands.log` | `893e7d24f3deee9e5ad34312345ed62f5c0e89ba8d2e2e23836aa6a7c533ca20` | Yes (`OK`) |
| `workflow/evidence/HO-STRATA-007/test-output.txt` | `7986a489b77ad26f7174b200b651964e43fd60c2fe2e1f836d0d0485540a8aa9` | Yes (`OK`) |
| `workflow/evidence/HO-STRATA-007/artifacts/prompt.txt` | `0b8b55f996e7040d630079da36b3f1e0f08dffa8d014c9e5dada28b80396cbc4` | Yes (`OK`) |
| `workflow/evidence/HO-STRATA-007/artifacts/prompt-token-ids.txt` | `e70bdc1bb2837068ae9ebde778d1c8a08f3bae2ee28f927df2bdcb24539037b7` | Yes (`OK`) |
| `workflow/evidence/HO-STRATA-007/artifacts/generated-token-ids.txt` | `d66cf4606974589d85738a7e9aa1b32741d7c5809e4eb1ba5d8a9e6f7b46d49e` | Yes (`OK`) |
| `workflow/evidence/HO-STRATA-007/artifacts/generated-text.txt` | `1d0bf1eaa15565e363b2a9a61936716b624647961c3688605d5866164902f1c5` | Yes (`OK`) |
| `workflow/evidence/HO-STRATA-007/artifacts/control-launch-help.txt` | `db628003fee734fc49e20c1358762ca39e71cf5b952969210b329df7bfb72791` | No (M1) |
| `workflow/evidence/HO-STRATA-007/artifacts/control-plan-qwen36.json` | `198f239ac3a5cdb27a4b4dc47b60d41b326474a9abf0ddac6549d7f7c3ce5cac` | No (M1) |
| `workflow/evidence/HO-STRATA-007/artifacts/decode-command.txt` | `a8fb22e399fb03989b6d95c7665592b43fb76408c957047bd81487a5d8fa4068` | No (M1) |
| `workflow/evidence/HO-STRATA-007/artifacts/engine-families.txt` | `1885051ba1bf85ff948a0ec880fa2c1b47b05bac8f30d7ba7a84c7beb6d02f0f` | No (M1) |
| `workflow/evidence/HO-STRATA-007/artifacts/engine-generate-help.txt` | `6e6a1e01cc27ac601ba9211b441d62db8d7262570f87fc50734e93b40a5308a1` | No (M1) |
| `workflow/evidence/HO-STRATA-007/artifacts/engine-geometry.txt` | `d3bf520127354479c1de74999156654279c5d077618074593877814cce145c39` | No (M1) |

---

## 2. Diff and guard-rail review

- [x] **Diff is within scope; no unrelated files.** `git diff afcc2096367cc8b17f72acd9708c886c9acc94bc..f6ee355 --name-status` touches exactly 17 files: 14 files in `workflow/evidence/HO-STRATA-007/`, `workflow/handoffs/HO-STRATA-007.md`, `workflow/handoffs/HO-STRATA-007-QAQC.md`, and 1 line in `workflow/STATUS.md`.
- [x] **No Strata source changes.** `/home/kupipi/Documents/git/strata` is at `baf16363b4403ef0ed4f538f5d5ed11c43fb9535` with `git status --porcelain` empty and `build-hip` git-ignored (`.gitignore:12:build*/`).
- [x] **No new dependencies without approval.** No `pip`, `apt`, or ROCm packages were added or modified.
- [x] **No secrets/tokens in the diff, logs, or evidence.** Pattern scan across `workflow/evidence/HO-STRATA-007/` and `workflow/handoffs/HO-STRATA-007*.md` returned 0 matches. No model weights committed to git (largest file in the evidence bundle is `commands.log` at 34,500 bytes; the 22.85 GB GGUF lives at `/tmp/opencode/qwen36/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf`).
- [x] **Tests are meaningful; no skips hidden as passes.** Both reasons why the two example shapes in the original `HO-STRATA-007.md` §10 were adapted are documented in `manifest.md` §4 (`:51-52`) and `HO-STRATA-007.md` §10 (`:112-126`) and backed by raw artifacts:
  1. `strata.py launch` could not execute the run because the signed update feed has no pre-built HIP engine package for `gfx1150` (`artifacts/control-plan-qwen36.json`: `"engine_missing": true, "engine_usable": false`).
  2. `./build-hip/strata generate ...` exits `2` with `unknown argument: generate` (`artifacts/engine-generate-help.txt:1`) because the `baf16363` binary takes flags directly and routes `--native <qwen35moe.gguf>` to `strata-q36` (`src/program/generate.cpp:3647-3658`).
- [x] **Evidence matches the commands that were run.** Re-running the exact command produced bit-identical generated token IDs and matching GPU memory footprint.
- [x] **One profile only; no performance/support/quality claims.** Only `qwen35moe` (`Qwen3.6-35B-A3B` / `UD-Q4_K_XL`) on `gfx1150` was tested; no Mixtral, Qwen3-30B-A3B, or DeepSeek work; engine timing lines are preserved as raw output and explicitly disclaimed (`manifest.md:54`).
- [x] **Role-model separation satisfied at runtime.** Coder ran on `opencode-go/kimi-k2.7-code` (`kimi`), QAQC ran on `opencode-go/gemini-4-argon` (`gemini`), and Auditor is configured on `opencode-go/deepseek-v4.1-flash` (`deepseek`).

---

## 3. Findings (severity order)

No Blocker or Major findings. Four Minor non-blocking documentation observations are recorded for the Auditor:

| # | Severity | Finding | File:line / evidence | Required action |
|---|---|---|---|---|
| M1 | Minor | `hashes.txt` and `manifest.md` §3 list 8 hashes (the GGUF, the signed binary, `test-output.txt`, `commands.log`, and the 4 prompt/generated token/text artifacts) and all 8 match (`OK`), but 6 auxiliary files in `artifacts/` (`control-launch-help.txt`, `control-plan-qwen36.json`, `decode-command.txt`, `engine-families.txt`, `engine-generate-help.txt`, `engine-geometry.txt`) and `manifest.md` are omitted from `hashes.txt`. | `workflow/evidence/HO-STRATA-007/hashes.txt:1-17`, `manifest.md:37-46` | Non-blocking; all 15 SHA256 digests are computed and recorded in §1.2 of this report. |
| M2 | Minor | Decimal `GB` (`10^9`) vs binary `GiB` (`2^30`) unit labels in `manifest.md` prose: `manifest.md:31` summarizes `/proc/meminfo` (`42,092,528 kB`, `14,446,844 kB`, `27,238,816 kB`) as `Pre MemFree 42.1 GiB, post MemFree 14.4 GiB, GPUActive ~27.2 GiB` (`40.14 GiB`, `13.78 GiB`, `25.98 GiB` in binary `2^30`), and `manifest.md:61` writes `22.8 GiB` for the `22,853,663,008` B GGUF (`22.85 GB` decimal / `21.28 GiB` binary). The raw kB and byte counts in `test-output.txt` and `setup.py:747` are exact. | `workflow/evidence/HO-STRATA-007/manifest.md:31,61` | Non-blocking; raw numbers in `test-output.txt` are exact. |
| M3 | Minor | `HO-STRATA-007.md` §5 requests `license/provenance`. `manifest.md:17,28` records the exact HuggingFace provenance URL (`unsloth/Qwen3.6-35B-A3B-MTP-GGUF`) and cites the `setup.py` pin (`setup.py:747-758`), where `OWN_PATH_FAMILIES["qwen36"]["license"]` is `"Apache 2.0: https://huggingface.co/Qwen/Qwen3.6-35B-A3B"`, but does not inline the string `"Apache 2.0"` in `manifest.md`. | `workflow/evidence/HO-STRATA-007/manifest.md:17,28`, `/home/kupipi/Documents/git/strata/setup.py:758` | Non-blocking; provenance URL and `setup.py` pin are recorded and verified. |
| M4 | Minor | `manifest.md:8` lists `Python 3.12` in the environment summary; while `/usr/bin/python3.12` is present on the Linux Mint 22.3 host, the default `python3` in `PATH` is `Python 3.14.10`. Both execute `strata.py` and `tools/strata_tokenizer.py` identically. | `workflow/evidence/HO-STRATA-007/manifest.md:8` | Non-blocking observation. |

---

## 4. Verdict and next state

- **PASS** → `AUDIT_REVIEW`; attach this report (`workflow/reports/qaqc/HO-STRATA-007-qaqc.md`) and the evidence path (`workflow/evidence/HO-STRATA-007/`).

### `QAQC_TO_AUDITOR` handoff record

Per the QAQC write boundary (`workflow/ENGINEERING_WORKFLOW.md` §4: *"Only the owning role writes its report directory; QAQC and Auditor are read-only everywhere else"*), the complete `QAQC_TO_AUDITOR` handoff is embedded below (and can be filed as `workflow/handoffs/HO-STRATA-007-AUDIT.md` by the Architect/orchestrator if a separate file is desired):

```markdown
# HO-STRATA-007-AUDIT — qwen35moe low-tier baseline: Audit review

| Field | Value |
|---|---|
| **ID** | HO-STRATA-007-AUDIT |
| **Type** | QAQC_TO_AUDITOR |
| **State** | AUDIT_REVIEW |
| **Created / updated (UTC)** | 2026-11-16 / 2026-11-16 |
| **From → To** | QAQC (`qaqc`, `opencode-go/gemini-4-argon`) → Auditor (`auditor`, `opencode-go/deepseek-v4.1-flash`) |
| **Work package** | `strata-007-qwen35moe-lowtier` |
| **Branch / base commit** | `wp/strata-007-qwen35moe-lowtier` / `f6ee3556d1e546607fe0fe5f5a72aa0e7c29b52a` on top of `afcc2096367cc8b17f72acd9708c886c9acc94bc` |
| **Priority / timebox** | P0 · 1 working day |
| **Original handoff** | `workflow/handoffs/HO-STRATA-007.md` |
| **QAQC report** | `workflow/reports/qaqc/HO-STRATA-007-qaqc.md` |
| **Evidence path** | `workflow/evidence/HO-STRATA-007/` |

## 1. Scope (in)

- Audit the coder's evidence bundle (`workflow/evidence/HO-STRATA-007/`) and the independent QAQC report (`workflow/reports/qaqc/HO-STRATA-007-qaqc.md`) against `workflow/handoffs/HO-STRATA-007.md` and `DEC-017`.
- Verify claims, guard rails, scope, role-model separation, and evidence integrity.
- Write `workflow/reports/audit/HO-STRATA-007-audit.md` and transition to `ARCHITECT_APPROVAL` (PASS) or `REWORK` (FAIL).

## 2. Out of scope

- No code, test, doc, or Strata checkout modifications.
- No other model families (Mixtral, Qwen3-30B-A3B, DeepSeek).
- No performance, throughput, quality, or support claims.

## 3. Inputs

| Input | Path / hash | Status |
|---|---|---|
| Architect handoff | `workflow/handoffs/HO-STRATA-007.md` | CODER_DONE |
| Coder→QAQC handoff | `workflow/handoffs/HO-STRATA-007-QAQC.md` | reviewed (PASS) |
| QAQC report | `workflow/reports/qaqc/HO-STRATA-007-qaqc.md` | PASS → `AUDIT_REVIEW` |
| Evidence bundle | `workflow/evidence/HO-STRATA-007/` | verified |
| Signed gfx1150 binary | `/home/kupipi/Documents/git/strata/build-hip/strata` (`d58ee2398596d1a100c15d5b9459e24bd86854cb5e5fb7ce88dbc6c7ed9f5858`) | verified |
| Model pack | `/tmp/opencode/qwen36/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf` (`55983c5a75a1ab969824077b3bb3de4146e82a9234072b48ad4e8f92ad3fe9f1`) | verified |

## 4. Acceptance criteria (for Audit)

| # | Criterion | Check | Expected |
|---|---|---|---|
| 1 | Evidence integrity | Verify `workflow/evidence/HO-STRATA-007/` and SHA256 hashes | All artifacts present; hashes match |
| 2 | Independent QAQC verification | Review `workflow/reports/qaqc/HO-STRATA-007-qaqc.md` | All AC-1..AC-7 re-run and passed; runtime model separation (`kimi` → `gemini` → `deepseek`) confirmed |
| 3 | Guard rails & scope | Check diff `afcc2096..f6ee355` and Strata checkout `baf16363` | Only `HO-STRATA-007` files touched; Strata clean; one profile only; no perf/support/quality claims |

## 5. Signatures

| Role | Name/agent | Date | Decision |
|---|---|---|---|
| Sender (QAQC) | `qaqc` (`opencode-go/gemini-4-argon`) | 2026-11-16 | PASS → `AUDIT_REVIEW` |
| Receiver (Auditor) | `auditor` | | |
```

---

## 5. Statement

I did not modify code, tests, docs, configuration, evidence, or handoffs. This report (`workflow/reports/qaqc/HO-STRATA-007-qaqc.md`) is the only artifact I wrote.
