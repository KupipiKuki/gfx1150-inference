# Evidence manifest — HO-STRATA-010

| Field | Value |
|---|---|
| **Handoff** | HO-STRATA-010 |
| **Commit / branch** | `836b475100bf9e188bf03bc7621ba4f8dd198855` / `wp/strata-010-reference-oracle` |
| **Author / date (UTC)** | coder-primary / 2026-11-18 |
| **Environment** | Ubuntu 24.04, Linux 7.0.0-42-generic, GCC 13.3.0, Python 3.14.10, CPU-only |
| **Working directory** | `/home/kupipi/Documents/git/gfx1150-inference` |

## 1. Commands

| # | Command (copy-paste) | CWD | Exit | Output file |
|---|---|---|---|---|
| 0a | `git clone https://github.com/ggerganov/llama.cpp.git /tmp/opencode/llama.cpp` | anywhere | 0 | `commands.log` |
| 0b | `git -C /tmp/opencode/llama.cpp checkout 78e05298f0d68abff41d08d79fa7469264b2aff0` | anywhere | 0 | `commands.log` |
| 0c | `cmake -S /tmp/opencode/llama.cpp -B /tmp/opencode/llama.cpp/build -DLLAMA_CURL=OFF -DBUILD_SHARED_LIBS=ON -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF -DLLAMA_BUILD_SERVER=OFF -DCMAKE_BUILD_TYPE=Release && cmake --build /tmp/opencode/llama.cpp/build -j` | `/tmp/opencode/llama.cpp` | 0 | `commands.log` |
| 1 | `g++ -O2 -std=c++17 workflow/evidence/HO-STRATA-010/artifacts/oracle_harness.cpp -o /tmp/opencode/oracle_harness -I/tmp/opencode/llama.cpp/include -I/tmp/opencode/llama.cpp/ggml/include -L/tmp/opencode/llama.cpp/build/bin -lllama -lggml -lggml-base -lggml-cpu -lpthread` | repo root | 0 (warnings only) | `commands.log` |
| 2 | `python3 workflow/evidence/HO-STRATA-010/artifacts/tokenize_compare.py --gguf <deepseek> --harness /tmp/opencode/oracle_harness` | repo root | 0 | `artifacts/tokenizer_parity_table.md` |
| 3 | `LD_LIBRARY_PATH=/tmp/opencode/llama.cpp/build/bin /tmp/opencode/oracle_harness --model <deepseek> --tokens 549,6077,280,7239 --n 0 --dump-layers artifacts/runs/deepseek_p1_4_layers.bin` | repo root | 0 | `test-output.txt` |
| 4 | `LD_LIBRARY_PATH=/tmp/opencode/llama.cpp/build/bin /tmp/opencode/oracle_harness --model <deepseek> --tokens 549,6077,280,7239,317 --n 16 --dump-logits artifacts/runs/deepseek_p1_logits.bin` | repo root | 0 | `test-output.txt` |
| 5 | repeat command 4 with `deepseek_p1_logits_run2.bin` | repo root | 0 | `test-output.txt` |
| 6 | `diff deepseek_p1_logits.bin deepseek_p1_logits_run2.bin` | `artifacts/runs` | 0 (empty) | `test-output.txt` |
| 7 | `python3 artifacts/check_layers.py artifacts/runs/deepseek_p1_4_layers.bin` | repo root | 0 | `test-output.txt` |

DeepSeek pack path: `/home/kupipi/.cache/huggingface/hub/models--Lucy-in-the-Sky--deepseek-moe-16b-base-Q4_K_M-GGUF/snapshots/1f2b397cdb560ffb519aa8371d2f9eebae50d34d/deepseek-moe-16b-base-q4_k_m.gguf`

## 2. Acceptance criteria ↔ evidence

| # | Criterion | Command | Observed | Pass? |
|---|---|---|---|---|
| 1 | llama.cpp pinned and built; provenance recorded | `cmake -B build -DLLAMA_CURL=OFF -DBUILD_SHARED_LIBS=ON ...` | tag `b12527`, commit `78e05298...`, libs hashed, see §4 | PASS (DeepSeek) |
| 2 | Harness reproduces same IDs on two consecutive runs | commands 4 + 5 + `diff` | `gen:` identical; logits binaries identical; only `wall_s` differs | PASS |
| 3 | Tokenizer parity: 3 prompts, zero ID differences | command 2 | All 3 prompts match exactly; P2 multi-line decode now parsed in full; no BOS added by either side | PASS |
| 4 | Reference token IDs for DeepSeek, P1, 16 tokens | command 4 | `gen: 8913 13 185 40619 317 254 6077 280 7239 13 185 40619 317 254 6077 280` | PASS |
| 5 | Per-layer dumps exist, documented shape, non-degenerate | command 3 + 7 | shape `[4][28][2048]`; all 28 layers non-zero at all 4 positions; L0 vs L1 L2 norm 3.57; no nan/inf | PASS |
| 6 | Logits/top-2 dumps exist for 16 steps | command 4 | shape `[16][2][2]` (`[step][rank][(id_f32, logit_f32)]`), 256 bytes | PASS |
| 7 | Harness script committed and runnable from clean checkout | source in `artifacts/oracle_harness.cpp`; build command in `commands.log` | builds and runs | PASS |
| 8 | No engine change | `git -C /home/kupipi/Documents/git/strata status --porcelain` | empty; HEAD `baf16363...` | PASS |
| 9 | No perf/support claim | review | only CPU wall time recorded as observation | PASS |

## 3. Artifacts and hashes

| Artifact | Path | SHA256 |
|---|---|---|
| Model pack | `/home/kupipi/.cache/huggingface/hub/models--Lucy-in-the-Sky--deepseek-moe-16b-base-Q4_K_M-GGUF/snapshots/.../deepseek-moe-16b-base-q4_k_m.gguf` | `f00ecd83d2fc4f28d1d5531c9583ed9c07452263c84590167bbe014f65c330f5` |
| Harness source | `workflow/evidence/HO-STRATA-010/artifacts/oracle_harness.cpp` | `bdc9303d6d884452175e199fff3a894836409543ef6f5f390a4e7eb9ab9b8f33` |
| Tokenizer parity script | `workflow/evidence/HO-STRATA-010/artifacts/tokenize_compare.py` | `9903bc16ad8f7277631f6a209654c8903fa2d5295fc5aafd5e551c536c03e43c` |
| Layer check script | `workflow/evidence/HO-STRATA-010/artifacts/check_layers.py` | `65eca3bd7917805432e90ca782ad1d92dcfad9e211b9f291505e41f9957c3cfa` |
| Pack hashes | `workflow/evidence/HO-STRATA-010/artifacts/pack_hashes.txt` | `eee7093bb547b860e88b63d9e0d20d8fcec37beadec01a71112d6825a7568378` |
| Tokenizer parity table | `workflow/evidence/HO-STRATA-010/artifacts/tokenizer_parity_table.md` | `06c62d18c39a016c086fb949404de76910035a20e334c39b790f947287a6c815` |
| Layer dump | `workflow/evidence/HO-STRATA-010/artifacts/runs/deepseek_p1_4_layers.bin` | `db6eccb3e8a949827c5c961fc732159daa1a0a9d52f7f88156d669845e0c7c73` |
| Logits top-2 dump | `workflow/evidence/HO-STRATA-010/artifacts/runs/deepseek_p1_logits.bin` | `5334baef84380f6060f8b1c4afda5fd45d367e9065ecdf2c6e4ea0642153fb2e` |
| Run 1 stdout | `workflow/evidence/HO-STRATA-010/artifacts/runs/run1.txt` | `222623bc9db87e1bfebf77e7eba9487603b15ea73c1a02fe081a4374fe5bdaa5` |
| Run 2 stdout | `workflow/evidence/HO-STRATA-010/artifacts/runs/run2.txt` | `abf25cc48b42730a96309930e2d1a7ac96de9df124560cd2c4096c370a63ca6a` |
| Run 1 normalized | `workflow/evidence/HO-STRATA-010/artifacts/runs/run1.norm.txt` | `88de45824c276d1ac4ecb3572e3ba6dd42a4130bb137522c3e64dcff780ead2a` |
| Run 2 normalized | `workflow/evidence/HO-STRATA-010/artifacts/runs/run2.norm.txt` | `88de45824c276d1ac4ecb3572e3ba6dd42a4130bb137522c3e64dcff780ead2a` |
| Commands log | `workflow/evidence/HO-STRATA-010/commands.log` | `f12b6c227aa82a0719098f84062447c098d10b75fff8438635362ae10cf53928` |
| Test output | `workflow/evidence/HO-STRATA-010/test-output.txt` | `8ddadcb920b4c346d14bd0f04a5ae6f057596e3f5eeace85e752a0b468383650` |

## 4. llama.cpp provenance

| Field | Value |
|---|---|
| Tag | `b12527` |
| Commit | `78e05298f0d68abff41d08d79fa7469264b2aff0` |
| Clone path | `/tmp/opencode/llama.cpp` (temporary) |
| Build command | `cmake -B build -DLLAMA_CURL=OFF -DBUILD_SHARED_LIBS=ON -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF -DLLAMA_BUILD_SERVER=OFF -DCMAKE_BUILD_TYPE=Release && cmake --build build -j` |
| Compiler | GCC 13.3.0 |
| Build type | Release |
| `libllama.so.1` | `2397a75f56dfd74b7b66c68b507c46080ee3bbca0bd4aa2e1aa179f552d1b8b1` |
| `libggml.so.1` | `8f923882e63e28c33db684010ef44ed4867842c19c79701ac5ba8e62840fc34a` |
| `libggml-base.so.1` | `2cc34f6f2e91adafddfab9640596a3d8a882517685c029fcc5acaff9ce0327b2` |
| `libggml-cpu.so.1` | `fcc9fa13f1a3b3136c08e5ffc7ef7e9a120f5157496ab1cc19bc9b53da2bff14` |

To rebuild from a clean checkout, run the clone/build commands in §1 (0a–0c), then the harness build command in §1 (1).

## 5. Failures, skips, limits

- **Mixtral 8x7B Q3_K_M is deferred** per DEC-029. The TheBloke pack uses the legacy per-expert tensor layout (`blk.0.ffn_down.0.weight` etc.), which llama.cpp `b12527` no longer loads (it expects stacked `ffn_down_exps.weight`). Mixtral is out of scope for S0; only DeepSeek-MoE-16B Q4_K_M reference outputs are produced.
- The planning file `planning/strata-engine/13-family-support-test-plan.md` was not present in the repository at the time of work; it is noted in `hashes-notes.txt`.
- `/tmp/opencode/llama.cpp` is temporary; the exact rebuild recipe is recorded in §1 and §4.
- CPU wall time is reported as an observation only (no performance claim).
- `workflow/MODELS.md` is pinned by commit (`068e8fef...`) in `hashes-notes.txt` per DEC-024 and is intentionally excluded from `hashes.txt` to avoid drift.
- The four helper stdout files (`run1.txt`, `run2.txt`, `run1.norm.txt`, `run2.norm.txt`) are now hashed in `hashes.txt`; the git-ignored duplicate `deepseek_p1_logits_run2.bin` is excluded because it is a transient reproducibility check, not a committed reference artifact.

## 6. Environment notes

- `LD_LIBRARY_PATH=/tmp/opencode/llama.cpp/build/bin` required at runtime because the harness binary is not committed.
- No GPU used; `n_gpu_layers=0`.
- No secrets, tokens, or model weights committed.

## 7. Statement

- [x] Commands are reproducible.
- [x] Outputs are raw; no paraphrasing.
- [x] No secrets.
- [x] Every claim cites an artifact.
- [x] One profile per claim (CPU, DeepSeek-MoE-16B Q4_K_M).
