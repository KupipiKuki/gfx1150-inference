# Evidence manifest — HO-STRATA-011

| **Handoff** | HO-STRATA-011 |
| **Commit / branch** | `wp/strata-011-olmoe-oracle` / base `8ce28c4e2e33904b824d8541d69f1ea770548424` |
| **Author / date (UTC)** | coder-primary / 2026-11-20 |
| **Environment** | Ubuntu 24.04, Linux 7.0.0-42-generic, GCC 13.3.0, Python 3.14.10, CPU-only, AMD Ryzen AI 9 HX 370 w/ Radeon 890M, 24 vCPUs |
| **Working directory** | `/home/kupipi/Documents/git/gfx1150-inference` |

## 1. Commands

| # | Command (copy-paste) | CWD | Exit | Output file |
|---|---|---|---|---|
| 0 | `python3 - <model>` (size, sha256, architecture read) | repo root | 0 | `artifacts/cmd-0.out.txt` |
| 1 | `g++ -O2 -std=c++17 workflow/evidence/HO-STRATA-011/artifacts/oracle_harness.cpp -o /tmp/opencode/oracle_harness -I/tmp/opencode/llama.cpp/include -I/tmp/opencode/llama.cpp/ggml/include -L/tmp/opencode/llama.cpp/build/bin -lllama -lggml -lggml-base -lggml-cpu -lpthread` | repo root | 0 (warnings only) | `artifacts/cmd-1.{out,err}.txt` |
| 2 | `python3 workflow/evidence/HO-STRATA-011/artifacts/generate_parity_table.py --gguf <olmoe> --harness /tmp/opencode/oracle_harness` | repo root | 0 | `artifacts/cmd-2.out.txt` (also `artifacts/tokenizer_parity_table.md`) |
| 3 | `LD_LIBRARY_PATH=/tmp/opencode/llama.cpp/build/bin /tmp/opencode/oracle_harness --model <olmoe> --tokens 510,5347,273,6181 --n 0 --dump-layers workflow/evidence/HO-STRATA-011/artifacts/runs/olmoe_p1_4_layers.bin` | repo root | 0 | `artifacts/cmd-3.out.txt` |
| 4 | `LD_LIBRARY_PATH=/tmp/opencode/llama.cpp/build/bin /tmp/opencode/oracle_harness --model <olmoe> --tokens 510,5347,273,6181,310 --n 16 --dump-logits workflow/evidence/HO-STRATA-011/artifacts/runs/olmoe_p1_logits.bin > workflow/evidence/HO-STRATA-011/artifacts/runs/run1.txt` | repo root | 0 | `artifacts/cmd-4.out.txt` / `artifacts/runs/run1.txt` |
| 5 | `LD_LIBRARY_PATH=/tmp/opencode/llama.cpp/build/bin /tmp/opencode/oracle_harness --model <olmoe> --tokens 510,5347,273,6181,310 --n 16 --dump-logits workflow/evidence/HO-STRATA-011/artifacts/runs/olmoe_p1_logits_run2.bin > workflow/evidence/HO-STRATA-011/artifacts/runs/run2.txt` | repo root | 0 | `artifacts/cmd-5.out.txt` / `artifacts/runs/run2.txt` |
| 6a | `diff workflow/evidence/HO-STRATA-011/artifacts/runs/run1.txt workflow/evidence/HO-STRATA-011/artifacts/runs/run2.txt` | repo root | 1 | `artifacts/cmd-6a.out.txt` |
| 6b | `grep '^gen:' run1.txt > run1.norm.txt && grep '^gen:' run2.txt > run2.norm.txt && diff run1.norm.txt run2.norm.txt` | repo root | 0 | `artifacts/cmd-6b.out.txt` |
| 6c | `diff workflow/evidence/HO-STRATA-011/artifacts/runs/olmoe_p1_logits.bin workflow/evidence/HO-STRATA-011/artifacts/runs/olmoe_p1_logits_run2.bin` | repo root | 0 | `artifacts/cmd-6c.out.txt` |
| 7 | `python3 - workflow/evidence/HO-STRATA-011/artifacts/runs/olmoe_p1_4_layers.bin` (shape / non-degeneracy) | repo root | 0 | `artifacts/cmd-7.out.txt` |
| 8 | `sha256sum -c workflow/evidence/HO-STRATA-011/hashes.txt` | repo root | 0 | `artifacts/cmd-8.out.txt` |
| 9 | `git -C /home/kupipi/Documents/git/strata status --porcelain && git -C /home/kupipi/Documents/git/strata rev-parse HEAD && sha256sum /home/kupipi/Documents/git/strata/build-hip/strata` | repo root | 0 | `artifacts/cmd-9.out.txt` |

`<olmoe>` expands to `/home/kupipi/Documents/models/gguf/olmoe-1b-7b/olmoe-1b-7b-0924-instruct-q4_k_m.gguf`.

## 2. Acceptance criteria ↔ evidence

| # | Criterion | Command | Observed | Pass? |
|---|---|---|---|---|
| 1 | Pack identity verified (size, SHA256, arch) | 0 | size 4,213,512,672; sha `8c310f14…`; arch `olmoe` | PASS |
| 2 | Harness built at the pin; provenance recorded | 1 + §4 | tag `b12527`, commit `78e05298…`, libs hashed, see §4 | PASS |
| 3 | Tokenizer parity: 3 prompts, zero differences, BOS convention stated | 2 | Harness ids listed for all 3 prompts; engine tokenizer raises `UnknownPreTokenizer('olmo')` at this pin — recorded as a finding, not hidden; BOS convention stated | **FINDING** (engine tokenizer does not load `olmo` pre-tokenizer) |
| 4 | Reference tokens: P1, 16 greedy, reproducible across two runs | 4 + 5 + 6a + 6b + 6c | `gen:` identical; logits binaries identical; `raw_diff_exit=1`; `normalized_diff_exit=0` | PASS on normalized gate |
| 5 | Layer dump `[4][L][H]` with every layer and position non-zero | 3 + 7 | shape `[4][16][2048]`; all 16 layers non-zero at all 4 positions; no nan/inf | PASS |
| 6 | Logits/top-2 dump `[16][2][2]` with layout documented | 4 | shape `[16][2][2]` (`[step][rank][(token_id_f32, logit_f32)]`), 256 bytes | PASS |
| 7 | Evidence bundle complete; hashes verify; pins include digests | 8 + §3 + `hashes-notes.txt` | `sha256sum -c` clean; base-commit digests recorded | PASS |
| 8 | No engine change | 9 | Strata clean at `baf16363…`; binary `d58ee239…` | PASS |
| 9 | No claim | review | only CPU wall time recorded as observation; no support claim | PASS |

## 3. Artifacts and hashes

| Artifact | Path | SHA256 |
|---|---|---|
| Model pack | `/home/kupipi/Documents/models/gguf/olmoe-1b-7b/olmoe-1b-7b-0924-instruct-q4_k_m.gguf` | `8c310f1435a1222338fd2d3d974975be9cd908180b644bab0c2a94da1ac32f3f` |
| Harness source | `workflow/evidence/HO-STRATA-011/artifacts/oracle_harness.cpp` | `bdc9303d6d884452175e199fff3a894836409543ef6f5f390a4e7eb9ab9b8f33` |
| Tokenizer parity script | `workflow/evidence/HO-STRATA-011/artifacts/tokenize_compare.py` | `9903bc16ad8f7277631f6a209654c8903fa2d5295fc5aafd5e551c536c03e43c` |
| Layer check script | `workflow/evidence/HO-STRATA-011/artifacts/check_layers.py` | `65eca3bd7917805432e90ca782ad1d92dcfad9e211b9f291505e41f9957c3cfa` |
| Parity table generator | `workflow/evidence/HO-STRATA-011/artifacts/generate_parity_table.py` | (in `hashes.txt`) |
| Tokenizer parity table | `workflow/evidence/HO-STRATA-011/artifacts/tokenizer_parity_table.md` | (in `hashes.txt`) |
| Layer dump | `workflow/evidence/HO-STRATA-011/artifacts/runs/olmoe_p1_4_layers.bin` | (in `hashes.txt`) |
| Logits top-2 dump | `workflow/evidence/HO-STRATA-011/artifacts/runs/olmoe_p1_logits.bin` | (in `hashes.txt`) |
| Run 1 stdout | `workflow/evidence/HO-STRATA-011/artifacts/runs/run1.txt` | (in `hashes.txt`) |
| Run 2 stdout | `workflow/evidence/HO-STRATA-011/artifacts/runs/run2.txt` | (in `hashes.txt`) |
| Run 1 normalized | `workflow/evidence/HO-STRATA-011/artifacts/runs/run1.norm.txt` | (in `hashes.txt`) |
| Run 2 normalized | `workflow/evidence/HO-STRATA-011/artifacts/runs/run2.norm.txt` | (in `hashes.txt`) |
| Commands log | `workflow/evidence/HO-STRATA-011/commands.log` | (in `hashes.txt`) |
| Test output | `workflow/evidence/HO-STRATA-011/test-output.txt` | (in `hashes.txt`) |
| Pin notes | `workflow/evidence/HO-STRATA-011/hashes-notes.txt` | (in `hashes.txt`) |
| Manifest | `workflow/evidence/HO-STRATA-011/manifest.md` | (in `hashes.txt`) |

All SHA-256 values are in `hashes.txt`. `olmoe_p1_logits_run2.bin` is a transient
reproducibility check and is intentionally excluded.

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
| `libggml-base.so.1` | `437dd6b7b20c6c4595ef5bbd6628250a819b884e34661f4ee3717194f704ddf5` |
| `libggml-cpu.so.1` | `fcc9fa13f1a3b3136c08e5ffc7ef7e9a120f5157496ab1cc19bc9b53da2bff14` |

**Host-scoped hashes:** because `GGML_NATIVE=ON` selects `-march=native`, the
`ggml-cpu` (and indirectly `ggml-base`) shared-library digests depend on the
host CPU features. The recipe in §1 is reproducible; the digests above are valid
only on this AMD Ryzen AI 9 HX 370 host and this build. The oracle dumps and
generation results remain bit-identical across rebuilds on the same model and
quant.

## 5. Failures, skips, limits

- **Tokenizer parity finding:** the engine's `strata_tokenizer.py` at the Strata
  pin raises `UnknownPreTokenizer("olmo")` when loading the OLMoE GGUF. The
  table therefore records the harness ids and the engine failure side by side.
  This is a genuine finding for the 50k `olmo` vocabulary; it is not hidden or
  treated as a passing comparison.
- CPU wall time is reported as an observation only (no performance claim).
- `workflow/MODELS.md`, `planning/strata-engine/13-family-support-test-plan.md`,
  and `workflow/DECISIONS.md` are pinned by commit `8ce28c4` in
  `hashes-notes.txt` and are intentionally excluded from `hashes.txt` to avoid
  drift.
- The four helper stdout files (`run1.txt`, `run2.txt`, `run1.norm.txt`,
  `run2.norm.txt`) are hashed in `hashes.txt`; the git-ignored duplicate
  `olmoe_p1_logits_run2.bin` is excluded because it is a transient
  reproducibility check, not a committed reference artifact.

## 6. Tokenizer convention

Both sides are intended to use raw-text BPE without prepending BOS:

- **Harness:** `llama_tokenize(vocab, text, add_special=false, parse_special=true)`
  → no `50279` BOS emitted.
- **Engine:** `Tokenizer.encode(text)` would return BPE ids directly; the GGUF
  metadata has `tokenizer.ggml.add_bos_token=False`. At this pin the engine
  refuses to load the `olmo` pre-tokenizer, so no engine-side ids are produced.
- **Empirical:** none of the harness id lists contain `50279`.

## 7. Environment notes

- `LD_LIBRARY_PATH=/tmp/opencode/llama.cpp/build/bin` required at runtime because
  the harness binary is built in `/tmp/opencode`.
- No GPU used; `n_gpu_layers=0`.
- No secrets, tokens, or model weights committed.

## 8. Statement

- [x] Commands are reproducible.
- [x] Outputs are raw; no paraphrasing.
- [x] No secrets.
- [x] Every claim cites an artifact.
- [x] One profile per claim (CPU, OLMoE-1B-7B-Instruct Q4_K_M).
