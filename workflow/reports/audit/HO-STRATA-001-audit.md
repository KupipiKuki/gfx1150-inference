# Audit report — HO-STRATA-001

| Field | Value |
|---|---|
| **Handoff** | HO-STRATA-001 (`ARCHITECT_TO_CODER`), state at review: `AUDIT_REVIEW` (per `STATUS.md:9`; the handoff file itself still says `CODER_DONE` — see P3) |
| **Reviewer** | Auditor (`auditor`), session model **`opencode-go/deepseek-v4.1-flash`** |
| **Date (UTC)** | 2026-11-16 (audit window 01:20–01:45 UTC) |
| **Verdict** | **PASS** → `ARCHITECT_APPROVAL`, with three process findings for the architect (P1–P3) and four residual risks. **No rework.** Nothing in the coder's or QAQC's work failed an acceptance criterion. |
| **Evidence reviewed** | `workflow/evidence/HO-STRATA-001/` — `manifest.md`, `commands.log`, `test-output.txt`, `hashes.txt`, 16 `artifacts/`; recomputed here, not taken from the manifest |
| **QAQC reports** | `workflow/reports/qaqc/HO-STRATA-001-qaqc.md` §1–§6 (FAIL), §7 (re-check, PASS), §8 (separation check, PASS) |
| **Rework** | `workflow/handoffs/RW-HO-STRATA-001-1.md` — F1–F7 closed, N1–N3 recorded; **no open rework** |
| **Profile (one only)** | AMD Radeon 890M / `gfx1150` / Ryzen AI 9 HX 370, ROCm `/opt/rocm/core-10.1`, hipBLASLt `100401`, **no model loaded** |
| **Repository state** | `gfx1150-inference` `wp/strata-001-gfx1150-build`, base `a6166f7e`; tip at dispatch `1f5e104`, tip at end of audit **`5b0adec`** (moved during review — P2). Strata `/home/kupipi/Documents/git/strata` pinned `baf16363b4403ef0ed4f538f5d5ed11c43fb9535`, porcelain empty |

## 0. Disclosures

**Model / separation (declared, not hidden).** This audit runs on `opencode-go/deepseek-v4.1-flash`.
That is the **same base model family as the architect**, so `MODEL_POLICY.md` **R2** ("the Auditor
model family is exclusive to the auditor") and **R5** ("no model reviews work it produced … the
architect family ≠ any other role") are **not satisfied** by this review. It is permitted only under
**DEC-009 / WAIVER-001** (`workflow/DECISIONS.md:137-153`, `workflow/model_policy.json`), and it must
be read as `WAIVED`, not `PASS`, on the owner checklist (`workflow/OWNER_AUDIT_CHECKLIST.md:46`).

Two of the three QAQC passes also ran on this family (QAQC report §7.7 says so explicitly). So the
finding set for HO-STRATA-001 was produced three times by one family. §5.3 states exactly what an
owner should discount because of that, and what is unaffected.

**Independence of this review.** I did not take the architect's log, the QAQC report, or
`manifest.md` as proof of anything load-bearing. Every claim in §3 was re-derived by me from the
pinned Strata checkout at `baf16363` and from the bundle bytes on disk, in this session. Where I
could not verify something (the runtime model of the QAQC §8 session; the link step of the build),
I say so instead of inheriting the assertion.

`DEC-014` ("owner audit uses Mistral 4", `workflow/DECISIONS.md:239-251`) was committed to the
branch during this audit. It does not change this report's verdict: this is the **internal audit
gate**, and the owner's independent Mistral 4 audit is a separate, later checkpoint. Because
`DEC-013` fixes a subagent's model at launch, this session could not have been Mistral 4 regardless
of timing.

---

## 1. Evidence verification

- [x] **Manifest complete; commands reproducible.** `manifest.md` §1 lists 15 command rows with
      CWD and exit code for AC-1…AC-8; §2 maps each criterion to command + observed + verdict.
      I re-ran the load-bearing subset (§4) from the recorded CWDs and got the recorded results.
- [x] **Outputs raw; failures and skips kept verbatim.** Three non-zero exits are kept with their
      cause: AC-3 configure `exit=1` (`configure.log:28,43`, `Could not find a package
      configuration file provided by "hip"`), AC-4 bare `--families` `exit=127`
      (`families.txt`: `libhipblas.so.3: cannot open shared object file`), AC-5 `launch --plan`
      `exit=2` with the refusal text quoted in full. Three non-observations are declared rather
      than papered over: no model run (`manifest.md` §4.4), taken-vs-fallback unobservable
      (§4.5), no `ctest` (§4.8, and `-- strata tests: ON` is explained as *registered*, not run).
- [x] **Artifacts and hashes match.** Recomputed all 19 bundle entries and diffed against
      `hashes.txt`: **19/19 exact**. `hashes.txt` carries 21 sha256 lines = 19 bundle files + the
      pinned tuning table + the built binary; the two absolute-path lines are the pinned inputs and
      are labelled as such. `hashes.txt` correctly excludes itself (20 files tracked in git).
- [x] **Pinned inputs reproduce.** Tuning table
      `aee2867c096887cccaef8bc04a9ef10adec43da58421edfdaaec04a61ec5549c`, 146 lines, header
      `STRATA_HIPBLASLT_TUNING_V1 gfx1150 100401`. Built binary
      `d58ee2398596d1a100c15d5b9459e24bd86854cb5e5fb7ce88dbc6c7ed9f5858`, 39,736,088 B,
      mtime `2026-11-15 18:49:38 -0500` (= 23:49:38Z, which ties to `build.log`'s end window).
      Strata `HEAD` = the pin; `git status --porcelain` **empty**; `build-hip` ignored by
      `.gitignore:12 build*/`.
- [x] **Environment recorded.** `artifacts/toolchain.txt` contains every command AC-2 names —
      `uname -a`, `/etc/os-release` (Linux Mint 22.3), `dpkg -l linux-firmware`, `ls -d /opt/rocm*`,
      `hipcc --version` (HIP 7.16.26385-0000000, `InstalledDir /opt/rocm/core-10.1/lib/llvm/bin`),
      `ls -l /opt/rocm/*/lib/libhipblaslt.so*` (→ `libhipblaslt.so.1.4`), `cmake --version`
      (3.28.3), `c++ --version`, `python3 --version`, `cat /sys/module/ttm/parameters/pages_limit`
      (12050777), `rocminfo` (`gfx1150`, `AMD Radeon 890M Graphics`).
- [x] **No secrets.** Scans for `ghp_`, `github_pat_`, `sk-`, `AKIA`, `Bearer …` over the whole
      bundle: no matches (exit 1). No credentials in `commands.log`; the hipBLASLt probe's scratch
      directory is `/tmp/opencode/hblt-ver` and its source is quoted inside the artifact.
- [x] **No model weights.** No `*.gguf`/`*.safetensors`/`*.bin`/`*.pt` anywhere in the bundle; the
      largest file is `test-output.txt` at ~3.5 MB.

---

## 2. Per-criterion findings

| # | Criterion | My independent check | Verdict |
|---|---|---|---|
| 1 | Pinned commit verified | `git -C strata rev-parse HEAD` → `baf16363b4403ef0ed4f538f5d5ed11c43fb9535`; `status --porcelain` → empty; `log -1` → `2026-11-15 20:46:59 +0100 release manifest: …`. Matches `verify-pin.txt` and `pinned-commit.txt`. | **PASS** |
| 2 | Toolchain recorded | All AC-2 commands present in `toolchain.txt` with raw output and exit codes. **I rebuilt the 12-line probe myself** (`hipcc -o v v.cpp -I/opt/rocm/core-10.1/include -L/opt/rocm/core-10.1/lib -lhipblaslt`, compile exit 0, run exit 0 → `hipblasLtGetVersion = 100401`). Header constants `1/4/1` re-read. The `100401` is a measurement, not an inference from the header. | **PASS** |
| 3 | gfx1150 build | `configure.log`: literal configure `exit=1` with the verbatim CMake error; retry with `-DCMAKE_PREFIX_PATH=/opt/rocm/core-10.1` → `configure (retry 1) exit=0`, `-- Strata: HIP enabled, arch gfx1150`. `build.log` ends `[100%] Built target strata`, `build exit=0`, and carries the `file`/`sha256sum` of the binary. Binary present at the recorded size/hash, ELF PIE x86-64, `strings` shows the `gfx1150` target. **I did not re-run the link step** (proportionality — this is a documentation-integrity audit, and QAQC re-ran both configure variants); the binary is tied to the log by size + sha256 + mtime window, which is a provenance tie, not a reproducible build. That limit is stated in §6.5. | **PASS** |
| 4 | Engine support surface | Ran it: `LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib ./build-hip/strata --families` → `qwen4exp qwen35moe`, **exit 0**; `--geometry` → `flash_next`, **exit 0**. Bare run still exits 127 (host loader path, reproduced by QAQC and consistent with `ldd`). **The F1 correction is true** — see §3.1. | **PASS** |
| 5 | Control plan (no changes) | `launch-plan.txt` holds both the human and `--output json` forms, `exit=2`, refusal verbatim, with the note that this is the *Control*, not the engine binary. No model was installed, downloaded or served; `strata launch` without `--plan` never ran. AC-5 explicitly permits the refusal. | **PASS** |
| 6 | Engine-boundary note | Five headings (a)–(e), 89 lines. Every citation I re-read is correct: `cmake/strata_gpu_engine.cmake:510` `add_executable(strata src/program/generate.cpp)`, `:513` the link list, `:544` `target_link_libraries(strata PRIVATE strata_qwen35)`, `:545` `STRATA_HAVE_QWEN35=1`, all inside `:532-546 if(NOT STRATA_HIP_GFX906)`. File counts exact (src 500, include 281, strata_cli 56, strata_control 126, serve 201, apps 1018). `wc -l strata.py` → 43. `serve/server.py:1163` `popen("the Strata engine", [exe, "--serve", *args], …)`. `device.cu:41` `compiled_for`, `:53` `arch_problem`, `:61` the wave32 check. `--pack` defaults to `pack/full` and `--tokens` is the only required flag (`help.txt`: `--tokens LIST … (required)`); `--ple-gguf` is **not** parser-enforced (`generate.cpp:3724` is an optional `else if`) but is required for a correct run (`help.txt:176` "WITHOUT IT LAYER 1's PLE IS SILENTLY SKIPPED", and `generate.cpp:4820` errors under `--native`). **Headless answer "yes" holds, three independent ways** — see §3.4. | **PASS** |
| 7 | Tuning table match/fallback | Table hash, length and header re-read; `hipblasLtGetVersion` re-measured = `100401` → **MATCH** on both header fields. Gate re-read at **`src/prefill/gemm.cu:322`** `if (!table_forced && arch != "gfx1151") return nullptr;`. `:310-311` is the HIP device-query failure branch, as the rework says. `STRATA_HIPBLASLT_TUNING` is read at `:278`, **before** the gate, so the env var wins on any card; `docs/AMD_HIP.md:637` says for Radeon 890M "Setup does not use it; point `STRATA_HIPBLASLT_TUNING` at it". Therefore **default = plain hipBLAS, opt-in only**, correctly stated. Taken-vs-fallback declared unobservable without a pack — correct and not overclaimed. | **PASS** |
| 8 | Evidence bundle complete | `manifest.md`, `commands.log`, `test-output.txt`, `hashes.txt`, 16 artifacts, all tracked (20 files in git, including `hashes.txt`). The three contract-required `*.log` files are tracked **by rule** now: `.gitignore` carries `!workflow/evidence/**/*.log` and `git check-ignore commands.log` exits 1. No secrets, no weights. | **PASS** |

**No acceptance criterion failed. No REWORK is warranted.**

---

## 3. Claims vs artifacts — what I checked myself

The five load-bearing claims, re-derived at the pin in this session:

### 3.1 The `--families` → marketing-name mapping (the F1 correction)

```
$ grep -n 'FAMILY_MODEL_NAMES' serve/server.py
9695:FAMILY_MODEL_NAMES = {"qwen4exp": "qwen3.8-flash-next", "qwen35moe": "qwen3.6-35b-a3b"}
$ grep -n 'TARGET_ARCH = ' strata_control/drafting.py
476:TARGET_ARCH = "qwen4exp"    # general.architecture of the Qwen3.8-Flash-Next GGUFs
$ grep -n 'MODEL_FAMILIES_INSTALLABLE' strata_control/feed.py
155:MODEL_FAMILIES_INSTALLABLE = ("qwen4exp", "qwen35moe")
$ sed -n '3564,3576p' src/program/generate.cpp   # the list is compiled in
$ grep -n 'STRATA_HAVE_QWEN35' cmake/strata_gpu_engine.cmake
545:  target_compile_definitions(strata PRIVATE STRATA_HAVE_QWEN35=1)
```

So `qwen4exp` **is** Qwen3.8-Flash-Next and `qwen35moe` **is** Qwen3.6-35B-A3B. The statement now
in `manifest.md:51`, `manifest.md:122-138`, `commands.log:166-177`,
`HO-STRATA-001-QAQC.md:173-178` and `HO-STRATA-001.md:249-257` is **true**, and the earlier
"Qwen3.8-Flash-Next is not supported" inference is **withdrawn, not merely softened**. The
distinction "`qwen35moe` = Qwen3.6-35B-A3B ≠ Qwen3-30B-A3B" is stated in all three places, which
matters for HO-003.

### 3.2 The unsupported families (Mixtral 8x7B, Qwen3-30B-A3B, DeepSeek)

```
$ grep -rni 'mixtral' src/ include/ strata_control/                → exit=1, no output
$ grep -rni 'qwen3moe\|30b-a3b' src/ include/ strata_control/      → exit=1, no output
$ grep -n 'FAMILY = "deepseek41"' strata_control/retired.py        → 19
$ grep -n 'def _refuse_deepseek' strata_control/runtime.py         → 561
```

Absence proven by a failing grep, and DeepSeek proven to be a *retired family the Control refuses*
rather than an engine family. Correctly framed as "not implemented at `baf16363`", not as a
permanent product statement, and not widened into a support claim.

### 3.3 `gemm.cu:322` and the tuning default

```
$ grep -n 'table_forced && arch' src/prefill/gemm.cu
322:        if (!table_forced && arch != "gfx1151") return nullptr;
$ sed -n '308,313p' src/prefill/gemm.cu     # 310-311 = the device-query failure branch, not the gate
318:    if (from_package) {
...
322:        if (!table_forced && arch != "gfx1151") return nullptr;
$ grep -n 'STRATA_HIPBLASLT_TUNING' src/prefill/gemm.cu   → 278 (read before the gate)
$ grep -n 'STRATA_HIPBLASLT_TABLE'  src/prefill/gemm.cu   → 281, 290 (off), 291 (on)
```

`grep -rn '310-311' workflow/evidence workflow/handoffs/HO-STRATA-001.md workflow/handoffs/HO-STRATA-001-QAQC.md`
→ **exit 1** (zero deliverable hits; the only remaining occurrences are in the QAQC report and the
RW file, describing the defect). Citation correction complete.

`artifacts/tuning-table-raw.txt` now carries absolute numbers `255:`–`325:`; `322:` is visibly the
gate and `310:`/`311:` visibly the device-query branch, so the F2/F3 root cause is checkable from
inside the artifact rather than on trust. That is the right fix.

### 3.4 Headless-without-app/server

- `add_executable(strata src/program/generate.cpp)` with sources/link libs only under `src/`/`include/`
  (`cmake/strata_gpu_engine.cmake:510`, `:513`, `:544`).
- `strings -a build-hip/strata | grep -c 'strata_cli\|strata_control\|serve/server'` → **0**.
- `ldd build-hip/strata` → ROCm libs + libc/libstdc++/libm/libgcc; **no Python, no Node**. (My run
  resolves the full transitive ROCm set — `librocroller`, `libamd_comgr`, `libLLVM`, `librocsolver`,
  … — which the note compresses into "the ROCm math/runtime set". Every extra entry is a ROCm
  library, so the load-bearing half of the claim, "no Python, no Node", stands; see §6.4.)
- The binary ran `--families` and `--geometry` with exit 0 from a build directory containing
  neither `apps/` nor `serve/`.
- `serve/server.py:1163` shows the dependency direction: the server spawns the engine, not the
  reverse. `AGENTS.md:17` confirms the installers "carry no engine".

**Conclusion "yes, headless" is correctly evidenced.** It is also correctly bounded — the note says
this proves the binary *starts and answers*, not that a generation run works.

### 3.5 Guard rails

| Guard rail | Result |
|---|---|
| No Strata source change | **Clean.** `status --porcelain` empty; no `src/`, `include/`, `cmake/`, `docs/`, `tools/`, `third_party/` entry in `git status`; the only addition is `build-hip/`, ignored by `.gitignore:12 build*/`. I found no patch, stash entry, or untracked file. |
| No model download or run | **Clean.** No weights anywhere; AC-5 is `--plan --no-tui` only; `manifest.md` §4.4 states the engine never loaded a pack. |
| No package installs / ROCm change | **Clean.** Both host obstacles were solved with a configure flag and a loader path, not an install. `ccache` absent and left absent. |
| No performance / support / quality claim | **Clean.** Grep of `manifest.md`, `engine-boundary.md`, `tuning-table.md` for `tok/s|throughput|faster|speed` returns only disclaimers. The `1.5-1.7x` figure in `docs/AMD_HIP.md:542` is **upstream prose quoted nowhere** — it appears only in the pinned doc, not in the bundle. No support verdict is claimed. |
| One profile | **Clean.** Every claim is `gfx1150` / Radeon 890M / Ryzen AI 9 HX 370. `gfx1151`/`gfx1201` appear only inside quoted source comments that *explain the gate being audited*, never as a result. No 780M/MI25/gfx1100/gfx1103/gfx1201 work. |
| No secrets / weights | **Clean.** §1. |
| No merge, no push to `main` | **Clean.** `main` is untouched (`git log main -1` = the pre-existing merge commit); the branch is local-only in this worktree. |

---

## 4. Process integrity

This is where the serious findings are, and none of them is a coder defect.

### 4.1 P1 (Major, architect) — the branch is not a single work package, and a plain merge is a landmine

The dispatch said three workstreams. There are **four** on top of `origin/main`, and the branch is
cut from something other than `main`:

```
$ git merge-base origin/main HEAD      → 34191b4 ("7G-C: sign the gate", 2026-11-15 12:41)
$ git rev-list --count origin/main..HEAD → 29 commits, 82 files
$ git log --oneline HEAD..origin/main   → eccdc39 ("Merge PR #14 from wp/7G-C-closure")   # 1 divergent
$ git diff --name-only origin/main..HEAD | cut -d/ -f1 | sort | uniq -c
     47 workflow   14 planning   11 .opencode   9 research   1 .gitignore
```

**The base commit is not on `main`.** `a6166f7e` is the tip of `research/strata-memo`
(`git branch -a --contains a6166f7e`), and `git rev-list --count main..a6166f7e` = **52**. So the
work-package branch was cut from an *unmerged research branch*, not from `main`.

Local `main` is also stale: `git branch -vv` reports `main c68cb27 [origin/main: behind 41]`.
Therefore **`git merge wp/strata-001-gfx1150-build` into local `main` would fast-forward 69
commits** (`git merge-base --is-ancestor main HEAD` succeeds), while the same merge into
`origin/main` is a real merge of 29 commits with one divergent commit on the other side.

The 17 commits in `a6166f7e..HEAD` split as follows:

| Group | Commits | Files |
|---|---|---|
| **HO-STRATA-001 work package + reviews** | `5a64aac`*, `3bb67fc`*, `290922d`, `a34c818`, `86bed35`, `a7f303c`, `a56bc37`, `76034a0`, `1f5e104` | 20 evidence + 4 handoffs + QAQC report + `STATUS.md` + `.gitignore` + `DECISIONS.md` |
| **Model-policy workstream** (DEC-006/009/013, concurrent session) | `5a64aac`*, `3bb67fc`*, `d56a1be`, `bba7fd8`, `e4db1d5`, `59d1f08` | `MODEL_POLICY.md`, `model_policy.json`, `check_model_policy.py`, `ENGINEERING_WORKFLOW.md`, `README.md`, `SESSION_KICKOFF.md`, `.opencode/agents/{auditor,qaqc}.md`, planning/11 |
| **Planning workstream** (DEC-011/012) | `6090b5e`, `7d182b8`, part of `e4db1d5` | `planning/strata-engine/{10,11,12}`, `DECISIONS.md` |
| **Owner-audit workstream** (DEC-014) | `e47e7a3`, `5b0adec` | `workflow/OWNER_AUDIT_CHECKLIST.md`, `DECISIONS.md` |

`*` = one commit carrying **two** workstreams: `5a64aac` and `3bb67fc` each contain both evidence
files and policy files, because they were parent-session commits that swept the shared worktree.
Those two commits **cannot be cherry-picked whole** without pulling the policy workstream.

`DECISIONS.md` is touched by three groups, so it cannot be attributed to one workstream either.
`OT-STRATA-001.md` gained one row (the "Model policy applied" checkpoint) from `5a64aac`.

**Consequence for the architect:** the merge is a **selection**, not a merge. §7 says exactly what
to select and what to refuse. Nothing here is hidden: the coder disclosed the sweep in
`manifest.md:177-194` and `HO-STRATA-001.md:259-272`, QAQC filed it as F8, and `STATUS.md` still
points at `76034a0`. Credit where due — the disclosure is what makes this auditable rather than
corrupt.

### 4.2 P2 (Minor, architect) — the branch moved twice during review; the dispatch pin and `STATUS.md` are stale

- The dispatch named tip **`1f5e104`**. That was correct when this audit started
  (`git log -1` returned it). During the audit the branch advanced to **`5b0adec`**
  (`workflow: owner audit uses Mistral 4; add owner-audit record and role checks`).
- `STATUS.md:9` still records the branch at **`76034a0`**, three commits behind the tip at
  dispatch and four behind now.

I verified `git diff --name-only 1f5e104..5b0adec` → `workflow/DECISIONS.md` and
`workflow/OWNER_AUDIT_CHECKLIST.md` only. **No bundle file changed**, so every hash and every
measurement in §1–§3 is valid at `1f5e104`, at `5b0adec`, and on disk now (worktree porcelain
empty). The verdict is unaffected; the *pin* is not reproducible from `STATUS.md`, and an owner
following that line would check the wrong commit. Same class as QAQC's N4, second occurrence.
This is a shared-worktree working practice, not a coder act — but it is now a pattern.

### 4.3 The first-review false claim: correction is complete in the deliverables

The FAIL happened because the coder copied the architect's **own log error** into the manifest: an
inference read off a printed string (`--families` prints `qwen4exp`, therefore
"Qwen3.8-Flash-Next is unsupported"), propagated as a HO-002 scope observation. That is the exact
failure mode the contract exists to prevent — a claim with no artifact behind it, laundered through
a review where it looked like a finding.

Status now:

| Site | State |
|---|---|
| `manifest.md:51` (AC-4 row) | corrected, true |
| `manifest.md:122-138` (§4.6) | corrected, true, with an explicit supersede note |
| `commands.log:166-177` | corrected; the striking line `Qwen3.8-Flash-Next was not in this build's list` survives **only inside the withdrawal note** "*Corrected by RW-1 F1: an earlier version of this paragraph wrongly stated…*" |
| `HO-STRATA-001.md:249-257` | withdrawn, aligned to the architect's `:294-300` entry |
| `HO-STRATA-001-QAQC.md:173-178` (QAQC's N1) | corrected |
| `test-output.txt` (derived) | re-assembled; `grep` for the withdrawn sentence → **exit 1** |
| `artifacts/families.txt` | original 13 lines byte-intact, RW-1 block appended with the mapping greps, the compiled-list capture, both absence greps, and `exit=` for each |

**Two surviving instances I want on the record, both in immutable commit messages:**

1. **`290922d`'s message** (the reviewed coder commit) still says, in its "Limits / blockers"
   paragraph: *"`--families` omits Qwen3.8-Flash-Next, the family the cited gfx1150 bench
   measured"*, and in its results paragraph: *"AC-7 table MATCH …; default = plain hipBLAS
   (`gemm.cu:310-311`)"*. Both sentences are wrong and un-fixable without rewriting reviewed
   history, which §9 forbids. They are superseded by the bundle and by the handoff log, and no
   artifact rests on them — but `git log` is what a future reader opens first, so it is recorded
   here rather than left to be re-discovered.
2. **`a7f303c`'s message** says the QAQC-handoff citation was "reported, not edited" while the
   commit does edit it (QAQC's N3). Already recorded in `RW-HO-STRATA-001-1.md:191-196`; the
   architect authorised the edit afterwards. Stale message, correct edit, no action.

**No live claim anywhere still rests on the withdrawn inference.** The architect's own
`HO-STRATA-001.md:294-300` entry and `DEC-010`'s context both state the corrected mapping, and I
verified both against the source. The correction is complete in the places that carry claims.

### 4.4 Process bookkeeping (P3, Minor)

The state machine is recorded in three files with three values:

| File | State field |
|---|---|
| `workflow/handoffs/HO-STRATA-001.md:7` | **`CODER_DONE`** |
| `workflow/handoffs/HO-STRATA-001-QAQC.md:7` | **`QAQC_REVIEW`** |
| `workflow/STATUS.md:9` | **`AUDIT_REVIEW`** |

The QAQC transition `QAQC_REVIEW → AUDIT_REVIEW` was made on the status board but not in the
handoff file, which the contract calls the contract ("If it is not in the file, it is not in
scope"; §6 makes transitions role-exclusive records). This is not a coder error — the coder set
`CODER_DONE` correctly, and the RW explicitly held the state at `CODER_DONE` during rework. It is a
QAQC/architect bookkeeping gap, and `OWNER_AUDIT_CHECKLIST.md:87` ("STATUS.md matches the handoff
state") will fail on it. **Architect action at approval**, since the auditor may not edit handoffs.

### 4.5 Model independence — what is and is not affected

Three review passes exist: QAQC §1–§6 (DeepSeek), QAQC §7 (DeepSeek), QAQC §8 (asserted Gemini
`gemini-4-argon`). So **two of three ran on this audit's family**, which is also the architect's
family. Two things follow, and they are different in kind:

- **The measurement layer is family-independent.** Every load-bearing claim reduces to a command
  and raw output against a pinned tree: a SHA256, a 39,736,088-byte ELF, a `grep -n` line number, a
  version integer from a 12-line program, an observed exit code. I re-derived all of them myself.
  A model's beliefs cannot move a `sha256sum`. So the numeric core of this bundle does not need
  cross-family corroboration to be trusted.
- **The judgment layer is not.** "Is the finding set complete?", "is this severity right?", "is
  this overclaiming?" are where correlated blind spots live, and those came from one family three
  times. Concretely: the F1 error was *found* by a DeepSeek review, fixed by the coder, and then
  *verified* by a DeepSeek review and by me (DeepSeek). The verification of that correction is
  therefore not independent of the reviewer family — only the three `grep` lines in §3.1 are, and
  anyone can run them.
- **I cannot verify QAQC §8's runtime model.** It is a self-report in the report header. There is
  no runtime artifact in the bundle (no OpenCode usage export) that would let me confirm the fresh
  session actually ran Argon. `MODEL_POLICY.md` §4 asks for the exception to be *recorded in the
  handoff log*; `DEC-013` records the general rule, and QAQC §7.7/§8.3 assert the separation is
  satisfied. I accept that as a claim, not as verified evidence, and I flag it because the owner
  checklist tells the owner to check the usage UI (`OWNER_AUDIT_CHECKLIST.md:50-51`) — which they
  can do and I cannot.

---

## 5. DoD honesty (§9)

Every tick is genuinely true, with two caveats that are disclosed rather than concealed:

| Line | True? | Note |
|---|---|---|
| AC-1…AC-8 run; raw output; failures verbatim | **Yes** | three non-zero exits kept verbatim with diagnosis |
| Pinned SHA and toolchain recorded | **Yes** | `verify-pin.txt`, `toolchain.txt`, `hashes.txt` |
| Build attempted; exit 0 or documented blocker | **Yes** | exit 0 |
| `--families` / `--geometry` / `launch --plan` recorded | **Yes** | all three raw, plus `--output json` and `--help` |
| Engine-boundary note, five headings | **Yes** | (a)–(e) present, ≤1 page |
| Tuning match/fallback and the opt-in default stated | **Yes** | MATCH; default = plain hipBLAS; unobservable half stated |
| Strata checkout still clean | **Yes** | porcelain empty now |
| Nothing written outside `workflow/evidence/HO-STRATA-001/**` + this file | **Yes for the coder's own commits** | `290922d`, `a7f303c`, `76034a0` touch only evidence + the three handoff files. **Not true of the branch**, which carries four workstreams — disclosed, assigned to the architect (P1). |
| No secrets, no weights, no perf/support claims | **Yes** | verified independently |
| Manifest complete; `CODER_DONE`; `CODER_TO_QAQC` created | **Yes** | state field now stale (P3) |
| Committed on the WP branch; no merge, no push to `main` | **Yes** | `main` untouched |

**The one honest gap in §9's wording** is the eighth line: as written it is a claim about the tree,
and the tree carries more than the coder wrote. The coder disclosed it in three places and QAQC
filed it; nobody hid it. `RW-1`'s note that "the rework changed only prose/citations" is also true —
I checked `git show --stat a7f303c 76034a0`: no measurement artifact (`toolchain.txt`,
`configure.log`, `build.log`, `help.txt`, `geometry.txt`, `launch-plan.txt`,
`hipblaslt-version-probe.txt`, `verify-pin.txt`, `engine-deps.txt`, `boundary-layout.txt`,
`control-launch-help.txt`) appears in either commit.

---

## 6. Residual risks (carried, not defects)

1. **No model ever ran.** HO-001 proves the engine *builds* for `gfx1150`, *starts headless*, and
   *reports* its compiled surface. It does not prove a generation run works on this APU. Every
   downstream baseline (002–004, 006, 007) inherits that unproven step.
2. **Taken-vs-fallback is unobservable here.** The `gemm.cu:322` reading is sound and I verified the
   line, but the start-log line and `fallbacks=` count need a pack. HO-002 must produce them, or the
   default-vs-taken claim stays a static reading forever.
3. **The binary is not a reproducible artifact.** Only sha256 + size + mtime tie it to `build.log`.
   A fresh build on the same host is not bit-identical by contract, so "the delivered binary is the
   one built" is provenance, not proof. I did not re-run the link step; QAQC re-ran configure.
4. **One compressed dependency claim.** `engine-boundary.md` (b) lists the ROCm libs as the four
   direct ones plus libc/libstdc++/libm/libgcc. `ldd` with the loader path also resolves the ROCm
   transitive set (rocroller, comgr, LLVM, rocsolver, roctx, origami, kpack, sysdeps). The
   load-bearing part (`no Python, no Node`) is true and the verbatim artifact is honest; the prose
   understates the set. Not worth a rework — a two-word fix if the file is ever touched.
5. **No `ctest`.** HIP kernel tests were registered, not built or run on this card. AC-3 asked for
   `--target strata` only, so this is in scope — but it means the first real kernel evidence on
   gfx1150 will come from HO-002.
6. **One profile, no transfer.** Nothing here supports a claim on any other card, quant or workload.
7. **Model-correlated review** (§4.5) — measurement layer unaffected; judgment layer needs the
   owner's DEC-014 Mistral 4 pass to be genuinely independent.

---

## 7. What may be merged, and what must not

**May be selected into `main`** (content is audited and hash-matching — take all 20 bundle files
from **one** commit so `hashes.txt` stays true):

```
workflow/evidence/HO-STRATA-001/**                 (20 files: manifest, commands.log,
                                                    test-output.txt, hashes.txt, 16 artifacts)
workflow/handoffs/HO-STRATA-001.md
workflow/handoffs/HO-STRATA-001-QAQC.md
workflow/handoffs/RW-HO-STRATA-001-1.md
workflow/reports/qaqc/HO-STRATA-001-qaqc.md
workflow/reports/audit/HO-STRATA-001-audit.md      (this file)
.gitignore                                         (the `!workflow/evidence/**/*.log` negation,
                                                    DEC-008; without it the three required logs
                                                    are untracked)
```

**May be merged only by explicit decision** (shared files; do not take them blind):

- `workflow/DECISIONS.md` — carries DEC-007/008/010 (this work package) **and** DEC-011/012/013/014
  (the other workstreams). Take by hunk, or take whole and say so in `DECISIONS.md`.
- `workflow/STATUS.md` — take it, but fix the `@76034a0` pin to the merge commit (P2).
- `workflow/handoffs/OT-STRATA-001.md` — one added checkpoint row plus the auditor's status section;
  take it.

**Must not be merged without a decision of their own** (they are a different session's workstream,
outside HO-STRATA-001's scope, and `MODEL_POLICY.md` is explicitly **PENDING** — merging it puts a
policy on `main` that `check_model_policy.py --strict` fails with 3 unset roles):

```
workflow/MODEL_POLICY.md          workflow/model_policy.json
workflow/check_model_policy.py    workflow/ENGINEERING_WORKFLOW.md
workflow/README.md                workflow/SESSION_KICKOFF.md
.opencode/agents/auditor.md       .opencode/agents/qaqc.md
workflow/OWNER_AUDIT_CHECKLIST.md
planning/strata-engine/10-*.md    11-*.md    12-*.md
```

**Must not happen at all:**

- **`git merge wp/strata-001-gfx1150-build` into local `main`** — that is a **fast-forward of 69
  commits**, because local `main` (`c68cb27`) is 41 behind `origin/main` and is an ancestor of the
  tip. It would land the entire `research/strata-memo` lineage and every policy/planning commit
  under a HO-STRATA-001 merge message.
- A merge into `origin/main` that does not account for the **1 divergent commit** (`eccdc39`,
  merge-base `34191b4`).
- Force-pushing the branch to "clean it up": `ENGINEERING_WORKFLOW.md` §9 forbids rewriting shared
  branches, and `290922d` is reviewed history.
- Any claim from this bundle about a model run, throughput, or support. There is none, and none may
  be inferred.

---

## 8. Findings

| # | Severity | Finding | Required action | Owner |
|---|---|---|---|---|
| P1 | **Major (process)** | Branch carries **four** workstreams over `origin/main` (29 commits, 82 files): the HO work package, the DEC-006/009/013 model-policy workstream, the DEC-011/012 planning workstream, and the DEC-014 owner-audit workstream. Two commits (`5a64aac`, `3bb67fc`) mix evidence and policy content and cannot be cherry-picked whole. The base `a6166f7e` is the tip of `research/strata-memo`, **not** on `main`; local `main` is 41 behind `origin/main`; `git merge` into local `main` would fast-forward 69 commits. `DECISIONS.md` is shared by three groups. | **Select at merge** per §7; do not fast-forward; record the selection (or the acceptance of the extra workstreams) in `DECISIONS.md`. | Architect |
| P2 | Minor (process) | The branch moved during review: dispatch pin `1f5e104` → tip `5b0adec`; `STATUS.md:9` still says `76034a0`. Bundle content unchanged (`1f5e104..5b0adec` touches only `DECISIONS.md` + `OWNER_AUDIT_CHECKLIST.md`), so no hash is affected. Second occurrence of the N4 pattern. | Correct the `STATUS.md` pin at merge to the actual merge commit; assign HO work to a workflow-repo worktree that is not shared with other sessions, or freeze the branch during a review window. | Architect |
| P3 | Minor (process) | State field disagrees across three files: handoff `CODER_DONE`, QAQC handoff `QAQC_REVIEW`, `STATUS.md` `AUDIT_REVIEW`. The `QAQC_REVIEW → AUDIT_REVIEW` transition was never written into the handoff file. | Update the handoff state field to `AUDIT_REVIEW`/`DONE` at sign-off (auditor may not edit handoffs). | Architect |
| P4 | Minor (documentation, in history) | `290922d`'s commit message body still carries the withdrawn claim ("`--families` omits Qwen3.8-Flash-Next") and the old `gemm.cu:310-311` citation. Immutable without a history rewrite, which §9 forbids; no artifact rests on it. | None — recorded here so a future reader does not resurrect it from `git log`. If a merge commit is written, its message should point at `manifest.md` §4.6. | Architect (note only) |
| P5 | Observation | `engine-boundary.md` (b) compresses the ROCm dependency set; `ldd` resolves more ROCm transitive libs than listed. Claim "no Python, no Node" unaffected; artifact raw output is honest. | Two-word prose fix if the file is touched again. Not a rework. | Coder (next touch) |
| P6 | Observation | QAQC §8's runtime model (`gemini-4-argon`) is a self-report; no runtime artifact in the bundle proves it. `MODEL_POLICY.md` §4's "record the exception in the handoff log" is satisfied by `DEC-013` generally, not by a per-review record. | Owner checks the OpenCode usage UI (`OWNER_AUDIT_CHECKLIST.md:50-51`); tolerant of configuration-only claims elsewhere. | Architect/owner |

**Nothing else was found.** No fabricated output, no hidden failure, no unrecorded skip, no scope
taken unilaterally, no Strata source edit, no install, no secret, no weight, no perf/support/quality
claim, no cross-profile transfer.

---

## 9. Verdict

- **PASS** → `ARCHITECT_APPROVAL`. Attach this report and
  `workflow/evidence/HO-STRATA-001/` (as selected per §7).
- **No `REWORK`.** P1–P3 are architect/process actions, not coder defects; P4–P6 need no code or
  evidence change. A rework to the coder for a shared-branch composition it disclosed and cannot
  legally fix would be a wrong use of the loop.
- **The architect signs**; I do not. The signature should record: the state-field correction (P3),
  the merge selection made (P1), and that the bundle is accepted at the tip it actually merges.

---

## 10. Owner-task oversight

- **Owner task:** `OT-STRATA-001` (auditor is the intake).
- **Checkpoints met:**
  - *Build spike (001)* — **done, pending architect sign-off.** This audit is the last gate before
    it. Owner-facing acceptance criteria 1, 2 and 5 are **satisfied by this handoff**: reproducible
    build with the toolchain recorded (§2 AC-1–AC-3), `--families`/`--plan` output plus the
    engine-boundary note (§2 AC-4–AC-6), and a complete bundle with no unsupported claim (§2 AC-8,
    §3, §5). Criterion 3 (one baseline per family) and criterion 4 (Route 2 vs Route 3) are
    **not** met and are not in this handoff's scope.
  - *Model policy applied (`--strict`)* — **still pending.** `python3 workflow/check_model_policy.py
    --strict` exits **2**: architect, coder-primary and coder-secondary are `<unset>`.
  - Checkpoints 002–005 — untouched (blocked, see below).
- **Owner acceptance:** **pending.** Nothing in this audit is an owner acceptance; the owner's
  independent Mistral 4 pass (`DEC-014`, `workflow/OWNER_AUDIT_CHECKLIST.md`) comes first.
- **Open owner decisions 2–5** (packs and timebox) remain unanswered in `OT-STRATA-001` §2, and
  decision 3's option set is now partly obsolete: Qwen3-30B-A3B **is not an implemented family at
  the pin** (`grep -rni 'qwen3moe\|30b-a3b' src/ include/ strata_control/` → exit 1). Decision 2
  (Mixtral 8x7B) and decision 4 (DeepSeek) are in the same position.
- **The scope question this evidence created:** `OT-STRATA-001` §1 asks for "one small-MoE baseline
  per family: Mixtral 8x7B, Qwen3-30B-A3B, DeepSeek". At `baf16363` **none of the three is an
  implemented engine family**; the build runs `qwen4exp` (Qwen3.8-Flash-Next) and `qwen35moe`
  (Qwen3.6-35B-A3B) only. `DEC-010` already routes this correctly: HO-006 (read-only support
  investigation) first, then add the cheapest family, then low-tier tests on every supported class,
  with 002–004 **blocked on 006**. So the owner task's test-bed list needs a recorded amendment —
  either accept `DEC-010`'s support-first reordering and re-point decisions 2–4 at "which family do
  we add support for first", or explicitly descope the three-family baseline. That is an **owner
  decision**, not an architect one, and it is recorded in the OT status appended today.

---

## 11. Commands run (this session)

All reads; no build, no install, no model, no commit, no push. CWDs as shown.

```text
# repository state
git rev-parse --abbrev-ref HEAD && git log -1 --format='%H %ci %s'
git status --porcelain
git log --oneline a6166f7e..HEAD
git log --oneline main..HEAD ; git log --oneline HEAD..origin/main
for c in $(git rev-list --reverse a6166f7e..HEAD); do git show --stat $c; done
git merge-base origin/main HEAD ; git rev-list --count origin/main..HEAD
git diff --name-only origin/main..HEAD ; git diff --name-only 1f5e104..5b0adec
git merge-base --is-ancestor main HEAD ; git branch -vv ; git worktree list

# pinned input + built artifact
git -C /home/kupipi/Documents/git/strata rev-parse HEAD
git -C /home/kupipi/Documents/git/strata status --porcelain        # empty
git -C /home/kupipi/Documents/git/strata log -1 --format='%ci %s'
sha256sum /home/kupipi/Documents/git/strata/tools/hip/gfx1150-hipblaslt-100401.txt
wc -l /home/kupipi/Documents/git/strata/tools/hip/gfx1150-hipblaslt-100401.txt ; head -2 …
sha256sum /home/kupipi/Documents/git/strata/build-hip/strata
stat -c '%s %y' /home/kupipi/Documents/git/strata/build-hip/strata   # 39736088, 2026-11-15 18:49:38 -0500

# bundle hashes (19/19 match)
cd workflow/evidence/HO-STRATA-001
diff -u <(grep -E '^[0-9a-f]{64}  ' hashes.txt | grep -v '/home/') \
        <(sha256sum manifest.md commands.log test-output.txt; (cd artifacts && sha256sum *))
        → ALL_BUNDLE_HASHES_MATCH

# AC-2 hipBLASLt version — rebuilt the 12-line probe from the artifact's quoted source
mkdir -p /tmp/opencode/audit-strata001 && cd $_
cat > v.cpp <<'EOF' … hipblasLtCreate / hipblasLtGetVersion … EOF
hipcc -o v v.cpp -I/opt/rocm/core-10.1/include -L/opt/rocm/core-10.1/lib -lhipblaslt   # exit 0
LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib ./v        → hipblasLtGetVersion = 100401, exit 0
grep VERSION_MAJOR|MINOR|PATCH /opt/rocm/core-10.1/include/hipblaslt/hipblaslt-version.h  → 1/4/1

# AC-4 / AC-6 surface and binary evidence
cd /home/kupipi/Documents/git/strata
LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib ./build-hip/strata --families   → qwen4exp qwen35moe, exit 0
LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib ./build-hip/strata --geometry   → flash_next, exit 0
ldd build-hip/strata                                   # ROCm + libc/libstdc++, no python/node
strings -a build-hip/strata | grep -c 'strata_cli\|strata_control\|serve/server'   → 0
for d in src include strata_cli strata_control serve apps; do find $d -type f | wc -l; done
wc -l strata.py                                        → 43
sed -n '508,515p;530,546p' cmake/strata_gpu_engine.cmake
grep -n 'popen(' serve/server.py                       → 1163
sed -n '41,64p' src/core/device.cu ; sed -n '14,22p' AGENTS.md ; sed -n '1,20p' bin/strata

# AC-4 family mapping + unsupported families
grep -n 'FAMILY_MODEL_NAMES' serve/server.py           → 9695 qwen4exp=qwen3.8-flash-next, qwen35moe=qwen3.6-35b-a3b
grep -n 'TARGET_ARCH = ' strata_control/drafting.py     → 476 "qwen4exp"
grep -n 'MODEL_FAMILIES_INSTALLABLE' strata_control/feed.py → 155 ("qwen4exp","qwen35moe")
sed -n '3564,3576p' src/program/generate.cpp           # compiled-in list
grep -n 'STRATA_HAVE_QWEN35' cmake/strata_gpu_engine.cmake → 531, 545
grep -rni 'mixtral' src/ include/ strata_control/                        → exit 1
grep -rni 'qwen3moe\|30b-a3b' src/ include/ strata_control/              → exit 1
grep -n 'FAMILY = "deepseek41"' strata_control/retired.py                → 19
grep -n 'def _refuse_deepseek' strata_control/runtime.py                 → 561

# AC-7 tuning gate + selection rule
grep -n 'table_forced && arch' src/prefill/gemm.cu     → 322
sed -n '308,313p;318,326p' src/prefill/gemm.cu         # 310-311 = device-query branch
grep -n 'STRATA_HIPBLASLT_TUNING|TABLE|VERBOSE' src/prefill/gemm.cu     → 213,278,281,290,291,351,431
sed -n '619,640p' docs/AMD_HIP.md                      # 637: gfx1150 "Setup does not use it"
for r in 260 274 276 278 290 291 318 330 336 339 351 376; do sed -n "${r}p" … ; done

# withdrawn-claim + citation residue scans (repo root)
grep -rn '310-311' workflow/evidence workflow/handoffs/HO-STRATA-001.md …/HO-STRATA-001-QAQC.md → exit 1
grep -rn -i 'not in this build.s list|does not list Qwen3.8|not supported by this build' workflow/…
        → only the withdrawal note in commands.log:177, RW-1, and the QAQC report describing the defect
grep -n … test-output.txt                              → exit 1 (derived file clean)

# secrets / weights / hygiene
grep -rnE 'ghp_|github_pat_|sk-|AKIA|Bearer ' workflow/evidence/HO-STRATA-001/   → exit 1
find … \( -name '*.gguf' -o -name '*.safetensors' -o -name '*.bin' \)            → none
git ls-files 'workflow/evidence/HO-STRATA-001/*' | wc -l                         → 20
git check-ignore -v workflow/evidence/HO-STRATA-001/commands.log                 → exit 1 (tracked by rule)

# model policy
python3 workflow/check_model_policy.py            → PENDING: 3 roles unset (architect, coder-primary, coder-secondary)
python3 workflow/check_model_policy.py --strict   → exit 2
```

---

## 12. Statement

I did not modify code, tests, docs, evidence, handoffs, or configuration. The only files I wrote are
this report and the dated status section appended to `workflow/handoffs/OT-STRATA-001.md`; both are
inside the auditor's own remit. I made no commit, no merge, no push, and no force-push. All scratch
output went to `/tmp/opencode/audit-strata001/`. The workflow worktree was clean before and after
(`git status --porcelain` empty), and the Strata checkout remains at
`baf16363b4403ef0ed4f538f5d5ed11c43fb9535` with an empty porcelain.

The verdict is **PASS** on the evidence and **no** on a blind merge. The build is real, the surface
is real, the tuning verdict is a correct static reading that is labelled as one, and the failures
that happened are in the bundle in their own words. What the architect must not do is treat a
green audit of 40 in-window files as a green audit of the 82 files the branch would carry.
