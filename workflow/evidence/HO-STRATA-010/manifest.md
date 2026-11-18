# Evidence manifest — HO-STRATA-010

| Field | Value |
|---|---|
| **Handoff** | HO-STRATA-010 |
| **Commit / branch** | `068e8fe` / `wp/strata-010-reference-oracle` (to be updated after final commit) |
| **Author / date (UTC)** | coder-primary / 2026-11-18 |
| **Environment** | Ubuntu 24.04, Linux 7.0.0-42-generic, GCC 13.3.0, Python 3.14.10, CPU-only |
| **Working directory** | `/home/kupipi/Documents/git/gfx1150-inference` |

## 1. Commands

| # | Command (copy-paste) | CWD | Exit | Output file |
|---|---|---|---|---|
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
| 3 | Tokenizer parity: 3 prompts, zero ID differences | command 2 | All 3 prompts match exactly; no BOS added by either side | PASS |
| 4 | Reference token IDs for DeepSeek, P1, 16 tokens | command 4 | `gen: 8913 13 185 40619 317 254 6077 280 7239 13 185 40619 317 254 6077 280` | PASS |
| 5 | Per-layer dumps exist, documented shape, non-degenerate | command 3 + 7 | shape `[4][28][2048]`; L0 vs L1 L2 norm 3.57; no nan/inf | PASS |
| 6 | Logits/top-2 dumps exist for 16 steps | command 4 | shape `[16][2]`, 256 bytes | PASS |
| 7 | Harness script committed and runnable from clean checkout | source in `artifacts/oracle_harness.cpp`; build command in `commands.log` | builds and runs | PASS |
| 8 | No engine change | `git -C /home/kupipi/Documents/git/strata status --porcelain` | empty; HEAD `baf16363...` | PASS |
| 9 | No perf/support claim | review | only CPU wall time recorded as observation | PASS |

## 3. Artifacts and hashes

| Artifact | Path | SHA256 |
|---|---|---|
| Model pack | `/home/kupipi/.cache/huggingface/hub/models--Lucy-in-the-Sky--deepseek-moe-16b-base-Q4_K_M-GGUF/snapshots/.../deepseek-moe-16b-base-q4_k_m.gguf` | `f00ecd83d2fc4f28d1d5531c9583ed9c07452263c84590167bbe014f65c330f5` |
| Harness source | `workflow/evidence/HO-STRATA-010/artifacts/oracle_harness.cpp` | `fc0a01dad9808d0aa48833225e8432fa59ba2950f09703a0d713b31eb88cf3fb` |
| Tokenizer parity script | `workflow/evidence/HO-STRATA-010/artifacts/tokenize_compare.py` | `9ff5a3947920de6e8ce4af45f6c64461edc8fe0a422b73f4f5e8b3a81f24ef33` |
| Layer check script | `workflow/evidence/HO-STRATA-010/artifacts/check_layers.py` | `65eca3bd7917805432e90ca782ad1d92dcfad9e211b9f291505e41f9957c3cfa` |
| Pack hashes | `workflow/evidence/HO-STRATA-010/artifacts/pack_hashes.txt` | `eee7093bb547b860e88b63d9e0d20d8fcec37beadec01a71112d6825a7568378` |
| Tokenizer parity table | `workflow/evidence/HO-STRATA-010/artifacts/tokenizer_parity_table.md` | `06c62d18c39a016c086fb949404de76910035a20e334c39b790f947287a6c815` |
| Layer dump | `workflow/evidence/HO-STRATA-010/artifacts/runs/deepseek_p1_4_layers.bin` | `51c833657bffcdd87759d73e8372838af51d9bca0f2cdbb4ee69e748ac618459` |
| Logits top-2 dump | `workflow/evidence/HO-STRATA-010/artifacts/runs/deepseek_p1_logits.bin` | `5334baef84380f6060f8b1c4afda5fd45d367e9065ecdf2c6e4ea0642153fb2e` |
| Commands log | `workflow/evidence/HO-STRATA-010/commands.log` | `dd72817354607116044b057f02f495f78543a4e7fc26871f0f07bb9d2c52acf6` |
| Test output | `workflow/evidence/HO-STRATA-010/test-output.txt` | `2bfe2d0d0bad562d5154c816a830adf4c1b2b06a762df880789f52f2596083ea` |

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

To rebuild from a clean checkout, run the clone/build command above, then the harness build command in §1.

## 5. Failures, skips, limits

- **Mixtral 8x7B Q3_K_M is deferred** per DEC-029. The TheBloke pack uses the legacy per-expert tensor layout (`blk.0.ffn_down.0.weight` etc.), which llama.cpp `b12527` no longer loads (it expects stacked `ffn_down_exps.weight`). Mixtral is out of scope for S0; only DeepSeek-MoE-16B Q4_K_M reference outputs are produced.
- The planning file `planning/strata-engine/13-family-support-test-plan.md` was not present in the repository at the time of work; it is noted in `hashes-notes.txt`.
- `/tmp/opencode/llama.cpp` is temporary; the exact rebuild recipe is recorded in §4.
- CPU wall time is reported as an observation only (no performance claim).

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
