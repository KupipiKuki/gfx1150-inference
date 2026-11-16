# Evidence manifest — HO-STRATA-007

| Field | Value |
|---|---|
| **Handoff** | HO-STRATA-007 |
| **Commit / branch** | base `afcc2096367cc8b17f72acd9708c886c9acc94bc`, evidence `f03348dd51f6e74e73baad1f8d83d98fb350f06d`, review head `a3da3d64ef30c03763b0245320c7d7fe5cbd7a74` / `wp/strata-007-qwen35moe-lowtier` |
| **Author / date (UTC)** | Primary Coder (`coder-primary`) / 2026-11-16 |
| **Environment** | Linux Mint 22.3 (Zena) / kernel 7.0.0-42-generic; ROCm 10.1.0 (`/opt/rocm/core-10.1`); HIP 7.16.26385; hipBLASLt 1.4 (`libhipblaslt.so.1.4`); amd-smi 27.1.0+7da43026; default `python3` = 3.14.10 (`/usr/bin/python3.12` exists but was not used; tokenizer artifacts produced by `python3` 3.14.10) |
| **Working directory** | `/home/kupipi/Documents/git/strata` |

## 1. Commands

| # | Command (copy-paste) | CWD | Exit | Output file |
|---|---|---|---|---|
| 1 | `LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib ./build-hip/strata --families` | `/home/kupipi/Documents/git/strata` | 0 | `artifacts/engine-families.txt` |
| 2 | `LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib python3 strata.py launch --plan --model UD-Q4_K_XL --family qwen36 --output json` | `/home/kupipi/Documents/git/strata` | 0 | `artifacts/control-plan-qwen36.json` |
| 3 | `wget -c -O /tmp/opencode/qwen36/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf 'https://huggingface.co/unsloth/Qwen3.6-35B-A3B-MTP-GGUF/resolve/main/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf'` | `/tmp/opencode/qwen36` | 0 | wget output (not kept; file hash in `hashes.txt`) |
| 4 | `sha256sum /tmp/opencode/qwen36/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf` | — | 0 | `hashes.txt` |
| 5 | `python3 -c "import sys; sys.path.insert(0,'/home/kupipi/Documents/git/strata/tools'); from strata_tokenizer import Tokenizer; tok=Tokenizer.from_gguf('/tmp/opencode/qwen36/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf'); print(tok.encode('The capital of France is', parse_special=False))"` | `/home/kupipi/Documents/git/strata` | 0 | `artifacts/prompt-token-ids.txt` |
| 6 | `LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib ./build-hip/strata --native /tmp/opencode/qwen36/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf --tokens 760,6511,314,9338,369 --n 32 --max-context 1024` | `/home/kupipi/Documents/git/strata` | 0 | `test-output.txt` |
| 7 | post-run `cat /proc/meminfo`; `dmesg` tail | — | — | `test-output.txt` |
| 8 | `which rocm-smi` | `/home/kupipi/Documents/git/strata` | 1 | `commands.log` |
| 9 | `amd-smi metric -g 0 -m` sampled before, during and after the generation command | `/home/kupipi/Documents/git/strata` | 0 | `artifacts/amd-smi-gtt.txt` |
| 10 | Repeat of the accepted generation command | `/home/kupipi/Documents/git/strata` | 0 | `commands.log` / token IDs match `artifacts/generated-token-ids.txt` |
| 11 | `sha256sum -c hashes.txt` | `workflow/evidence/HO-STRATA-007` | 0 | `commands.log` |

## 2. Acceptance criteria ↔ evidence

| # | Criterion | Command | Observed | Pass? |
|---|---|---|---|---|
| 1 | Pack identified (`qwen35moe` / Qwen3.6-35B-A3B) | `strata.py launch --plan --model UD-Q4_K_XL --family qwen36 --output json` | Plan returns `"family": "qwen36"`, `"model": "UD-Q4_K_XL"`; engine `--families` lists `qwen35moe` | PASS |
| 2 | Pack hashes | `sha256sum` of the GGUF | `55983c5a75a1ab969824077b3bb3de4146e82a9234072b48ad4e8f92ad3fe9f1` matches the pin in `setup.py` | PASS |
| 3 | Model loads on signed binary | engine command with `--native GGUF` | Loads 753 tensors, places routed experts, reports `every routed expert in VRAM (18.75 GiB)`, warms up | PASS |
| 4 | Generation ≥16 tokens | engine command `--n 32` | 32 tokens generated; raw token IDs saved; decoded text saved | PASS |
| 5 | Resources / stability | `/proc/meminfo` pre/post, `dmesg`; `amd-smi metric -g 0 -m` | Pre MemFree 42,092,528 kB (40.14 GiB / 42.09 GB), post MemFree 14,446,844 kB (13.78 GiB / 14.45 GB), GPUActive 27,238,816 kB (25.98 GiB / 27.24 GB); GTT peak 26,798 MB (26.16 GiB / 26.80 GB); no GPU reset/new error in `dmesg` | PASS |
| 6 | Environment | `rocminfo`, `hipcc --version`, binary SHA256 | gfx1150, HIP 7.16.26385, binary `d58ee23…` (signed build `baf16363`) | PASS |
| 7 | No claims | report | One profile only (`gfx1150` / `qwen35moe` / `UD-Q4_K_XL`); no performance/support/quality claim made | PASS |

## 3. Artifacts and hashes

| Artifact | Path | SHA256 |
|---|---|---|
| model pack (not in git) | `/tmp/opencode/qwen36/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf` | `55983c5a75a1ab969824077b3bb3de4146e82a9234072b48ad4e8f92ad3fe9f1` (license: `Apache 2.0: https://huggingface.co/Qwen/Qwen3.6-35B-A3B`, `setup.py:758`) |
| signed engine binary | `/home/kupipi/Documents/git/strata/build-hip/strata` | `d58ee2398596d1a100c15d5b9459e24bd86854cb5e5fb7ce88dbc6c7ed9f5858` |
| prompt text | `artifacts/prompt.txt` | `0b8b55f996e7040d630079da36b3f1e0f08dffa8d014c9e5dada28b80396cbc4` |
| prompt token IDs | `artifacts/prompt-token-ids.txt` | `e70bdc1bb2837068ae9ebde778d1c8a08f3bae2ee28f927df2bdcb24539037b7` |
| generated token IDs | `artifacts/generated-token-ids.txt` | `d66cf4606974589d85738a7e9aa1b32741d7c5809e4eb1ba5d8a9e6f7b46d49e` |
| generated text | `artifacts/generated-text.txt` | `1d0bf1eaa15565e363b2a9a61936716b624647961c3688605d5866164902f1c5` |
| full run log | `test-output.txt` | `7986a489b77ad26f7174b200b651964e43fd60c2fe2e1f836d0d0485540a8aa9` |
| commands log | `commands.log` | `5c1e521c4b507d8143898ef58953aee9d69d9ba8575e1d7834bb465d6c491e68` |
| GTT sampling log | `artifacts/amd-smi-gtt.txt` | `a6b775b747251770f93a849c88671baa37ca177fd75c1532aecf7cee3e0051e6` |

## 4. Failures, skips, limits

- No failures or skips.
- The Control's local server path (`strata.py launch …`) could not be used because the signed update feed has no pre-built HIP engine package for `gfx1150`; the locally-built signed binary (`baf16363`) was used directly via the engine's one-shot path.
- The first attempt used `./build-hip/strata generate …`; the `baf16363` binary rejects the `generate` subcommand and uses flags directly, routing a `qwen35moe` file to `strata-q36` when `--native <GGUF>` is passed. The corrected command is the one recorded in §1 and `test-output.txt`.
- One profile only: AMD gfx1150 / Qwen3.6-35B-A3B / `UD-Q4_K_XL` / greedy / 1024 context cells.
- No performance, support or quality claim is made; the engine printed its own timing line and it is preserved verbatim, not interpreted.

## 5. Environment notes

- `LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib` is required; without it the binary exits 127 with missing shared libraries.
- `HSA_OVERRIDE_GFX_VERSION` was not set.
- Model weights are not committed; only hashes are in git.
- The model file is at `/tmp/opencode/qwen36/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf` (22.8 GiB) and will persist only on this host.

## 6. Statement

- [x] Commands are reproducible.
- [x] Outputs are raw; no paraphrasing.
- [x] No secrets.
- [x] Every claim cites an artifact.
- [x] One profile per claim.
