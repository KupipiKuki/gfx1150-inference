# QAQC report — HO-STRATA-001

| Field | Value |
|---|---|
| **Handoff** | HO-STRATA-001 (`ARCHITECT_TO_CODER`) → reviewed via `CODER_TO_QAQC` `HO-STRATA-001-QAQC` |
| **Reviewer** | QAQC (`qaqc` subagent), model `opencode-go/deepseek-v4.1-flash` |
| **Date (UTC)** | 2026-11-16 (review window 00:30–00:45 UTC) |
| **Verdict** | **FAIL** — one failed criterion (**AC-4**), plus one Major and five Minor documentation defects in the AC-6/AC-7 deliverables. All measurements reproduce; the rework is documentation-only. |
| **Scope reviewed** | `wp/strata-001-gfx1150-build` `86bed35` vs base `a6166f7e` (33 files; 20 evidence + 13 non-evidence); `workflow/evidence/HO-STRATA-001/**` (manifest, commands.log, test-output.txt, hashes.txt, 16 artifacts); `artifacts/engine-boundary.md`; `artifacts/tuning-table.md`; the pinned Strata tree `baf16363b4403ef0ed4f538f5d5ed11c43fb9535` (read-only) |
| **Profile (one only)** | AMD Radeon 890M / `gfx1150` / Ryzen AI 9 HX 370, ROCm `/opt/rocm/core-10.1`, hipBLASLt `100401`, **no model loaded** |

**Role-model policy:** `workflow/MODEL_POLICY.md` is **PENDING** (`python3 workflow/check_model_policy.py` →
`PENDING: 4 role(s) have no explicit model: architect, coder-primary, coder-secondary, qaqc`; `--strict` exits 2).
The proposed QAQC model (`gemini-4-argon#high`) is **not applied**; this review ran on
`opencode-go/deepseek-v4.1-flash`, which is the **auditor's** model (`.opencode/agents/auditor.md:5`).
Therefore the QAQC/auditor separation (R2/R5) is **not satisfied for this review**, and the
"setup exception" that `MODEL_POLICY.md` §4 requires to be *recorded in the handoff log* is not
recorded anywhere (finding F9). The review itself is technically valid; its independence from the
audit step is not.

---

## 1. Acceptance criteria re-run

Re-run = I executed the command myself in this session. "From raw log" = the command was not
re-executed (see §1.1 for why) and the criterion is verified from the committed raw output plus
out-of-band corroboration. Nothing was taken from `manifest.md` on trust.

### 1.1 What I re-ran and what I verified from raw output only

| Criterion | Re-ran | Verified from raw output only | Why |
|---|---|---|---|
| AC-1 | ✅ | | cheap, decides the pin |
| AC-2 | ✅ (incl. rebuilding the hipBLASLt probe from the source quoted in `artifacts/hipblaslt-version-probe.txt`) | | the `100401` claim is load-bearing for AC-7 |
| AC-3 | ✅ configure, both variants (literal → exit 1; `+CMAKE_PREFIX_PATH` → exit 0, `-- Strata: HIP enabled, arch gfx1150`) | link/compile step | a cold rebuild was not required by the review scope; the delivered binary is tied to the logged build window by **size + sha256 + mtime 2026-11-15 18:49:38 -0500 = 23:49:38Z = `build.log` `date-utc-end`**, plus `strings` `gfx1150`/`hip-amdgcn-amd-amdhsa--gfx1150` (107 hits) and `[100%] Built target strata` / `build exit=0` in `build.log` |
| AC-4 | ✅ both `--families` (bare and with `LD_LIBRARY_PATH`) and `--geometry` | | the family list is the criterion |
| AC-5 | ✅ `--plan --no-tui` and `--output json` | | refusal must be verbatim |
| AC-6 | ✅ every cited line re-read in the pinned tree (`ldd`, `strings`, `cmake/strata_gpu_engine.cmake`, `src/core/device.cu`, `serve/server.py`, `AGENTS.md`, `strata.py`, `bin/strata`) | | claims must be checked against the files they cite |
| AC-7 | ✅ `sha256sum`, `head -2`, every `gemm.cu`/`hipblaslt_tuning.hpp`/`docs/AMD_HIP.md` citation, and the version probe | | the "default = fallback" verdict depends on one line of C++ |
| AC-8 | ✅ full `sha256sum` recomputation of the bundle, secrets scan, weight scan | | integrity is the QAQC gate |

### 1.2 Results

| # | Criterion | Command (as re-run) | Observed (my run) | Pass? |
|---|---|---|---|---|
| 1 | Pinned commit verified | `cd /home/kupipi/Documents/git/strata && git rev-parse HEAD; git status --porcelain; git check-ignore -v build-hip` | `baf16363b4403ef0ed4f538f5d5ed11c43fb9535`; porcelain **empty**; `.gitignore:12:build*/  build-hip`; origin `https://github.com/Niko1221/Strata` | **PASS** |
| 2 | Toolchain recorded | `uname -a`; `/etc/os-release`; `dpkg -l linux-firmware`; `hipcc --version`; `cmake --version`; `c++ --version`; `python3 --version`; ttm; `hipblaslt-version.h`; `rocminfo`; probe rebuilt in `/tmp/opencode/qaqc-strata001/hblt-ver` | kernel 7.0.0-42-generic; Linux Mint 22.3; linux-firmware 20240318.git3b128b60.0ubuntu3.1; HIP 7.16.26385-0000000 (clang 24.0.0git); CMake 3.28.3; g++ 13.3.0; Python 3.14.10; ttm 12050777; header 1.4.1; `libhipblaslt.so.1 → .1.4`; `Name: gfx1150` / `Marketing Name: AMD Radeon 890M Graphics`; **my probe build: `hipblasLtGetVersion = 100401`, compile exit 0, run exit 0** | **PASS** |
| 3 | gfx1150 build | `cmake -S . -B /tmp/.../b1 …` then `… -DCMAKE_PREFIX_PATH=/opt/rocm/core-10.1` → `b2`; `ls -l/sha256sum/file build-hip/strata`; `build.log` tail | b1 **exit 1**, `CMake Error at cmake/hip_backend.cmake:58 (find_package): Could not find a package configuration file provided by "hip"`; b2 **exit 0**, `-- Strata: HIP enabled, arch gfx1150`, `-- strata tests: ON - cpu, hip`, `-- Configuring done (3.3s)`; binary 39,736,088 B, sha256 `d58ee2398596d1a100c15d5b9459e24bd86854cb5e5fb7ce88dbc6c7ed9f5858`, ELF PIE x86-64; `build.log`: `[100%] Built target strata`, `build exit=0` (link step from raw log, §1.1) | **PASS** (documented host-env fix, no source change) |
| 4 | Engine support surface | `./build-hip/strata --families` (bare); `LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib ./build-hip/strata --families`; `… --geometry` | bare **exit 127** (`libhipblas.so.3: cannot open shared object file`); with loader path `qwen4exp qwen35moe` **exit 0**; `flash_next` **exit 0**. Output and transcription are correct — **but the "unsupported families named" element is factually wrong** (F1) | **FAIL** |
| 5 | Control plan (no changes) | `python3 strata.py launch --plan --no-tui; echo $?`; `… --output json` | `strata: No model fits this computer by Strata's rules, and none was chosen. Name one with --model (strata launch --help lists them); a bigger one will run slowly.` **exit 2**; JSON `{"schema_version": 1, "ok": false, "error": {"code": 2, "message": "…"}}` **exit 2**. Refusal recorded verbatim, as AC-5 permits; no model installed, downloaded or served | **PASS** |
| 6 | Engine-boundary note | re-read every citation: `ldd`, `strings … \| grep -c`, `sed -n '505,520p' cmake/strata_gpu_engine.cmake`, `sed -n '524,548p'` (same file), `grep -n 'Popen\|subprocess' serve/server.py`, `grep -n 'bool compiled_for\|warpSize != 32' src/core/device.cu`, `find … -type f \| wc -l`, `wc -l strata.py`, help text | Headings (a)–(e) present, ≤1 page (89 lines). Verified: `ldd` = 4 ROCm libs (`not found` until `LD_LIBRARY_PATH`) + libc/libstdc++/libm/libgcc, **no Python/Node**; `strings … grep -c 'strata_cli\|strata_control\|serve/server'` → **0**; `add_executable(strata src/program/generate.cpp)` at `:510`; `serve/server.py:1163` popen of the binary; `device.cu:41` `compiled_for`, `:53` `arch_problem`, `:61` `warpSize != 32`; file counts `src 500 / include 281 / strata_cli 56 / strata_control 126 / serve 201 / apps 1018` all exact. Three descriptive errors (F4–F6); the **headless answer "yes" is correctly evidenced three ways** | **PASS** (3 Minor defects) |
| 7 | Tuning table match/fallback | `sha256sum tools/hip/gfx1150-hipblaslt-100401.txt`; `wc -l`; `head -2`; `grep -n 'table_forced && arch' src/prefill/gemm.cu`; `sed -n '255,340p'`; `sed -n '20,80p' src/prefill/hipblaslt_tuning.hpp`; `sed -n '615,645p' docs/AMD_HIP.md`; version probe | SHA256 `aee2867c…ec5549c` = Architect's pin record; 146 lines; header `STRATA_HIPBLASLT_TUNING_V1 gfx1150 100401`; runtime **100401** (measured by me); `HipLtTable::load` rejects on arch (`:61-66`) and version (`:67-71`); **default = fallback**: `if (!table_forced && arch != "gfx1151") return nullptr;` at **`gemm.cu:322`**; `docs/AMD_HIP.md:637` "Setup does not use it; point `STRATA_HIPBLASLT_TUNING` at it"; taken-vs-fallback explicitly **not** claimed, "cannot be observed without a model run" stated. Verdict words are correct and **not** overclaimed — but the gate is cited as `gemm.cu:310-311` in six places (F2) | **PASS** (1 Major citation defect) |
| 8 | Evidence bundle complete | `sha256sum manifest.md commands.log test-output.txt artifacts/*.*` vs `grep -E '^[0-9a-f]{64}  ' hashes.txt`; `sha256sum` of the table and the binary; secrets/weight scans | **All 19 listed files match `hashes.txt` exactly**; table and binary hashes match; 16 artifacts; secrets scan (`ghp_/github_pat_/sk-/AKIA/Bearer/password=/api_key=`) → **no matches**; no `*.gguf`/`*.safetensors`/`*.bin`, no file >10 M (largest is `test-output.txt`, 3.6 M); `commands.log`/`build.log`/`configure.log` now tracked by rule (`.gitignore` negation, DEC-008), not `-f` | **PASS** |

---

## 2. Diff and guard-rail review

- [x] **Diff within scope for the coder's own writes.** `git diff a6166f7e..HEAD --name-status` → 33 files: 20 under `workflow/evidence/HO-STRATA-001/`, the two handoffs, plus 11 bookkeeping/policy files. The coder's own writing is confined to the evidence bundle and the two handoff files, as §6 requires.
- [~] **No unrelated files — with a disclosed exception (F8).** The branch also carries a *different* workstream: `MODEL_POLICY.md`, `check_model_policy.py`, `model_policy.json`, `ENGINEERING_WORKFLOW.md`, `README.md`, `SESSION_KICKOFF.md`, `.opencode/agents/auditor.md`, `OT-STRATA-001.md` — authored by concurrent parent-session commits `5a64aac` / `3bb67fc` ("DeepSeek Auditor <auditor@localhost>") that swept the coder's staged paths, plus the architect's bookkeeping `a34c818` (`.gitignore`, `DECISIONS.md`, `STATUS.md`) and `86bed35` (`STATUS.md`). Disclosed by the coder in `manifest.md:165-182` and `HO-STRATA-001.md:255-281`; not fixed by rewriting shared history (§9), correctly.
- [x] **No new dependencies.** No `pip`/`apt`/ROCm change; `ccache` absent and left absent; the only build inputs are vendored (`third_party/strata-ggml`) plus ROCm already on the host.
- [x] **No secrets/tokens.** Bundle scan clean; no credentials in the diff; no model weights (none fetched).
- [x] **No skip hidden as a pass.** `manifest.md` §4.8 declares "No test suite was run" (`--target strata` only; `-- strata tests: ON` = registered, not run). `manifest.md` §4.4 declares the engine never ran a model. `manifest.md` §4.5 declares the taken-vs-fallback half unobservable. The two non-zero first runs (configure exit 1, `--families` exit 127) are kept verbatim with diagnosis.
- [x] **Evidence matches the commands.** Spot-checked `test-output.txt` against `artifacts/`: the AC-4 section is byte-identical to `artifacts/families.txt` (including the `exit=127` attempt and the retry). `test-output.txt` = 33,764 lines ≈ build.log 32,376 + the other sections.
- [x] **Strata tree untouched.** `git status --porcelain` empty at review time, HEAD = the pin, `build-hip` ignored by `.gitignore:12 build*/`. No `src/`, `include/`, `cmake/`, `docs/`, `tools/`, `third_party/` change.
- [x] **No merge, no push to `main`.** Branch `wp/strata-001-gfx1150-build` at `86bed35`; worktree clean after my review.
- [x] **No performance / support / quality claim.** Grep of the bundle for `tok/s|faster|throughput|performance` returns only disclaimers. One profile only (890M `gfx1150`). `launch --plan` exit 2 is presented as the documented refusal, not a success or a hidden failure.

---

## 3. Findings (severity order)

| # | Severity | Finding | File:line / evidence | Required action |
|---|---|---|---|---|
| **F1** | **Major (fails AC-4)** | **False claim.** The bundle states that the build does **not** support Qwen3.8-Flash-Next because `--families` prints `qwen4exp qwen35moe`. `qwen4exp` **is** the GGUF architecture of Qwen3.8-Flash-Next: `serve/server.py:9695` `FAMILY_MODEL_NAMES = {"qwen4exp": "qwen3.8-flash-next", "qwen35moe": "qwen3.6-35b-a3b"}`; `strata_control/drafting.py:476` `TARGET_ARCH = "qwen4exp"  # general.architecture of the Qwen3.8-Flash-Next GGUFs`; `strata_control/feed.py:153-155` `MODEL_FAMILIES_INSTALLABLE = ("qwen4exp", "qwen35moe")` = "GGUF architectures the engine runs: `strata --families`"; `src/program/generate.cpp:3566` "the GGUF architectures this build runs". No command in `commands.log` supports the coder's inference — it is a claim without an artifact, and it was carried to the architect as a HO-002 scope observation before the architect corrected it (`HO-STRATA-001.md:290-296`). | `manifest.md:51` (AC-4 row), `manifest.md:122-126` (§4.6), `commands.log:166-169`, `HO-STRATA-001.md:249-251` and `:215-231` | Rewrite to: `qwen4exp` = Qwen3.8-Flash-Next, `qwen35moe` = Qwen3.6-35B-A3B; unsupported = every other family. Delete observation (i) (or restate it as the architect's, with the mapping). Add the mapping to `artifacts/families.txt` as `grep -n 'FAMILY_MODEL_NAMES' serve/server.py`, `grep -n 'TARGET_ARCH' strata_control/drafting.py`, `grep -n 'MODEL_FAMILIES_INSTALLABLE' strata_control/feed.py`. Regenerate `hashes.txt`. |
| **F2** | **Major** | The load-bearing AC-7 citation is wrong. The gfx1151 gate is quoted as `gemm.cu:310-311`; `310-311` is actually the *HIP device-query failure* branch (`if (hipGetDevice(…) != hipSuccess …`). The quoted line `if (!table_forced && arch != "gfx1151") return nullptr;` is **`src/prefill/gemm.cu:322`**. The conclusion (default = plain hipBLAS on gfx1150) is **true and I verified it at `:322`**; only the pointer is wrong. A reviewer following the citation lands on unrelated code. | `artifacts/tuning-table.md:39`, `:48`, `:88`; `commands.log:238`; `manifest.md:54` (AC-7 row), `:118` (§4.5); `HO-STRATA-001.md:241` | `310-311` → `322` in all six places. |
| F3 | Minor | Remaining `gemm.cu` line references drift from the pinned file (same root cause): `:285-289` for `STRATA_HIPBLASLT_TABLE=off` → **`:290`**; `:290` for `=on` → **`:291`**; `:334` for the start-log line → **`:336`**; `:346-379` for the verbose fallbacks → **`:351-376`**; `:276-337` for `create_hipblaslt_state` → **`:276-339`**. All five claims are true; the numbers are not. | `artifacts/tuning-table.md:66-69`, `:72`, `:39` | Correct the five references. |
| F4 | Minor | `strata.py` is described as "a 5-line stdlib entry point". It is **43 lines** (stdlib-only, imports `strata_cli.cli` in `__main__`). "stdlib-only" is right; "5-line" is not. | `artifacts/engine-boundary.md:13` | "a 43-line stdlib-only entry point". |
| F5 | Minor | "`--pack` and `--tokens` are the only required pair". `--pack` has a default (`pack/full`); the only required flag is `--tokens` (or `--tokens-file`). | `artifacts/engine-boundary.md:87` vs `artifacts/help.txt:6-10` | "`--tokens` (or `--tokens-file`) is the only required flag; `--pack` defaults to `pack/full`; `--ple-gguf` is not enforced but is required for a correct run". |
| F6 | Minor | The `strata` target's link libraries are cited to `cmake/strata_gpu_engine.cmake:513`, which lists only `strata_engine strata_prefill strata_spec` + runtime. `strata_qwen35` is added at **`:544`** (`target_link_libraries(strata PRIVATE strata_qwen35)`, inside `if(NOT STRATA_HIP_GFX906)`, `:532-546`). The list in the note is correct; the citation does not show it. | `artifacts/engine-boundary.md:12` | Cite `:510` + `:513` + `:544`. |
| F7 | Minor | The raw AC-7 excerpt is mislabelled "`src/prefill/gemm.cu around 259-320`" while its content runs to line 325 — the origin of F2/F3 (the gate was counted back from a wrong label). | `artifacts/tuning-table-raw.txt` (section header) | Correct the header to `259-325` (and `325-395` → keep), or re-capture with `cat -n`. |
| F8 | Process (architect) | The work-package branch mixes two workstreams (see §2). The DoD line "nothing written outside `workflow/evidence/HO-STRATA-001/**` + this file" is true for the coder's own writes but **not** for the branch: `MODEL_POLICY.md`, `check_model_policy.py`, `model_policy.json`, `ENGINEERING_WORKFLOW.md`, `README.md`, `SESSION_KICKOFF.md`, `.opencode/agents/auditor.md`, `OT-STRATA-001.md` also differ from base. Disclosed, not hidden. | `manifest.md:165-182`; `HO-STRATA-001.md:255-268`; commits `5a64aac`, `3bb67fc`, `a34c818`, `86bed35` | Architect: do not fast-forward the whole branch to `main`; select the HO-STRATA-001 content (or accept the policy files knowingly) at merge, and say which in `DECISIONS.md`. No coder action. |
| F9 | Process (architect/auditor) | Role-model policy is `PENDING` and QAQC is unset; this review ran on the auditor's model (`deepseek-v4.1-flash`), so QAQC→Audit separation is absent, and the "setup exception" required by `MODEL_POLICY.md` §4 is not recorded in either handoff log. | `workflow/check_model_policy.py` output (`PENDING: 4 role(s) … qaqc`; `--strict` exit 2); `.opencode/agents/auditor.md:5`; no hit for `model.policy` in either handoff | Architect: record the identity/exception in the handoff log now; apply the policy before HO-002. No coder action. |

**Nothing else was found.** In particular: no fabricated output, no hidden failure, no scope change taken unilaterally, no source edit in the Strata tree, no perf/support/quality claim, no secret, no model weight. The two host obstacles (configure `CMAKE_PREFIX_PATH`, runtime `LD_LIBRARY_PATH`) are documented, diagnosed, and were **not** "fixed" by editing Strata source or installing anything — I reproduced both behaviours myself (exit 1 → exit 0 with the flag; exit 127 → exit 0 with the loader path).

---

## 4. Verdict and next state

**FAIL** → `REWORK` (from `QAQC_REVIEW`). Scope of rework: **documentation and its hashes only** — no rebuild, no re-measurement, no Strata change, no dependency, no new artifact beyond the three `grep` lines in F1.

Per my scoping instruction I wrote only this report; the rework record below is complete and can be filed verbatim as `workflow/handoffs/RW-HO-STRATA-001-1.md` by the architect/auditor (or on request).

```text
RW-HO-STRATA-001-1  (REWORK, qaqc → coder-primary)
Failed criterion: AC-4 "Engine support surface" — element "unsupported families named"
  is factually wrong (F1). Supporting defects in AC-6 (F4–F6) and AC-7 (F2, F3, F7)
  are documentation accuracy, not measurement failures.
Exact evidence that failed:
  manifest.md:51 / :122-126, commands.log:166-169, HO-STRATA-001.md:249-251 claim
  "Qwen3.8-Flash-Next is not in this build's family list". Refuted at the same pin by
  serve/server.py:9695 {"qwen4exp": "qwen3.8-flash-next", ...},
  strata_control/drafting.py:476 TARGET_ARCH = "qwen4exp" # Qwen3.8-Flash-Next GGUFs,
  strata_control/feed.py:153-155 MODEL_FAMILIES_INSTALLABLE = ("qwen4exp","qwen35moe").
Required fix: F1 (rewrite + add the three greps to artifacts/families.txt), F2 (six
  citations 310-311 → 322), F3 (five line numbers), F4, F5, F6, F7; then regenerate
  hashes.txt over the changed files and commit on wp/strata-001-gfx1150-build.
Guard rails: fix only these; do NOT rebuild, do NOT re-measure, do NOT touch the
  Strata checkout, do NOT modify the acceptance criteria, no new files outside the
  bundle, no dependency, no scope expansion.
Evidence required to prove the fix: `grep -n` output for each corrected citation in
  artifacts/tuning-table-raw.txt, the corrected statements, and `sha256sum` of the
  changed files matching the regenerated hashes.txt.
Re-checked by: qaqc.
```

Not in the rework (architect/auditor decisions): F8 (branch composition) and F9 (model policy). Neither is a coder defect and neither may be fixed by rewriting shared history.

---

## 5. Residual risks (carried, not defects)

1. **No model ever ran.** This handoff proves the engine *builds* for `gfx1150`, *starts* headless, and *reports* its compiled surface. It does not prove a generation run works on this card. `manifest.md` §4.4 states this; I agree with the framing.
2. **Taken-vs-fallback is unobservable here.** The static reading of `gemm.cu:322` is sound (I verified the line), but the start-log line and the `fallbacks=` count do not exist without a pack. HO-STRATA-002+ must produce them.
3. **`build-hip/strata` is not a committed artifact.** Only its sha256 is recorded; a fresh build is not bit-reproducible by contract, so the hash is provenance, not verifiable output. My verification therefore rests on configure (re-run), `build.log` (exit 0, `Built target strata`) and the mtime/size/hash tie to the log window — stated in §1.1 rather than papered over.
4. **No `ctest`.** The suite was registered (`-- strata tests: ON - cpu, hip`), not built or run. Out of scope per AC-3, but it means HIP kernel tests have not run on this card in this handoff.
5. **One profile.** Nothing here transfers to 780M/gfx1103, gfx1151, or any NVIDIA path.
6. **Single-model review.** Because QAQC ran on the auditor's family (F9), the usual cross-family catch did not occur for this report; the auditor should read F1 and F2 against the source lines themselves.

---

## 6. Statement

I did not modify code, tests, docs, configuration, evidence, or handoffs. This report is the
only file I wrote. Every command above was run in this session in
`/home/kupipi/Documents/git/strata` (read-only) or `/home/kupipi/Documents/git/gfx1150-inference`
(read-only); all scratch output went to `/tmp/opencode/qaqc-strata001/`. No commit, no merge, no
push. The workflow worktree was clean (`git status --porcelain` empty) before and after this review,
and the Strata tree is still at `baf16363b4403ef0ed4f538f5d5ed11c43fb9535` with an empty porcelain.
