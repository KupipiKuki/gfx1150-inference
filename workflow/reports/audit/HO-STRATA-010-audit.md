# Audit report — HO-STRATA-010

| Field | Value |
|---|---|
| **Handoff** | HO-STRATA-010 (`ARCHITECT_TO_CODER`, state `CODER_DONE`); reviewed via `CODER_TO_QAQC` `HO-STRATA-010-QAQC` and the embedded `QAQC_TO_AUDITOR` record (DEC-018) |
| **Reviewer** | Auditor (`auditor`), runtime model `opencode-go/deepseek-v4.1-flash` (family `deepseek`) — **WAIVED under WAIVER-001 / DEC-009**, not a clean independent-family PASS (see §2.5) |
| **Date (UTC)** | 2026-11-18 |
| **Verdict** | **FAIL → `REWORK`** (`RW-HO-STRATA-010-1`, §4): the oracle itself reproduces exactly, but two files in the evidence bundle state the opposite of what they show, and the QAQC PASS predates the bundle it is meant to cover |
| **Evidence reviewed** | `workflow/evidence/HO-STRATA-010/` at `02bc3c2` (`manifest.md`, `commands.log`, `test-output.txt`, `hashes.txt` 15 entries, `hashes-notes.txt`, `artifacts/` × 6 + `artifacts/runs/` × 7) |
| **QAQC report** | `workflow/reports/qaqc/HO-STRATA-010-qaqc.md` (QAQC `opencode-go/gemini-4-argon`, family `gemini`, PASS with M1–M5) — **stale: it reviews `e54a319`, not the audited `02bc3c2`** |
| **Scope reviewed** | Diff `36609255e28da370a35b3a687e9bc351c52981a0..02bc3c2` — 22 files (18 under `workflow/evidence/HO-STRATA-010/`, `HO-STRATA-010.md`, `HO-STRATA-010-QAQC.md`, `workflow/MODELS.md`, `workflow/DECISIONS.md`, `workflow/STATUS.md`, the QAQC report); pinned Strata checkout `/home/kupipi/Documents/git/strata` read-only |
| **Profile (one only)** | CPU-only oracle (`n_gpu_layers=0`), llama.cpp tag `b12527` / commit `78e05298f0d68abff41d08d79fa7469264b2aff0`, GCC `13.3.0-6ubuntu2~24.04.1`, Ubuntu 24.04, `Linux 7.0.0-42-generic x86_64` · model `DeepSeek-MoE-16B-base` (GGUF `deepseek`, 28 blocks, hidden 2048, 64 experts top-6, vocab 102,400) · quant `Q4_K_M` (`f00ecd83…`) · workload: 3-prompt raw-text tokenizer parity, 4-token per-layer dump (`--tokens 549,6077,280,7239 --n 0`), 5-token 16-step greedy decode + top-2 logits (`--tokens 549,6077,280,7239,317 --n 16`, `n_ctx=4096`) |

---

## 1. Evidence verification

- [x] **Manifest complete; commands reproducible.** `manifest.md` §1/§4 records the llama.cpp clone/checkout/CMake recipe, the harness build, and the four run commands with CWD and exit codes. I rebuilt the harness and re-ran every acceptance command from the committed sources (§1.1) — all reproduced bit-for-bit. Two command-table rows carry a repo-root CWD with a bundle-relative path that does not exist from there (A-5).
- [ ] **Outputs raw; failures/skips kept verbatim.** Raw transcript is preserved (Mixtral refusal, wall times, full diff bodies). **Two statements in the raw record are false** (A-1, A-2): a parity artifact still carries the pre-fix decode-mismatch line, and `test-output.txt` records `stdout_diff_exit=0` for a `diff` that exits `1`.
- [x] **Artifacts/hashes match the manifest.** `sha256sum -c hashes.txt` → **15/15 `OK`**, exit `0`. Every digest in `manifest.md` §3 equals both `hashes.txt` and the file on disk. The commit-pinned input resolves: `git show 068e8fef:workflow/MODELS.md` → `dae0b4ea06b41c67d63c9b5ccb4d13ce5508df46c35f7b6ac39b65842cb44627`, equal to today's `workflow/MODELS.md`. Hashing is self-consistent; the defect is *what* one hashed file still says (A-1).
- [x] **Environment recorded.** OS, kernel, compiler, Python, CPU-only flag, `CMAKE_BUILD_TYPE=Release`, `BUILD_SHARED_LIBS=ON`, `LLAMA_CURL=OFF`, `LLAMA_BUILD_{TESTS,EXAMPLES,SERVER}=OFF`, and the four shared-library digests are present and independently matched (§1.1). `GGML_NATIVE` (CMake default `ON`), the host CPU model, `cmake`/`ld` versions and the `-j` width are not recorded, so the *recipe* is complete but the *hashes* are host-scoped (A-7).
- [x] **No secrets.** Pattern scan (`ghp_*`, `github_pat_*`, `hf_*`, `sk-*`, `api_key`, `password`, `token=`) over the whole bundle: zero matches. No weights in git — largest committed file is the layer dump, 917,504 B.

### 1.1 Independent re-run (this audit)

Working dir `/home/kupipi/Documents/git/gfx1150-inference`; `G` = `/home/kupipi/.cache/huggingface/hub/models--Lucy-in-the-Sky--deepseek-moe-16b-base-Q4_K_M-GGUF/snapshots/1f2b397cdb560ffb519aa8371d2f9eebae50d34d/deepseek-moe-16b-base-q4_k_m.gguf`; outputs under `/tmp/opencode/audit-010/`.

```text
$ git -C /tmp/opencode/llama.cpp rev-parse HEAD        -> 78e05298f0d68abff41d08d79fa7469264b2aff0
$ git -C /tmp/opencode/llama.cpp describe --tags --exact-match -> b12527
$ git -C /tmp/opencode/llama.cpp status --porcelain    -> (empty)
$ sha256sum build/bin/lib{llama,ggml,ggml-base,ggml-cpu}.so.1
  2397a75f…  libllama.so.1        (= manifest §4)
  8f923882…  libggml.so.1         (= manifest §4)
  2cc34f6f…  libggml-base.so.1    (= manifest §4)
  fcc9fa13…  libggml-cpu.so.1     (= manifest §4)

$ g++ -O2 -std=c++17 workflow/evidence/HO-STRATA-010/artifacts/oracle_harness.cpp \
    -o /tmp/opencode/audit-010/oracle_harness -I/tmp/opencode/llama.cpp/include \
    -I/tmp/opencode/llama.cpp/ggml/include -L/tmp/opencode/llama.cpp/build/bin \
    -lllama -lggml -lggml-base -lggml-cpu -lpthread
  exit 0; 5 deprecation warnings (llama_batch_init/llama_decode/llama_batch_free)
  40cf635f0dc36a26202f9145af786423c200633c4b9bd1986be42f7159f68506  /tmp/opencode/audit-010/oracle_harness
  40cf635f…  also == /tmp/opencode/oracle_harness (the binary the coder left on disk)

$ LD_LIBRARY_PATH=/tmp/opencode/llama.cpp/build/bin /tmp/opencode/audit-010/oracle_harness \
    --model "$G" --tokens 549,6077,280,7239,317 --n 16 --dump-logits /tmp/opencode/audit-010/logits_run1.bin
gen: 8913 13 185 40619 317 254 6077 280 7239 13 185 40619 317 254 6077 280
wall_s: 0.697
logits shape: [16][2][2]  … logits layout: [step][rank][(token_id_f32, logit_f32)]  ranks: top-1, top-2
… same command again (run2, wall_s 0.703) -> identical gen line
5334baef84380f6060f8b1c4afda5fd45d367e9065ecdf2c6e4ea0642153fb2e  logits_run1.bin
5334baef…  logits_run2.bin
5334baef…  workflow/evidence/HO-STRATA-010/artifacts/runs/deepseek_p1_logits.bin   <-- bit-identical

$ LD_LIBRARY_PATH=… /tmp/opencode/audit-010/oracle_harness \
    --model "$G" --tokens 549,6077,280,7239 --n 0 --dump-layers /tmp/opencode/audit-010/layers.bin
layers shape: [4][28][2048]  exit 0
db6eccb3e8a949827c5c961fc732159daa1a0a9d52f7f88156d669845e0c7c73  layers.bin
db6eccb3…  also == workflow/evidence/HO-STRATA-010/artifacts/runs/deepseek_p1_4_layers.bin

$ python3 workflow/evidence/HO-STRATA-010/artifacts/check_layers.py /tmp/opencode/audit-010/layers.bin
shape: (4, 28, 2048)
non-zero rows per position: [(0, 28), (1, 28), (2, 28), (3, 28)]
L0 vs L1 L2 norm (last pos): 3.566159
L0 vs L1 dot (last pos): 43.325943
any nan/inf: False

$ python3 workflow/evidence/HO-STRATA-010/artifacts/tokenize_compare.py --gguf "$G" \
    --harness /tmp/opencode/audit-010/oracle_harness
P1 'The capital of France is'      -> [549, 6077, 280, 7239, 317]                    match=True
P2 'def add(a, b):\n    return'    -> [1558, 962, 7, 64, 11, 270, 1780, 185, 300, 972] match=True
P3 'Three primary colors are'      -> [21477, 6663, 8247, 418]                        match=True
stderr: (empty — no decode mismatch)
```

Independent content checks (not just hashes):

```text
layers.bin: 0 zero rows out of 112 (4 pos × 28 layers); all finite;
  consecutive-layer L2 differences 1.9642 … 759.1475 (every layer distinct);
  pos0..2 layer27 ||·|| = 345.84 / 153.50 / 214.60, pos3 = 172.65
deepseek_p1_logits.bin: 64 float32 = 16×2×2; top-1 id column == the 16 gen ids;
  rank-1 logit > rank-2 logit at every step
```

### 1.2 Closures C1–C5 (the evidence changed after the QAQC PASS)

| # | Closure | Status | Independent evidence |
|---|---|---|---|
| **C1 / M2** | Layer dump populated for all 28 layers at all 4 positions; hash `db6eccb3…`; generation unchanged | **CLOSED** | My rebuild reproduces `db6eccb3…` exactly; `[(0,28),(1,28),(2,28),(3,28)]`; **0** all-zero rows of 112. Diff against the pre-fix dump (`e54a319:…deepseek_p1_4_layers.bin`): layers 0–26 are **bit-identical at all 4 positions** (max abs diff `0.0`), only `l_out-27` gained its pos 0–2 rows ⇒ the fix is additive, no regression. Generation path unchanged: with `--dump-logits` only, `collect_layers` is false, so `batch.logits[]` is exactly the old last-token-only pattern, and the logits dump is bit-identical to the pre-fix hash `5334baef…`. |
| **C2 / M3** | Shape label `[16][2][2]` with layout documented; file actually 16×2×2 floats | **CLOSED** | `oracle_harness.cpp:350-351` prints `logits shape: [16][2][2]` + `logits layout: [step][rank][(token_id_f32, logit_f32)]`; `manifest.md:37` and `test-output.txt:17-18,24-25` repeat it; file is 256 B = 64 float32 = 16×2×2, values are real `(id, logit)` pairs. |
| **C3 / M4** | `workflow/MODELS.md` out of `hashes.txt`; four `runs/*` helper files hashed | **CLOSED** | 15 digest lines, no `workflow/MODELS.md`; `run1.txt`, `run2.txt`, `run1.norm.txt`, `run2.norm.txt` all listed and `OK`; commit pin `068e8fef:workflow/MODELS.md` → `dae0b4ea…` verified, and the pin equals today's file. |
| **C4 / M1** | P2 parity compares the full multi-line decode, no false mismatch | **PARTIAL — script fixed, artifact of record stale** | The fixed `tokenize_compare.py` (`9903bc16…`) parses everything after `decode: ` and my run emits **no** mismatch on stderr. But the committed `artifacts/tokenizer_parity_table.md` still begins with `  harness decode mismatch: 'def add(a, b):'`, and re-running the recorded command produces a file without that line (`diff` = `0a1`, exit `1`). The file was last touched in `d5d4800`, i.e. it was **not regenerated** in the closure commit. → A-1. |
| **C5 / M5** | `commands.log` contains clone / checkout / CMake | **CLOSED** | `commands.log:5-12`: `git clone …`, `git -C … checkout 78e05298…`, `cmake -S … -B …`, `cmake --build … -j`, `# exit 0`. |

---

## 2. Claim and scope audit

- [ ] **Every claim cites a command and an output.** All substantive claims do (gen line, dumps, parity, provenance, no-engine-change). **Two do not hold against their own artifact**: `manifest.md:34` (AC-3 "P2 multi-line decode now parsed in full") points at a table that still shows the mismatch (A-1), and `test-output.txt:37` claims a clean diff exit for a diff that differs (A-2).
- [x] **One profile per claim.** CPU-only, `DeepSeek-MoE-16B-base` `Q4_K_M`, 3-prompt parity + 4-token dump + 16-step decode, `n_ctx=4096`. No Mixtral data, no Strata run, no 780M/MI25/gfx1100, no cross-profile transfer. `Q8_0`/Mixtral Q4_K_M never touched (only Q3_K_M was attempted and refused).
- [x] **Scope matches the handoff; no silent expansion.** 22 files, all HO-010 workflow artifacts + the DEC-029 `MODELS.md` format note the decision authorises. No engine code, no CMake, no family enum, no S1+ work. Mixtral narrowing is recorded in DEC-029 and `HO-STRATA-010.md` §2.5.
- [x] **Guard rails respected.** Strata checkout clean, `HEAD baf16363b4403ef0ed4f538f5d5ed11c43fb9535`, and `build-hip/strata` still `d58ee2398596d1a100c15d5b9459e24bd86854cb5e5fb7ce88dbc6c7ed9f5858` — **not rebuilt**. No model download or conversion: the DeepSeek pack (`f00ecd83…`) predates the work and matches `MODELS.md`; the Mixtral pack hash matches `pack_hashes.txt`. No prompt tuning. No secrets. llama.cpp lives in `/tmp`, not in git.
- [x] **No perf/support claim.** `faster|speedup|outperform|tok/s|supported|SOTA|production|benchmark` — zero hits in the bundle. `wall_s` values (0.675 / 0.667 recorded, 0.697 / 0.703 here) are labelled observations. No tolerance or KL bound is chosen; the only `tolerance|KL` hit is the handoff's out-of-scope line.
- [ ] **Rework history is closed or named.** None open; this audit opens `RW-HO-STRATA-010-1` for A-1/A-2.

### 2.1 BOS / tokenizer convention (both sides)

- GGUF metadata (parsed independently): `tokenizer.ggml.add_bos_token=True`, `bos_token_id=100000`, `add_eos_token=False`, `pre='deepseek-llm'`, `model='gpt2'`.
- Harness: `oracle_harness.cpp:197-198` `llama_tokenize(..., add_special=false, parse_special=true)` → **no BOS**.
- Engine: `strata_tokenizer.py:341-349` `Tokenizer.encode()` returns the BPE ids directly and never prepends BOS (`extract()` even writes `"add_bos_token": False`).
- Empirical: no id list on either side contains `100000`; all three prompts match.
⇒ **Consistent: no BOS on either side.** The convention is only *implicit* in the bundle (source line + absent 100000) and the harness runs `parse_special=true` while the engine default is `False` — harmless for three plain prompts, but it must be written down for S1+ (A-8).

### 2.5 Process and model separation

- **Coder vs QAQC: satisfied.** `coder-primary` `opencode-go/kimi-k2.7-code` (kimi) vs `qaqc` `opencode-go/gemini-4-argon` (gemini) — different base families.
- **Auditor: WAIVED, not PASS.** I am `opencode-go/deepseek-v4.1-flash`, the architect's family (`deepseek-v4-pro#max`). `python3 workflow/check_model_policy.py --strict` → `RESULT: WAIVED — WAIVER-001 in force`. This verdict is a **WAIVED audit**; do not read it as clean independent-family review.
- **QAQC gate staleness (A-3).** `workflow/reports/qaqc/HO-STRATA-010-qaqc.md` was committed at `fd26ff4` against `e54a319`; the audited bundle is `02bc3c2`, which changed `oracle_harness.cpp`, `tokenize_compare.py`, the layer dump, `run1/2.txt`, `commands.log`, `hashes.txt`, `manifest.md` and `test-output.txt`. `HO-STRATA-010-QAQC.md:126` says "ready for QAQC re-review" — that re-review never happened. So the independent-review gate does not cover the evidence under audit.
- **State chain:** `READY` (`9d8660d`) → `IN_PROGRESS` → `CODER_DONE` → `QAQC_REVIEW` → `AUDIT_REVIEW` (`fd26ff4`, report only) → closures at `02bc3c2` with no state change. Bookkeeping is stale in two places (A-12): `STATUS.md:17` still `CODER_DONE` @ `068e8fe`, and `HO-STRATA-010-QAQC.md:7` still `PROPOSED`.

---

## 3. Findings / rework

### 3.1 QAQC M1–M5 — dispositions

| QAQC | Severity | My disposition |
|---|---|---|
| **M1** decode truncation in `tokenize_compare.py` | Minor | **Script closed; artifact NOT closed.** The parse fix is correct and verified. The committed parity table was never regenerated and still prints the false mismatch it was supposed to remove → raised to **Major** as A-1 (it is the AC-3 artifact of record and the recorded command no longer reproduces it). |
| **M2** `l_out-27` zero-padded at pos 0–2 | Minor | **Closed and verified.** 28/28 layers at all 4 positions, hash `db6eccb3…`, layers 0–26 bit-identical to the pre-fix dump, generation bit-identical. |
| **M3** `[16][2]` vs `[16][2][2]` label | Minor | **Closed and verified** (label + layout line + real 16×2×2 payload). |
| **M4** `MODELS.md` in `hashes.txt`, helper files unhashed | Minor | **Closed and verified** (15 entries, pin resolves to `dae0b4ea…`). |
| **M5** `commands.log` missing clone/build | Minor | **Closed and verified** (`commands.log:5-12`). |

### 3.2 New findings from this audit

| # | Severity | Finding | Required action | Owner |
|---|---|---|---|---|
| **A-1** | **Major** (evidence) | `artifacts/tokenizer_parity_table.md:1` still reads `  harness decode mismatch: 'def add(a, b):'`. The fixed script no longer emits it, `test-output.txt:2-6` does not contain it, and re-running the recorded command produces a file without it (`diff` → `0a1`, exit `1`). The file was last changed in `d5d4800` (pre-fix) and was **not regenerated** in `02bc3c2`. Consequence: `manifest.md:34` (AC-3) and the C4 closure are contradicted by the artifact they cite, and the recorded command does not reproduce the committed artifact. | Regenerate the table with the fixed script (`commands.log` step 2), confirm no mismatch line, update `hashes.txt` and `manifest.md` §3 with the new digest. | Coder |
| **A-2** | **Major** (evidence) | `test-output.txt:37` records `stdout_diff_exit=0`, but the transcript at lines 29–36 shows a non-empty `diff` (wall_s + output filename) and `diff run1.txt run2.txt` exits **1** (verified). The reproducibility result is actually carried by the normalized comparison (`normalized_diff_exit=0`), whose *generating command is not recorded anywhere* (A-4). A false exit code in a raw transcript is exactly what the evidence contract forbids, and QAQC repeated the claim ("`diff` exit `0`", QAQC report §1 row 2) instead of catching it. | Record the real exit (`1`) with the reason, or replace the gate with the normalized comparison and record its command. Do not present a non-empty diff as exit 0. | Coder |
| **A-3** | **Major** (process) | The QAQC PASS covers `e54a319`; C1–C5 landed in `02bc3c2` with no QAQC re-review, although `HO-STRATA-010-QAQC.md:126` declares it "ready for QAQC re-review". The independent-review gate therefore does not cover the audited bundle (and indeed two of the three majors above are in files QAQC never saw). | After the rework commit, QAQC re-runs AC-1…9 + C1–C5 against the new commit, re-hashes the bundle and refreshes the report fingerprint (commit + `hashes.txt` count/digests). The auditor then re-audits. | QAQC (after coder fix) |
| **A-4** | Minor (reproducibility) | `artifacts/runs/run1.norm.txt` / `run2.norm.txt` are hashed and are the basis of the reproducibility claim, but no command that produces them appears in `commands.log` or `manifest.md`. | Add the normalization command and its output to `commands.log`. | Coder |
| **A-5** | Minor (reproducibility) | `manifest.md` §1 rows 3, 4, 7 give CWD "repo root" with paths like `artifacts/runs/deepseek_p1_4_layers.bin`; from the repo root the file is at `workflow/evidence/HO-STRATA-010/artifacts/runs/…`. `commands.log` has the correct paths, so the manifest table is not copy-paste runnable as written. | Use the full bundle-relative path (or set CWD to the bundle) in the manifest table. | Coder |
| **A-6** | Minor (record) | `manifest.md:6` says "Commit / branch `836b475…`" but the manifest itself was last changed in `02bc3c2`; a reader diffing HEAD would use the wrong evidence commit. | Record the evidence commit that contains the bundle (and keep the base commit separately). | Coder |
| **A-7** | Minor (provenance) | The llama.cpp pin is recorded well enough to **rebuild** (tag, commit, clone URL, exact CMake flags, GCC 13.3.0, four lib digests, commands 0a–0c) but the library **hashes** are host-scoped: `GGML_NATIVE=ON` (CMake default, verified in `CMakeCache.txt`) means `-march=native`, and the host CPU model, `cmake`/`ld` versions and `-j` width are not recorded. On a different host the recipe reproduces, the digests will not. The pin also lives in `/tmp`. | Add `GGML_NATIVE=ON`, `cmake --version`, the host CPU model and `nproc` to `manifest.md` §4, and state explicitly that the lib digests are this-host only. | Coder |
| **A-8** | Minor (documentation) | BOS convention is consistent but implicit: `add_special=false` appears only as a positional argument at `oracle_harness.cpp:198`; the harness uses `parse_special=true` while `Tokenizer.encode()` defaults `parse_special=False`. No id list contains `100000` on either side. | State the exact tokenize flags on both sides in `manifest.md`, and align `parse_special` for S1+. | Coder (S1+ owner) |
| **A-9** | Observation (S4 input) | The C1 fix changes the last block's GEMM from `M=1` to `M=4`, so `l_out-27` at pos 3 moved by ≤ `3.81e-6` absolute (relative L2 `8.07e-8`, 699/2048 values bit-equal) versus the pre-fix dump; layers 0–26 and the generation logits are bit-identical. S4 must not assume last-layer bit-identity across the two decode shapes. | Record the note in `manifest.md` so S4 sets its layer tolerance from the right baseline. | Coder (one line) |
| **A-10** | Minor (traceability) | `DEC-024` is cited by `HO-STRATA-010.md:92`, `manifest.md:84`, `hashes-notes.txt:1` and the QAQC report as the authority for the commit-pin convention, but **no DEC-024 exists** in `workflow/DECISIONS.md` (headings run …022, 023, 028, 029; DEC-027 is cited too and also absent). | Record the decision, or repoint the citation to the decision that actually authorises commit-pinning. | Architect |
| **A-11** | Minor (inputs) | `planning/strata-engine/13-family-support-test-plan.md`, the handoff's declared plan (§4 S0), does not exist in the repository (only `00`…`12` plus `README.md` are tracked), yet DoR marks "Inputs available". The coder recorded the absence honestly in `manifest.md:81` and `hashes-notes.txt:9`. | Commit the plan file or correct the handoff reference and DoR. | Architect |
| **A-12** | Minor (bookkeeping) | `STATUS.md:17` still reads `CODER_DONE` / `@ 068e8fe` / "QAQC independent review"; `HO-STRATA-010-QAQC.md:7` still reads `PROPOSED` with an unticked DoD. DEC-018 assigns the mirroring to the architect. | Mirror the state and the QAQC signature after the rework PASS. | Architect |
| **A-13** | Minor (portability) | `tokenize_compare.py:8,32` hardcodes `/home/kupipi/Documents/git/strata/tools` and `/tmp/opencode/llama.cpp/build/bin`, and passes `env={"LD_LIBRARY_PATH": …}`, which wipes `PATH`/`HOME`. It works here (the harness is invoked by absolute path) but is not reusable off this host. | Take both paths from arguments/env for S1+. | Coder (S1+) |

### 3.3 Counter-hypotheses tested

| Hypothesis | Test | Result |
|---|---|---|
| The layer dump was padded/zero-filled to look complete | Byte compare against the pre-fix dump from `e54a319`; per-row non-zero counts | **Falsified.** 0 of 112 rows are zero; layers 0–26 are bit-identical to the pre-fix file; only `l_out-27` pos 0–2 changed from zero to real values, and pos 3 differs only at `1e-7` relative (A-9). |
| The `gen:` line is cached/quoted rather than computed | Fresh rebuild from the committed `.cpp`, two fresh runs | **Falsified.** Both runs reproduce the 16 ids and the bit-identical logits file `5334baef…`; the binary I built is digest-identical to the one on disk. |
| The "closure" commit changed the reference numbers | Compare `5334baef…` (pre-fix, from QAQC §1 row 2) with today's logits dump | **No change.** Generation is untouched by the dump fix, as the `collect_layers` guard implies. |
| The parity table's mismatch line is a real decode failure | Re-run the fixed script and the harness on P2 | **Falsified** — full multi-line payload matches (`'def add(a, b):\n    return'`); the line is a stale pre-fix artifact (A-1). |
| The engine was rebuilt for this work | `sha256sum build-hip/strata` vs the `MODELS.md` engine pin | **Falsified.** `d58ee239…` = the signed HO-001 build; checkout clean at `baf16363`. |
| Mixtral was silently skipped | Read `manifest.md` §5 + DEC-029; the refusal is a tooling-format rejection | **Documented, not hidden** — legacy per-expert layout vs stacked `ffn_down_exps`, exact error recorded, decision by the architect. |

---

## 4. Verdict

- **FAIL → `REWORK`.** Create `workflow/handoffs/RW-HO-STRATA-010-1.md` (Auditor → `coder-primary`), reviewer for the re-check: **Auditor** (`auditor`), after a QAQC re-pass (A-3).
- **What is *not* in question:** the oracle is sound. I rebuilt it from the committed source and reproduced the `gen:` line, the logits dump (`5334baef…`), the layer dump (`db6eccb3…`, 28/28 × 4/4), the parity IDs and the provenance (5 independent checks). C1, C2, C3 and C5 are closed; the engine is untouched; no claim is inflated; no scope was added.
- **Why FAIL and not PASS-with-conditions:** three files in the bundle assert something their own content refutes — the AC-3 artifact still prints the mismatch the closure claims to have removed (A-1), the transcript records `exit 0` for a diff that differs (A-2), and the independent review never saw the commit under audit (A-3). The evidence contract is explicit ("outputs raw", "no claim without an artifact"); a one-commit fix plus one QAQC re-pass is cheaper than signing a bundle whose parity artifact contradicts its own handoff. Nothing here changes a token, a hash or a shape.
- Rework pass condition: A-1 and A-2 fixed, A-4…A-9 fixed or explicitly deferred by the architect in the rework acknowledgment, `sha256sum -c` clean, QAQC re-pass on the new commit, then a short auditor re-audit.
- **Not signed by the auditor.** The architect decides `DONE` and merges.

## 5. Owner-task oversight

- Owner task: `OT-STRATA-001` (S0 authorised 2026-11-18, DEC-028).
- Checkpoints met: **S0 — reference oracle + parity harness** is met at the *technical* level (oracle reproducible, tokenizer parity proven for DeepSeek P1/P2/P3, layer/logits dumps present, no engine change, Mixtral deferred by DEC-029). It is **not yet accepted**: the evidence bundle needs `RW-HO-STRATA-010-1`.
- Owner-facing statement that is supportable today: *on CPU with llama.cpp `b12527` pinned at `78e05298…`, the DeepSeek-MoE-16B Q4_K_M pack tokenizes the three fixed prompts identically to the engine's tokenizer (no BOS on either side), and generates the same 16 greedy tokens on every run, with per-layer and top-2 logits dumps that reproduce bit-for-bit. Mixtral's pack is refused by llama.cpp for its 2023 tensor layout (DEC-029); no engine code changed and no support or speed claim is made.*
- Owner acceptance: **pending** — recorded in `OT-STRATA-001` only after the rework, the QAQC re-pass and the architect's signature.

## 6. Statement

I did not modify code, tests, docs, configuration, evidence, handoffs, or the Strata checkout. My only writes were this report and `workflow/handoffs/RW-HO-STRATA-010-1.md`; all executions used `/tmp/opencode/audit-010/` as a scratch directory (harness build, two generation runs, one layer dump, one parity run) and the pinned trees read-only (`git`/`sha256sum`/`diff` on `/tmp/opencode/llama.cpp`, `/home/kupipi/Documents/git/strata`, `workflow/evidence/HO-STRATA-010/`). Model separation is **WAIVED** under WAIVER-001 (auditor and architect share the `deepseek` family); this is not a clean independent-family audit.

---

## 7. Re-audit (0369ec8) — after `RW-HO-STRATA-010-1`

| Field | Value |
|---|---|
| **Handoff** | HO-STRATA-010 (`ARCHITECT_TO_CODER`), state `CODER_DONE`; rework `RW-HO-STRATA-010-1` |
| **Reviewer** | Auditor (`auditor`), runtime `opencode-go/deepseek-v4.1-flash` (family `deepseek`) — **WAIVED under WAIVER-001 / DEC-009**, as in §2.5 |
| **Date (UTC)** | 2026-11-19 |
| **Audited commit** | `0369ec87d9e84e664356a3423f3744541054e321` (`0369ec8`, tip of `wp/strata-010-reference-oracle`), rebased onto `main` `8ce28c4e2e33904b824d8541d69f1ea770548424`; rework commit `664bd408ed011a7041f43a81c02c237f71290866` (`664bd40`); working tree clean |
| **Verdict** | **PASS → `ARCHITECT_APPROVAL`** — A-1, A-2, A-3, A-10, A-11 closed; full acceptance set reproduced bit-for-bit at the audited tip; residual R1 is reclassified **Minor fidelity (not cosmetic)** and is non-blocking (below) |
| **Evidence reviewed** | `workflow/evidence/HO-STRATA-010/` at `0369ec8` — 16 tracked files, `hashes.txt` 15 entries, `hashes-notes.txt`, `artifacts/` (5 files + `runs/` 6 tracked + 1 git-ignored) |
| **QAQC report** | `workflow/reports/qaqc/HO-STRATA-010-qaqc.md` — re-pass section names `664bd40`, 15/15 hashes, both dump digests. **Not stale this time.** |
| **Scope reviewed** | `git diff 8ce28c4..0369ec8` — 24 files (16 evidence, 3 handoffs, 2 reports, `DECISIONS.md`, `MODELS.md`, `STATUS.md`); `git diff 664bd40..0369ec8` — 1 file (the QAQC report only) |

### 7.1 Disposition of the first verdict (A-1, A-2, A-3, A-10, A-11, A-4…A-9, A-12)

| # | Was | Re-verified independently (this audit) | Status |
|---|---|---|---|
| **A-1** | Major (evidence) | `head -2 artifacts/tokenizer_parity_table.md` → `\| prompt \| text \| …` + separator; `grep -c 'harness decode mismatch'` → `0`; digest `8512eb971c4b029f38e9c934ecfb5a9cf53fffd102c79f93b613681d0b9d7270` = `hashes.txt:7` = `manifest.md:52`. Ran `tokenize_compare.py --gguf <deepseek> --harness /tmp/opencode/audit-010b/oracle_harness` → exit `0`, **0 stderr lines**, `diff` against the committed table → **empty, exit `0`**. The table is now the artifact of record the command produces, and P2 compares the full `'def add(a, b):\n    return'` payload. | **CLOSED** |
| **A-2** | Major (evidence) | `grep -n` on `test-output.txt` → `35:stdout_diff_exit=1`, `45:normalized_diff_exit=0` (QAQC's line refs are correct). `diff run1.txt run2.txt` on the committed files → exit **1** with body `2,3c2,3` (`wall_s` `0.686`/`0.678` + filename). The normalization command is in `commands.log:61-63` and `manifest.md:23` (row `6c`); re-running it on the committed `run1/run2.txt` reproduces both `.norm` files byte-for-byte (`88de4582…`, `diff` exit `0`) and they agree (`normalized_diff_exit=0`). No false exit code remains. Residual **R1** → §7.3. | **CLOSED** (R1 recorded as B-1) |
| **A-3** | Major (process) | The QAQC report names `664bd408ed011a7041f43a81c02c237f71290866` in the header, the re-pass fingerprint, and the `QAQC_TO_AUDITOR` record; it states **15/15** `hashes.txt` entries and both dump digests (`db6eccb3…` layers, `5334baef…` logits), which I verified. `git diff 664bd40..0369ec8` is **the QAQC report and nothing else**, so the re-pass covers exactly the evidence under audit. The gate now covers the commit it claims to. | **CLOSED** |
| **A-10** | Minor (traceability) | `DEC-024` and `DEC-027` exist **in-tree at both `8ce28c4` and `0369ec8`**; `DEC-028`/`DEC-029` are added by this branch and present at `0369ec8`. Every citation resolves: `HO-STRATA-010.md:13,92,126`, `manifest.md:85`, `hashes-notes.txt:9`. No dead SHA is used as an evidence pin (§7.4 B-3 for two stale bookkeeping references). | **CLOSED** |
| **A-11** | Minor (inputs) | `planning/strata-engine/13-family-support-test-plan.md` is tracked at `8ce28c4` and at `0369ec8`; `git show 8ce28c4:…13… \| sha256sum` → `023a37de06e785f96f94890fc16cec9279ca000513c1d2eedb6d779f28450bec`, the digest QAQC reported and the file present now. §4/S0 of the plan is the handoff's declared source. | **CLOSED** |
| **A-4** | Minor (reproducibility) | Normalization command present in `commands.log:61-63`, `manifest.md` row `6c`, `test-output.txt:42-44`; reproduces the `.norm` files (§A-2). | **CLOSED** |
| **A-5** | Minor (reproducibility) | `manifest.md` §1 rows `2`–`7` are repo-root CWD with full `workflow/evidence/HO-STRATA-010/…` paths; I executed rows `1`, `2`, `3`, `4`, `5`, `6a`–`6c`, `7` from the repo root unmodified. | **CLOSED** |
| **A-6** | Minor (record) | `manifest.md:4` no longer names a stale commit; it points to the handoff log and the branch, with `base main 8ce28c4`. No circular self-hash, no wrong SHA. | **CLOSED** |
| **A-7** | Minor (provenance) | `manifest.md:6,70-79` records CMake `3.28.3`, `GGML_NATIVE=ON`, `AMD Ryzen AI 9 HX 370 w/ Radeon 890M`, `24 vCPUs`, and says the lib digests are host-scoped. Verified `cmake --version` → `3.28.3`, `nproc` → `24`, `/proc/cpuinfo` → the named CPU; all four `.so.1` digests equal §4. Caveat → B-2. | **CLOSED** |
| **A-8** | Minor (documentation) | `manifest.md:92-100` states the convention: harness `llama_tokenize(…, add_special=false, parse_special=true)` (`oracle_harness.cpp:197-198`, positional `false, true`) and engine `Tokenizer.encode()` with `add_bos_token=False`; no id list contains `100000`. I re-derived the engine ids directly from `strata_tokenizer.py` (not via the compare script): P1/P2/P3 exact, round-trip `True`, no BOS; GGUF metadata `add_bos_token=True`, `bos_token_id=100000`, `add_eos_token=False`. | **CLOSED** |
| **A-9** | Observation (S4 input) | `manifest.md:90` records the C1 last-block note. I recomputed it from `e54a319:…deepseek_p1_4_layers.bin` vs the committed dump: layers 0–26 max abs diff **0.0**; `l_out-27` pos 3 max abs **3.8147e-06**, rel L2 **8.0729e-08**, **699/2048** bit-equal; pre-fix dump has **3** all-zero rows (pos 0–2 of `l_out-27`), current has **0**. The note's numbers are exact. | **CLOSED** |
| **A-12** | Minor (bookkeeping) | **Not closed**, and not the coder's to close: `STATUS.md:19` still `@ 068e8fe` / "QAQC independent review"; `HO-STRATA-010-QAQC.md:7` still `PROPOSED`, base `3660925…`, DoD unticked (`:113`). Neither is an evidence pin. → B-3. | **OPEN → B-3 (architect, DEC-018)** |
| **A-13** | Minor (portability) | Unchanged by design: `tokenize_compare.py:8,32` still hardcodes `/home/kupipi/Documents/git/strata/tools` and `/tmp/opencode/llama.cpp/build/bin`, and passes `env={"LD_LIBRARY_PATH": …}` (wiping `PATH`/`HOME`). Works here, not portable. The first report assigned this to S1+, so it is not a gate for S0. | **OPEN — deferred to S1+ (coder)** |

### 7.2 Independent full re-run at `0369ec8`

Scratch `/tmp/opencode/audit-010b/`; `G` = the DeepSeek GGUF; every command below is from the bundle's `commands.log` / `manifest.md` §1, run from the repo root. Nothing was written inside the repo.

```text
$ git rev-parse HEAD                     -> 0369ec87d9e84e664356a3423f3744541054e321
$ git status --porcelain                 -> (empty)
$ git -C /tmp/opencode/llama.cpp rev-parse HEAD -> 78e05298f0d68abff41d08d79fa7469264b2aff0
$ git -C /tmp/opencode/llama.cpp describe --tags --exact-match -> b12527
$ sha256sum lib{llama,ggml,ggml-base,ggml-cpu}.so.1
  2397a75f… 8f923882… 437dd6b7… fcc9fa13…   (= manifest §4, all four)

$ g++ -O2 -std=c++17 …/oracle_harness.cpp -o /tmp/opencode/audit-010b/oracle_harness …
  exit 0 (5 deprecation warnings)
  40cf635f0dc36a26202f9145af786423c200633c4b9bd1986be42f7159f68506  oracle_harness
  40cf635f…  == the binary on disk                     (source bdc9303d… matches hashes.txt)

$ harness --tokens 549,6077,280,7239,317 --n 16 --dump-logits logits1.bin   (run 1)
$ harness … --dump-logits logits2.bin                                        (run 2, fresh process)
gen: 8913 13 185 40619 317 254 6077 280 7239 13 185 40619 317 254 6077 280   (both runs)
5334baef84380f6060f8b1c4afda5fd45d367e9065ecdf2c6e4ea0642153fb2e  logits1.bin
5334baef…  logits2.bin
5334baef…  workflow/evidence/HO-STRATA-010/artifacts/runs/deepseek_p1_logits.bin   <-- 3-way match
  content: 64 float32 = 16x2x2; top-1 ids == the 16 gen ids; rank-1 > rank-2 at every
  step (min margin 0.3555, max 3.8040)

$ harness --tokens 549,6077,280,7239 --n 0 --dump-layers layers.bin
layers shape: [4][28][2048]  exit 0
db6eccb3e8a949827c5c961fc732159daa1a0a9d52f7f88156d669845e0c7c73  layers.bin
db6eccb3…  == artifacts/runs/deepseek_p1_4_layers.bin
  content: 0 zero rows of 112; all finite; consecutive-layer L2 (pos 3) 3.47…117.77;
  pos3 layer27 ||.|| = 172.65

$ python3 …/check_layers.py layers.bin
shape: (4, 28, 2048)
non-zero rows per position: [(0, 28), (1, 28), (2, 28), (3, 28)]
L0 vs L1 L2 norm (last pos): 3.566159
L0 vs L1 dot (last pos): 43.325943
any nan/inf: False

$ python3 …/tokenize_compare.py --gguf "$G" --harness audit-010b/oracle_harness > parity.md 2> parity.err
  exit 0; stderr: 0 lines
  P1 [549,6077,280,7239,317]  P2 [1558,962,7,64,11,270,1780,185,300,972]  P3 [21477,6663,8247,418]
  all match=True
$ diff parity.md …/artifacts/tokenizer_parity_table.md -> empty, exit 0
$ sha256sum parity.md -> 8512eb971c4b029f38e9c934ecfb5a9cf53fffd102c79f93b613681d0b9d7270

$ grep '^gen:' run1.txt > r1.norm && grep '^gen:' run2.txt > r2.norm && diff r1.norm r2.norm
  exit 0; both 88de45824c276d1ac4ecb3572e3ba6dd42a4130bb137522c3e64dcff780ead2a
  (== committed run1.norm.txt / run2.norm.txt byte-for-byte)

$ sha256sum -c workflow/evidence/HO-STRATA-010/hashes.txt     -> 15/15 OK, exit 0
   hashes.txt itself = 4f1f045ba7b432b8fb0ed91fb3d3c8992bd4e3ca7494beeac2efc48f2c41c535
$ sha256sum -c …/artifacts/pack_hashes.txt                    -> 2/2 OK, exit 0
   Mixtral 542d2453…  DeepSeek f00ecd83…
$ git show 8ce28c4:workflow/MODELS.md | sha256sum             -> 1883c62b…  (= pin)
$ git show 8ce28c4:planning/strata-engine/13-… | sha256sum    -> 023a37de…  (= pin)
$ sha256sum workflow/MODELS.md                                -> dae0b4ea…  (branch adds the DEC-029 note)
$ git -C /home/kupipi/Documents/git/strata status --porcelain -> (empty)
$ git -C …/strata rev-parse HEAD                              -> baf16363b4403ef0ed4f538f5d5ed11c43fb9535
$ sha256sum …/strata/build-hip/strata                         -> d58ee239…  (mtime 2026-11-15, not rebuilt)
```

**Re-run match: exact** — `40cf635f…` binary, the 16-token `gen:` line, `5334baef…` logits (three independent copies), `db6eccb3…` layers, `8512eb97…` parity table, `88de4582…` normalized gen line. No token, hash, or shape moved.

### 7.3 R1 — judgement: **Minor fidelity defect, not cosmetic; non-blocking**

R1 is real and QAQC's *description* of it is accurate, but its *classification* ("cosmetic") understates it. The facts:

- `diff run1.txt run2.txt` on the committed files prints the header `2,3c2,3` followed by **two changed lines per side** (`< wall_s`, `< logits shape`, `---`, `> wall_s`, `> logits shape`) — exit `1`. I reproduced this, and the identical shape from my own two fresh runs (`2,3c2,3`, `wall_s` + filename only).
- `test-output.txt:27-34` prints the correct header and exit but **six** body lines (**three per side**): it also prints `< logits layout: [step][rank][(token_id_f32, logit_f32)]  ranks: top-1, top-2` and the `>` twin, which are byte-identical in both files and which `diff` never emits. `git diff 25c6a9a..664bd40` shows the previous transcript used `2,4c2,4` with the same three-line body; the rework fixed the header to `2,3c2,3` and left the body. So the block was never a paste of command output — it is a hand transcription.

Why it is **not cosmetic**: it asserts a fact about the files that is false (that line 4 changed between runs), in a file whose section is labelled `=== diff run1 vs run2 (stdout) ===`. A cosmetic defect is one that changes only presentation; this changes meaning, narrowly.

Why it is nonetheless **non-blocking**:

1. **Direction.** The error *over-reports*: an identical line is shown as changed. Nothing is concealed, and no acceptance claim depends on line 4 differing or not.
2. **The gate of record is elsewhere and is clean.** AC-2's reproducibility result is carried by the normalized gen-line comparison: the command is recorded (`commands.log:61-63`, `manifest.md` row `6c`), it reproduces the hashed `.norm` files byte-for-byte, and `normalized_diff_exit=0` is true. I re-derived it three ways.
3. **The true diff is one command away on committed, hashed inputs.** `run1.txt`, `run2.txt` and both `.norm` files are committed and hashed; any reader can run `diff` and get the truth in one step. The transcript's exit code, reason line, and conclusion are correct.
4. **No criterion fails.** A-1 is closed, A-2's required fix (true exits + recorded, reproducible normalization) is done, and the parity/AC-3 artifact is now byte-reproducible.

Combined with B-1(b) (§7.4: the parity block drops the table's two header lines the command emits), the accurate statement is: **`test-output.txt` is a curated transcript, not a single raw command stream**, and `manifest.md` §8's "outputs are raw; no paraphrasing" is therefore a slight over-claim. That is a documentation/fidelity debt, not a false result. The correct fix is to regenerate the transcript from the recorded commands at the next touch of the bundle (and re-hash `test-output.txt`), not a new evidence round on its own. The architect may still prefer to issue `RW-HO-STRATA-010-2` for a strictly verbatim transcript — it is a two-line body plus two header lines — but my recommendation is to accept B-1 as recorded, because no claim, hash, shape, or scope depends on it and the underlying artifacts are committed.

### 7.4 New findings from this re-audit

| # | Severity | Finding | Required action | Owner |
|---|---|---|---|---|
| **B-1** | **Minor** (fidelity) | `test-output.txt` is a composed transcript, not raw stdout: (a) the `=== diff run1 vs run2 (stdout) ===` block prints 6 body lines under `2,3c2,3`, including the byte-identical `logits layout` line as changed (R1, §7.3); (b) the parity block (`:2-4`) omits the table header and separator lines that command 2 emits. `manifest.md:111` nevertheless ticks "outputs are raw; no paraphrasing". | At the next touch of the bundle, regenerate `test-output.txt` from the recorded commands (or store one file per command) and re-hash it. Not required for this PASS. | Coder (next touch) |
| **B-2** | Observation (provenance) | The shared-library digests are **build-instance** scoped, not merely host-scoped: `libggml-base.so.1` was `2cc34f6f…` in `manifest.md` at `02bc3c2` and is `437dd6b7…` today, from a rebuild at the same pin (`78e05298f`, embedded in the binary) on the same host. `libllama`, `libggml`, `libggml-cpu` did not move. The recipe reproduces; the digests do not identify a reproducible build. | Change "this-host only" (`manifest.md:79`) to "this host **and this build**"; keep the digests as identification, not as a build-reproducibility proof. No result depends on them — the dumps reproduce. | Coder (next touch) |
| **B-3** | Minor (bookkeeping) | A-12 carry-over. `STATUS.md:19`: `wp/strata-010-reference-oracle @ 068e8fe`, next action "QAQC independent review". `HO-STRATA-010-QAQC.md:7`: state `PROPOSED`, base `3660925…` (pre-rebase), DoD `:113` unticked. `068e8fe` and `3660925` are ancestors, so no diff is invalidated, but the board and the QAQC handoff disagree with `HO-STRATA-010.md:11` (base `8ce28c4`). | Architect mirrors the state (DEC-018): STATUS row to the audited tip + current next action; QAQC handoff state/base refreshed. | Architect |
| **B-4** | Minor (DEC-024 completeness) | `hashes-notes.txt:9-10` records the two commit pins but **not** the resulting digests, which DEC-024 requires ("`git show <sha>:<path> \| sha256sum` and the resulting digest recorded in `hashes-notes.txt`"). The pins are verifiable (I verified both: `1883c62b…`, `023a37de…`), so nothing is lost, but the note is incomplete on its own terms. | Add the two digests to `hashes-notes.txt` at the next touch. | Coder (next touch) |

No Blocker and no Major finding. B-1/B-2/B-4 are inside the evidence bundle and can be folded into any later commit; B-3 is the architect's board.

### 7.5 Evidence verification at `0369ec8`

- [x] **Manifest complete; commands reproducible.** Rows `1`–`7` of `manifest.md` §1 were executed as written from the repo root (§7.2); rows `0a`–`0c` were verified against the existing tree (tag `b12527`, commit `78e05298…`, clean, the four lib digests, CMake `3.28.3`). `<deepseek>` is expanded at `manifest.md:26`. The exit codes I observed match the table (`0` for rows 1–5 and 7, `1` for `6a`, `0` for `6b`/`6c`).
- [x] **Outputs raw; failures/skips kept verbatim — with the B-1 exception.** Mixtral's refusal, the non-empty stdout diff and the reason are preserved; the diff *body* and the parity block are curated (B-1). No failed step is hidden.
- [x] **Artifacts/hashes match the manifest.** `sha256sum -c hashes.txt` → **15/15 `OK`**, exit `0`; every §3 digest equals `hashes.txt` and the file on disk; `pack_hashes.txt` **2/2 `OK`** (13.7 s, both packs fully re-read).
- [x] **Environment recorded.** Ubuntu 24.04, `Linux 7.0.0-42-generic`, GCC `13.3.0`, Python `3.14.10`, CMake `3.28.3`, `GGML_NATIVE=ON`, `CMAKE_BUILD_TYPE=Release`, `BUILD_SHARED_LIBS=ON`, `LLAMA_CURL=OFF`, `LLAMA_BUILD_{TESTS,EXAMPLES,SERVER}=OFF`, CPU-only `n_gpu_layers=0`, Ryzen AI 9 HX 370, 24 vCPUs. Matches the host I ran on.
- [x] **No secrets.** Pattern scan (`ghp_`, `github_pat_`, `hf_<token>`, `sk-`, `api_key`, `password`, private-key header) over the bundle and handoff: **0** matches. Largest committed file is the 917,504 B layer dump; no weights.

### 7.6 Claim and scope audit at `0369ec8`

- [x] **Every claim cites a command and an output.** The parity claim cites command 2 + the regenerated table; the reproducibility claim cites commands 4/5/6b/6c + the hashed `.norm` files; the dump claims cite commands 3/4/7 + digests and shapes; provenance cites 0a–0c + §4; "no engine change" cites AC-8. The one over-claim is `manifest.md:111` "outputs are raw" (B-1); every *substantive* claim holds against its artifact.
- [x] **One profile per claim.** CPU-only, llama.cpp `b12527`/`78e05298…`, DeepSeek-MoE-16B-base `Q4_K_M` (`f00ecd83…`), 3-prompt parity + 4-token dump + 5-token/16-step decode, `n_ctx=4096`. No Mixtral data, no Strata run, no 780M/MI25/gfx1100. No cross-profile transfer.
- [x] **Scope matches the handoff; no silent expansion.** `8ce28c4..0369ec8` = 24 files: 16 evidence, `HO-STRATA-010.md`, `HO-STRATA-010-QAQC.md`, `RW-…-1.md`, the two reports, `DECISIONS.md`, `MODELS.md`, `STATUS.md`. The `DECISIONS.md` delta is DEC-028/DEC-029 (architect's decisions for this work package); `MODELS.md` is the DEC-029 format note the decision authorises; `STATUS.md` adds the HO-010 row. No engine code, no CMake, no family enum, no S1+ work.
- [x] **Guard rails respected.** Strata checkout clean at `baf16363…`, `build-hip/strata` `d58ee239…` (mtime 2026-11-15) — not rebuilt, not edited. No new dependency (numpy was already present; llama.cpp stays at the pin in `/tmp`). No download: the HF cache dirs are untouched since 2026-11-17 and no `.gguf` is newer; both packs match `pack_hashes.txt`. No prompt tuning (§2.3 prompts unchanged). No secret, no weights in git.
- [x] **Mixtral deferral is real, not hidden.** I parsed the Mixtral GGUF header independently: **995** tensors, arch `llama`, **0** stacked `*_exps` tensors, `blk.0.ffn_down.0…7.weight` present — exactly the per-expert 2023 layout DEC-029 describes, and the pack hash matches. The refusal reason is factually correct; the deferral is recorded in DEC-029, `MODELS.md`, and `manifest.md:85`.
- [x] **No perf/support claim; no tolerance chosen.** Case-insensitive scan for `faster|speedup|outperform|tok/s|SOTA|production|benchmark|performance` returns only the sentence "no performance claim". `tolerance|KL` returns only the S4-baseline note. Wall time stays an observation (`0.687`/`0.665` here vs `0.686`/`0.678` committed — labelled as such).
- [x] **Rework history closed.** `RW-HO-STRATA-010-1` F1/F2/F3 are closed (§7.1); the log entry at `HO-STRATA-010.md:166-174` records the rework; no open rework file.

### 7.7 Counter-hypotheses tested in this re-audit

| Hypothesis | Test | Result |
|---|---|---|
| The regenerated parity table was hand-edited to remove the mismatch line | Re-ran command 2 twice into fresh files, `diff` against the committed table, and read stderr | **Falsified.** Exit `0`, stderr `0` lines, byte-identical (`8512eb97…`). The line is gone because the script parses the full payload. |
| The "true exit" was fixed only in prose, not in the pipeline | Ran `diff run1.txt run2.txt` and the normalization recipe on the committed files | **Falsified.** Raw diff exits `1`; normalization exits `0` and reproduces the hashed `.norm` files. |
| The QAQC re-pass reviewed the new commit but an older bundle | `git diff 664bd40..0369ec8` | **Falsified.** The only post-rework commit changes the QAQC report; the evidence bytes QAQC saw are the bytes I audited. |
| The pins were moved to `8ce28c4` without the files existing there | `git show 8ce28c4:<path> \| sha256sum` for both inputs | **Falsified.** Both resolve; the plan is byte-identical, `MODELS.md` differs only by the branch's DEC-029 note, and both are present at `0369ec8`. |
| The dumps were re-generated from a different build and only the hashes were copied | Rebuilt the harness from the committed source, re-ran both generations, the dump and the parity check | **Falsified.** `40cf635f…` binary; `5334baef…` logits; `db6eccb3…` layers; `8512eb97…` table. |
| The engine was rebuilt to make parity pass | `sha256sum build-hip/strata` + mtime | **Falsified.** `d58ee239…`, mtime 2026-11-15, tree clean at `baf16363`. |
| The C1 note is a post-hoc rationalisation | Recomputed the pre-fix vs post-fix dump difference | **Confirmed accurate**, not rationalised: 0.0 for layers 0–26, `3.8147e-06` / `8.0729e-08` / 699-of-2048 at `l_out-27` pos 3. |

### 7.8 Verdict

- **PASS → `ARCHITECT_APPROVAL`.** Of the thirteen findings in §3.2, eleven are closed (A-1…A-11), A-12 is the architect's board (→ B-3) and A-13 was deferred to S1+ by the first report. The oracle, the parity gate, the dumps and the provenance reproduce exactly from the committed sources at `0369ec8`; the QAQC re-pass covers that commit; the pins resolve at `8ce28c4`; the scope is clean.
- **What changed since the first audit:** A-1 (stale parity artifact) and A-2 (falsified diff exit) are fixed *in the artifact*, not just in prose; A-3 (stale QAQC) is fixed by a re-pass on the audited commit; A-10/A-11 are fixed by the rebase that brought `DEC-024`, `DEC-027` and the family test plan in-tree.
- **What remains:** one Minor fidelity debt in the transcript assembly (B-1/R1, with its exact cause identified), one provenance-wording observation (B-2), one DEC-024 completeness item (B-4), and the architect's own board (B-3). None changes a token, a digest, a shape, a claim or the scope.
- **R1:** **not cosmetic — a Minor fidelity defect; non-blocking** (§7.3). The block's header and exit are right; its body shows an unchanged line as changed. It over-reports, contradicts no claim, and the true diff is reproducible from committed, hashed inputs in one command.
- **Not signed by the auditor.** The architect decides `DONE` and merges, and may fold B-1/B-2/B-4 into a later bundle commit or require them first via `RW-HO-STRATA-010-2`; my recommendation is to accept them as recorded and correct them at the next touch.

### 7.9 Owner-task oversight (updated)

- Owner task: `OT-STRATA-001` (S0 authorised 2026-11-18, DEC-028).
- Checkpoint **S0 — reference oracle + parity harness: met and evidence-verified**. Reproducible oracle (llama.cpp `b12527` @ `78e05298…`), tokenizer parity on three fixed prompts with no BOS on either side, 16-token reference IDs, `[4][28][2048]` layer dump and `[16][2][2]` top-2 logits, all bit-reproducible; engine untouched (`baf16363…`, `d58ee239…`); Mixtral deferred for a documented format reason (DEC-029).
- Owner acceptance: **still pending** — it is recorded in `OT-STRATA-001` only after the architect signs `HO-STRATA-010` `DONE`. Nothing in this re-audit requires owner action.

### 7.10 Statement (re-audit)

I did not modify code, tests, docs, configuration, evidence, handoffs, or the Strata checkout. My only write is this added section. All executions used `/tmp/opencode/audit-010b/` as scratch (harness rebuild, two generation runs, layer dump, parity run, normalization reproduction, a numpy inspection of both dumps, and a GGUF header read of both packs); the pinned trees were read-only (`git`/`sha256sum`/`diff` over `/tmp/opencode/llama.cpp`, `/home/kupipi/Documents/git/strata`, `workflow/evidence/HO-STRATA-010/`). Model separation remains **WAIVED** under WAIVER-001: `python3 workflow/check_model_policy.py --strict` → `RESULT: WAIVED — policy exception in force (not PASS)`, because auditor and architect share the `deepseek` family. This is a WAIVED audit, not a clean independent-family one. Coder (`kimi-k2.7-code`) and QAQC (`gemini-4-argon`) remain on different families.

---

## 8. `AUDITOR_TO_ARCHITECT` handoff record

Per DEC-018, the auditor's handoff to the architect is embedded here (write boundary: `workflow/reports/audit/` only).

```markdown
# HO-STRATA-010-ARCHITECT — S0 reference oracle: audit PASS (re-audit)

| Field | Value |
|---|---|
| **ID** | HO-STRATA-010-ARCHITECT |
| **Type** | AUDITOR_TO_ARCHITECT |
| **State** | ARCHITECT_APPROVAL |
| **Created / updated (UTC)** | 2026-11-19 |
| **From → To** | Auditor (`auditor`, `opencode-go/deepseek-v4.1-flash`) → Architect (`architect`) |
| **Work package** | `strata-010-reference-oracle` |
| **Branch / audited commit** | `wp/strata-010-reference-oracle` @ `0369ec87d9e84e664356a3423f3744541054e321`, based on `main` `8ce28c4e2e33904b824d8541d69f1ea770548424` |
| **Priority / timebox** | P1 |
| **Original handoff** | `workflow/handoffs/HO-STRATA-010.md` (state `CODER_DONE`) |
| **Rework** | `workflow/handoffs/RW-HO-STRATA-010-1.md` (closed) |
| **QAQC report** | `workflow/reports/qaqc/HO-STRATA-010-qaqc.md` (PASS on `664bd40`, re-pass section) |
| **Audit report** | `workflow/reports/audit/HO-STRATA-010-audit.md` (§7 re-audit) |
| **Evidence path** | `workflow/evidence/HO-STRATA-010/` |

## 1. Verdict

**PASS → `ARCHITECT_APPROVAL`.** A-1, A-2, A-3, A-10, A-11 and A-4…A-9 are closed and
independently reproduced. No Blocker, no Major finding. Four items remain, all
non-blocking (B-1 transcript fidelity, B-2 provenance wording, B-3 board
bookkeeping, B-4 pin digests).

## 2. Evidence the architect should look at

| Item | Value |
|---|---|
| `sha256sum -c workflow/evidence/HO-STRATA-010/hashes.txt` | 15/15 `OK`, exit 0; `hashes.txt` = `4f1f045ba7b432b8fb0ed91fb3d3c8992bd4e3ca7494beeac2efc48f2c41c535` |
| Reference gen line | `gen: 8913 13 185 40619 317 254 6077 280 7239 13 185 40619 317 254 6077 280` |
| Logits dump | `5334baef84380f6060f8b1c4afda5fd45d367e9065ecdf2c6e4ea0642153fb2e` (16x2x2) |
| Layer dump | `db6eccb3e8a949827c5c961fc732159daa1a0a9d52f7f88156d669845e0c7c73` (4x28x2048, 112/112 non-zero rows) |
| Parity table | `8512eb971c4b029f38e9c934ecfb5a9cf53fffd102c79f93b613681d0b9d7270` (regeneration diff empty, exit 0) |
| Harness binary (rebuilt) | `40cf635f0dc36a26202f9145af786423c200633c4b9bd1986be42f7159f68506` |
| Pins at `8ce28c4` | `MODELS.md` `1883c62b…`; `planning/strata-engine/13-…` `023a37de…` |
| Engine guard rail | Strata clean at `baf16363…`; `build-hip/strata` `d58ee239…` (not rebuilt) |
| Model packs | DeepSeek `f00ecd83…` OK; Mixtral `542d2453…` OK (995 tensors, 0 stacked `_exps` — DEC-029 reason confirmed) |

## 3. Decisions requested from the architect

1. **Sign or reject** `HO-STRATA-010` at `0369ec8` (`DONE` / `REWORK`). If signing,
   record `ARCHITECT_APPROVAL` and merge with the HO ID and evidence path.
2. **B-1:** accept the curated-transcript debt (recommended: correct at the next
   bundle touch) or require `RW-HO-STRATA-010-2` for a verbatim `test-output.txt`.
3. **B-3:** update `STATUS.md:19` (still `@ 068e8fe`) and the QAQC handoff
   (`PROPOSED`, base `3660925…`) when mirroring the state (DEC-018).

## 4. Acceptance status

| AC | Status |
|---|---|
| 1 llama.cpp pinned/built, provenance | PASS (tag `b12527`, `78e05298…`, flags, CMake `3.28.3`, `GGML_NATIVE=ON`, host CPU/24 vCPU, lib digests) |
| 2 reproduces on two runs | PASS (raw diff exit 1 for `wall_s`+filename only; normalized gen gate exit 0; logits binaries identical) |
| 3 tokenizer parity, 3 prompts, zero diffs | PASS (regenerated table byte-identical, 0 mismatch lines, no BOS either side) |
| 4 reference IDs, DeepSeek P1, 16 tokens | PASS (Mixtral deferred, DEC-029) |
| 5 per-layer dump, shape, non-degenerate | PASS (112/112 rows non-zero, finite, layers distinct) |
| 6 logits/top-2 for 16 steps | PASS (256 B, 16x2x2, top-1 == gen ids) |
| 7 harness committed and runnable | PASS (rebuilt and re-run from the repo root) |
| 8 no engine change | PASS (clean `baf16363…`, binary `d58ee239…`) |
| 9 no perf/support claim | PASS (wall time labelled observation; no tolerance/KL chosen) |

## 5. Signatures

| Role | Name/agent | Date | Decision |
|---|---|---|---|
| Sender (Auditor) | `auditor` (`opencode-go/deepseek-v4.1-flash`, WAIVED) | 2026-11-19 | PASS → `ARCHITECT_APPROVAL` |
| Receiver (Architect) | `architect` | | |
```
