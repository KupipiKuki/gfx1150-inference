# QAQC report — HO-STRATA-010

| Field | Value |
|---|---|
| **Handoff** | HO-STRATA-010 (`ARCHITECT_TO_CODER`) → reviewed via `CODER_TO_QAQC` `HO-STRATA-010-QAQC` and re-checked after `RW-HO-STRATA-010-1` |
| **Reviewer** | QAQC (`qaqc` subagent), runtime model `Gemini 4 Argon` (`opencode-go/gemini-4-argon`, family `gemini` — distinct from `coder-primary` `opencode-go/kimi-k2.7-code` and `auditor` `opencode-go/deepseek-v4.1-flash`) |
| **Date (UTC)** | 2026-11-19 (re-pass after `RW-HO-STRATA-010-1`; initial review 2026-11-18) |
| **Verdict** | **PASS** → `AUDIT_REVIEW` (re-audit after `RW-HO-STRATA-010-1` closure at `664bd40`) |
| **Scope reviewed** | Branch `wp/strata-010-reference-oracle` at commit `664bd408ed011a7041f43a81c02c237f71290866` (`664bd40`), rebased onto `main` `8ce28c4e2e33904b824d8541d69f1ea770548424` (`8ce28c4`) — 24 files in `8ce28c4..664bd40` (16 under `workflow/evidence/HO-STRATA-010/`, `workflow/handoffs/HO-STRATA-010.md`, `workflow/handoffs/HO-STRATA-010-QAQC.md`, `workflow/handoffs/RW-HO-STRATA-010-1.md`, `workflow/reports/audit/HO-STRATA-010-audit.md`, `workflow/reports/qaqc/HO-STRATA-010-qaqc.md`, `workflow/MODELS.md`, `workflow/DECISIONS.md`, `workflow/STATUS.md`); pinned Strata checkout `/home/kupipi/Documents/git/strata` at `baf16363b4403ef0ed4f538f5d5ed11c43fb9535` (read-only, binary `build-hip/strata` `d58ee2398596d1a100c15d5b9459e24bd86854cb5e5fb7ce88dbc6c7ed9f5858`) |
| **Profile (one only)** | CPU-only reference oracle (`n_gpu_layers=0`, `llama.cpp` tag `b12527` / commit `78e05298f0d68abff41d08d79fa7469264b2aff0`, CMake `3.28.3`, `GGML_NATIVE=ON`, GCC `13.3.0`, Ubuntu 24.04, Linux `7.0.0-42-generic`, AMD Ryzen AI 9 HX 370 w/ Radeon 890M, 24 vCPUs), model `DeepSeek-MoE-16B-base` (GGUF arch `deepseek`, 28 blocks, hidden 2048, 64 routed experts top-6 + 2 shared experts, 1 leading dense block, vocab 102,400), quant `Q4_K_M` (`deepseek-moe-16b-base-q4_k_m.gguf`, `10,850,181,856` B, SHA256 `f00ecd83d2fc4f28d1d5531c9583ed9c07452263c84590167bbe014f65c330f5`), workload: 3-prompt raw-text tokenizer parity (`P1`, `P2`, `P3`), 4-token prompt per-layer hidden-state dump (`--tokens 549,6077,280,7239 --n 0`), and 5-token prompt 16-step greedy decode + top-2 logits dump (`--tokens 549,6077,280,7239,317 --n 16`, `n_ctx=4096`) |

---

## Re-pass (`664bd40`)

This section records the independent QAQC re-pass on commit `664bd408ed011a7041f43a81c02c237f71290866` (`HO-STRATA-010: close RW-HO-STRATA-010-1 (parity artifact + diff exit)`), rebased onto `main` `8ce28c4e2e33904b824d8541d69f1ea770548424`. All checks were executed independently by QAQC using a temporary scratch directory (`/tmp/opencode/qaqc-repass-010`, removed after verification) without modifying any repository or evidence file.

### Re-pass fingerprint

| Item | Verified value |
|---|---|
| **Reviewed commit SHA** | `664bd408ed011a7041f43a81c02c237f71290866` (`664bd40`) on branch `wp/strata-010-reference-oracle` (base `main` `8ce28c4e2e33904b824d8541d69f1ea770548424`) |
| **`hashes.txt` entry count & check** | **15/15 entries `OK`** (`sha256sum -c workflow/evidence/HO-STRATA-010/hashes.txt` exit `0`); together with `hashes.txt` itself (`4f1f045ba7b432b8fb0ed91fb3d3c8992bd4e3ca7494beeac2efc48f2c41c535`), all **16 committed files** in `workflow/evidence/HO-STRATA-010/` are accounted for, plus **2/2 model packs `OK`** in `artifacts/pack_hashes.txt` |
| **Rebuilt harness binary SHA256** | `40cf635f0dc36a26202f9145af786423c200633c4b9bd1986be42f7159f68506` (rebuilt from committed `oracle_harness.cpp` `bdc9303d6d884452175e199fff3a894836409543ef6f5f390a4e7eb9ab9b8f33`; bit-identical to `/tmp/opencode/oracle_harness`) |
| **Layer dump digest (`deepseek_p1_4_layers.bin`)** | `db6eccb3e8a949827c5c961fc732159daa1a0a9d52f7f88156d669845e0c7c73` (`[4][28][2048]` `float32`, `917,504` B; all 28 layers non-zero at all 4 positions `[(0, 28), (1, 28), (2, 28), (3, 28)]`, `any nan/inf: False`; bit-identical on QAQC re-run) |
| **Logits dump digest (`deepseek_p1_logits.bin`)** | `5334baef84380f6060f8b1c4afda5fd45d367e9065ecdf2c6e4ea0642153fb2e` (`[16][2][2]` `float32`, `256` B; bit-identical across both QAQC re-runs and the committed artifact) |
| **Tokenizer parity table digest (`tokenizer_parity_table.md`)** | `8512eb971c4b029f38e9c934ecfb5a9cf53fffd102c79f93b613681d0b9d7270` (byte-identical on QAQC regeneration; `diff` empty, exit `0`) |
| **Reference `gen:` line (`run1.norm.txt` / `run2.norm.txt`)** | `gen: 8913 13 185 40619 317 254 6077 280 7239 13 185 40619 317 254 6077 280` (SHA256 `88de45824c276d1ac4ecb3572e3ba6dd42a4130bb137522c3e64dcff780ead2a`; identical across both QAQC runs and committed runs) |
| **Re-pass verdict** | **PASS** → `AUDIT_REVIEW` (this report serves as the `QAQC_TO_AUDITOR` record per DEC-018; the auditor should now re-audit `664bd40`) |

### Verification of `RW-HO-STRATA-010-1` findings (F1–F3, A-4…A-9, C1–C5, and pins)

| Item | Requirement | QAQC independent check & evidence | Status |
|---|---|---|---|
| **F1 / A-1** (Major) | Regenerate `artifacts/tokenizer_parity_table.md` with the recorded command; `diff` empty (exit `0`); `head -2` shows `\| prompt \|` header; `grep -c 'harness decode mismatch'` is `0`; hashes updated | Ran `python3 workflow/evidence/HO-STRATA-010/artifacts/tokenize_compare.py --gguf <deepseek> --harness /tmp/opencode/qaqc-repass-010/oracle_harness > /tmp/opencode/qaqc-repass-010/tokenizer_parity_table.md 2> /tmp/opencode/qaqc-repass-010/parity.err`: exit `0`, stderr empty (`0` lines). `diff` against committed `workflow/evidence/HO-STRATA-010/artifacts/tokenizer_parity_table.md` is empty, exit `0`. `head -2` shows `\| prompt \| text \| engine ids \| harness ids \| match \| notes \|` and `\|---\|---\|---\|---\|---\|---\|`. `grep -c 'harness decode mismatch'` returns `0`. SHA256 `8512eb971c4b029f38e9c934ecfb5a9cf53fffd102c79f93b613681d0b9d7270` matches `hashes.txt:7` and `manifest.md:52`. | **CLOSED / PASS** |
| **F2 / A-2** (Major) | Record true `stdout_diff_exit=1` and `normalized_diff_exit=0` in `test-output.txt`; record normalization command in `commands.log` and `manifest.md` §1 and verify it reproduces `.norm` files | `grep -n 'stdout_diff_exit\|normalized_diff_exit' workflow/evidence/HO-STRATA-010/test-output.txt` outputs `35:stdout_diff_exit=1` and `45:normalized_diff_exit=0`. Running `diff workflow/evidence/HO-STRATA-010/artifacts/runs/run1.txt workflow/evidence/HO-STRATA-010/artifacts/runs/run2.txt` exits `1` (because `wall_s: 0.686` vs `0.678` and output filenames differ). Running the normalization command recorded in `commands.log:61-63` and `manifest.md:23` (`grep '^gen:' ... > run{1,2}.norm.txt && diff ...`) exits `0` and reproduces `run1.norm.txt` and `run2.norm.txt` byte-for-byte (`88de45824c276d1ac4ecb3572e3ba6dd42a4130bb137522c3e64dcff780ead2a`). *(See residual cosmetic observation R1 on `test-output.txt:30,34`.)* | **CLOSED / PASS** |
| **F3 / A-3** (Major) | QAQC re-runs AC-1…9 and C1–C5 against the new commit and refreshes `workflow/reports/qaqc/HO-STRATA-010-qaqc.md` | Full acceptance set and C1–C5 independently rebuilt and re-run against `664bd40`; report refreshed with commit SHA, hash counts, dump digests, and updated `QAQC_TO_AUDITOR` record. | **CLOSED / PASS** |
| **Pins (`8ce28c4`)** | `workflow/MODELS.md` and `planning/strata-engine/13-family-support-test-plan.md` pinned at `8ce28c4` in `hashes-notes.txt`; no dead SHA (`068e8fe`, `836b475`, `d5d4800`, `3660925`) remains as a pin | `hashes-notes.txt:9-10` pins both files at `8ce28c4`. Verified `git show 8ce28c4:workflow/MODELS.md \| sha256sum` → `1883c62b5052e36316fc31f48ccfb4b3912ef0d14540170475c4c79071f6e10b` (base inventory; branch commit `5097706` appends the DEC-029 Mixtral format note → working tree `dae0b4ea06b41c67d63c9b5ccb4d13ce5508df46c35f7b6ac39b65842cb44627`) and `git show 8ce28c4:planning/strata-engine/13-family-support-test-plan.md \| sha256sum` → `023a37de06e785f96f94890fc16cec9279ca000513c1d2eedb6d779f28450bec` (identical to working tree). `grep -rnE '068e8fe\|836b475\|d5d4800\|3660925' workflow/evidence/HO-STRATA-010/ workflow/handoffs/HO-STRATA-010.md` returns 0 matches. | **CLOSED / PASS** |
| **A-4** (Minor) | Record normalization command in `commands.log` and `manifest.md` | Present in `commands.log:61-63`, `manifest.md:23` (row `6c`), and `test-output.txt:42-44`. Re-run reproduces `run1.norm.txt` and `run2.norm.txt` (`88de4582…`, `diff` exit `0`). | **CLOSED / PASS** |
| **A-5** (Minor) | `manifest.md` §1 paths runnable from stated CWD | Rows `1`–`7` in `manifest.md:16-24` all specify CWD `repo root` and use full repo-root-relative paths (`workflow/evidence/HO-STRATA-010/...`). Verified copy-paste runnable from `/home/kupipi/Documents/git/gfx1150-inference`. | **CLOSED / PASS** |
| **A-6** (Minor) | `manifest.md` commit field sensible | `manifest.md:4` reads `bundle commit recorded in HO-STRATA-010.md log / wp/strata-010-reference-oracle (base main 8ce28c4)`, avoiding self-hash circularity while `HO-STRATA-010.md:11,166-174` names base `8ce28c4` and the tip of `wp/strata-010-reference-oracle` (`664bd40`). | **CLOSED / PASS** |
| **A-7** (Minor) | Provenance records `GGML_NATIVE=ON`, `cmake --version`, host CPU, `nproc`, and host-scoped lib digests | `manifest.md:6,70-79` records `AMD Ryzen AI 9 HX 370 w/ Radeon 890M, 24 vCPUs`, CMake `3.28.3`, `GGML_NATIVE=ON`, and states that shared-library digests are host-scoped. Independently verified against `/proc/cpuinfo`, `nproc` (`24`), `cmake --version` (`3.28.3`), `CMakeCache.txt`, and `sha256sum` of all 4 `.so.1` files (`libllama.so.1` `2397a75f…`, `libggml.so.1` `8f923882…`, `libggml-base.so.1` `437dd6b7…`, `libggml-cpu.so.1` `fcc9fa13…`). | **CLOSED / PASS** |
| **A-8** (Minor) | State BOS / `add_special` / `parse_special` convention on both sides | `manifest.md:92-100` (§6) explicitly documents `llama_tokenize(vocab, text, add_special=false, parse_special=true)` on the harness side and `Tokenizer.encode(text)` (`add_bos_token=False`) on the engine side, with no BOS `100000` in any of the six ID lists, and notes `parse_special` alignment for S1+. | **CLOSED / PASS** |
| **A-9** (Observation) | Record C1 last-block GEMM note (`M=1` → `M=4`) in `manifest.md` | `manifest.md:90` records that requesting logits for all 4 prompt positions changes the final block's GEMM from `M=1` to `M=4`, shifting `l_out-27` at `pos=3` by `≤ 3.81e-6` abs (rel L2 `8.07e-8`, `699/2048` bit-equal) while layers `0..26` and generation logits remain bit-identical. | **CLOSED / PASS** |
| **C1–C5** (Prior QAQC M1–M5) | Layer dump 28/28 at all 4 positions (`db6eccb3…`); logits shape `[16][2][2]` + layout line; `MODELS.md` out of `hashes.txt` & 4 run files hashed; full multi-line decode in `tokenize_compare.py` & table; clone/build in `commands.log` | All 5 closures verified on `664bd40`: `check_layers.py` reports `[(0, 28), (1, 28), (2, 28), (3, 28)]` on `db6eccb3…`; harness prints `logits shape: [16][2][2]` and layout line; `hashes.txt` has 15 entries (all `OK`, no `MODELS.md`, all 4 `run*.txt` included); `tokenizer_parity_table.md` (`8512eb97…`) has 0 mismatch warnings; `commands.log:5-11` has clone/checkout/CMake steps. | **CLOSED / PASS** |

---

## 1. Acceptance criteria re-run (at `664bd40`)

Every acceptance criterion in `HO-STRATA-010.md` (§4, criteria 1–9) and `HO-STRATA-010-QAQC.md` (§4, criteria 1–9) was independently rebuilt and re-run on commit `664bd40` using `/tmp/opencode/qaqc-repass-010` (removed after verification).

| # | Criterion | Command (re-run by QAQC) | Observed (QAQC independent run on `664bd40`) | Pass? |
|---|---|---|---|---|
| 1 | `llama.cpp` pinned and built; provenance recorded | `git -C /tmp/opencode/llama.cpp status --porcelain && git -C /tmp/opencode/llama.cpp rev-parse HEAD && git -C /tmp/opencode/llama.cpp describe --tags --exact-match && cmake --version && nproc && grep -E "^(CMAKE_BUILD_TYPE\|LLAMA_CURL\|BUILD_SHARED_LIBS\|LLAMA_BUILD_TESTS\|LLAMA_BUILD_EXAMPLES\|LLAMA_BUILD_SERVER\|GGML_NATIVE):" /tmp/opencode/llama.cpp/build/CMakeCache.txt && sha256sum /tmp/opencode/llama.cpp/build/bin/lib{llama,ggml,ggml-base,ggml-cpu}.so.1` | Clean tree; tag `b12527`; commit `78e05298f0d68abff41d08d79fa7469264b2aff0`; CMake `3.28.3`; 24 vCPUs (`AMD Ryzen AI 9 HX 370 w/ Radeon 890M`); `CMAKE_BUILD_TYPE=Release`, `BUILD_SHARED_LIBS=ON`, `GGML_NATIVE=ON`, `LLAMA_CURL=OFF`, `LLAMA_BUILD_{TESTS,EXAMPLES,SERVER}=OFF`; GCC `13.3.0`. All 4 `.so.1` digests match `manifest.md` §4 (`libllama.so.1`: `2397a75f…`, `libggml.so.1`: `8f923882…`, `libggml-base.so.1`: `437dd6b7…`, `libggml-cpu.so.1`: `fcc9fa13…`). | **PASS** |
| 2 | Harness builds and reproduces the same IDs and logits on two consecutive runs | `g++ -O2 -std=c++17 workflow/evidence/HO-STRATA-010/artifacts/oracle_harness.cpp -o /tmp/opencode/qaqc-repass-010/oracle_harness -I/tmp/opencode/llama.cpp/include -I/tmp/opencode/llama.cpp/ggml/include -L/tmp/opencode/llama.cpp/build/bin -lllama -lggml -lggml-base -lggml-cpu -lpthread` followed by two runs of `LD_LIBRARY_PATH=/tmp/opencode/llama.cpp/build/bin /tmp/opencode/qaqc-repass-010/oracle_harness --model <deepseek> --tokens 549,6077,280,7239,317 --n 16 --dump-logits <out.bin>` | Compile exits `0` (5 deprecation warnings); rebuilt binary SHA256 `40cf635f0dc36a26202f9145af786423c200633c4b9bd1986be42f7159f68506` matches `/tmp/opencode/oracle_harness`. Both QAQC runs emitted `gen: 8913 13 185 40619 317 254 6077 280 7239 13 185 40619 317 254 6077 280` and bit-identical logits binaries (`5334baef84380f6060f8b1c4afda5fd45d367e9065ecdf2c6e4ea0642153fb2e`). Raw stdout `run1.txt` vs `run2.txt` differs in `wall_s` (`0.686` vs `0.678` committed; `0.676` vs `0.695` in QAQC re-run) and output filename (`stdout_diff_exit=1`); the normalized `gen:` comparison (`grep '^gen:'` → `run1.norm.txt` vs `run2.norm.txt`, `88de4582…`) is the reproducibility gate of record and exits `0`. | **PASS** |
| 3 | Tokenizer parity: all 3 prompts, DeepSeek, zero ID differences vs reference; BOS check | `python3 workflow/evidence/HO-STRATA-010/artifacts/tokenize_compare.py --gguf <deepseek> --harness /tmp/opencode/qaqc-repass-010/oracle_harness > /tmp/opencode/qaqc-repass-010/tokenizer_parity_table.md` + `diff` against `workflow/evidence/HO-STRATA-010/artifacts/tokenizer_parity_table.md` | Exit `0`, empty stderr (`0` mismatch warnings), byte-identical to committed `artifacts/tokenizer_parity_table.md` (`8512eb971c4b029f38e9c934ecfb5a9cf53fffd102c79f93b613681d0b9d7270`, `diff` exit `0`). `P1` → `[549, 6077, 280, 7239, 317]`, `P2` → `[1558, 962, 7, 64, 11, 270, 1780, 185, 300, 972]`, `P3` → `[21477, 6663, 8247, 418]`, all `match=True`. Neither side prepends BOS `100000` (`manifest.md` §6). | **PASS** |
| 4 | Reference token IDs for DeepSeek, P1, 16 tokens (Mixtral deferred per DEC-029) | QAQC generation runs above + Mixtral refusal check | Saved and reproduced: `gen: 8913 13 185 40619 317 254 6077 280 7239 13 185 40619 317 254 6077 280` (`' Paris.\nParis is the capital of France.\nParis is the capital of'`). Mixtral deferred per DEC-029. | **PASS** |
| 5 | Per-layer dumps exist with documented shape and are non-degenerate | `LD_LIBRARY_PATH=/tmp/opencode/llama.cpp/build/bin /tmp/opencode/qaqc-repass-010/oracle_harness --model <deepseek> --tokens 549,6077,280,7239 --n 0 --dump-layers /tmp/opencode/qaqc-repass-010/deepseek_p1_4_layers.bin && python3 workflow/evidence/HO-STRATA-010/artifacts/check_layers.py /tmp/opencode/qaqc-repass-010/deepseek_p1_4_layers.bin` | Prints `layers shape: [4][28][2048]`, size `917,504` B, SHA256 `db6eccb3e8a949827c5c961fc732159daa1a0a9d52f7f88156d669845e0c7c73` (bit-identical to committed `artifacts/runs/deepseek_p1_4_layers.bin`). `check_layers.py` confirms `shape: (4, 28, 2048)`, `non-zero rows per position: [(0, np.int64(28)), (1, np.int64(28)), (2, np.int64(28)), (3, np.int64(28))]`, `L0 vs L1 L2 norm (last pos): 3.566159`, `L0 vs L1 dot (last pos): 43.325943`, `any nan/inf: False`. | **PASS** |
| 6 | Logits/top-2 dumps exist for the 16 steps | Inspection of `/tmp/opencode/qaqc-repass-010/deepseek_p1_logits.bin` and committed `workflow/evidence/HO-STRATA-010/artifacts/runs/deepseek_p1_logits.bin` | File present, `256` B (`64` `float32` values = `[16][2][2]`, layout `[step][rank][(token_id_f32, logit_f32)]`), SHA256 `5334baef84380f6060f8b1c4afda5fd45d367e9065ecdf2c6e4ea0642153fb2e`. All 16 top-1 token IDs match the generated sequence with finite margins over top-2. | **PASS** |
| 7 | Harness script committed and runnable from a clean checkout of the workflow repo | Review of `workflow/evidence/HO-STRATA-010/artifacts/oracle_harness.cpp`, `manifest.md` §1/§4, and `commands.log` | `oracle_harness.cpp` (`bdc9303d…`), `tokenize_compare.py` (`9903bc16…`), and `check_layers.py` (`65eca3bd…`) are committed; `commands.log` and `manifest.md` §1 provide full repo-root-runnable commands from clone/build through verification. | **PASS** |
| 8 | No engine change | `git -C /home/kupipi/Documents/git/strata status --porcelain && git -C /home/kupipi/Documents/git/strata rev-parse HEAD && sha256sum /home/kupipi/Documents/git/strata/build-hip/strata` | Working tree clean (`status --porcelain` empty); HEAD `baf16363b4403ef0ed4f538f5d5ed11c43fb9535`; binary `build-hip/strata` unchanged at `d58ee2398596d1a100c15d5b9459e24bd86854cb5e5fb7ce88dbc6c7ed9f5858`. | **PASS** |
| 9 | No perf/support claim; hashes verified | `sha256sum -c workflow/evidence/HO-STRATA-010/hashes.txt` + `sha256sum -c workflow/evidence/HO-STRATA-010/artifacts/pack_hashes.txt` + `git show 8ce28c4:<path> \| sha256sum` | All **15/15** entries in `hashes.txt` pass (`OK`), all **2/2** entries in `pack_hashes.txt` pass (`OK`), and both `8ce28c4` commit pins in `hashes-notes.txt` resolve (`workflow/MODELS.md` → `1883c62b…` at base `8ce28c4`, `dae0b4ea…` on branch with DEC-029 format note; `13-family-support-test-plan.md` → `023a37de…`). No performance or family-support claims. | **PASS** |

---

### 1.1 Independent SHA256 verification of all bundle files and external inputs (at `664bd40`)

All 15 entries in `workflow/evidence/HO-STRATA-010/hashes.txt` pass `sha256sum -c` from the repository root (and `hashes.txt` itself is the 16th file in `workflow/evidence/HO-STRATA-010/`):

| File | SHA256 | Verification |
|---|---|---|
| `workflow/evidence/HO-STRATA-010/artifacts/oracle_harness.cpp` | `bdc9303d6d884452175e199fff3a894836409543ef6f5f390a4e7eb9ab9b8f33` | In `hashes.txt` (`OK`) & `manifest.md` §3 |
| `workflow/evidence/HO-STRATA-010/artifacts/tokenize_compare.py` | `9903bc16ad8f7277631f6a209654c8903fa2d5295fc5aafd5e551c536c03e43c` | In `hashes.txt` (`OK`) & `manifest.md` §3 |
| `workflow/evidence/HO-STRATA-010/artifacts/check_layers.py` | `65eca3bd7917805432e90ca782ad1d92dcfad9e211b9f291505e41f9957c3cfa` | In `hashes.txt` (`OK`) & `manifest.md` §3 |
| `workflow/evidence/HO-STRATA-010/artifacts/pack_hashes.txt` | `eee7093bb547b860e88b63d9e0d20d8fcec37beadec01a71112d6825a7568378` | In `hashes.txt` (`OK`) & `manifest.md` §3 |
| `workflow/evidence/HO-STRATA-010/artifacts/tokenizer_parity_table.md` | `8512eb971c4b029f38e9c934ecfb5a9cf53fffd102c79f93b613681d0b9d7270` | In `hashes.txt` (`OK`) & `manifest.md` §3 |
| `workflow/evidence/HO-STRATA-010/artifacts/runs/deepseek_p1_4_layers.bin` | `db6eccb3e8a949827c5c961fc732159daa1a0a9d52f7f88156d669845e0c7c73` | In `hashes.txt` (`OK`) & `manifest.md` §3 |
| `workflow/evidence/HO-STRATA-010/artifacts/runs/deepseek_p1_logits.bin` | `5334baef84380f6060f8b1c4afda5fd45d367e9065ecdf2c6e4ea0642153fb2e` | In `hashes.txt` (`OK`) & `manifest.md` §3 |
| `workflow/evidence/HO-STRATA-010/artifacts/runs/run1.txt` | `b61da3fa0e50f8c0dac24dae61691877703265027509c26c526e04db08b8a9a4` | In `hashes.txt` (`OK`) & `manifest.md` §3 |
| `workflow/evidence/HO-STRATA-010/artifacts/runs/run2.txt` | `f1d6ade0cf5ffd4648d40126579a5202d4fa1b9b5dbf73c3813ad8bb0c6c2859` | In `hashes.txt` (`OK`) & `manifest.md` §3 |
| `workflow/evidence/HO-STRATA-010/artifacts/runs/run1.norm.txt` | `88de45824c276d1ac4ecb3572e3ba6dd42a4130bb137522c3e64dcff780ead2a` | In `hashes.txt` (`OK`) & `manifest.md` §3 |
| `workflow/evidence/HO-STRATA-010/artifacts/runs/run2.norm.txt` | `88de45824c276d1ac4ecb3572e3ba6dd42a4130bb137522c3e64dcff780ead2a` | In `hashes.txt` (`OK`) & `manifest.md` §3 |
| `workflow/evidence/HO-STRATA-010/commands.log` | `5027e17e629c0eb93bb1b120018e46020b09d5880d621e2db3fa013580e890cb` | In `hashes.txt` (`OK`) & `manifest.md` §3 |
| `workflow/evidence/HO-STRATA-010/test-output.txt` | `b4517ef5ddf7a315b0b74c4ddc7ca396f3fd21dea7a7a75a9244be949810e583` | In `hashes.txt` (`OK`) & `manifest.md` §3 |
| `workflow/evidence/HO-STRATA-010/manifest.md` | `e597c01fa7237ce9e6764bb1f60af7e9f3cd0d9e7c613a3ebfba2b5fd3d9bfd8` | In `hashes.txt` (`OK`) |
| `workflow/evidence/HO-STRATA-010/hashes-notes.txt` | `338d537c82b922926f18153a08e4c123d0e4b8e26593e6061e28a08b7edc5403` | In `hashes.txt` (`OK`) & `manifest.md` §3 |
| `workflow/evidence/HO-STRATA-010/hashes.txt` (16th bundle file) | `4f1f045ba7b432b8fb0ed91fb3d3c8992bd4e3ca7494beeac2efc48f2c41c535` | Self-consistent (`15/15 OK`) |
| `workflow/MODELS.md` pinned at `8ce28c4` (and working tree w/ DEC-029 note) | `1883c62b5052e36316fc31f48ccfb4b3912ef0d14540170475c4c79071f6e10b` (`8ce28c4`) / `dae0b4ea06b41c67d63c9b5ccb4d13ce5508df46c35f7b6ac39b65842cb44627` (`HEAD`) | Pinned in `hashes-notes.txt` (`OK`) |
| `planning/strata-engine/13-family-support-test-plan.md` pinned at `8ce28c4` | `023a37de06e785f96f94890fc16cec9279ca000513c1d2eedb6d779f28450bec` | Pinned in `hashes-notes.txt` (`OK`) |
| DeepSeek GGUF (`deepseek-moe-16b-base-q4_k_m.gguf`) | `f00ecd83d2fc4f28d1d5531c9583ed9c07452263c84590167bbe014f65c330f5` | In `pack_hashes.txt` (`OK`) & `manifest.md` §3 |
| Mixtral GGUF (`mixtral-8x7b-v0.1.Q3_K_M.gguf`) | `542d24532f63219db9f530bd2819be9c74f514919ab661dc5162cef844bac38b` | In `pack_hashes.txt` (`OK`) |

---

## 2. Diff and guard-rail review

- [x] **Diff is within scope; no unrelated files.** `git diff 8ce28c4..664bd40 --name-status` touches 24 workflow files (`workflow/evidence/HO-STRATA-010/*`, handoffs, reports, `workflow/DECISIONS.md`, `workflow/MODELS.md`, `workflow/STATUS.md`). Rework commit `664bd40` touches only the 8 allowed evidence files under `workflow/evidence/HO-STRATA-010/` plus `workflow/handoffs/HO-STRATA-010.md` (base commit + log entry).
- [x] **No Strata engine changes.** `git -C /home/kupipi/Documents/git/strata status --porcelain` is empty, `HEAD` is `baf16363b4403ef0ed4f538f5d5ed11c43fb9535`, and `/home/kupipi/Documents/git/strata/build-hip/strata` has SHA256 `d58ee2398596d1a100c15d5b9459e24bd86854cb5e5fb7ce88dbc6c7ed9f5858`.
- [x] **No new dependencies without approval.** `llama.cpp` remains at tag `b12527` (`78e05298f0d68abff41d08d79fa7469264b2aff0`) in `/tmp/opencode/llama.cpp`. No model downloads or conversions were performed.
- [x] **No secrets/tokens in the diff, logs, or evidence.** Verified by regex scan across the bundle and handoffs.
- [x] **Tests are meaningful; no skips hidden as passes.** Mixtral's legacy per-expert tensor layout refusal in `llama.cpp` `b12527` is explicitly deferred via `DEC-029`.
- [x] **Evidence matches the commands that were run.** Rebuilding `oracle_harness.cpp` and re-running tokenizer parity, layer dump, and two 16-step generation runs reproduced identical SHA256 hashes for the binary (`40cf635f…`), the parity table (`8512eb97…`), the layer dump (`db6eccb3…`), the logits dump (`5334baef…`), and the normalized `gen:` output (`88de4582…`).

---

## 3. Findings (severity order)

No Blocker or Major findings remain. All five initial QAQC minor findings (`M1`–`M5` / `C1`–`C5`) and all coder-assigned `RW-HO-STRATA-010-1` items (`F1`/`A-1`, `F2`/`A-2`, `A-4`…`A-9`, and `8ce28c4` pins) are **CLOSED**. One non-blocking cosmetic observation (`R1`) is noted for completeness:

| # | Severity | Finding | File:line / evidence | Required action |
|---|---|---|---|---|
| R1 | Minor (cosmetic) | In `test-output.txt:27-35`, the header (`2,3c2,3`), the `wall_s` lines (`0.686` vs `0.678`), the filenames (`deepseek_p1_logits.bin` vs `deepseek_p1_logits_run2.bin`), and the exit code (`stdout_diff_exit=1`) all accurately reflect `diff run1.txt run2.txt`, but lines `30` and `34` retain the unchanged 4th line (`logits layout: [step][rank][(token_id_f32, logit_f32)]  ranks: top-1, top-2`) inside the `2,3c2,3` hunk from the earlier `2,4c2,4` transcript edit. | `workflow/evidence/HO-STRATA-010/test-output.txt:27-35` | None (non-blocking; `stdout_diff_exit=1` and the reason on line 36 are accurate, and the reproducibility gate of record is the normalized `gen:` comparison at lines 41–45 with `normalized_diff_exit=0`). |

---

## 4. Verdict and next state

- **PASS** → `AUDIT_REVIEW`; attach this refreshed report (`workflow/reports/qaqc/HO-STRATA-010-qaqc.md`) and the evidence path (`workflow/evidence/HO-STRATA-010/`). The auditor should now re-audit commit `664bd40`.

### `QAQC_TO_AUDITOR` handoff record (per DEC-018)

Per the QAQC write boundary (`workflow/ENGINEERING_WORKFLOW.md` §4 and `DEC-018`), the refreshed `QAQC_TO_AUDITOR` handoff record for commit `664bd40` is embedded below:

```markdown
# HO-STRATA-010-AUDIT — S0 reference oracle and parity harness: Audit re-review (post-RW-HO-STRATA-010-1)

| Field | Value |
|---|---|
| **ID** | HO-STRATA-010-AUDIT |
| **Type** | QAQC_TO_AUDITOR |
| **State** | AUDIT_REVIEW |
| **Created / updated (UTC)** | 2026-11-18 / 2026-11-19 |
| **From → To** | QAQC (`qaqc`, `opencode-go/gemini-4-argon`) → Auditor (`auditor`, `opencode-go/deepseek-v4.1-flash`) |
| **Work package** | `strata-010-reference-oracle` |
| **Branch / base commit** | `wp/strata-010-reference-oracle` at `664bd408ed011a7041f43a81c02c237f71290866` (`664bd40`), rebased onto `main` `8ce28c4e2e33904b824d8541d69f1ea770548424` (`8ce28c4`) |
| **Priority / timebox** | P1 · 1 working day |
| **Original handoff** | `workflow/handoffs/HO-STRATA-010.md` |
| **Coder→QAQC handoff** | `workflow/handoffs/HO-STRATA-010-QAQC.md` |
| **Rework handoff** | `workflow/handoffs/RW-HO-STRATA-010-1.md` |
| **QAQC report** | `workflow/reports/qaqc/HO-STRATA-010-qaqc.md` |
| **Evidence path** | `workflow/evidence/HO-STRATA-010/` |

## 1. Scope (in)

- Re-audit the S0 reference oracle evidence bundle (`workflow/evidence/HO-STRATA-010/`) at commit `664bd40` and this refreshed QAQC report (`workflow/reports/qaqc/HO-STRATA-010-qaqc.md`) against `workflow/handoffs/HO-STRATA-010.md` and `workflow/handoffs/RW-HO-STRATA-010-1.md`.
- Verify closure of `F1`/`A-1`, `F2`/`A-2`, `F3`/`A-3`, minor findings `A-4`…`A-9`, `C1`–`C5`, and the `8ce28c4` commit pins.
- Update `workflow/reports/audit/HO-STRATA-010-audit.md` and transition to `ARCHITECT_APPROVAL` (PASS) or `REWORK` (FAIL).

## 2. Out of scope

- Mixtral 8x7B reference outputs (deferred by DEC-029 until a stacked-format GGUF is fetched).
- Any changes to the `strata` checkout (`/home/kupipi/Documents/git/strata` at `baf16363b4403ef0ed4f538f5d5ed11c43fb9535`) or S1+ family implementation work.
- Choosing S4 layer tolerances or S5 KL bounds.
- Any performance or support claims.

## 3. Inputs

| Input | Path / hash | Status |
|---|---|---|
| Architect handoff | `workflow/handoffs/HO-STRATA-010.md` | CODER_DONE (base `8ce28c4`) |
| Rework handoff | `workflow/handoffs/RW-HO-STRATA-010-1.md` | closed at `664bd40` |
| QAQC report | `workflow/reports/qaqc/HO-STRATA-010-qaqc.md` | PASS → `AUDIT_REVIEW` (re-pass on `664bd40`) |
| Evidence bundle | `workflow/evidence/HO-STRATA-010/` | verified (15/15 `hashes.txt` `OK`, 16 bundle files total) |
| Harness source | `workflow/evidence/HO-STRATA-010/artifacts/oracle_harness.cpp` (`bdc9303d6d884452175e199fff3a894836409543ef6f5f390a4e7eb9ab9b8f33`) | rebuilt (`40cf635f…`) & verified |
| Layer dump | `workflow/evidence/HO-STRATA-010/artifacts/runs/deepseek_p1_4_layers.bin` (`db6eccb3e8a949827c5c961fc732159daa1a0a9d52f7f88156d669845e0c7c73`) | reproduced bit-for-bit |
| Logits dump | `workflow/evidence/HO-STRATA-010/artifacts/runs/deepseek_p1_logits.bin` (`5334baef84380f6060f8b1c4afda5fd45d367e9065ecdf2c6e4ea0642153fb2e`) | reproduced bit-for-bit |
| Parity table | `workflow/evidence/HO-STRATA-010/artifacts/tokenizer_parity_table.md` (`8512eb971c4b029f38e9c934ecfb5a9cf53fffd102c79f93b613681d0b9d7270`) | reproduced byte-for-byte |
| DeepSeek model pack | `/home/kupipi/.cache/huggingface/hub/models--Lucy-in-the-Sky--deepseek-moe-16b-base-Q4_K_M-GGUF/snapshots/1f2b397cdb560ffb519aa8371d2f9eebae50d34d/deepseek-moe-16b-base-q4_k_m.gguf` (`f00ecd83d2fc4f28d1d5531c9583ed9c07452263c84590167bbe014f65c330f5`) | verified |

## 4. Acceptance criteria (for Audit re-review)

| # | Criterion | Check | Expected |
|---|---|---|---|
| 1 | Evidence integrity & pins | `sha256sum -c workflow/evidence/HO-STRATA-010/hashes.txt` and `hashes-notes.txt` commit pin check at `8ce28c4` | All 15 entries `OK`; pins at `8ce28c4` verified; no dead SHAs |
| 2 | Rework closure (F1, F2, F3, A-4…A-9) | Verify `tokenizer_parity_table.md` regeneration (`diff` exit `0`, 0 mismatch lines), `stdout_diff_exit=1` and `normalized_diff_exit=0`, normalization command in `commands.log` and `manifest.md` §1, and QAQC re-pass on `664bd40` | All closed and verified |
| 3 | Guard rails & scope | Check diff `8ce28c4..664bd40` and Strata checkout `baf16363` (`build-hip/strata` `d58ee239…`) | Only `HO-STRATA-010` workflow files touched; Strata clean; single CPU oracle profile; no perf/support claims |

## 5. Signatures

| Role | Name/agent | Date | Decision |
|---|---|---|---|
| Sender (QAQC) | `qaqc` (`opencode-go/gemini-4-argon`) | 2026-11-19 | PASS → `AUDIT_REVIEW` |
| Receiver (Auditor) | `auditor` | | |
```

---

## 5. Statement

I did not modify code, tests, docs, configuration, evidence, or handoffs. This report (`workflow/reports/qaqc/HO-STRATA-010-qaqc.md`) is the only artifact I wrote.
