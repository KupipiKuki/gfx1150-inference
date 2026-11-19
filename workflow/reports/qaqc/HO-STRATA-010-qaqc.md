# QAQC report — HO-STRATA-010

| Field | Value |
|---|---|
| **Handoff** | HO-STRATA-010 (`ARCHITECT_TO_CODER`) → reviewed via `CODER_TO_QAQC` `HO-STRATA-010-QAQC` |
| **Reviewer** | QAQC (`qaqc` subagent), runtime model `Gemini 4 Argon` (`opencode-go/gemini-4-argon`, family `gemini` — distinct from `coder-primary` `opencode-go/kimi-k2.7-code` and `auditor` `opencode-go/deepseek-v4.1-flash`) |
| **Date (UTC)** | 2026-11-18 |
| **Verdict** | **PASS** → `AUDIT_REVIEW` |
| **Scope reviewed** | Branch `wp/strata-010-reference-oracle` at `e54a319aea8431e1712a2b8078d63ceaa83d84d5` (commits `9d8660d`..`e54a319`, evidence commit `836b475100bf9e188bf03bc7621ba4f8dd198855`) vs base `36609255e28da370a35b3a687e9bc351c52981a0` (21 files: 16 under `workflow/evidence/HO-STRATA-010/`, `workflow/handoffs/HO-STRATA-010.md`, `workflow/handoffs/HO-STRATA-010-QAQC.md`, `workflow/MODELS.md`, `workflow/DECISIONS.md`, `workflow/STATUS.md`); pinned Strata checkout `/home/kupipi/Documents/git/strata` at `baf16363b4403ef0ed4f538f5d5ed11c43fb9535` (read-only) |
| **Profile (one only)** | CPU-only reference oracle (`n_gpu_layers=0`, `llama.cpp` tag `b12527` / commit `78e05298f0d68abff41d08d79fa7469264b2aff0`, GCC `13.3.0`, Ubuntu 24.04, Linux `7.0.0-42-generic`), model `DeepSeek-MoE-16B-base` (GGUF arch `deepseek`, 28 blocks, hidden 2048, 64 routed experts top-6 + 2 shared experts, 1 leading dense block, vocab 102,400), quant `Q4_K_M` (`deepseek-moe-16b-base-q4_k_m.gguf`, `10,850,181,856` B, SHA256 `f00ecd83d2fc4f28d1d5531c9583ed9c07452263c84590167bbe014f65c330f5`), workload: 3-prompt raw-text tokenizer parity (`P1`, `P2`, `P3`), 4-token prompt per-layer hidden-state dump (`--tokens 549,6077,280,7239 --n 0`), and 5-token prompt 16-step greedy decode + top-2 logits dump (`--tokens 549,6077,280,7239,317 --n 16`, `n_ctx=4096`) |

---

## 1. Acceptance criteria re-run

Every acceptance criterion in `HO-STRATA-010.md` (§4, criteria 1–9) and `HO-STRATA-010-QAQC.md` (§4, criteria 1–8) was independently rebuilt and re-run in this QAQC session using an isolated output directory (`/tmp/opencode/qaqc-010`, removed after verification) so the repository and evidence tree remained untouched.

| # | Criterion | Command (re-run by QAQC) | Observed (QAQC independent run) | Pass? |
|---|---|---|---|---|
| 1 | `llama.cpp` pinned and built; provenance recorded | `git -C /tmp/opencode/llama.cpp status --porcelain && git -C /tmp/opencode/llama.cpp rev-parse HEAD && git -C /tmp/opencode/llama.cpp describe --tags --exact-match && grep -E "^(CMAKE_BUILD_TYPE\|LLAMA_CURL\|BUILD_SHARED_LIBS\|LLAMA_BUILD_TESTS\|LLAMA_BUILD_EXAMPLES\|LLAMA_BUILD_SERVER):" /tmp/opencode/llama.cpp/build/CMakeCache.txt && sha256sum /tmp/opencode/llama.cpp/build/bin/libllama.so.1 /tmp/opencode/llama.cpp/build/bin/libggml.so.1 /tmp/opencode/llama.cpp/build/bin/libggml-base.so.1 /tmp/opencode/llama.cpp/build/bin/libggml-cpu.so.1` | Clean working tree (`status --porcelain` empty); tag `b12527`; commit `78e05298f0d68abff41d08d79fa7469264b2aff0`; remote `https://github.com/ggerganov/llama.cpp.git`; CMake cache confirms `CMAKE_BUILD_TYPE=Release`, `BUILD_SHARED_LIBS=ON`, `LLAMA_CURL=OFF`, `LLAMA_BUILD_TESTS=OFF`, `LLAMA_BUILD_EXAMPLES=OFF`, `LLAMA_BUILD_SERVER=OFF`, compiler `/usr/bin/c++` (`g++ 13.3.0`). All 4 shared-library SHA256 hashes match `manifest.md` §4 (`libllama.so.1`: `2397a75f...`, `libggml.so.1`: `8f923882...`, `libggml-base.so.1`: `2cc34f6f...`, `libggml-cpu.so.1`: `fcc9fa13...`). | **PASS** |
| 2 | Harness builds and reproduces the same IDs and logits on two consecutive runs | `g++ -O2 -std=c++17 workflow/evidence/HO-STRATA-010/artifacts/oracle_harness.cpp -o /tmp/opencode/qaqc-010/oracle_harness -I/tmp/opencode/llama.cpp/include -I/tmp/opencode/llama.cpp/ggml/include -L/tmp/opencode/llama.cpp/build/bin -lllama -lggml -lggml-base -lggml-cpu -lpthread` followed by two runs of `LD_LIBRARY_PATH=/tmp/opencode/llama.cpp/build/bin /tmp/opencode/qaqc-010/oracle_harness --model <deepseek> --tokens 549,6077,280,7239,317 --n 16 --dump-logits <out.bin>` | Compile exits `0` (5 deprecation warnings on `llama_batch_init`/`llama_decode`/`llama_batch_free`); rebuilt binary SHA256 `083ea0357eacbe516f9cfb7ec2ed31173f013c18cfa9b8e0256ab9b9722e8410` matches `/tmp/opencode/oracle_harness` bit-for-bit. Both QAQC runs emitted `gen: 8913 13 185 40619 317 254 6077 280 7239 13 185 40619 317 254 6077 280` (`diff` exit `0` between run 1, run 2, and recorded `artifacts/runs/run1.txt`) and bit-identical logits binaries with SHA256 `5334baef84380f6060f8b1c4afda5fd45d367e9065ecdf2c6e4ea0642153fb2e`. | **PASS** |
| 3 | Tokenizer parity: all 3 prompts, DeepSeek, zero ID differences vs reference; BOS check | `python3 workflow/evidence/HO-STRATA-010/artifacts/tokenize_compare.py --gguf <deepseek> --harness /tmp/opencode/qaqc-010/oracle_harness` + inspection of `oracle_harness.cpp:197-198`, `tools/strata_tokenizer.py:341-350`, and GGUF metadata | Exit `0`; output matches `artifacts/tokenizer_parity_table.md` (`diff` exit `0`). All 3 prompts match (`match=True`): `P1` → `[549, 6077, 280, 7239, 317]`, `P2` → `[1558, 962, 7, 64, 11, 270, 1780, 185, 300, 972]`, `P3` → `[21477, 6663, 8247, 418]`. **BOS check:** GGUF metadata sets `tokenizer.ggml.add_bos_token=True` and `tokenizer.ggml.bos_token_id=100000`, `tokenizer.ggml.pre='deepseek-llm'`. `Tokenizer.encode()` performs raw-text BPE without prepending BOS `100000`, and `oracle_harness.cpp:198` calls `llama_tokenize(..., add_special=false, parse_special=true)`. Neither side adds or silently drops BOS `100000`. (See Minor M1 on `tokenize_compare.py`'s single-line stdout parse of P2 `decode:`.) | **PASS** |
| 4 | Reference token IDs for DeepSeek, P1, 16 tokens (Mixtral deferred per DEC-029) | QAQC generation runs above + decode check via `Tokenizer.from_gguf(<deepseek>).decode(...)` + Mixtral refusal check `LD_LIBRARY_PATH=/tmp/opencode/llama.cpp/build/bin /tmp/opencode/qaqc-010/oracle_harness --model <mixtral> --prompt "The capital of France is"` | Saved and reproduced: `gen: 8913 13 185 40619 317 254 6077 280 7239 13 185 40619 317 254 6077 280`, which decodes to `' Paris.\nParis is the capital of France.\nParis is the capital of'`. Mixtral `mixtral-8x7b-v0.1.Q3_K_M.gguf` (`542d2453...`) exits `1` (`error: failed to load model ...`), matching DEC-029 (`blk.0.ffn_down_exps.weight` not found in legacy 2023 per-expert layout). | **PASS** |
| 5 | Per-layer dumps exist with documented shape and are non-degenerate | `LD_LIBRARY_PATH=/tmp/opencode/llama.cpp/build/bin /tmp/opencode/qaqc-010/oracle_harness --model <deepseek> --tokens 549,6077,280,7239 --n 0 --dump-layers /tmp/opencode/qaqc-010/deepseek_p1_4_layers.bin && python3 workflow/evidence/HO-STRATA-010/artifacts/check_layers.py /tmp/opencode/qaqc-010/deepseek_p1_4_layers.bin` + GGUF metadata & slice inspection | Prints `layers shape: [4][28][2048]`, file size `917,504` B (`4 * 28 * 2048 * 4`), SHA256 `51c833657bffcdd87759d73e8372838af51d9bca0f2cdbb4ee69e748ac618459` (bit-identical to `artifacts/runs/deepseek_p1_4_layers.bin`). Matches GGUF geometry (`deepseek.block_count=28`, `deepseek.embedding_length=2048`). `check_layers.py` confirms `shape: (4, 28, 2048)`, `non-zero rows per position: [(0, 27), (1, 27), (2, 27), (3, 28)]`, `L0 vs L1 L2 norm (last pos): 3.566159`, `L0 vs L1 dot (last pos): 43.325943`, `any nan/inf: False`. Across all 27 consecutive layer pairs `(l, l+1)` at `pos=3`, L2 differences range from `3.4678` to `117.7664` (non-degenerate throughout; see Minor M2 on `l_out-27` zero-padding at `pos 0..2`). | **PASS** |
| 6 | Logits/top-2 dumps exist for the 16 steps | Inspection of `/tmp/opencode/qaqc-010/deepseek_p1_logits_1.bin` and `workflow/evidence/HO-STRATA-010/artifacts/runs/deepseek_p1_logits.bin` | File present, `256` bytes (`64` `float32` values = 16 steps × top-2 candidates × `(id_f32, logit_f32)`), SHA256 `5334baef84380f6060f8b1c4afda5fd45d367e9065ecdf2c6e4ea0642153fb2e`. All 16 top-1 token IDs in the binary match the 16 generated IDs (`8913, 13, 185, 40619, ...`) with finite margins over top-2 (e.g., step 0: `8913 ' Paris' = 27.1122` vs `245 ' a' = 25.5232`; step 7: `280 ' of' = 33.6740` vs `3787 ' city' = 31.9089`). See Minor M3 on the `[16][2]` vs `[16][2][2]` shape notation. | **PASS** |
| 7 | Harness script committed and runnable from a clean checkout of the workflow repo | Review of `workflow/evidence/HO-STRATA-010/artifacts/oracle_harness.cpp`, `manifest.md` §1/§4, and `commands.log` | `oracle_harness.cpp` (`353` lines, SHA256 `fc0a01da...`), `tokenize_compare.py` (`9ff5a394...`), and `check_layers.py` (`65eca3bd...`) are committed in git. `manifest.md` §4 records the `llama.cpp` tag (`b12527`), commit (`78e05298f0d68abff41d08d79fa7469264b2aff0`), exact CMake flags, GCC `13.3.0`, and shared-library SHA256 hashes, sufficient to rebuild from a clean machine (see Minor M5). | **PASS** |
| 8 | No engine change | `git -C /home/kupipi/Documents/git/strata status --porcelain && git -C /home/kupipi/Documents/git/strata rev-parse HEAD` | Output empty for `status --porcelain`; HEAD is `baf16363b4403ef0ed4f538f5d5ed11c43fb9535`. | **PASS** |
| 9 | No perf/support claim; hashes verified | `sha256sum -c workflow/evidence/HO-STRATA-010/hashes.txt` + commit-pin verification of `hashes-notes.txt` + review of `manifest.md` and `HO-STRATA-010.md` | All 12 entries in `hashes.txt` pass (`OK`). Commit pin `068e8fef8698ede9dae05d8e4f328ed3da084cac:workflow/MODELS.md` hashes to `dae0b4ea06b41c67d63c9b5ccb4d13ce5508df46c35f7b6ac39b65842cb44627` (`OK`). CPU wall times (`0.107 s`, `0.696 s`, `0.702 s`) are explicitly labeled as observations only; no performance or family-support claims are made. | **PASS** |

---

### 1.1 Independent dump inspection (QAQC verification)

#### Layer dump (`deepseek_p1_4_layers.bin`, shape `(4, 28, 2048)` `float32`, `917,504` bytes)

```text
layer  0: pos L2 norms = [6.9308, 6.0075, 4.3595, 5.8627],   pos3[:5] = [0.06615, 0.06112, 0.15603, -0.07936, 0.07609]
layer  1: pos L2 norms = [15.1982, 9.7880, 6.5593, 8.0622],  pos3[:5] = [0.07280, -0.05200, 0.02528, -0.19384, 0.21856]
layer  2: pos L2 norms = [58.3318, 9.0639, 7.5201, 7.8530],  pos3[:5] = [0.02506, -0.16313, 0.14945, -0.23553, 0.22948]
layer 13: pos L2 norms = [837.9457, 26.2074, 27.0281, 28.3949], pos3[:5] = [0.12012, -0.60473, 0.19773, 0.01388, 0.21037]
layer 26: pos L2 norms = [71.5962, 82.1692, 102.9182, 95.1394], pos3[:5] = [-1.16753, -2.94912, -0.46610, -1.55423, 0.00995]
layer 27: pos L2 norms = [0.0000, 0.0000, 0.0000, 172.6473], pos3[:5] = [-2.50602, -4.66061, -1.42284, 0.50884, -0.89194]
pos3 consecutive-layer L2 norm differences (l vs l+1, l=0..26): min = 3.4678 (L1 vs L2), L0 vs L1 = 3.5662, max = 117.7664 (L26 vs L27)
```

#### Logits top-2 dump (`deepseek_p1_logits.bin`, 16 steps × top-2 `(id_f32, logit_f32)`, `256` bytes)

```text
step  0: top1=(  8913,  27.1122) ' Paris'   | top2=(   245,  25.5232) ' a'       | match_gen=True
step  1: top1=(    13,  29.5376) '.'        | top2=(    11,  29.1237) ','        | match_gen=True
step  2: top1=(   185,  24.6364) '\n'       | top2=(   429,  23.9509) ' The'     | match_gen=True
step  3: top1=( 40619,  24.4886) 'Paris'    | top2=( 28670,  23.1462) 'French'   | match_gen=True
step  4: top1=(   317,  27.3620) ' is'      | top2=(    11,  25.4636) ','        | match_gen=True
step  5: top1=(   254,  28.3960) ' the'     | top2=(   245,  27.7507) ' a'       | match_gen=True
step  6: top1=(  6077,  27.7730) ' capital' | top2=(  1094,  27.3315) ' most'    | match_gen=True
step  7: top1=(   280,  33.6740) ' of'      | top2=(  3787,  31.9089) ' city'    | match_gen=True
step  8: top1=(  7239,  31.3760) ' France'  | top2=(   254,  28.2229) ' the'     | match_gen=True
step  9: top1=(    13,  29.2794) '.'        | top2=(   285,  27.9959) ' and'     | match_gen=True
step 10: top1=(   185,  26.5674) '\n'       | top2=(   809,  25.8055) ' It'      | match_gen=True
step 11: top1=( 40619,  19.4659) 'Paris'    | top2=(   549,  19.1105) 'The'      | match_gen=True
step 12: top1=(   317,  29.7102) ' is'      | top2=(    11,  26.6109) ','        | match_gen=True
step 13: top1=(   254,  30.7836) ' the'     | top2=(   245,  28.3183) ' a'       | match_gen=True
step 14: top1=(  6077,  30.7931) ' capital' | top2=(  8397,  26.9891) ' largest' | match_gen=True
step 15: top1=(   280,  33.9332) ' of'      | top2=(  3787,  31.2359) ' city'    | match_gen=True
```

---

### 1.2 Independent SHA256 verification of all bundle files and external inputs

All 12 entries in `workflow/evidence/HO-STRATA-010/hashes.txt` pass `sha256sum -c`:

| File | SHA256 | In `hashes.txt`? |
|---|---|---|
| `workflow/MODELS.md` (pinned at `068e8fef8698ede9dae05d8e4f328ed3da084cac`) | `dae0b4ea06b41c67d63c9b5ccb4d13ce5508df46c35f7b6ac39b65842cb44627` | Yes (`OK`) |
| `workflow/evidence/HO-STRATA-010/artifacts/oracle_harness.cpp` | `fc0a01dad9808d0aa48833225e8432fa59ba2950f09703a0d713b31eb88cf3fb` | Yes (`OK`) |
| `workflow/evidence/HO-STRATA-010/artifacts/tokenize_compare.py` | `9ff5a3947920de6e8ce4af45f6c64461edc8fe0a422b73f4f5e8b3a81f24ef33` | Yes (`OK`) |
| `workflow/evidence/HO-STRATA-010/artifacts/check_layers.py` | `65eca3bd7917805432e90ca782ad1d92dcfad9e211b9f291505e41f9957c3cfa` | Yes (`OK`) |
| `workflow/evidence/HO-STRATA-010/artifacts/pack_hashes.txt` | `eee7093bb547b860e88b63d9e0d20d8fcec37beadec01a71112d6825a7568378` | Yes (`OK`) |
| `workflow/evidence/HO-STRATA-010/artifacts/tokenizer_parity_table.md` | `06c62d18c39a016c086fb949404de76910035a20e334c39b790f947287a6c815` | Yes (`OK`) |
| `workflow/evidence/HO-STRATA-010/artifacts/runs/deepseek_p1_4_layers.bin` | `51c833657bffcdd87759d73e8372838af51d9bca0f2cdbb4ee69e748ac618459` | Yes (`OK`) |
| `workflow/evidence/HO-STRATA-010/artifacts/runs/deepseek_p1_logits.bin` | `5334baef84380f6060f8b1c4afda5fd45d367e9065ecdf2c6e4ea0642153fb2e` | Yes (`OK`) |
| `workflow/evidence/HO-STRATA-010/commands.log` | `dd72817354607116044b057f02f495f78543a4e7fc26871f0f07bb9d2c52acf6` | Yes (`OK`) |
| `workflow/evidence/HO-STRATA-010/test-output.txt` | `2bfe2d0d0bad562d5154c816a830adf4c1b2b06a762df880789f52f2596083ea` | Yes (`OK`) |
| `workflow/evidence/HO-STRATA-010/manifest.md` | `e5d3ef38eb24b1a51c44c4e68d799d25fb60216630fc572f33c21526da5957c4` | Yes (`OK`) |
| `workflow/evidence/HO-STRATA-010/hashes-notes.txt` | `1459853277685c669adb036ea527526ccb819a6502aafa8ff9b920e873f99e7c` | Yes (`OK`) |
| `workflow/evidence/HO-STRATA-010/artifacts/runs/run1.txt` | `fa71666f602b50be180a89e47aa25d872a40b6e8faa8cc304902b90e17ff586a` | No (M4) |
| `workflow/evidence/HO-STRATA-010/artifacts/runs/run2.txt` | `bca2a8045ef7bd59d7ecad46795b9ca02fbf97859d7ac88afdf622251f8bedd9` | No (M4) |
| `workflow/evidence/HO-STRATA-010/artifacts/runs/run1.norm.txt` | `88de45824c276d1ac4ecb3572e3ba6dd42a4130bb137522c3e64dcff780ead2a` | No (M4) |
| `workflow/evidence/HO-STRATA-010/artifacts/runs/run2.norm.txt` | `88de45824c276d1ac4ecb3572e3ba6dd42a4130bb137522c3e64dcff780ead2a` | No (M4) |
| DeepSeek GGUF (`deepseek-moe-16b-base-q4_k_m.gguf`) | `f00ecd83d2fc4f28d1d5531c9583ed9c07452263c84590167bbe014f65c330f5` | In `pack_hashes.txt` (`OK`) |
| Mixtral GGUF (`mixtral-8x7b-v0.1.Q3_K_M.gguf`) | `542d24532f63219db9f530bd2819be9c74f514919ab661dc5162cef844bac38b` | In `pack_hashes.txt` (`OK`) |

---

## 2. Diff and guard-rail review

- [x] **Diff is within scope; no unrelated files.** `git diff 36609255e28da370a35b3a687e9bc351c52981a0..e54a319aea8431e1712a2b8078d63ceaa83d84d5 --name-status` touches 21 files: 16 under `workflow/evidence/HO-STRATA-010/`, `workflow/handoffs/HO-STRATA-010.md`, `workflow/handoffs/HO-STRATA-010-QAQC.md`, `workflow/MODELS.md`, `workflow/DECISIONS.md` (DEC-028, DEC-029), and `workflow/STATUS.md`. Scope narrowing to DeepSeek-MoE-16B Q4_K_M is explicitly authorized and recorded in `DEC-029` and `HO-STRATA-010.md` §2.5.
- [x] **No Strata engine changes.** `git -C /home/kupipi/Documents/git/strata status --porcelain` is empty and `HEAD` is `baf16363b4403ef0ed4f538f5d5ed11c43fb9535`.
- [x] **No new dependencies without approval.** `llama.cpp` was built in `/tmp/opencode/llama.cpp` as explicitly authorized by `HO-STRATA-010.md` §2.1 and §7. No model downloads or conversions were performed.
- [x] **No secrets/tokens in the diff, logs, or evidence.** No credentials, tokens, or model weights are committed to git (the largest committed evidence file is `deepseek_p1_4_layers.bin` at `917,504` bytes, well under the 50 MB threshold in `HO-STRATA-010.md` §5).
- [x] **Tests are meaningful; no skips hidden as passes.** Mixtral's legacy per-expert tensor layout refusal in `llama.cpp` `b12527` (`blk.0.ffn_down_exps.weight` not found) was reported to the Architect and deferred via `DEC-029` rather than worked around or silently skipped.
- [x] **Evidence matches the commands that were run.** Rebuilding `oracle_harness.cpp` and re-running the tokenizer parity, layer dump, and two 16-step generation runs reproduced identical SHA256 hashes for the binary, the layer dump, the logits dump, and the `gen:` token ID sequence.

---

## 3. Findings (severity order)

No Blocker or Major findings. Five Minor non-blocking technical/documentation observations are recorded for the Auditor and for downstream S4/S5 parity stages:

| # | Severity | Finding | File:line / evidence | Required action |
|---|---|---|---|---|
| M1 | Minor | `tokenize_compare.py` prints `harness decode mismatch: 'def add(a, b):'` on stderr for `P2`, even though `oracle_harness` detokenizes `P2` accurately to the full multi-line string `def add(a, b):\n    return`. The warning is caused by `tokenize_compare.py:39-41` iterating over `out.stdout.splitlines()` and capturing only the first line starting with `"decode:"`, which truncates at the embedded newline `\n`. Token ID lists match identically (`[1558, 962, 7, 64, 11, 270, 1780, 185, 300, 972]`). | `workflow/evidence/HO-STRATA-010/artifacts/tokenize_compare.py:39-41`, `test-output.txt:2` | Non-blocking; if `tokenize_compare.py` is reused in S1+, parse everything after `\ndecode: ` rather than a single `splitlines()` entry. |
| M2 | Minor | In `deepseek_p1_4_layers.bin` (`[4][28][2048]`), layers `0..26` are non-zero across all 4 prompt positions (`pos 0..3`), whereas the final block (`l_out-27`, layer index `27`) is non-zero only at `pos=3` (`L2 norm = 172.6473`) and zero-padded at `pos 0..2`. This occurs because `oracle_harness.cpp:259-261` sets `batch.logits[i] = 0` for `i = 0..2` and `batch.logits[3] = 1`, so `llama.cpp` slices the final transformer block output to `n_outputs = 1` (`pos=3`). | `workflow/evidence/HO-STRATA-010/artifacts/oracle_harness.cpp:259-261,284-292`, `test-output.txt:43` | Non-blocking for S0 (explicitly reported by `check_layers.py`); S4 layer-parity comparisons should either compare `l_out-27` at `pos=3` (and `l_out-0..26` at `pos=0..3`) or set `batch.logits[i] = 1` for all prompt tokens when regenerating. |
| M3 | Minor | `oracle_harness.cpp:344` prints `logits shape: [16][2]` for `deepseek_p1_logits.bin` (`256` bytes = `64` `float32` values). Because each of the 16 steps writes two `(float(token_id), float(logit))` pairs (top-1 and top-2), the binary layout is 16 steps × 2 ranks × 2 floats (`[16][2][2]` `float32`). | `workflow/evidence/HO-STRATA-010/artifacts/oracle_harness.cpp:308-309,339-344` | Non-blocking; S5 consumers reading `deepseek_p1_logits.bin` should reshape as `(16, 2, 2)` `float32` (`[step, rank, (id_f32, logit_f32)]`). |
| M4 | Minor | `hashes.txt` includes `workflow/MODELS.md` (line 3) in addition to pinning `workflow/MODELS.md` by commit `068e8fef8698ede9dae05d8e4f328ed3da084cac` in `hashes-notes.txt`, and omits the 4 small helper stdout files `artifacts/runs/run{1,2}{.norm,}.txt` (plus the git-ignored duplicate `deepseek_p1_logits_run2.bin` left on disk). `sha256sum -c workflow/evidence/HO-STRATA-010/hashes.txt` passes 12/12 `OK` today, though a future edit to `workflow/MODELS.md` on `main` would cause line 3 of `hashes.txt` to drift (DEC-024). | `workflow/evidence/HO-STRATA-010/hashes.txt:3`, `hashes-notes.txt:8` | Non-blocking; all 16 committed bundle file digests and the `068e8fef` blob digest (`dae0b4ea...`) are verified and recorded in §1.2 above. |
| M5 | Minor | `manifest.md` §4 records the exact `llama.cpp` tag (`b12527`), commit (`78e05298f0d68abff41d08d79fa7469264b2aff0`), clone path (`/tmp/opencode/llama.cpp`), CMake flags, compiler (`GCC 13.3.0`), and shared-library hashes, which is sufficient to reproduce from a clean machine, but `commands.log` starts at step 1 (`g++ ... oracle_harness.cpp`) and omits the literal `git clone https://github.com/ggerganov/llama.cpp.git /tmp/opencode/llama.cpp && git -C /tmp/opencode/llama.cpp checkout 78e05298f0d68abff41d08d79fa7469264b2aff0` command. | `workflow/evidence/HO-STRATA-010/manifest.md:54-69`, `commands.log:1-11` | Non-blocking; the commit SHA, tag, remote URL, and CMake command are documented in `manifest.md` §4 and §1 of this report. |

---

## 4. Verdict and next state

- **PASS** → `AUDIT_REVIEW`; attach this report (`workflow/reports/qaqc/HO-STRATA-010-qaqc.md`) and the evidence path (`workflow/evidence/HO-STRATA-010/`).

### `QAQC_TO_AUDITOR` handoff record (per DEC-018)

Per the QAQC write boundary (`workflow/ENGINEERING_WORKFLOW.md` §4 and `DEC-018`), the complete `QAQC_TO_AUDITOR` handoff record is embedded below:

```markdown
# HO-STRATA-010-AUDIT — S0 reference oracle and parity harness: Audit review

| Field | Value |
|---|---|
| **ID** | HO-STRATA-010-AUDIT |
| **Type** | QAQC_TO_AUDITOR |
| **State** | AUDIT_REVIEW |
| **Created / updated (UTC)** | 2026-11-18 / 2026-11-18 |
| **From → To** | QAQC (`qaqc`, `opencode-go/gemini-4-argon`) → Auditor (`auditor`, `opencode-go/deepseek-v4.1-flash`) |
| **Work package** | `strata-010-reference-oracle` |
| **Branch / base commit** | `wp/strata-010-reference-oracle` / `e54a319aea8431e1712a2b8078d63ceaa83d84d5` (evidence commit `836b475100bf9e188bf03bc7621ba4f8dd198855`) on top of `36609255e28da370a35b3a687e9bc351c52981a0` |
| **Priority / timebox** | P1 · 1 working day |
| **Original handoff** | `workflow/handoffs/HO-STRATA-010.md` |
| **Coder→QAQC handoff** | `workflow/handoffs/HO-STRATA-010-QAQC.md` |
| **QAQC report** | `workflow/reports/qaqc/HO-STRATA-010-qaqc.md` |
| **Evidence path** | `workflow/evidence/HO-STRATA-010/` |

## 1. Scope (in)

- Audit the coder's S0 reference oracle evidence bundle (`workflow/evidence/HO-STRATA-010/`) and the independent QAQC report (`workflow/reports/qaqc/HO-STRATA-010-qaqc.md`) against `workflow/handoffs/HO-STRATA-010.md`, `DEC-024`, `DEC-028`, and `DEC-029`.
- Verify claims, guard rails, scope narrowing (DeepSeek-MoE-16B Q4_K_M in scope; Mixtral 8x7B Q3_K_M deferred per DEC-029), role-model separation, and evidence integrity.
- Write `workflow/reports/audit/HO-STRATA-010-audit.md` and transition to `ARCHITECT_APPROVAL` (PASS) or `REWORK` (FAIL).

## 2. Out of scope

- Mixtral 8x7B reference outputs (deferred by DEC-029 until a stacked-format GGUF is fetched).
- Any changes to the `strata` checkout (`/home/kupipi/Documents/git/strata` at `baf16363b4403ef0ed4f538f5d5ed11c43fb9535`) or S1+ family implementation work.
- Choosing S4 layer tolerances or S5 KL bounds.
- Any performance or support claims.

## 3. Inputs

| Input | Path / hash | Status |
|---|---|---|
| Architect handoff | `workflow/handoffs/HO-STRATA-010.md` | CODER_DONE |
| Coder→QAQC handoff | `workflow/handoffs/HO-STRATA-010-QAQC.md` | reviewed (PASS) |
| QAQC report | `workflow/reports/qaqc/HO-STRATA-010-qaqc.md` | PASS → `AUDIT_REVIEW` |
| Evidence bundle | `workflow/evidence/HO-STRATA-010/` | verified (12/12 `hashes.txt` `OK`) |
| Harness source | `workflow/evidence/HO-STRATA-010/artifacts/oracle_harness.cpp` (`fc0a01dad9808d0aa48833225e8432fa59ba2950f09703a0d713b31eb88cf3fb`) | rebuilt & verified |
| DeepSeek model pack | `/home/kupipi/.cache/huggingface/hub/models--Lucy-in-the-Sky--deepseek-moe-16b-base-Q4_K_M-GGUF/snapshots/1f2b397cdb560ffb519aa8371d2f9eebae50d34d/deepseek-moe-16b-base-q4_k_m.gguf` (`f00ecd83d2fc4f28d1d5531c9583ed9c07452263c84590167bbe014f65c330f5`) | verified |

## 4. Acceptance criteria (for Audit)

| # | Criterion | Check | Expected |
|---|---|---|---|
| 1 | Evidence integrity | `sha256sum -c workflow/evidence/HO-STRATA-010/hashes.txt` and `hashes-notes.txt` commit pin check | All 12 entries `OK`; commit pin `068e8fef8698ede9dae05d8e4f328ed3da084cac:workflow/MODELS.md` verified |
| 2 | Independent QAQC verification | Review `workflow/reports/qaqc/HO-STRATA-010-qaqc.md` | All AC-1..AC-9 independently rebuilt/re-run and passed; bit-identical layer and logits dump hashes; runtime model separation (`kimi` → `gemini` → `deepseek`) confirmed |
| 3 | Guard rails & scope | Check diff `36609255..e54a319` and Strata checkout `baf16363` | Only `HO-STRATA-010` / DEC-028..029 / `MODELS.md` touched; Strata clean; single CPU oracle profile; no perf/support claims |

## 5. Signatures

| Role | Name/agent | Date | Decision |
|---|---|---|---|
| Sender (QAQC) | `qaqc` (`opencode-go/gemini-4-argon`) | 2026-11-18 | PASS → `AUDIT_REVIEW` |
| Receiver (Auditor) | `auditor` | | |
```

---

## 5. Statement

I did not modify code, tests, docs, configuration, evidence, or handoffs. This report (`workflow/reports/qaqc/HO-STRATA-010-qaqc.md`) is the only artifact I wrote.
