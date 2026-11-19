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
