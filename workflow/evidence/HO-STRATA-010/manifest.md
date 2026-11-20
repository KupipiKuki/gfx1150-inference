# Evidence manifest — HO-STRATA-010

| **Handoff** | HO-STRATA-010 |
| **Commit / branch** | bundle commit recorded in `HO-STRATA-010.md` log / `wp/strata-010-reference-oracle` (base `main` `8ce28c4`) |
| **Author / date (UTC)** | coder-primary / 2026-11-19 |
| **Environment** | Ubuntu 24.04, Linux 7.0.0-42-generic, GCC 13.3.0, Python 3.14.10, CPU-only, AMD Ryzen AI 9 HX 370 w/ Radeon 890M, 24 vCPUs |
| **Working directory** | `/home/kupipi/Documents/git/gfx1150-inference` |

## 1. Commands

| # | Command (copy-paste) | CWD | Exit | Output file |
|---|---|---|---|---|
| 0a | `git clone https://github.com/ggerganov/llama.cpp.git /tmp/opencode/llama.cpp` | anywhere | 0 | `commands.log` |
| 0b | `git -C /tmp/opencode/llama.cpp checkout 78e05298f0d68abff41d08d79fa7469264b2aff0` | anywhere | 0 | `commands.log` |
| 0c | `cmake -S /tmp/opencode/llama.cpp -B /tmp/opencode/llama.cpp/build -DLLAMA_CURL=OFF -DBUILD_SHARED_LIBS=ON -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF -DLLAMA_BUILD_SERVER=OFF -DCMAKE_BUILD_TYPE=Release && cmake --build /tmp/opencode/llama.cpp/build -j` | `/tmp/opencode/llama.cpp` | 0 | `commands.log` |
| 1 | `g++ -O2 -std=c++17 workflow/evidence/HO-STRATA-010/artifacts/oracle_harness.cpp -o /tmp/opencode/oracle_harness -I/tmp/opencode/llama.cpp/include -I/tmp/opencode/llama.cpp/ggml/include -L/tmp/opencode/llama.cpp/build/bin -lllama -lggml -lggml-base -lggml-cpu -lpthread` | repo root | 0 (warnings only) | `commands.log` |
| 2 | `python3 workflow/evidence/HO-STRATA-010/artifacts/tokenize_compare.py --gguf <deepseek> --harness /tmp/opencode/oracle_harness > workflow/evidence/HO-STRATA-010/artifacts/tokenizer_parity_table.md` | repo root | 0 | `artifacts/tokenizer_parity_table.md` |
| 3 | `LD_LIBRARY_PATH=/tmp/opencode/llama.cpp/build/bin /tmp/opencode/oracle_harness --model <deepseek> --tokens 549,6077,280,7239 --n 0 --dump-layers workflow/evidence/HO-STRATA-010/artifacts/runs/deepseek_p1_4_layers.bin` | repo root | 0 | `test-output.txt` |
| 4 | `LD_LIBRARY_PATH=/tmp/opencode/llama.cpp/build/bin /tmp/opencode/oracle_harness --model <deepseek> --tokens 549,6077,280,7239,317 --n 16 --dump-logits workflow/evidence/HO-STRATA-010/artifacts/runs/deepseek_p1_logits.bin > workflow/evidence/HO-STRATA-010/artifacts/runs/run1.txt` | repo root | 0 | `test-output.txt` |
| 5 | `LD_LIBRARY_PATH=/tmp/opencode/llama.cpp/build/bin /tmp/opencode/oracle_harness --model <deepseek> --tokens 549,6077,280,7239,317 --n 16 --dump-logits workflow/evidence/HO-STRATA-010/artifacts/runs/deepseek_p1_logits_run2.bin > workflow/evidence/HO-STRATA-010/artifacts/runs/run2.txt` | repo root | 0 | `test-output.txt` |
| 6a | `diff workflow/evidence/HO-STRATA-010/artifacts/runs/run1.txt workflow/evidence/HO-STRATA-010/artifacts/runs/run2.txt` | repo root | 1 (wall_s + filename differ) | `test-output.txt` |
| 6b | `diff workflow/evidence/HO-STRATA-010/artifacts/runs/deepseek_p1_logits.bin workflow/evidence/HO-STRATA-010/artifacts/runs/deepseek_p1_logits_run2.bin` | repo root | 0 (empty) | `test-output.txt` |
| 6c | `grep '^gen:' workflow/evidence/HO-STRATA-010/artifacts/runs/run1.txt > workflow/evidence/HO-STRATA-010/artifacts/runs/run1.norm.txt && grep '^gen:' workflow/evidence/HO-STRATA-010/artifacts/runs/run2.txt > workflow/evidence/HO-STRATA-010/artifacts/runs/run2.norm.txt && diff workflow/evidence/HO-STRATA-010/artifacts/runs/run1.norm.txt workflow/evidence/HO-STRATA-010/artifacts/runs/run2.norm.txt` | repo root | 0 (empty) | `test-output.txt` |
| 7 | `python3 workflow/evidence/HO-STRATA-010/artifacts/check_layers.py workflow/evidence/HO-STRATA-010/artifacts/runs/deepseek_p1_4_layers.bin` | repo root | 0 | `test-output.txt` |

`<deepseek>` expands to `/home/kupipi/.cache/huggingface/hub/models--Lucy-in-the-Sky--deepseek-moe-16b-base-Q4_K_M-GGUF/snapshots/1f2b397cdb560ffb519aa8371d2f9eebae50d34d/deepseek-moe-16b-base-q4_k_m.gguf`.

## 2. Acceptance criteria ↔ evidence

| # | Criterion | Command | Observed | Pass? |
|---|---|---|---|---|
| 1 | llama.cpp pinned and built; provenance recorded | `cmake -B build -DLLAMA_CURL=OFF -DBUILD_SHARED_LIBS=ON ...` | tag `b12527`, commit `78e05298...`, libs hashed, see §4 | PASS (DeepSeek) |
| 2 | Harness reproduces same IDs on two consecutive runs | commands 4 + 5 + 6b + 6c | `gen:` identical; logits binaries identical; normalized gen-line diff empty; only `wall_s` differs | PASS |
| 3 | Tokenizer parity: 3 prompts, zero ID differences | command 2 | All 3 prompts match exactly; P2 multi-line decode parsed in full; no mismatch line in table | PASS |
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
| Pin notes | `workflow/evidence/HO-STRATA-010/hashes-notes.txt` | `338d537c82b922926f18153a08e4c123d0e4b8e26593e6061e28a08b7edc5403` |
| Tokenizer parity table | `workflow/evidence/HO-STRATA-010/artifacts/tokenizer_parity_table.md` | `8512eb971c4b029f38e9c934ecfb5a9cf53fffd102c79f93b613681d0b9d7270` |
| Layer dump | `workflow/evidence/HO-STRATA-010/artifacts/runs/deepseek_p1_4_layers.bin` | `db6eccb3e8a949827c5c961fc732159daa1a0a9d52f7f88156d669845e0c7c73` |
| Logits top-2 dump | `workflow/evidence/HO-STRATA-010/artifacts/runs/deepseek_p1_logits.bin` | `5334baef84380f6060f8b1c4afda5fd45d367e9065ecdf2c6e4ea0642153fb2e` |
| Run 1 stdout | `workflow/evidence/HO-STRATA-010/artifacts/runs/run1.txt` | `b61da3fa0e50f8c0dac24dae61691877703265027509c26c526e04db08b8a9a4` |
| Run 2 stdout | `workflow/evidence/HO-STRATA-010/artifacts/runs/run2.txt` | `f1d6ade0cf5ffd4648d40126579a5202d4fa1b9b5dbf73c3813ad8bb0c6c2859` |
| Run 1 normalized | `workflow/evidence/HO-STRATA-010/artifacts/runs/run1.norm.txt` | `88de45824c276d1ac4ecb3572e3ba6dd42a4130bb137522c3e64dcff780ead2a` |
| Run 2 normalized | `workflow/evidence/HO-STRATA-010/artifacts/runs/run2.norm.txt` | `88de45824c276d1ac4ecb3572e3ba6dd42a4130bb137522c3e64dcff780ead2a` |
| Commands log | `workflow/evidence/HO-STRATA-010/commands.log` | `5027e17e629c0eb93bb1b120018e46020b09d5880d621e2db3fa013580e890cb` |
| Test output | `workflow/evidence/HO-STRATA-010/test-output.txt` | `b4517ef5ddf7a315b0b74c4ddc7ca396f3fd21dea7a7a75a9244be949810e583` |

## 4. llama.cpp provenance

| Field | Value |
|---|---|
| Tag | `b12527` |
| Commit | `78e05298f0d68abff41d08d79fa7469264b2aff0` |
| Clone path | `/tmp/opencode/llama.cpp` (temporary) |
| Build command | `cmake -B build -DLLAMA_CURL=OFF -DBUILD_SHARED_LIBS=ON -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF -DLLAMA_BUILD_SERVER=OFF -DCMAKE_BUILD_TYPE=Release && cmake --build build -j` |
| CMake version | `3.28.3` |
| `GGML_NATIVE` | `ON` (CMake default; `-march=native` used by `ggml-cpu`) |
| Compiler | GCC 13.3.0 |
| Build type | Release |
| `libllama.so.1` | `2397a75f56dfd74b7b66c68b507c46080ee3bbca0bd4aa2e1aa179f552d1b8b1` |
| `libggml.so.1` | `8f923882e63e28c33db684010ef44ed4867842c19c79701ac5ba8e62840fc34a` |
| `libggml-base.so.1` | `437dd6b7b20c6c4595ef5bbd6628250a819b884e34661f4ee3717194f704ddf5` (this-host only) |
| `libggml-cpu.so.1` | `fcc9fa13f1a3b3136c08e5ffc7ef7e9a120f5157496ab1cc19bc9b53da2bff14` |

**Host-scoped hashes:** because `GGML_NATIVE=ON` selects `-march=native`, the `ggml-cpu` (and indirectly `ggml-base`) shared-library digests depend on the host CPU features. The recipe in §1 (commands 0a–0c) is reproducible; the digests above are valid only on this AMD Ryzen AI 9 HX 370 host. The oracle dumps and generation results remain bit-identical across rebuilds on the same model and quant.

To rebuild from a clean checkout, run the clone/build commands in §1 (0a–0c), then the harness build command in §1 (1).

## 5. Failures, skips, limits

- **Mixtral 8x7B Q3_K_M is deferred** per DEC-029. The TheBloke pack uses the legacy per-expert tensor layout (`blk.0.ffn_down.0.weight` etc.), which llama.cpp `b12527` no longer loads (it expects stacked `ffn_down_exps.weight`). Mixtral is out of scope for S0; only DeepSeek-MoE-16B Q4_K_M reference outputs are produced.
- `/tmp/opencode/llama.cpp` is temporary; the exact rebuild recipe is recorded in §1 and §4.
- CPU wall time is reported as an observation only (no performance claim).
- `workflow/MODELS.md` and `planning/strata-engine/13-family-support-test-plan.md` are pinned by commit `8ce28c4` in `hashes-notes.txt` and are intentionally excluded from `hashes.txt` to avoid drift.
- The four helper stdout files (`run1.txt`, `run2.txt`, `run1.norm.txt`, `run2.norm.txt`) are hashed in `hashes.txt`; the git-ignored duplicate `deepseek_p1_logits_run2.bin` is excluded because it is a transient reproducibility check, not a committed reference artifact.
- **C1 last-block effect:** the C1 fix changes the prompt-batch logits flag from last-token-only to all-positions when dumping layers, which moves the final block's GEMM from `M=1` to `M=4`. Compared with the pre-fix dump, `l_out-27` at position 3 changed by ≤ `3.81e-6` absolute (relative L2 `8.07e-8`, 699/2048 values bit-equal); layers 0–26 and the generation logits are bit-identical. S4 must set layer tolerances against this post-fix baseline.

## 6. Tokenizer convention

Both sides use raw-text BPE without prepending BOS:

- **Harness:** `llama_tokenize(vocab, text, add_special=false, parse_special=true)` → no `100000` BOS emitted.
- **Engine:** `Tokenizer.encode(text)` returns BPE ids directly; the tokenizer metadata is read from the GGUF and never prepends BOS (`add_bos_token=False` in the engine's extracted config).
- **Empirical:** none of the six id lists (P1/P2/P3 × engine/harness) contain `100000`.

For S1+, align `parse_special` if special-token behavior becomes part of the parity gate.

## 7. Environment notes

- `LD_LIBRARY_PATH=/tmp/opencode/llama.cpp/build/bin` required at runtime because the harness binary is not committed.
- No GPU used; `n_gpu_layers=0`.
- No secrets, tokens, or model weights committed.

## 8. Statement

- [x] Commands are reproducible.
- [x] Outputs are raw; no paraphrasing.
- [x] No secrets.
- [x] Every claim cites an artifact.
- [x] One profile per claim (CPU, DeepSeek-MoE-16B Q4_K_M).
