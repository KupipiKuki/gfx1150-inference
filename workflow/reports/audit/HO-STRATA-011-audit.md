# Audit report — HO-STRATA-011

| Field | Value |
|---|---|
| **Handoff** | HO-STRATA-011 (`ARCHITECT_TO_CODER`, S0b OLMoE oracle); reviewed after `RW-HO-STRATA-011-1` and the QAQC re-pass |
| **Reviewer** | Auditor (`auditor`), runtime model `opencode-go/deepseek-v4.1-flash` (family `deepseek`) — **reported as WAIVED under WAIVER-001 / DEC-009**, not as a clean independent-family PASS. `check_model_policy.py --strict` → `RESULT: WAIVED — policy exception in force (not PASS)`; the auditor shares the `deepseek` family with the architect (compensating checks: architect final review, owner acceptance, QAQC on `gemini`, evidence bundle) |
| **Date (UTC)** | 2026-11-20T01:29Z |
| **Verdict** | **PASS (WAIVED — WAIVER-001)** → `ARCHITECT_APPROVAL`, with conditions **C1 (architect must ratify the AC-3 substitution)** and **C2 (review-state bookkeeping)** to be closed before `DONE` |
| **Evidence reviewed** | `workflow/evidence/HO-STRATA-011/` at `c73b42428cfdf693e9c242b1b0b6c6b7b4f0427d` (43 tracked files: `manifest.md`, `commands.log`, `hashes.txt` 41 entries, `hashes-notes.txt`, `test-output.txt`, 5 helpers + `oracle_harness.cpp`, 28 per-command raw transcripts, 6 run/dump artifacts). Also `workflow/evidence/HO-STRATA-010/` via `wp/strata-010-reference-oracle` @ `664bd40` (that bundle is not on this branch) |
| **QAQC report** | `workflow/reports/qaqc/HO-STRATA-011-qaqc.md` (QAQC `opencode-go/gemini-4-argon#high`, family `gemini`; first pass on `bc93b56` FAIL → `RW-HO-STRATA-011-1`; re-pass on `c73b424` PASS). **The PASS version is uncommitted** — see finding L2 |
| **Rework reviewed** | `RW-HO-STRATA-011-1` (F1 bundle ignored `.bin`; F2 hash paths; F3 hardcoded layer count + unrecorded stdin scripts; F4 stale pins / bare digests / relative binary path) |
| **Scope reviewed** | `git diff --name-status 6679e93..c73b424` → 49 paths: `.gitignore` (+1 negation), `workflow/STATUS.md`, 3 handoff files, the QAQC report, and 43 files under `workflow/evidence/HO-STRATA-011/`. Strata checkout `/home/kupipi/Documents/git/strata` @ `baf16363b4403ef0ed4f538f5d5ed11c43fb9535`, `git status --porcelain` empty, binary `d58ee239…` |
| **Profile (one only)** | CPU-only reference oracle (`n_gpu_layers=0`), llama.cpp tag `b12527` / commit `78e05298f0d68abff41d08d79fa7469264b2aff0`, CMake `3.28.3`, `GGML_NATIVE=ON`, GCC `13.3.0`, Python `3.14.10`, Linux `7.0.0-42-generic` (Ubuntu 24.04), AMD Ryzen AI 9 HX 370 w/ Radeon 890M, `nproc=24`; model OLMoE-1B-7B-0924-Instruct Q4_K_M, GGUF arch `olmoe`; workload: 3-prompt tokenizer table, 4-token per-layer dump, 5-token 16-step greedy decode + top-2 logits (P1 = `510,5347,273,6181,310`) |

---

## 1. Evidence verification

- [x] **Manifest complete; commands reproducible.** All 16 command rows (`0`, `1`, `2`, `3`, `4`, `5`, `6a`, `6b`, `6c`, `7`, `8`, `9`, `10`) carry command text, CWD, exit code and output path; the environment block names OS, kernel, compiler, Python, CPU and `nproc`. I re-ran 0, 1, 2, 3, 4, 5, 6a/b/c, 7, 8, 9 myself; every exit code matched the recorded one (details in §1.2–§1.4). Two cosmetic replay gaps are recorded as L5/L6, neither of which changes a result.
- [x] **Outputs raw; failures/skips kept verbatim.** 28 per-command `cmd-*.{out,err}.txt` files hold each command's stdout/stderr separately; `cmd-6a.out.txt` keeps the **non-empty** raw diff and `commands.log:19` records `[6a] exit=1` — the failure was not hidden. `cmd-7.out.txt` shows the non-degeneracy check; `cmd-1.err.txt` keeps all 5 deprecation warnings and `[1] exit=0` is correct. The engine tokenizer refusal is preserved in `cmd-2.out.txt` and reproduced by me (§1.3).
- [x] **Artifacts/hashes match the manifest.** `sha256sum -c workflow/evidence/HO-STRATA-011/hashes.txt` from the repo root → **41/41 `OK`, exit 0, zero warnings**; same result from a clean `git archive c73b424` extraction (§1.4). Every digest in `manifest.md` §3 equals its file; the 4 llama.cpp library digests in §4 equal the libraries on disk; the model pack digest equals the handoff §2.
- [x] **Environment recorded.** `manifest.md` §4/§7 and `hashes-notes.txt` record the tag/commit/build flags/CMake/compiler/CPU/`nproc` and all four `.so.1` digests, explicitly scoped to **this host and this build** (B-2). I confirmed `uname` = `Linux … 7.0.0-42-generic #42~24.04.1-Ubuntu`, `g++ 13.3.0`, `cmake 3.28.3`, `python3 3.14.10`, `nproc 24`.
- [x] **No secrets.** Pattern scan (`ghp_*`, `github_pat_*`, `hf_*`, `sk-*`, `AKIA*`, `BEGIN … PRIVATE`) over the bundle, both handoffs and the QAQC report → zero matches. No model weights in git: largest committed bundle file is the 524,288 B layer dump.

### 1.1 Pack identity and the geometry the dumps imply (independent re-derivation)

I read the GGUF header with my own parser (not `check_pack.py`):

| Field | Observed (auditor) | Handoff §2 / claim | Match |
|---|---|---|---|
| Size | `4,213,512,672` B | `4,213,512,672` B | ✅ |
| SHA256 | `8c310f1435a1222338fd2d3d974975be9cd908180b644bab0c2a94da1ac32f3f` | same | ✅ |
| `general.architecture` | `olmoe` | `olmoe` | ✅ |
| `olmoe.block_count` | 16 | 16 layers | ✅ |
| `olmoe.embedding_length` | 2048 | 2048 hidden | ✅ |
| `olmoe.expert_count` / `expert_used_count` | 64 / 8 | 64 experts, top-8 | ✅ |
| `olmoe.feed_forward_length`, heads / KV heads | 1024, 16 / 16 | FFN 1024, 16/16 | ✅ |
| `olmoe.context_length` / rope base | 4096 / 10000.0 | `n_ctx=4096` | ✅ |
| `tokenizer.ggml.model` / `.pre` | `gpt2` / **`olmo`** | gpt2 / olmo | ✅ |
| `tokenizer.ggml.tokens` len, BOS/EOS, `add_bos_token` | 50304, 50279/50279, `False` | 50,304, 50279, False | ✅ |
| `expert_shared_feed_forward_length` | absent (no shared expert) | no shared expert | ✅ |
| GGUF version / tensors | 3 / 195 | n/a | — |

Dump geometry corroborates the header: `olmoe_p1_4_layers.bin` = **524,288 B = 4 × 16 × 2048 float32** and `olmoe_p1_logits.bin` = **256 B = 16 × 2 × 2 float32**. The 16-layer / 2048-hidden geometry is therefore confirmed twice, independently (header and file size). The 64-experts/top-8 axis is **metadata-only**: no per-expert routing artifact exists, and the handoff does not claim one — that axis is unexercised until S1+.

### 1.2 Reproduction (independent rebuild, two runs)

```
g++ -O2 -std=c++17 workflow/evidence/HO-STRATA-011/artifacts/oracle_harness.cpp \
    -o /tmp/opencode/audit011/oracle_harness \
    -I/tmp/opencode/llama.cpp/include -I/tmp/opencode/llama.cpp/ggml/include \
    -L/tmp/opencode/llama.cpp/build/bin -lllama -lggml -lggml-base -lggml-cpu -lpthread
# exit 0, 5 deprecation warnings; stderr byte-identical to cmd-1.err.txt after path normalisation
# binary SHA256 40cf635f0dc36a26202f9145af786423c200633c4b9bd1986be42f7159f68506
```

| Check | Recorded | Auditor re-run | Result |
|---|---|---|---|
| `--tokens 510,5347,273,6181,310 --n 16` run 1 | `gen: 7785 15 187 187 510 14731 273 6181 310 14029 15 187 187 510 3072 273` | identical | ✅ |
| run 2 | same | identical | ✅ |
| `normalized_diff_exit` | 0 (`gen:` lines equal, `feac86a5…`) | **0**, my `run*.norm.txt` hash `feac86a5…` | ✅ truthful |
| `raw_diff_exit` | 1 (`wall_s` + dump filename differ) | **1**, same two lines only | ✅ truthful |
| logits dump | `a73e3eae9da4216e0a0ac110c9ec775b0f31d17ac17f527572b110c2402494be` | **both** my runs bit-identical to the committed file | ✅ |
| layer dump `--tokens 510,5347,273,6181 --n 0` | `3c72636a2e713cf99ed279f635fe85832cca1ba4a2f260feb2323d1bbd51fa50` | my re-dump bit-identical | ✅ |
| `check_layers.py --layers 16` | `(4,16,2048)`, `[(0,16),(1,16),(2,16),(3,16)]`, no nan/inf | exit 0, **byte-identical to `cmd-7.out.txt`** | ✅ |
| parity table | `c84b0a2d03fca837b23e02e1d6e2a6ccb597164367c0d6e8520170be2237f58d` | regenerated, byte-identical (`diff` clean, stderr empty) | ✅ |
| pack check | `cmd-0.out.txt` | `check_pack.py` re-run byte-identical | ✅ |

I also checked the dumps directly with numpy rather than the coder's helper: **64 distinct `[position][layer]` rows**, row L2 norms `0.248 … 76.06`, all finite, and the logits top-1 ids equal the generated token sequence with positive top-1/top-2 margins `0.1753 … 8.1076`. The dump is non-degenerate, not a broadcast/zero-fill, and internally consistent with the `gen:` line.

### 1.3 AC-3: the tokenizer finding — honest, and correctly left to the architect

I reproduced the engine refusal directly:

```
$ python3 /home/kupipi/Documents/git/strata/tools/strata_tokenizer.py \
    --gguf .../olmoe-1b-7b-0924-instruct-q4_k_m.gguf --out /tmp/.../tok.json
exit=1
UnknownPreTokenizer: This model splits text with a rule Strata doesn't have yet ('olmo'),
so it isn't loaded: running it with the wrong rule would change what it reads.
```

`tools/strata_tokenizer.py:104-112` `pre_tokenizer_kind()` returns a rule only for `"qwen35"` and `p.startswith("deepseek")`; the GGUF's `tokenizer.ggml.pre` is `olmo`, so it returns `None` and `__init__` (line 123) raises. The error string in `cmd-2.out.txt` is the exact exception text, character for character.

**Judgement: honest, not a dodge — but AC-3 is not met as written, and only the architect can close that gap.**

- Honest: `manifest.md` §2 row 3 says `**FINDING** (engine tokenizer does not load olmo pre-tokenizer)` — it is *not* checked `PASS`; the parity table prints `match: False` for all three prompts with the engine column `N/A — <the refusal>`; `test-output.txt:13` and `hashes-notes.txt:73-75` say the same thing. Nothing is presented as zero differences.
- Not a dodge: the harness reference ids are a real, reproducible `llama_tokenize(add_special=false, parse_special=true)` result (`P1 [510,5347,273,6181,310]`, `P2 [1545,823,9,66,13,270,2262,187,50274,2309]`, `P3 [11831,3625,9830,403]`, no BOS 50279), the BOS convention is stated, and there is no legal alternative: producing engine ids at this pin would require editing the read-only Strata checkout, which AC-8 and DEC-016 forbid.
- The gap is real and pre-anticipated: `HO-STRATA-011.md:116` (DoD) already says "engine tokenizer refuses `olmo` pre-tokenizer recorded as a finding", so the coder followed the architect's own instruction rather than inventing a substitute. That does not amend **AC-3**, whose text still demands "zero differences". Contract §4/§11 make criteria the architect's to change. This audit passes the *evidence*, not a tokenizer parity demonstration; **C1** below requires the architect to ratify the substitution in `DECISIONS.md` (or amend AC-3) so S1+ does not inherit an ambiguity.

### 1.4 Bundle integrity and the fresh-clone test (RW-011-1 findings)

| RW finding | Auditor check | Result |
|---|---|---|
| **F1** dumps ignored | `git ls-tree -r c73b424 …/artifacts/runs/` lists 6 files incl. both `.bin` (blobs `aa79391a…`, `55712f0a…`); `git status --ignored --porcelain workflow/evidence/HO-STRATA-011/` → **empty**; bundle = 43 files on disk = 43 tracked; no stray `*run2.bin` in the repo | **RESOLVED** |
| **F2** hash paths | `hashes.txt` = 41 entries, all repo-root-relative except the absolute model path; `sha256sum -c` from `/home/kupipi/Documents/git/gfx1150-inference` → 41/41 OK, exit 0 | **RESOLVED** |
| **F3** hardcoded layers | `grep -n "28\|27" artifacts/*.py` → no layer-count hits (only BOS `50279`); `check_layers.py --layers 16` runs, derives `n_embd` from size, reproduces `cmd-7.out.txt`; `check_pack.py` committed and reproduces `cmd-0.out.txt`; no `python3 -` invocation remains in `manifest.md` §1 or `commands.log` | **RESOLVED** |
| **F4** pins / digests / path | `git show 6679e938:…` digests = `workflow/MODELS.md` `16041e44…`, `13-family-support-test-plan.md` `1cfe6f4a…`, `workflow/DECISIONS.md` `8a03370d…` — all three match `hashes-notes.txt:13-17`; `manifest.md` §3 carries explicit 64-hex digests; `cmd-9.out.txt:2` prints the absolute `…/build-hip/strata` | **RESOLVED** |

**Fresh-clone test (performed by me, not taken from the bundle):**

```
$ mkdir -p /tmp/opencode/audit-011-fresh
$ git archive c73b424 | tar -x -C /tmp/opencode/audit-011-fresh      # 845 files
$ cd /tmp/opencode/audit-011-fresh
$ sha256sum -c workflow/evidence/HO-STRATA-011/hashes.txt
exit=0   OK count=41   FAILED count=0
```

Nothing in the bundle depends on an ignored or untracked file; the only external dependency is the read-only GGUF pack, which is hashed by absolute path and present.

**RW guard rail held:** the dump digests recorded *before* the rework (`bc93b56`'s `hashes.txt`: `3c72636a…`, `a73e3eae…`) are identical at `c73b424`, and `runs/run{1,2}*.txt` have unchanged blob ids — the rework re-packaged the existing artifacts and did **not** re-measure or regenerate them, exactly as `RW-011-1` §3 required. `hashes.txt` moved 38 → 41 entries only by adding the path prefix and the three new files (`check_pack.py`, `cmd-10.out`, `cmd-10.err`).

### 1.5 Fidelity against the HO-010 lessons

HO-010's bundle is not on this branch; I read it from `wp/strata-010-reference-oracle` @ `664bd40`. Its `oracle_harness.cpp` and `tokenize_compare.py` have the **same digests** as HO-011's (`bdc9303d…`, `9903bc16…`) — the harness was reused, not rewritten, as the handoff required.

| HO-010 lesson | HO-011 evidence | Verdict |
|---|---|---|
| 1. Raw per-command transcript, never a passing exit for a non-zero command | 28 `cmd-*.{out,err}.txt`; `[6a] exit=1` recorded and raw diff preserved; `[1] exit=0 (warnings only)` matches the 5-warning stderr; every other recorded exit matches my re-run | ✅ |
| 2. Normalization is the gate; record `raw_diff_exit` / `normalized_diff_exit` truthfully | `1` / `0`, reproducible; both stated in `commands.log`, `manifest.md` §2 row 4, `test-output.txt:22-24` | ✅ |
| 3. Pins carry commit **and** digest | `hashes-notes.txt` pins all three mutable files at `6679e938` with digests that verify; mutable files are excluded from `hashes.txt` per DEC-024 | ✅ |
| 4. Provenance scoped to host + build | §4 and `hashes-notes.txt` say the library digests are this-host/this-build only (`GGML_NATIVE=ON`), with CMake, compiler, CPU and `nproc`; all four library digests match disk | ✅ |
| 5. Curated output labelled and non-contradictory | `test-output.txt:1` carries the required label; its numbers agree with the raw files except one stale count (L3/L4) | ✅ (with L3) |

---

## 2. Claim and scope audit

- [x] **Every claim cites a command and an output.** Pack (cmd 0), provenance (§4 + on-disk libs), reference run (4/5/6a-c), dumps (3/7 + file sizes), bundle (8/10), engine unchanged (9). No unsupported statement found; `wall_s` appears only as an observation.
- [x] **One profile per claim.** Everything is CPU, OLMoE-1B-7B-0924-Instruct Q4_K_M, `n_gpu_layers=0`. No result is presented as transferable to another family, quant or the GPU path.
- [x] **Scope matches the handoff; no silent expansion.** 49-path diff = `.gitignore` negation, `STATUS.md`, three handoff files, the QAQC report, and the bundle. No engine file, no dependency, no downloaded model, no tolerance/KL value, no performance or support claim (`grep` for `faster|speedup|tok/s|throughput|supported|works on` in the manifest/test-output/notes → zero hits). AC-8 re-verified: Strata clean at `baf16363…`, binary `d58ee239…`.
- [x] **Guard rails respected.** Out-of-scope items (engine change, Mixtral, dense llama, `qwen4exp`, tolerance, new downloads) are absent; the RW guard rail "do not re-measure" is proven by identical pre/post digests (§1.4).
- [x] **Rework history is named and resolved.** F1–F4 all RESOLVED at `c73b424`; the RW *file* is still `OPEN` and its QAQC acknowledgment row is empty (L2).

### 2.1 Acceptance criteria (auditor's own verdicts)

| # | Criterion | Auditor finding |
|---|---|---|
| 1 | Pack identity (size, SHA256, arch) | **MET** — all three + full geometry, independently re-derived |
| 2 | Harness built at the pin; provenance recorded | **MET** — rebuild reproduces QAQC's binary digest; libs match; host-scoped |
| 3 | Tokenizer parity: 3 prompts, zero differences, BOS stated | **NOT MET AS WRITTEN — recorded as `FINDING`, honest; architect ratification required (C1)** |
| 4 | Reference tokens, 16 greedy, reproducible, truthful diff exits | **MET** — `gen:` identical over my two runs plus two QAQC runs; `1`/`0` truthful |
| 5 | Layer dump `[4][L][H]`, every layer and position non-zero | **MET** — `(4,16,2048)`, 16/16 rows per position, 64 distinct rows, finite |
| 6 | Logits/top-2 `[16][2][2]`, layout documented | **MET** — 256 B, layout line printed, top-1 = generated ids |
| 7 | Bundle complete; hashes verify; pins carry digests | **MET** — 41/41 from repo root and from my fresh clone; pins verify with digests |
| 8 | No engine change | **MET** — clean Strata at `baf16363…`, binary `d58ee239…` |
| 9 | No claim | **MET** — no perf/support/tolerance statement anywhere |

---

## 3. Findings / rework

| # | Severity | Finding | Required action | Owner |
|---|---|---|---|---|
| **C1** | **Major (criterion, not evidence)** | **AC-3 is not met as written.** `HO-STRATA-011.md` §6 AC-3 demands "zero differences" for the three prompts; the bundle reports `match: False` × 3 and marks AC-3 `**FINDING**`. The evidence is honest and the refusal is reproduced, but a coder cannot convert an acceptance criterion into a finding — only the architect can (contract §4, §11). No coder rework is possible: fixing it needs an engine `olmo` pre-tokenizer, forbidden by AC-8/DEC-016 | Record the amendment in `DECISIONS.md` (new DEC) and/or amend AC-3 to: "parity for families the engine can load; where the engine's `pre_tokenizer_kind` rejects the GGUF's `tokenizer.ggml.pre`, the refusal must be reproduced verbatim and recorded as a finding with the reference ids beside it." Carry `olmoe` pre-tokenizer support as an S1+ engine item | **Architect** |
| **C2** | **Minor (bookkeeping, blocks `DONE`)** | The QAQC **PASS** report is **uncommitted**: at `c73b424` `workflow/reports/qaqc/HO-STRATA-011-qaqc.md` still holds the FAIL verdict (`git status` shows ` M`). Consequences: `HO-STRATA-011.md:7` state is still `REWORK`, `RW-HO-STRATA-011-1.md:7` is still `OPEN` with an empty QAQC acknowledgment row, `HO-STRATA-011-QAQC.md` is `PROPOSED`, and `STATUS.md:19` still says `CODER_DONE` | QAQC to fill the RW-011-1 acknowledgment and the `AUDIT_REVIEW` transition; architect to commit the PASS report, close the RW, set the handoff state and update `STATUS.md` at signoff | **QAQC + Architect** |
| L1 | Low | `manifest.md:63` says the manifest is "not self-hashed", but `hashes.txt:42` hashes `manifest.md` — the one file most likely to be amended later (exactly DEC-024's rot risk). The manifest also never names the evidence commit (`c73b424`), unlike HO-010 | Correct §3, or drop `manifest.md` from `hashes.txt` and pin it by commit instead; add an "evidence commit" line | Coder (next touch) |
| L2′ | Low | `cmd-10.out.txt` proves the fresh clone against **39** entries (the `hashes.txt` of that moment); `cmd-10.*` were appended afterwards. The "41/41 from a fresh clone" claim is *not* proven by the bundled transcript | Add `hashes.txt` to the exclusions note, or re-capture command `[10]` at the final hash count. Verified independently by QAQC and by me, so no result is in doubt | Coder (next touch) |
| L3 | Low | `test-output.txt:47` says "all 38 entries OK"; the authoritative count is 41. It is a truthful snapshot (39 lines = model + 38) inside a file labelled *curated excerpt*, so it does not contradict the raw files, but the number is stale | Refresh if the bundle is re-captured; otherwise leave (label already covers it) | Coder (optional) |
| L4 | Low | `commands.log:14,16` omit the `> …/runs/run{1,2}.txt` redirects that `manifest.md` §1 rows 4–5 and `cmd-4/5.out.txt` show; replaying `commands.log` literally does not regenerate `run1.txt`/`run2.txt` | Add the redirects to `commands.log` | Coder (next touch) |
| L5 | Low | QAQC report arithmetic: "48 files in `6679e93..c73b424`" (actual **49**) and "42 tracked files under the evidence bundle" (actual **43**). The F1–F4 conclusions are unaffected | Correct the two counts | QAQC |
| L6 | Info | `oracle_harness.cpp:260` still comments `l_out-27` (DeepSeek's 28 layers) although the code is family-agnostic; `check_layers.py --pos` defaults to `4`; the transient `olmoe_p1_logits_run2.bin` is not retained, so `[6c]` is not literally replayable (its conclusion is: my two runs produce bit-identical logits) | Comment/hint only; no action needed for this handoff | Coder (optional) |
| L7 | Info | The QAQC handoff `HO-STRATA-011-QAQC.md` §5 requires QAQC re-run artifacts under `workflow/evidence/HO-STRATA-011/artifacts/qaqc/`, which conflicts with `ENGINEERING_WORKFLOW.md` §4 (QAQC read-only outside its report dir). QAQC correctly wrote nothing into the coder's bundle | Fix the template text for the next handoff | Architect |

No finding is a blocker for the evidence verdict; **C1 and C2 must be closed by the architect before `DONE`**.

---

## 4. Verdict

- **PASS (WAIVED — WAIVER-001)** → `ARCHITECT_APPROVAL`; attach this report.
- Conditions before `DONE`: **C1** (architect ratifies / amends AC-3 in `DECISIONS.md`) and **C2** (commit the QAQC PASS report, close `RW-HO-STRATA-011-1`, set the handoff state and `STATUS.md`).
- The architect should note two things when merging: the working tree carries an uncommitted QAQC report edit, and an untracked HO-010 leftover (`workflow/evidence/HO-STRATA-010/artifacts/runs/deepseek_p1_logits_run2.bin`) that belongs to another branch and must not be swept into this merge.
- This report is not a final approval. The architect signs; the owner accepts.

---

## 5. Owner-task oversight

- Owner task: `OT-STRATA-001` (S0b authorized 2026-11-19 under **DEC-031**, three-model set qwen35moe / deepseek / olmoe; S1+ remain held by DEC-016).
- Checkpoints met: pack registered (`workflow/MODELS.md` at `6679e938`, digest-verified); S0b oracle values measured and reproducible; bundle shippable from a fresh clone; engine untouched.
- Open for the owner: the OLMoE **tokenizer** pre-tokenizer (`olmo`) is a real engine gap at pin `baf16363` — S0b measures around it and records it; it is not a pass and not a support claim. S1 will need it before any `olmoe` token-level comparison.
- Owner acceptance: **pending**.

---

## 6. Statement

I did not modify code, tests, docs, or configuration. I wrote nothing outside `/tmp/opencode/audit011/` scratch space and this report; this report is the only repository artifact I wrote. My own seat is **WAIVED under WAIVER-001** (auditor and architect share the `deepseek` family): this PASS is an evidence verdict under a disclosed independence exception, not a clean cross-family sign-off.

---

## 7. `HO-STRATA-011-ARCHITECT` (`AUDITOR_TO_ARCHITECT`) record

Embedded here per the DEC-018 pattern: the audit report is the authoritative record of the audit verdict and of the `AUDIT_REVIEW → ARCHITECT_APPROVAL` transition, and the architect mirrors the state field and this signature into the handoff file. I did not write a separate handoff file.

```markdown
# HO-STRATA-011-ARCHITECT — OLMoE oracle extension (S0b): audit PASS to final review

| Field | Value |
|---|---|
| **ID** | HO-STRATA-011-ARCHITECT |
| **Type** | AUDITOR_TO_ARCHITECT |
| **State** | READY (AUDIT_REVIEW → ARCHITECT_APPROVAL) |
| **Created (UTC)** | 2026-11-20T01:29Z |
| **From → To** | Auditor (`auditor`, `opencode-go/deepseek-v4.1-flash`, **WAIVED — WAIVER-001**) → Architect (`architect`) |
| **Work package** | `strata-011-olmoe-oracle` (HO-STRATA-011) |
| **Branch / commit audited** | `wp/strata-011-olmoe-oracle` @ `c73b42428cfdf693e9c242b1b0b6c6b7b4f0427d` (base `8ce28c4e…`, READY `6679e938…`) |
| **Audit report** | `workflow/reports/audit/HO-STRATA-011-audit.md` |
| **Evidence path** | `workflow/evidence/HO-STRATA-011/` — 43 tracked files, `hashes.txt` 41 entries, 41/41 OK from the repo root and from `git archive c73b424` |
| **QAQC report** | `workflow/reports/qaqc/HO-STRATA-011-qaqc.md` (PASS at `c73b424`) — **currently uncommitted** (condition C2) |
| **Verdict** | **PASS (WAIVED)** with C1 and C2 |
| **Independent reproduction** | harness rebuilt (binary `40cf635f…`), `gen:` line and both dump digests (`3c72636a…`, `a73e3eae…`) bit-identical over two fresh runs; `raw_diff_exit=1`, `normalized_diff_exit=0`; engine refusal `UnknownPreTokenizer('olmo')` reproduced |
| **Conditions before DONE** | **C1**: architect ratifies / amends AC-3 (tokenizer parity recorded as a finding) in `DECISIONS.md`. **C2**: commit the QAQC PASS report, close `RW-HO-STRATA-011-1`, set `HO-STRATA-011` → `AUDIT_REVIEW`, QAQC acknowledgment, update `STATUS.md` |
| **Merge caution** | do not sweep in the uncommitted QAQC edit as if it were coder work, and do not add the untracked HO-010 leftover `workflow/evidence/HO-STRATA-010/artifacts/runs/deepseek_p1_logits_run2.bin` |
```

