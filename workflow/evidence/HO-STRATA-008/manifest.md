# Evidence manifest — HO-STRATA-008 (refreshed after RW-HO-STRATA-008-1)

| Field | Value |
|---|---|
| **Handoff** | HO-STRATA-008 |
| **Rework referenced** | RW-HO-STRATA-008-1 |
| **Commit / branch** | `3b8d1ec59cad9cdc9a7dbb46f70a3270c2676570` / `wp/strata-008-family-probe` |
| **Strata base commit** | `baf16363b4403ef0ed4f538f5d5ed11c43fb9535` |
| **Author / date (UTC)** | Primary Coder (`coder-primary`) / 2026-11-18T04:24Z |
| **Environment** | Linux Mint 22.3 / kernel 7.0.0-42-generic; ROCm 10.1.0; HIP 7.16.26385; hipBLASLt 1.4; amd-smi 27.1.0+7da43026 |
| **Working directory** | `/home/kupipi/Documents/git/strata` |

## Parser split note

The Strata CLI has two argument parsers:

- The `qwen35` path (`src/qwen35/q36_engine.cu`) accepts `--n N` for generation count.
- The generic parser (`src/program/generate.cpp`) accepts only `--max-new N`; it has no `--n`.

The family switch in `src/program/generate.cpp:3644-3656` dispatches to `qwen35` only when the GGUF architecture is `qwen35moe`; every other architecture falls through to the generic parser. The first attempt therefore died with `unknown argument: --n` before either model was inspected. It is kept below as **"CLI parse — family path not reached"**, not erased.

## 1. Commands

| # | Command (copy-paste) | CWD | Exit | Output file |
|---|---|---|---|---|
| 1 | `LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib ./build-hip/strata --families` | `/home/kupipi/Documents/git/strata` | 0 | `artifacts/engine-families.txt` |
| 2 | `sha256sum <GGUF>` | — | 0 | `commands.log` |
| 3 (first attempt, CLI parse) | `LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib timeout 600 ./build-hip/strata --native <Mixtral-Q3_K_M> --tokens 760,6511,314,9338,369 --n 8 --max-context 512` | `/home/kupipi/Documents/git/strata` | 2 | `artifacts/mixtral-q3_k_m.{stdout,stderr}.txt` |
| 4 (first attempt, CLI parse) | `LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib timeout 600 ./build-hip/strata --native <DeepSeek-Q4_K_M> --tokens 760,6511,314,9338,369 --n 8 --max-context 512` | `/home/kupipi/Documents/git/strata` | 2 | `artifacts/deepseek-q4_k_m.{stdout,stderr}.txt` |
| 5 (generic parser attempt) | `LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib timeout 600 ./build-hip/strata --native <Mixtral-Q3_K_M> --tokens 760,6511,314,9338,369 --max-new 8 --max-context 512` | `/home/kupipi/Documents/git/strata` | 2 | `artifacts/mixtral-q3_k_m-generic.{stdout,stderr}.txt` |
| 6 (generic parser attempt) | `LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib timeout 600 ./build-hip/strata --native <DeepSeek-Q4_K_M> --tokens 760,6511,314,9338,369 --max-new 8 --max-context 512` | `/home/kupipi/Documents/git/strata` | 2 | `artifacts/deepseek-q4_k_m-generic.{stdout,stderr}.txt` |
| 7 | `amd-smi metric -g 0 -m` sampled before/after each attempt | `/home/kupipi/Documents/git/strata` | 0 | `commands.log`, `artifacts/amd-smi-envelope.txt` |
| 8 | `dmesg | tail` before/after each attempt | — | — | `commands.log` |
| 9 | `git -C /home/kupipi/Documents/git/strata status --porcelain` | — | 0 | `commands.log` |

Exact GGUF paths:
- Mixtral Q3_K_M: `~/.cache/huggingface/hub/models--TheBloke--Mixtral-8x7B-v0.1-GGUF/snapshots/38762deaceb8f976428ab44e4c3ccf927a91132a/mixtral-8x7b-v0.1.Q3_K_M.gguf`
- DeepSeek Q4_K_M: `~/.cache/huggingface/hub/models--Lucy-in-the-Sky--deepseek-moe-16b-base-Q4_K_M-GGUF/snapshots/1f2b397cdb560ffb519aa8371d2f9eebae50d34d/deepseek-moe-16b-base-q4_k_m.gguf`

## 2. Acceptance criteria ↔ evidence

| # | Criterion | Command | Observed | Pass? |
|---|---|---|---|---|
| 1 | Both new attempts executed on the signed binary from a clean checkout | `git status --porcelain` empty; HEAD `baf16363…`; binary SHA256 `d58ee239…` | Clean; HEAD `baf16363b4403ef0ed4f538f5d5ed11c43fb9535`; binary `d58ee2398596d1a100c15d5b9459e24bd86854cb5e5fb7ce88dbc6c7ed9f5858` | PASS |
| 2 | Raw stdout/stderr and exit code saved per attempt | files present | Original CLI-parse artifacts retained; new `artifacts/mixtral-q3_k_m-generic.{stdout,stderr}.txt`, `artifacts/deepseek-q4_k_m-generic.{stdout,stderr}.txt`; all exits recorded | PASS |
| 3 | Each new attempt classified with justifying line | manifest + test-output | Both generic attempts **REFUSED**; line `strata generate: --native requires --ple-gguf (the PLE key is native too), and no shard of the model holds per_layer_token_embd.weight` | PASS |
| 4 | Generated token IDs recorded if any | check stdout/stderr | No tokens generated on either generic attempt | PASS (N/A) |
| 5 | Resource envelope + `dmesg` recorded | `amd-smi metric -g 0 -m`, `dmesg | tail` | In `commands.log` and `artifacts/amd-smi-envelope.txt`; no GPU fault/reset | PASS |
| 6 | Model paths, sizes and SHA256 match `workflow/MODELS.md` | `sha256sum` | Mixtral `542d2453…` 20,363,355,584 B; DeepSeek `f00ecd83…` 10,850,181,856 B | PASS |
| 7 | No source change, no flag tuning, no support work | diff + command log | No Strata edits; generic commands run exactly as RW-008-1 §3 | PASS |
| 8 | No performance/support/quality claim | report review | No such claim made | PASS |

## 3. Classification

| Family | GGUF arch | Quant | Attempt | Exit | Classification | Justifying line | Tokens |
|---|---|---|---|---|---|---|---|
| Mixtral 8x7B v0.1 | `llama` | Q3_K_M | first (`--n`) | 2 | **CLI parse — family path not reached** | `unknown argument: --n` | none |
| DeepSeek-MoE-16B base | `deepseek` | Q4_K_M | first (`--n`) | 2 | **CLI parse — family path not reached** | `unknown argument: --n` | none |
| Mixtral 8x7B v0.1 | `llama` | Q3_K_M | generic (`--max-new`) | 2 | **REFUSED** | `strata generate: --native requires --ple-gguf (the PLE key is native too), and no shard of the model holds per_layer_token_embd.weight` | none |
| DeepSeek-MoE-16B base | `deepseek` | Q4_K_M | generic (`--max-new`) | 2 | **REFUSED** | `strata generate: --native requires --ple-gguf (the PLE key is native too), and no shard of the model holds per_layer_token_embd.weight` | none |

**Interpretation:** on the generic parser path, neither non-`qwen35moe` GGUF is loaded. The engine inspects the model, determines that `--native` requires a PLE key which these GGUFs do not provide, and exits non-zero with an explanatory message. This is a **REFUSED** outcome, not `LOADED-UNSUPPORTED` (no tokens emitted) and not `FAILED-OTHER` (no crash, no timeout, no OOM). No fallback was performed because the failure is not allocation/OOM.

## 4. Artifacts and hashes

| Artifact | Path | SHA256 |
|---|---|---|
| signed engine binary | `/home/kupipi/Documents/git/strata/build-hip/strata` | `d58ee2398596d1a100c15d5b9459e24bd86854cb5e5fb7ce88dbc6c7ed9f5858` |
| engine families | `artifacts/engine-families.txt` | (see `hashes.txt`) |
| Mixtral stdout (CLI parse) | `artifacts/mixtral-q3_k_m.stdout.txt` | (see `hashes.txt`) |
| Mixtral stderr (CLI parse) | `artifacts/mixtral-q3_k_m.stderr.txt` | (see `hashes.txt`) |
| DeepSeek stdout (CLI parse) | `artifacts/deepseek-q4_k_m.stdout.txt` | (see `hashes.txt`) |
| DeepSeek stderr (CLI parse) | `artifacts/deepseek-q4_k_m.stderr.txt` | (see `hashes.txt`) |
| Mixtral stdout (generic) | `artifacts/mixtral-q3_k_m-generic.stdout.txt` | (see `hashes.txt`) |
| Mixtral stderr (generic) | `artifacts/mixtral-q3_k_m-generic.stderr.txt` | (see `hashes.txt`) |
| DeepSeek stdout (generic) | `artifacts/deepseek-q4_k_m-generic.stdout.txt` | (see `hashes.txt`) |
| DeepSeek stderr (generic) | `artifacts/deepseek-q4_k_m-generic.stderr.txt` | (see `hashes.txt`) |
| amd-smi envelope | `artifacts/amd-smi-envelope.txt` | (see `hashes.txt`) |
| commands log | `commands.log` | (see `hashes.txt`) |
| test output | `test-output.txt` | (see `hashes.txt`) |
| manifest | `manifest.md` | (see `hashes.txt`) |
| model (not in git) | Mixtral Q3_K_M | `542d24532f63219db9f530bd2819be9c74f514919ab661dc5162cef844bac38b` |
| model (not in git) | DeepSeek Q4_K_M | `f00ecd83d2fc4f28d1d5531c9583ed9c07452263c84590167bbe014f65c330f5` |

## 5. Environment notes

- `LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib` is required.
- `HSA_OVERRIDE_GFX_VERSION` was not set.
- No model weights are committed; only hashes.
- Both GGUFs are symlinks in the Hugging Face cache; SHA256 and `stat -L` size are reported.

## 6. Statement

- [x] Commands are reproducible.
- [x] Outputs are raw; no paraphrasing.
- [x] No secrets.
- [x] Every claim cites an artifact.
- [x] One profile per claim: AMD gfx1150 / Strata `baf16363`.
