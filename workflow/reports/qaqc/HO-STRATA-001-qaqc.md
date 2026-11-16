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

---

# 7. Re-check after RW-HO-STRATA-001-1 — FINAL VERDICT: **PASS** → `AUDIT_REVIEW`

> **This section supersedes the header's verdict for the audit gate.** Sections 1–6 above are the
> first pass and are preserved unedited (FAIL is the historical verdict); this is the re-check of
> the rework only.

| Field | Value |
|---|---|
| **Reviewer / model** | QAQC (`qaqc`), session model **`opencode-go/deepseek-v4.1-flash`** (see §7.7 — the agent file now declares `gemini-4-argon#high`; *this session did not run on it*) |
| **Date (UTC)** | 2026-11-16, re-check window 00:45–00:58 UTC |
| **Subject** | `RW-HO-STRATA-001-1` fixes only (F1–F7). Criteria already passed were **not** re-opened; no build was re-run |
| **Commit re-checked** | `a7f303c` ("RW-HO-STRATA-001-1: correct the family mapping and the tuning-gate citations"), amended once from `5308507` — the amend rewrote only the coder's own unreviewed RW commit; `290922d` (the reviewed commit) still exists at the same SHA and is an ancestor |
| **Tip when re-checked** | `6090b5e` (see §7.5 N4 — the dispatch named `a56bc37`, which is an ancestor) |
| **Final verdict** | **PASS** — all seven findings closed and re-derived independently; two Minor residues (N1, N2) do not affect any claim in the evidence bundle |

## 7.1 Per-finding outcome

| # | Finding (first pass) | Outcome | Evidence I produced |
|---|---|---|---|
| **F1** | AC-4 false claim: "`--families` does not list Qwen3.8-Flash-Next" | **FIXED** | Withdrawn in all four places (`manifest.md:51`, `:120-140` §4.6; `commands.log:167-178`; `HO-STRATA-001.md:249-256`), each with an explicit "withdrawn / corrected by RW-1" note that keeps the history readable; mapped to the verified text. `artifacts/families.txt:15-65` now carries the mapping greps, the compiled-list capture, and both absence greps with exit codes. `qwen35moe` = Qwen3.6-35B-A3B is stated as **distinct** from Qwen3-30B-A3B in `manifest.md:139-140`, `commands.log:174-175` and `families.txt:57` |
| **F2** | Gate cited as `gemm.cu:310-311` (actual `:322`) | **FIXED** | `grep -rn '310-311' workflow/` → **exit 1** (the only remaining hits are this report and the RW, which quote the defect). All six places now say `:322`, and `:322` is the line I re-read in the pin |
| **F3a–f** | drifts `276-337`, `310-328`, `285-289`, `290`, `346-379`, `334` | **FIXED** | `tuning-table.md` now `276-339`, `318-330`, `290`, `291`, `351-376`, `336` — each verified against the pinned `gemm.cu` (the `from_package` block really is `318-330`; off-check `290`, on-check `291`, start line `336`, verbose fallbacks `351-376`) |
| **F4** | `strata.py` called "5-line" | **FIXED** | "**43-line** stdlib-only entry point (`wc -l strata.py` → 43)"; `wc -l` re-run = 43 |
| **F5** | "`--pack` and `--tokens` are the only required pair" | **FIXED** | "`--tokens` (or `--tokens-file`) is the only **required** flag; `--pack` defaults to `pack/full`" — matches `artifacts/help.txt:6-10` |
| **F6** | link libs cited to `:513` only | **FIXED** | "`:510` … `:513` and, inside `if(NOT STRATA_HIP_GFX906)` (`:532-546`), against `strata_qwen35` (`:544`)"; `:545` correctly carries `STRATA_HAVE_QWEN35=1` |
| **F7** | excerpt header mislabelled `259-320` | **FIXED** (label matches the capture; see N2) | Header `lines 255-325`; I confirmed `gemm.cu:255` is `};` (the capture's first line) and `:325` is the `path_own = …` line (its last), so `255-325` is the true range — the coder's justification for departing from my `259-325` suggestion is **correct** and I accept it |

**No overclaim was introduced.** The corrected text still says the API prints *architectures*, still
says the taken-vs-fallback half is unobservable without a model, and `families.txt:18` labels the new
block "these are reads at the pin; no new measurement". The unimplemented-family statement is the
conservative one (Mixtral 8x7B / Qwen3-30B-A3B / DeepSeek), not a widening of the support claim.

## 7.2 Commands run (raw output, key ones)

Mapping re-derived by me at `/home/kupipi/Documents/git/strata` (HEAD `baf16363b4403ef0ed4f538f5d5ed11c43fb9535`):

```
$ grep -n 'FAMILY_MODEL_NAMES' serve/server.py
9695:FAMILY_MODEL_NAMES = {"qwen4exp": "qwen3.8-flash-next", "qwen35moe": "qwen3.6-35b-a3b"}
9719:    return cfg.get("model_name") or FAMILY_MODEL_NAMES.get(cfg.get("arch") or "qwen4exp", "qwen3.8-flash-next")
$ grep -n 'TARGET_ARCH = ' strata_control/drafting.py
476:TARGET_ARCH = "qwen4exp"        # general.architecture of the Qwen3.8-Flash-Next GGUFs (tools/gguf_writer.py)
$ grep -n 'MODEL_FAMILIES_INSTALLABLE' strata_control/feed.py
155:MODEL_FAMILIES_INSTALLABLE = ("qwen4exp", "qwen35moe")
$ grep -rni 'mixtral' src/ include/ strata_control/            → exit=1 (no output)
$ grep -rni 'qwen3moe\|30b-a3b' src/ include/ strata_control/  → exit=1 (no output)
$ grep -n 'FAMILY = "deepseek41"' strata_control/retired.py    → 19:FAMILY = "deepseek41"
$ grep -n 'def _refuse_deepseek' strata_control/runtime.py      → 561:def _refuse_deepseek(name: str) -> None:
$ grep -n 'table_forced && arch' src/prefill/gemm.cu            → 322:        if (!table_forced && arch != "gfx1151") return nullptr;
$ sed -n '255p;325p' src/prefill/gemm.cu                        → };   /   path_own = dir + arch + "-hipblaslt-" + ... + ".txt";
```

F2 residue scan:

```
$ grep -rn '310-311' workflow/ | grep -v reports/qaqc/HO-STRATA-001-qaqc.md | grep -v handoffs/RW-HO-STRATA-001-1.md
exit=1
```

Withdrawn claim scan (bundle + handoff):

```
$ grep -rn 'not in this build.s list\|is not in this build' workflow/evidence/HO-STRATA-001/test-output.txt
exit=1
```

## 7.3 Evidence integrity at the re-checked tip

```
19/19 bundle files: sha256sum <file> == the declared line in hashes.txt   (no MISMATCH)
aee2867c096887cccaef8bc04a9ef10adec43da58421edfdaaec04a61ec5549c  .../tools/hip/gfx1150-hipblaslt-100401.txt   (unchanged)
d58ee2398596d1a100c15d5b9459e24bd86854cb5e5fb7ce88dbc6c7ed9f5858  .../build-hip/strata                        (unchanged)
git -C .../strata rev-parse HEAD                        → baf16363b4403ef0ed4f538f5d5ed11c43fb9535
git -C .../strata status --porcelain                    → (empty)
```

`hashes.txt` is regenerated (52/0 lineage kept: `families.txt` is **additions only**, 52 lines,
0 deletions — the original AC-4 capture is byte-intact) and declares the new generation time
`2026-11-16T00:50:29Z`.

## 7.4 Scope and drift review of `a7f303c`

- `git show --stat a7f303c` → **11 files, documentation/evidence only**: `manifest.md`,
  `commands.log`, `hashes.txt`, `test-output.txt`, `artifacts/families.txt`,
  `artifacts/engine-boundary.md`, `artifacts/tuning-table.md`, `artifacts/tuning-table-raw.txt`,
  `HO-STRATA-001.md`, `HO-STRATA-001-QAQC.md`, and the RW file.
- **No measurement artifact was touched** — `toolchain.txt`, `configure.log`, `build.log`,
  `help.txt`, `geometry.txt`, `launch-plan.txt`, `hipblaslt-version-probe.txt`, `verify-pin.txt`,
  `engine-deps.txt`, `boundary-layout.txt`, `control-launch-help.txt`, `pinned-commit.txt` are all
  absent from the diff. No rebuild, no re-run, no re-measurement: confirmed by the diff, not by the
  commit message.
- **`test-output.txt` re-assembled** (a derived concatenation): it now contains the RW-1 mapping
  section (`:32934`), contains **no** occurrence of the withdrawn claim, and its AC-4 block still
  reproduces `artifacts/families.txt` verbatim. Nothing in it contradicts the corrected statements.
- **`290922d` untouched**; no force-push of reviewed history; branch-only, no merge, no push to
  `main`.
- Strata checkout untouched; `build-hip/` still ignored.

## 7.5 New findings (none blocking)

| # | Severity | Finding | Location | Required action |
|---|---|---|---|---|
| N1 | Minor | The withdrawn claim survives in a **fifth** place: "*`--families` omits Qwen3.8-Flash-Next — flagged to the Architect as an observation for HO-002+, not an AC-4 failure.*" That is the F1 falsehood, still in the coder→QAQC handoff the auditor reads. It was **not** in my RW's enumerated list — **my under-scoping**, not a coder miss; the coder corrected the four places I named. | `workflow/handoffs/HO-STRATA-001-QAQC.md:173-174` (§7 item 6) | Architect: authorize this one 2-line correction (same class as F1, no re-measurement) before signing, or record explicitly that `manifest.md` §4.6 supersedes it. Until then the auditor should read it as superseded |
| N2 | Minor | The F7 header claims "*absolute file line numbers*", but the re-captured `255-325` block carries **no** line numbers (0 numbered lines in the block). The *range* is correct; the parenthetical is not — and an unnumbered capture is exactly what produced F2/F3 | `artifacts/tuning-table-raw.txt:75` | Coder, next touch: either re-capture with `cat -n`-style absolute numbering (a read) or drop the parenthetical. Not worth its own commit |
| N3 | Minor | `a7f303c`'s message says `HO-STRATA-001-QAQC.md:170` was "*reported, not edited*", but the commit **does** edit it (`310-311`→`322`), i.e. one file outside the RW's allowed list. The edit is correct and desirable; the message is stale from the pre-amend version | `a7f303c` message vs its diff | No action — history is not rewritten; recorded so the auditor is not surprised |
| N4 | Observation (architect) | The branch tip moved from the dispatched `a56bc37` to **`6090b5e`** during this re-check: a concurrent session committed `planning/strata-engine/12-large-model-support-investigation.md` + `DECISIONS.md` (that file was still untracked when I started). Neither touches the evidence bundle, but it extends **F8** (branch composition) — the branch is a shared worktree branch, not a clean single-work-package branch | `git log`, `git status`, `6090b5e --stat` | Architect: same decision as F8 at merge |

## 7.6 What the auditor should check first

1. **N1** — `HO-STRATA-001-QAQC.md:173-174`: read it as superseded by `manifest.md` §4.6, or wait for the
   architect-authorized one-liner. It is the only place left in `workflow/` where the withdrawn claim
   still stands.
2. **The corrected statement itself** (F1) against `serve/server.py:9695` — one command, ten seconds:
   `grep -n FAMILY_MODEL_NAMES serve/server.py` in `/home/kupipi/Documents/git/strata`.
3. **`gemm.cu:322`** (F2) — `grep -n 'table_forced && arch' src/prefill/gemm.cu`. Do not look at
   `310-311`; those lines are the device-query failure branch, which is what made the original
   citation wrong.
4. **That nothing measured moved**: the tuning-table SHA256 (`aee2867c…ec5549c`) and the binary
   SHA256 (`d58ee239…f5858`) are identical to the first-pass bundle, and no measurement artifact
   appears in `a7f303c`.
5. **N2** — if you cite the raw excerpt, cite the *range* (`255-325`), not line numbers printed in it.

## 7.7 Role-model note (uncomfortable, but it is the fact)

`workflow/check_model_policy.py` now reports `qaqc → opencode-go/gemini-4-argon#high` (family
`gemini`), `auditor → deepseek-v4.1-flash` (family `deepseek`), and `PENDING: 3 role(s)` for the
architect and the two coders. **But the configuration is not what ran.** This session's model is
`opencode-go/deepseek-v4.1-flash` — the **auditor's** family. So this re-check had *no* coder/QAQC
or QAQC/auditor separation at runtime (MODEL_POLICY R4/R5), despite the agent file. If the architect
wants this report to count as the first review with real separation, it must be produced by a
session actually running `gemini-4-argon#high`; as delivered it is not, and the policy check's
`gemini` row is a statement about configuration only.

## 7.8 Statement

I modified nothing in the code, tests, docs, evidence bundle, handoffs, or configuration. This is the
only file I changed (this appended section; sections 1–6 are byte-identical to the version the
architect committed at `a56bc37`). All commands were reads in `/home/kupipi/Documents/git/strata`
and `/home/kupipi/Documents/git/gfx1150-inference`; scratch output went to
`/tmp/opencode/qaqc-strata001/`. No commit, no merge, no push. The Strata tree remains at
`baf16363b4403ef0ed4f538f5d5ed11c43fb9535` with an empty porcelain.

**Final verdict: PASS → `AUDIT_REVIEW`** (auditor), with N1/N2/N3 carried as Minor and N4 as an
architect observation.

---

# 8. Independent separation check (fresh session)

| Field | Value |
|---|---|
| **Reviewer / runtime model** | QAQC (`qaqc` subagent, fresh session), **Name: `Gemini 4 Argon`, Provider ID: `opencode-go`, Model ID: `gemini-4-argon`** (agent config `.opencode/agents/qaqc.md`: `opencode-go/gemini-4-argon#high`, family `gemini` — distinct from `auditor` `opencode-go/deepseek-v4.1-flash`) |
| **Date (UTC)** | 2026-11-16 (`2026-11-16T01:05:14Z`) |
| **Commits reviewed** | Coder RW chain `a7f303c` + follow-up `76034a0` (branch `wp/strata-001-gfx1150-build` at HEAD `e47e7a3`, where `e47e7a3` touches only `workflow/OWNER_AUDIT_CHECKLIST.md`) |
| **Strata checkout** | `/home/kupipi/Documents/git/strata` pinned at `baf16363b4403ef0ed4f538f5d5ed11c43fb9535` (read-only, porcelain empty) |
| **Profile (one only)** | AMD Radeon 890M / `gfx1150` / Ryzen AI 9 HX 370, ROCm `/opt/rocm/core-10.1`, hipBLASLt `100401`, **no model loaded** |
| **Audit-gate verdict** | **PASS → `AUDIT_REVIEW` (auditor)** |

## 8.1 Per-item independent verification results

| # | Check item | Independent verification summary | Verdict |
|---|---|---|---|
| **1** | **Corrected family claim is true** | Re-ran `LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib ./build-hip/strata --families` → `qwen4exp qwen35moe` (exit 0). Confirmed compiled-in list at `src/program/generate.cpp:3566-3574` and `STRATA_HAVE_QWEN35=1` at `cmake/strata_gpu_engine.cmake:545`. Confirmed mapping at `serve/server.py:9695` (`{"qwen4exp": "qwen3.8-flash-next", "qwen35moe": "qwen3.6-35b-a3b"}`), `strata_control/drafting.py:476` (`TARGET_ARCH = "qwen4exp"`), and `strata_control/feed.py:155` (`MODEL_FAMILIES_INSTALLABLE = ("qwen4exp", "qwen35moe")`). Confirmed absence of Mixtral 8x7B (`grep -rni 'mixtral' src/ include/ strata_control/` → exit 1) and Qwen3-30B-A3B (`grep -rni 'qwen3moe\|30b-a3b' src/ include/ strata_control/` → exit 1), and retirement/refusal of DeepSeek (`strata_control/retired.py:19`, `strata_control/runtime.py:561`). Verified all 5 corrected sites (`manifest.md:51`, `manifest.md:122-138`, `commands.log:166-177`, `HO-STRATA-001.md:249-256`, `HO-STRATA-001-QAQC.md:173-178`, plus `artifacts/families.txt:15-65` and `test-output.txt:32934`) state the true mapping, name Mixtral 8x7B / Qwen3-30B-A3B / DeepSeek as unimplemented, and explicitly distinguish `qwen35moe` (Qwen3.6-35B-A3B) from Qwen3-30B-A3B. Whole-bundle/handoff grep found zero surviving instances of the withdrawn claim. | **PASS** |
| **2** | **Citation is right (`gemm.cu:322`)** | Re-read `src/prefill/gemm.cu` at the pin: line `322` is `if (!table_forced && arch != "gfx1151") return nullptr;` (`310-311` is the HIP device-query failure branch). Grep across `workflow/evidence/HO-STRATA-001/` and `workflow/handoffs/` confirms zero remaining `310-311` citations in any deliverable (matches appear only in `RW-HO-STRATA-001-1.md` describing the defect). Verified all `gemm.cu:` citations (`276-339`, `278`, `322`, `260-274, 318-330`, `290`, `291`, `351-376`, `336`). Diffed `artifacts/tuning-table-raw.txt:76-146` against `nl -ba -w 1 -s ': ' src/prefill/gemm.cu \| sed -n '255,325p'` → exact byte match (exit 0). | **PASS** |
| **3** | **Evidence integrity at `76034a0`** | Recomputed SHA256 over all 19 bundle entries in `workflow/evidence/HO-STRATA-001/hashes.txt` (`manifest.md`, `commands.log`, `test-output.txt`, and 16 `artifacts/*` files) and diffed against `hashes.txt` → 19/19 exact match. Recomputed `tools/hip/gfx1150-hipblaslt-100401.txt` (`aee2867c096887cccaef8bc04a9ef10adec43da58421edfdaaec04a61ec5549c`), `build-hip/strata` (`d58ee2398596d1a100c15d5b9459e24bd86854cb5e5fb7ce88dbc6c7ed9f5858`, `39736088` bytes), Strata `HEAD` (`baf16363b4403ef0ed4f538f5d5ed11c43fb9535`), and `git -C /home/kupipi/Documents/git/strata status --porcelain` (empty). Inspected `git show --stat a7f303c 76034a0`: only documentation, handoffs, derived `test-output.txt`, and `hashes.txt` changed — no rebuilt binary, no re-measured number, no Strata edit. | **PASS** |
| **4** | **Substance still holds** | Build exit 0 (`artifacts/build.log`: `[100%] Built target strata`, `build exit=0`). Surface re-verified (`--families` → `qwen4exp qwen35moe` exit 0; `--geometry` → `flash_next` exit 0). Headless-without-app/server conclusion verified (`cmake/strata_gpu_engine.cmake:510-546` links only C++/HIP targets; `strings -a build-hip/strata \| grep -c 'strata_cli\|strata_control\|serve/server'` → `0`; `ldd` shows only ROCm + standard C/C++ libs). Tuning-table verdict verified: table present (146 lines), header `STRATA_HIPBLASLT_TUNING_V1 gfx1150 100401` matches local `gfx1150` + `100401` (`hipblaslt-version.h` 1.4.1 and probe `100401`), **default is plain hipBLAS** (`gemm.cu:322`), opt-in only (`STRATA_HIPBLASLT_TUNING` / `STRATA_HIPBLASLT_TABLE=on`), and runtime taken-vs-fallback is explicitly stated as unobservable without a model run (no overclaim). Single profile only (`gfx1150` / Radeon 890M), no performance/support/quality claims. | **PASS** |
| **5** | **Honesty checks** | Both host obstacles are recorded verbatim and diagnosed without editing Strata source or installing packages: (a) literal configure fails exit 1 (`Could not find a package configuration file provided by "hip"`), resolved via `-DCMAKE_PREFIX_PATH=/opt/rocm/core-10.1`; (b) bare `./build-hip/strata --families` fails exit 127 (`libhipblas.so.3: cannot open shared object file`), reproduced by me and resolved at runtime via `LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib`. Re-ran `python3 strata.py launch --plan --no-tui` (and `--output json`) → exit 2 with the verbatim refusal (`No model fits this computer by Strata's rules, and none was chosen...`), recorded as the designed refusal and not hidden. | **PASS** |

## 8.2 Commands and raw output (executed in this session)

```text
$ git -C /home/kupipi/Documents/git/strata rev-parse HEAD
baf16363b4403ef0ed4f538f5d5ed11c43fb9535
$ git -C /home/kupipi/Documents/git/strata status --porcelain
(empty)
$ git -C /home/kupipi/Documents/git/strata check-ignore -v build-hip
.gitignore:12:build*/	build-hip

$ cd /home/kupipi/Documents/git/strata
$ ./build-hip/strata --families || echo "bare exit=$?"
./build-hip/strata: error while loading shared libraries: libhipblas.so.3: cannot open shared object file: No such file or directory
bare exit=127
$ LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib ./build-hip/strata --families; echo "families exit=$?"
qwen4exp qwen35moe
families exit=0
$ LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib ./build-hip/strata --geometry; echo "geometry exit=$?"
flash_next
geometry exit=0
$ python3 strata.py launch --plan --no-tui || echo "launch-plan exit=$?"
strata: No model fits this computer by Strata's rules, and none was chosen. Name one with --model (strata launch --help lists them); a bigger one will run slowly.
launch-plan exit=2
$ python3 strata.py launch --plan --no-tui --output json || echo "launch-plan-json exit=$?"
{"schema_version": 1, "ok": false, "error": {"code": 2, "message": "No model fits this computer by Strata's rules, and none was chosen. Name one with --model (strata launch --help lists them); a bigger one will run slowly."}}
launch-plan-json exit=2

$ sed -n '3566,3574p' src/program/generate.cpp
        // `strata --families`: the GGUF architectures this build runs (setup asks before it installs one)
        if (std::strcmp(argv[i], "--families") == 0) {
#if defined(STRATA_HAVE_QWEN35)
            std::printf("qwen4exp qwen35moe\n");
#else
            std::printf("qwen4exp\n");
#endif
            return 0;
        }
$ grep -n 'STRATA_HAVE_QWEN35' cmake/strata_gpu_engine.cmake
531:  # STRATA_HAVE_QWEN35, so a gfx906 build links and runs the Qwen3.8 family, and `strata --families` says so
545:  target_compile_definitions(strata PRIVATE STRATA_HAVE_QWEN35=1)
$ grep -n 'FAMILY_MODEL_NAMES' serve/server.py
9695:FAMILY_MODEL_NAMES = {"qwen4exp": "qwen3.8-flash-next", "qwen35moe": "qwen3.6-35b-a3b"}
9719:    return cfg.get("model_name") or FAMILY_MODEL_NAMES.get(cfg.get("arch") or "qwen4exp", "qwen3.8-flash-next")
$ grep -n 'TARGET_ARCH' strata_control/drafting.py
476:TARGET_ARCH = "qwen4exp"                                    # general.architecture of the Qwen3.8-Flash-Next GGUFs (tools/gguf_writer.py)
605:    if facts["arch"] != TARGET_ARCH:
$ grep -n 'MODEL_FAMILIES_INSTALLABLE' strata_control/feed.py
155:MODEL_FAMILIES_INSTALLABLE = ("qwen4exp", "qwen35moe")
$ grep -rni 'mixtral' src/ include/ strata_control/ || echo "mixtral exit=$?"
mixtral exit=1
$ grep -rni 'qwen3moe\|30b-a3b' src/ include/ strata_control/ || echo "qwen3moe/30b-a3b exit=$?"
qwen3moe/30b-a3b exit=1
$ grep -n 'FAMILY = "deepseek41"' strata_control/retired.py
19:FAMILY = "deepseek41"
$ grep -n 'def _refuse_deepseek' strata_control/runtime.py
561:def _refuse_deepseek(name: str) -> None:

$ sed -n '322p' src/prefill/gemm.cu
        if (!table_forced && arch != "gfx1151") return nullptr;
$ diff -u <(sed -n '76,146p' /home/kupipi/Documents/git/gfx1150-inference/workflow/evidence/HO-STRATA-001/artifacts/tuning-table-raw.txt) \
          <(nl -ba -w 1 -s ': ' src/prefill/gemm.cu | sed -n '255,325p') && echo "EXCERPT_255_325_EXACT_MATCH"
EXCERPT_255_325_EXACT_MATCH

$ cd /home/kupipi/Documents/git/gfx1150-inference
$ grep -rn -i 'omits Qwen3.8\|not in this build\|does not list Qwen3.8\|not supported by this build' workflow/evidence/HO-STRATA-001/ workflow/handoffs/
workflow/evidence/HO-STRATA-001/commands.log:177:Qwen3.8-Flash-Next was not in this build's list. The transcribed output above is unchanged.*
workflow/handoffs/RW-HO-STRATA-001-1.md:184:  **N1** — the withdrawn "`--families` omits Qwen3.8-Flash-Next" claim survived in a fifth place,
$ grep -rn '310-311' workflow/evidence/HO-STRATA-001/ workflow/handoffs/HO-STRATA-001.md workflow/handoffs/HO-STRATA-001-QAQC.md || echo "exit=$?"
exit=1

$ cd /home/kupipi/Documents/git/gfx1150-inference/workflow/evidence/HO-STRATA-001
$ diff -u <(grep -E '^[0-9a-f]{64}  ' hashes.txt | grep -v '/home/kupipi/Documents/git/strata') \
          <(sha256sum manifest.md commands.log test-output.txt; (cd artifacts && sha256sum $(ls -1))) && echo "ALL_19_BUNDLE_HASHES_MATCH"
ALL_19_BUNDLE_HASHES_MATCH
$ sha256sum /home/kupipi/Documents/git/strata/tools/hip/gfx1150-hipblaslt-100401.txt
aee2867c096887cccaef8bc04a9ef10adec43da58421edfdaaec04a61ec5549c  /home/kupipi/Documents/git/strata/tools/hip/gfx1150-hipblaslt-100401.txt
$ sha256sum /home/kupipi/Documents/git/strata/build-hip/strata
d58ee2398596d1a100c15d5b9459e24bd86854cb5e5fb7ce88dbc6c7ed9f5858  /home/kupipi/Documents/git/strata/build-hip/strata
$ stat -c '%s %n' /home/kupipi/Documents/git/strata/build-hip/strata
39736088 /home/kupipi/Documents/git/strata/build-hip/strata
$ strings -a /home/kupipi/Documents/git/strata/build-hip/strata | grep -c 'strata_cli\|strata_control\|serve/server' || true
0
```

## 8.3 New findings

**None.** All first-pass findings (**F1–F7**) and re-check leftovers (**N1–N3**) are verified closed in `a7f303c` + `76034a0`:
- `workflow/handoffs/HO-STRATA-001-QAQC.md:173-178` (former N1) is updated and withdrawals are explicit.
- `workflow/evidence/HO-STRATA-001/artifacts/tuning-table-raw.txt:76-146` (former N2) carries exact absolute line numbers `255:`–`325:` matching `src/prefill/gemm.cu`.
- `workflow/handoffs/RW-HO-STRATA-001-1.md:191-196` (former N3) records the stale commit-message line in `a7f303c` without rewriting history.
- Role-model separation between QAQC (`opencode-go/gemini-4-argon`) and Auditor (`opencode-go/deepseek-v4.1-flash`) is now satisfied at runtime by this fresh-session review.

## 8.4 Audit-gate verdict

**PASS → `AUDIT_REVIEW` (auditor).** Evidence path: `workflow/evidence/HO-STRATA-001/`. Report path: `workflow/reports/qaqc/HO-STRATA-001-qaqc.md`. No files outside this report were modified; no commits were made.
