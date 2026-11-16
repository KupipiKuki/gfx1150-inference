# Evidence manifest — HO-STRATA-001

| Field | Value |
|---|---|
| **Handoff** | HO-STRATA-001 |
| **Commit / branch** | (see §7 — commit SHA on `wp/strata-001-gfx1150-build`) / `wp/strata-001-gfx1150-build` |
| **Author / date (UTC)** | `coder-primary` / 2026-11-16 |
| **Environment** | Linux Mint 22.3 (Zena), kernel 7.0.0-42-generic, AMD Radeon 890M `gfx1150`, Ryzen AI 9 HX 370, HIP 7.16.26385-0000000 (clang 24.0.0git), ROCm prefix `/opt/rocm/core-10.1`, hipBLASLt 1.4.1 = `100401` (measured), CMake 3.28.3, g++ 13.3.0, Python 3.14.10, linux-firmware 20240318.git3b128b60.0ubuntu3.1, ttm pages_limit 12050777 |
| **Working directory** | `/home/kupipi/Documents/git/strata` (read-only input, pinned) for AC-1…AC-7; `/home/kupipi/Documents/git/gfx1150-inference` for the evidence bundle |

**One profile only.** AMD Radeon 890M / `gfx1150` / Ryzen AI 9 HX 370. **No model was loaded,
downloaded or run** in this handoff, so no performance, throughput, support or quality claim is
made anywhere in this bundle.

Strata is a **separate read-only checkout**, not a branch of the workflow repo:
`/home/kupipi/Documents/git/strata` @ `baf16363b4403ef0ed4f538f5d5ed11c43fb9535`, no branch, no
commits, `git status --porcelain` empty at start and at finish. Only `build-hip/` was added and
it is git-ignored (`.gitignore:12: build*/`).

## 1. Commands

Full transcript with cwd, env and exit codes: **`commands.log`**. Raw output: **`test-output.txt`**
(assembled verbatim from `artifacts/`).

| # | Command (copy-paste) | CWD | Exit | Output file |
|---|---|---|---|---|
| AC-1 | `git rev-parse HEAD && git status --porcelain && git remote get-url origin` | strata | 0 | `artifacts/verify-pin.txt` |
| AC-2 | `uname -a`; `cat /etc/os-release`; `dpkg -l linux-firmware`; `rocminfo`; `hipcc --version`; `ls -d /opt/rocm*`; `ls -l /opt/rocm/*/lib/libhipblaslt.so*`; `cmake --version`; `c++ --version`; `python3 --version`; `cat /sys/module/ttm/parameters/pages_limit` | strata | 0 | `artifacts/toolchain.txt` |
| AC-2b | `hipcc -o v v.cpp -I/opt/rocm/core-10.1/include -L/opt/rocm/core-10.1/lib -lhipblaslt && ./v` (hipBLASLt version probe) | `/tmp/opencode/hblt-ver` | 0 | `artifacts/hipblaslt-version-probe.txt` |
| AC-3a | `cmake -S . -B build-hip -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_HIP=ON -DSTRATA_ENABLE_CUDA=OFF -DCMAKE_HIP_ARCHITECTURES=gfx1150` | strata | **1** | `artifacts/configure.log` (first block) |
| AC-3b | same + `-DCMAKE_PREFIX_PATH=/opt/rocm/core-10.1` (after `rm -rf build-hip`) | strata | 0 | `artifacts/configure.log` (retry block) |
| AC-3c | `cmake --build build-hip --target strata -j$(nproc)` | strata | 0 | `artifacts/build.log` |
| AC-4a | `./build-hip/strata --families` | strata | **127** | `artifacts/families.txt` |
| AC-4a′ | `LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib ./build-hip/strata --families` | strata | 0 | `artifacts/families.txt` |
| AC-4b | `LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib ./build-hip/strata --geometry` | strata | 0 | `artifacts/geometry.txt` |
| AC-4c | `LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib ./build-hip/strata --help` | strata | 0 | `artifacts/help.txt` |
| AC-5 | `python3 strata.py launch --plan --no-tui` | strata | **2** | `artifacts/launch-plan.txt` |
| AC-5b | `python3 strata.py launch --plan --no-tui --output json` | strata | **2** | `artifacts/launch-plan.txt` |
| AC-5c | `python3 strata.py launch --help` | strata | 0 | `artifacts/control-launch-help.txt` |
| AC-7 | `sha256sum tools/hip/gfx1150-hipblaslt-100401.txt`; `head -2`; greps of `src/prefill/hipblaslt_tuning.hpp`, `src/prefill/gemm.cu`, `docs/AMD_HIP.md:619-640` | strata | 0 | `artifacts/tuning-table-raw.txt` |
| AC-6 | reads + `ldd build-hip/strata` + `ls build-hip/` + `strings … \| grep -c` | strata | 0 | `artifacts/engine-deps.txt`, `artifacts/boundary-layout.txt` |
| AC-8 | `ls -R workflow/evidence/HO-STRATA-001/` | gfx1150-inference | 0 | this file |

## 2. Acceptance criteria ↔ evidence

| # | Criterion | Command | Observed | Pass? |
|---|---|---|---|---|
| 1 | Pinned commit verified | `git rev-parse HEAD`; `git status --porcelain` | `baf16363b4403ef0ed4f538f5d5ed11c43fb9535`; porcelain empty; origin `https://github.com/Niko1221/Strata` | **PASS** |
| 2 | Toolchain recorded | see AC-2 row | all exit 0; `gfx1150` / `AMD Radeon 890M Graphics`; HIP 7.16.26385; ROCm `/opt/rocm/core-10.1`; **hipBLASLt = 100401** (measured via `hipblasLtGetVersion`) | **PASS** |
| 3 | gfx1150 build | configure + `cmake --build … --target strata` | literal command **exit 1** (`hip` package not found — env, not source); with `CMAKE_PREFIX_PATH` configure exit 0 → `Strata: HIP enabled, arch gfx1150`; build **exit 0**; `build-hip/strata` present, 39,736,088 B | **PASS** (with the documented configure-path fix) |
| 4 | Engine support surface | `--families`; `--geometry` | `qwen4exp qwen35moe` (exit 0); `flash_next` (exit 0). Families **not** supported by this build include **Qwen3.8-Flash-Next** (the family the gfx1150 bench note measured) — recorded as an observation for the Architect | **PASS** |
| 5 | Control plan (no changes) | `python3 strata.py launch --plan --no-tui` | exit 2, verbatim: `strata: No model fits this computer by Strata's rules, and none was chosen. Name one with --model (strata launch --help lists them); a bigger one will run slowly.` Nothing installed or downloaded | **PASS** (refusal recorded verbatim, as AC-5 allows) |
| 6 | Engine-boundary note | delivered file | `artifacts/engine-boundary.md`, ≤1 page, headings (a)–(e); headless answer = **yes**, evidenced three ways | **PASS** |
| 7 | Tuning table match/fallback | `sha256sum`; `head -2`; version probe; `gemm.cu`/docs greps | table SHA256 `aee2867c…54c` (= Architect's pin); header `STRATA_HIPBLASLT_TUNING_V1 gfx1150 100401`; local runtime **100401** → **MATCH**; **default = fallback** on gfx1150 (`gemm.cu:310-311`), opt-in via `STRATA_HIPBLASLT_TUNING`; taken-vs-fallback **not observable** without a model run (stated) | **PASS** |
| 8 | Evidence bundle complete | `ls -R workflow/evidence/HO-STRATA-001/` | manifest, commands.log, test-output.txt, hashes.txt, artifacts/ (16 files) | **PASS** |

### Family list, transcribed from `artifacts/families.txt`

```
qwen4exp qwen35moe
```

### Geometry, transcribed from `artifacts/geometry.txt`

```
flash_next
```

## 3. Artifacts and hashes

| Artifact | Path | SHA256 |
|---|---|---|
| model | **N/A** — no model in this handoff (§2 of the handoff) | — |
| prompt / data | **N/A** — no prompt or dataset used | — |
| Strata pinned commit (as a value) | `git rev-parse HEAD` | `baf16363b4403ef0ed4f538f5d5ed11c43fb9535` |
| Tuning table (pinned input) | strata `tools/hip/gfx1150-hipblaslt-100401.txt` | `aee2867c096887cccaef8bc04a9ef10adec43da58421edfdaaec04a61ec5549c` |
| Built binary (not committed) | strata `build-hip/strata` | `d58ee2398596d1a100c15d5b9459e24bd86854cb5e5fb7ce88dbc6c7ed9f5858` |
| toolchain log | `artifacts/toolchain.txt` | in `hashes.txt` |
| configure log | `artifacts/configure.log` | in `hashes.txt` |
| build log | `artifacts/build.log` | in `hashes.txt` |
| families / geometry / help | `artifacts/families.txt`, `geometry.txt`, `help.txt` | in `hashes.txt` |
| launch plan / control help | `artifacts/launch-plan.txt`, `control-launch-help.txt` | in `hashes.txt` |
| boundary note | `artifacts/engine-boundary.md` | in `hashes.txt` |
| tuning note + raw | `artifacts/tuning-table.md`, `tuning-table-raw.txt` | in `hashes.txt` |
| hipBLASLt probe | `artifacts/hipblaslt-version-probe.txt` | in `hashes.txt` |
| pin verification | `artifacts/verify-pin.txt` | in `hashes.txt` |
| Architect pin record | `artifacts/pinned-commit.txt` | `0c128869b2c3de960fde9eaac43be785a95110bd287de9e2edf87400a93d7f8d` (kept unmodified) |

`hashes.txt` carries the full `sha256sum` listing of every file in the bundle.

## 4. Failures, skips, limits

Kept verbatim. None of these was hidden or paraphrased.

1. **AC-3 configure, literal command — exit 1.** `CMake Error at cmake/hip_backend.cmake:58
   (find_package): Could not find a package configuration file provided by "hip" with any of the
   following names: hipConfig.cmake hip-config.cmake`. **Diagnosis:** environment search path —
   `hip-config.cmake` exists at `/opt/rocm/core-10.1/lib/cmake/hip`, but `/opt/rocm` is a parent
   of `core`/`core-10`/`core-10.1`, so neither the compiler's discovery nor CMake's default search
   reaches it. Fixed with the configure flag CMake itself names,
   `-DCMAKE_PREFIX_PATH=/opt/rocm/core-10.1`; **no Strata source was modified.** This is a
   candidate report to upstream (docs/AMD_HIP.md tells you to set `CMAKE_HIP_COMPILER` when CMake
   cannot find HIP, but not `CMAKE_PREFIX_PATH`).
2. **AC-4 `--families`, first run — exit 127.** `./build-hip/strata: error while loading shared
   libraries: libhipblas.so.3: cannot open shared object file: No such file or directory`. Not a
   build defect (`ldd` shows the ROCm libs unresolved; `libhipblas.so.3` is present under
   `/opt/rocm/core-10.1/lib`). Fixed at run time with `LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib`.
   The build itself links cleanly and exits 0.
3. **AC-5 Control plan — exit 2, refused.** No model fits by Strata's rules and none was chosen.
   Recorded verbatim; **no model was installed or downloaded** (out of scope) and
   `strata launch` was never run without `--plan`.
4. **Not tested — the engine never ran a model.** `pack/full` is absent; `--families`,
   `--geometry`, `--help` are surface-reporting modes. Therefore this handoff does **not**
   establish that a generation run works on gfx1150, only that the engine builds for gfx1150, its
   binary starts, and it reports its compiled surface. No tok/s, no quality, no support claim.
5. **Not observed — tuning table taken vs fallback at runtime.** The decision code
   (`create_hipblaslt_state`, `src/prefill/gemm.cu:276`) runs only once the prefill hipBLASLt path
   initialises with a pack. What is *read* from source (`gemm.cu:310-311`: on `gfx1150`, unset env
   ⇒ `return nullptr` ⇒ plain hipBLAS) is a static reading, not a runtime observation. The start
   line `prefill gemm: hipBLASLt tuning enabled (…)` and the `fallbacks=` count were **not**
   produced. Needs HO-STRATA-002+ with a model.
6. **Observation, not a criterion — family coverage.** `--families` reports
   `qwen4exp qwen35moe`. The gfx1150 community bench note in the repo
   (`bench/results/2026-10-07-community-gfx1150/README.md`, cited by `docs/AMD_HIP.md:542`)
   measured **Qwen3.8-Flash-Next**, which is *not* in this build's family list. This matters for
   HO-STRATA-002/003/004 and is flagged for the Architect; it is not an AC-4 failure.
7. **`ccache` absent** (`Warning: ccache not found - consider installing it…`). Configure warning
   only; no install was attempted (guard rail), build exit 0 without it.
8. **No test suite was run.** AC-3 targets `--target strata` only, and the handoff's criteria do
   not ask for `ctest`. `-- strata tests: ON - cpu, hip` in the configure summary means the suite
   was *registered*, not built or executed. Out of scope here.

## 5. Environment notes

- `LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib` is **required** to execute the built engine on this
  host. Not set by anything in the repo; it is a host environment property, recorded rather than
  worked around by installing anything.
- `CMAKE_PREFIX_PATH=/opt/rocm/core-10.1` is **required** at configure time (see §4.1).
- `STRATA_HIPBLASLT_TUNING` was deliberately **left unset** so the observed default is the
  untuned one (AC-7).
- `HSA_OVERRIDE_GFX_VERSION` was **not** set: the card reports `gfx1150` natively
  (`rocminfo` Agent 2, ISA `amdgcn-amd-amdhsa--gfx1150` + `gfx11-generic`).
- `--split-engine`, `--batch`, replica/multi-GPU paths were not exercised: one card only.
- The hipBLASLt version probe harness lives in `/tmp/opencode/hblt-ver/` — outside both
  repositories, not committed, no install, no model. Its source is quoted in
  `artifacts/hipblaslt-version-probe.txt` so the measurement is reproducible.
- Known host caveat: `/opt/rocm` holds `core`, `core-10` (alternatives symlinks) and `core-10.1`
  (the real install, per `hipcc --version`'s `InstalledDir`); the versioned path is what both the
  configure flag and the loader path must name.

## 6. Statement

- [x] Commands are reproducible (cwd + env + exit code in `commands.log`).
- [x] Outputs are raw; no paraphrasing (failures in §4 are verbatim).
- [x] No secrets, tokens, or credentials anywhere in the bundle.
- [x] Every claim cites an artifact.
- [x] One profile per claim (890M `gfx1150`, no model loaded).
- [x] No performance, support, or quality claim is made.

## 7. Git

Committed on `wp/strata-001-gfx1150-build` only. Base
`a6166f7ebd48eabaffc4809c76c9460b92441cde`. No merge, no push to `main`, no rewrite of a shared
branch. The commit's subject is `HO-STRATA-001: …`; `git log -1 --format=%H` on this branch gives
the SHA (also recorded in the CODER_TO_QAQC handoff and in the reply to the Architect).
