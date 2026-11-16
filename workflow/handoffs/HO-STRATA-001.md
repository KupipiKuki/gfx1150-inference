# HO-STRATA-001 — gfx1150 build, support check, and engine boundary

| Field | Value |
|---|---|
| **ID** | HO-STRATA-001 |
| **Type** | ARCHITECT_TO_CODER |
| **State** | **CODER_DONE** (was READY → IN_PROGRESS → CODER_DONE) |
| **Created / updated (UTC)** | 2026-11-15 / 2026-11-16 |
| **From → To** | Architect → Primary Coder (`coder-primary`) |
| **Work package** | `strata-001-gfx1150-build` — build/support/engine-boundary spike |
| **Priority / timebox** | P0 · 1 working day (build + first run of the CLI surface) |
| **Owner task** | OT-STRATA-001 (auditor is the intake; report against its checkpoints) |

## 0. Repositories, branches and base commits

This work package touches **two** checkouts. Both are named here so there is no ambiguity.

| Checkout | Path | Branch | Base commit | What may change |
|---|---|---|---|---|
| **Workflow repo** (`gfx1150-inference`) | `/home/kupipi/Documents/git/gfx1150-inference` | `wp/strata-001-gfx1150-build` (created by the architect, based on `a6166f7ebd48eabaffc4809c76c9460b92441cde`) | `a6166f7ebd48eabaffc4809c76c9460b92441cde` | `workflow/evidence/HO-STRATA-001/**` and this handoff file only |
| **Strata checkout** | `/home/kupipi/Documents/git/strata` | **no branch, no commits** (detached-safe, read-only tree) | `baf16363b4403ef0ed4f538f5d5ed11c43fb9535` (**pinned**, DEC-006) | nothing — the build directory `build-hip/` is gitignored (`build*/`), everything else stays clean |

The Strata tree is a **read-only input** for this handoff: no source edits, no
patch, no commit. If the build needs a source change to proceed, that is a
blocker or a deviation, not a coder decision.

## 1. Scope (in)

1. **Verify the pin.** The Strata checkout exists at
   `/home/kupipi/Documents/git/strata` with `HEAD == baf16363b4403ef0ed4f538f5d5ed11c43fb9535`.
   Re-clone only if the checkout is missing; record what you did.
2. **Toolchain.** Record OS, kernel, `linux-firmware`, `rocminfo`, `hipcc --version`,
   ROCm install path, hipBLASLt version, CMake, host C++ compiler, Python, GPU
   memory/GTT parameters.
3. **Configure + build** the HIP engine for `gfx1150` from source, using the
   upstream-documented flags (§4 AC-3). Build log is an artifact either way.
4. **Engine support surface.** Run the *built engine binary*
   `build-hip/strata --families` (and `--geometry`) and the *Control CLI*
   `python3 strata.py launch --plan --no-tui` from the checkout root.
5. **Engine-boundary note** (≤ 1 page): engine core (`src/`, `include/`) vs the
   Control (`strata_cli/`, `strata_control/`, `strata.py`, `bin/strata`) vs the
   app/server (`apps/`, `serve/`). Answer explicitly: **can the engine be built
   and started headless without the app and the server?**
6. **Tuning table check**: does `tools/hip/gfx1150-hipblaslt-100401.txt` match
   the local hipBLASLt, and is it taken or does the engine fall back? Record the
   mechanism (`STRATA_HIPBLASLT_TUNING`, `STRATA_HIPBLASLT_VERBOSE=1`) and
   whether verification needs a model (a model run is out of scope here).
7. **Evidence bundle** for `HO-STRATA-001` per §5, and this handoff updated to
   `CODER_DONE` with the `CODER_TO_QAQC` request.

## 2. Out of scope

- **Downloading, running, or measuring any model** — that is HO-STRATA-002/003/004.
  No `strata launch` that would set up, fetch or serve a model.
- **Modifying Strata source, CMake, or docs.** Record blockers instead.
- `./setup.sh` / `setup.py` install path: upstream names gfx1150 as *not
  installed by setup* (`docs/AMD_HIP.md:42`). Do not attempt it as the primary
  path; if you try it, it is a side observation, not an acceptance criterion.
- 780M, MI25, gfx1100, gfx1151, gfx1201 — none of them.
- Performance, throughput, support, or quality claims of any kind.
- The P0–P9 capability framework (escalation annex).
- Product/app work in `apps/` or `serve/` beyond *reading* it for the boundary note.
- Installing new system packages or upgrading ROCm.

## 3. Inputs

| Input | Path / source | Status |
|---|---|---|
| Strata repository | `https://github.com/Niko1221/Strata` | cloned, pinned (§0) |
| Pin provenance | `workflow/evidence/HO-STRATA-001/artifacts/pinned-commit.txt` (Architect) | available |
| AMD/HIP doc — gfx1150 status, build flags, table | Strata `docs/AMD_HIP.md` (lines 42, 182–200, 542, 619–637, 801) | available |
| Engine/architecture doc | Strata `docs/HOW_IT_WORKS.md`, `AGENTS.md` | available |
| Boundary docs | Strata `docs/SPLIT_ENGINE.md`, `docs/SPLIT_SERVE.md`, `docs/CAPABILITIES.md` | available |
| Prior art on this exact profile | Strata `bench/results/2026-10-07-community-gfx1150/README.md` (890M, ROCm 7.14.1, engine 0.1.40.2) | available, **not** evidence for this build |
| Workflow contract | `workflow/HANDOFF_CONTRACT.md`, `workflow/ENGINEERING_WORKFLOW.md` | available |
| Evidence template | `workflow/templates/EVIDENCE_MANIFEST.md` | available |
| Owner task | `workflow/handoffs/OT-STRATA-001.md` | available |

**Architect pre-check (orientation only — NOT evidence; the coder re-runs all of it):**
`rocminfo` reports `gfx1150` / `AMD Radeon 890M Graphics` on `AMD Ryzen AI 9 HX 370`;
`hipcc` is HIP 7.16.26385-0000000 (ROCm at `/opt/rocm/core-10.1`, clang 24);
`libhipblaslt.so.1.4` → version number 100401, which matches the table header
`STRATA_HIPBLASLT_TUNING_V1 gfx1150 100401`; `third_party/strata-ggml` is
vendored, so configure needs **no** network fetch.

## 4. Acceptance criteria

Every criterion is a command with an expected result. "Documented blocker" is an
acceptable outcome **only** where stated, and only with the raw log attached —
never a paraphrase.

| # | Criterion | Command / check | Expected |
|---|---|---|---|
| 1 | Pinned commit verified | `cd /home/kupipi/Documents/git/strata && git rev-parse HEAD && git status --porcelain` | `baf16363b4403ef0ed4f538f5d5ed11c43fb9535`, and empty porcelain; both pasted in `commands.log` and `artifacts/` |
| 2 | Toolchain recorded | `uname -a`; `cat /etc/os-release`; `dpkg -l linux-firmware`; `rocminfo`; `hipcc --version`; `ls -d /opt/rocm*`; `ls -l /opt/rocm/*/lib/libhipblaslt.so*`; `cmake --version`; `c++ --version`; `python3 --version`; `cat /sys/module/ttm/parameters/pages_limit` | raw output saved as `artifacts/toolchain.txt`; the hipBLASLt version number (e.g. `100401`) is stated explicitly |
| 3 | gfx1150 build | `cmake -S . -B build-hip -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_HIP=ON -DSTRATA_ENABLE_CUDA=OFF -DCMAKE_HIP_ARCHITECTURES=gfx1150` then `cmake --build build-hip --target strata -j$(nproc)`, teed to `artifacts/configure.log` / `artifacts/build.log` | exit 0 and `build-hip/strata` exists, **or** a documented blocker: configure/build exit code + the failing lines verbatim + one-line diagnosis. A blocker does not fail the handoff |
| 4 | Engine support surface | `cd /home/kupipi/Documents/git/strata && build-hip/strata --families; echo "exit=$?"` and `build-hip/strata --geometry; echo "exit=$?"` | raw output in `artifacts/families.txt` / `artifacts/geometry.txt`; the family list is transcribed into the manifest; unsupported families named |
| 5 | Control plan (no changes) | `cd /home/kupipi/Documents/git/strata && python3 strata.py launch --plan --no-tui; echo "exit=$?"` (add `--output json` if the human view is ambiguous) | raw output in `artifacts/launch-plan.txt`. If it refuses without an installed model, paste the refusal verbatim and record it as an observation — **do not** install or download a model |
| 6 | Engine-boundary note | `workflow/evidence/HO-STRATA-001/artifacts/engine-boundary.md` | ≤ 1 page, with these five headings: (a) engine core vs Control vs app/server, each with the paths it covers; (b) what the engine needs at runtime; (c) **can it run headless without `apps/` and `serve/`?** with the file evidence; (d) what the Control adds that the engine does not have; (e) the smallest command line that starts the engine alone (flags from `--help`, not run) |
| 7 | Tuning table match/fallback | `sha256sum tools/hip/gfx1150-hipblaslt-100401.txt`; `head -2` of the table; the local hipBLASLt version from AC-2; grep of `src/prefill/hipblaslt_tuning.hpp` + `docs/AMD_HIP.md:619-637` for the selection rule | `artifacts/tuning-table.md`: table present, header vs local version (**match / mismatch**), whether it is auto-taken on gfx1150 (upstream: **no** — opt-in via `STRATA_HIPBLASLT_TUNING`, `docs/AMD_HIP.md:637`) and therefore the actual default = plain hipBLAS. State plainly if the "taken vs fallback" half cannot be observed without a model run |
| 8 | Evidence bundle complete | `ls -R workflow/evidence/HO-STRATA-001/` | `manifest.md` (filled from `templates/EVIDENCE_MANIFEST.md`), `commands.log`, `test-output.txt`, `artifacts/`, `hashes.txt`; no secrets; no model weights |

## 5. Evidence required

All paths are in the **workflow repo** (`gfx1150-inference`). This directory is
the only thing the coder writes there.

- `workflow/evidence/HO-STRATA-001/manifest.md` — filled `templates/EVIDENCE_MANIFEST.md`.
- `workflow/evidence/HO-STRATA-001/commands.log` — every command, cwd, env vars that matter, exit code.
- `workflow/evidence/HO-STRATA-001/test-output.txt` — raw command output; failures verbatim.
- `workflow/evidence/HO-STRATA-001/hashes.txt` — pinned SHA, table SHA256, SHA256 of every artifact under `artifacts/`.
- `workflow/evidence/HO-STRATA-001/artifacts/` — `toolchain.txt`, `configure.log`, `build.log`, `families.txt`, `geometry.txt`, `launch-plan.txt`, `engine-boundary.md`, `tuning-table.md`, `pinned-commit.txt` (architect-authored, keep it).
- Evidence for a *claim* must be the command + its output. A number with no
  command is not evidence. **One profile only**: AMD Radeon 890M `gfx1150`,
  Ryzen AI 9 HX 370, no model loaded in this handoff.

## 6. Guard rails

- **Do not modify the Strata source.** No edits under `src/`, `include/`,
  `cmake/`, `CMakeLists.txt`, `docs/`, `tools/`, `third_party/`. No patch, no
  `git commit`, no `git checkout -b` in `/home/kupipi/Documents/git/strata`;
  `git status --porcelain` must be empty when you finish (the build directory is
  ignored by `build*/` in `.gitignore`).
- **Do not download models. Do not run a model.** No `strata launch` without
  `--plan`, no `setup.sh`, no `--model`/`--family` install flows.
- **Do not touch the rest of `gfx1150-inference`**: no changes to `src/`,
  `tests/`, `docs/`, `planning/`, `scripts/`, or other workflow files. Only
  `workflow/evidence/HO-STRATA-001/**` and this handoff's state/log.
- **Do not merge, do not push to `main`.** Commit only to
  `wp/strata-001-gfx1150-build`; the architect merges after QAQC + audit + signoff.
- **Do not install or upgrade system packages** (no `apt`, no ROCm change, no pip
  installs). Missing prerequisite = blocker, not an install.
- **No 780M / MI25 / gfx1100 / gfx1151 / gfx1201 work or comparison.**
- **No performance, support, or quality claims.** This handoff produces a build,
  a CLI surface, and a boundary note — not a number.
- **No secrets, tokens, or credentials** in the repo, logs, or handoff.
- Do not change acceptance criteria or scope; raise a deviation instead
  (`DR-HO-STRATA-001-<n>`) and stop.

## 7. Dependencies / blockers

| Dependency | Owner | Status | Needed by |
|---|---|---|---|
| Strata commit pinned | Architect | **resolved** — `baf16363b4…` (DEC-006) | before READY |
| Work-package branch exists | Architect | **resolved** — `wp/strata-001-gfx1150-build` @ `a6166f7e` | before READY |
| ROCm/HIP toolchain usable | Coder | present (architect pre-check); coder confirms under AC-2 | AC-3 |
| gfx1150 is an **unvalidated** upstream target (`docs/AMD_HIP.md:42,542`) | Coder | **known risk** — a build blocker is an acceptable outcome for 001 if documented | AC-3 |
| Network | — | **not required**: `third_party/strata-ggml` is vendored | — |
| Model packs for 002–004 | Owner | **open** (OT-STRATA-001 decisions 2–4 unanswered) | HO-002+, not this handoff |

Escalate to the architect within 4 working hours of hitting a blocker that is
not the build itself (e.g. a source change that looks required).

## 8. Definition of Ready

- [x] ID/type/from/to/title/work package present
- [x] Branch and base commit named and existing (§0: `wp/strata-001-gfx1150-build` @ `a6166f7e`; Strata pinned at `baf16363b4…`)
- [x] Scope and out-of-scope explicit (§1, §2)
- [x] Inputs linked and available (§3, paths verified at the pin)
- [x] Every acceptance criterion has a command/check (§4, AC-1…AC-8)
- [x] Evidence requirements explicit and runnable (§5)
- [x] Guard rails explicit (§6)
- [x] Dependencies resolved or owned (§7)
- [x] Priority/timebox set (P0 · 1 working day)
- [x] No open `NEEDS_INFO` from the receiver

## 9. Definition of Done

- [x] AC-1…AC-8 run; raw output in the evidence bundle; failures verbatim
- [x] Pinned SHA and toolchain recorded
- [x] Build attempted; exit 0 **or** a documented blocker with the log
- [x] `--families` / `--geometry` / `launch --plan` output recorded
- [x] Engine-boundary note written with the five headings
- [x] Tuning-table match/fallback recorded (and the opt-in default stated)
- [x] Strata checkout still clean (`git status --porcelain` empty)
- [x] Nothing written outside `workflow/evidence/HO-STRATA-001/**` + this file
- [x] No secrets, no model weights, no perf/support claims
- [x] Evidence manifest complete; handoff `CODER_DONE`; `CODER_TO_QAQC` created
- [x] Work committed on `wp/strata-001-gfx1150-build` (no merge, no push to `main`)

Coder notes on the unticked-and-failed question: **nothing in §9 was left failed.** Two
*acceptance* commands exited non-zero on their first, literal invocation and are kept verbatim
with their diagnosis in `manifest.md` §4 — AC-3 configure (exit 1, `hip` package not found; fixed
with the `CMAKE_PREFIX_PATH` flag CMake itself names) and AC-4 `--families` (exit 127, missing
`LD_LIBRARY_PATH`; fixed at run time). AC-5 exits 2 by design (refusal without a model) and is
recorded as an observation, which AC-5 permits.

## 10. Signatures

| Role | Name/agent | Date | Decision |
|---|---|---|---|
| Sender (Architect) | architect | 2026-11-15 | READY — DoR complete |
| Receiver (Primary Coder) | `coder-primary` | 2026-11-16 | CODER_DONE — AC-1…AC-8 run; build exit 0; evidence in `workflow/evidence/HO-STRATA-001/` |

## 11. Log

- 2026-11-15 Auditor: owner task OT-STRATA-001 intake; this handoff drafted.
- 2026-11-15 Architect: PROPOSED; pin the Strata commit to reach READY.
- 2026-11-15 Architect: **validation** — §0 rewritten to name both checkouts,
  branches and base commits (the draft named one branch but two repositories, and
  its guard rail "do not touch `gfx1150-inference`" contradicted the evidence
  path inside it). AC-4/AC-5 split into the *engine binary* (`build-hip/strata`)
  vs the *Control CLI* (`strata.py`), which the draft conflated. AC-3 fixed to the
  upstream-documented flag set and `--target strata`. AC-7 pinned to the real
  table path (`tools/hip/gfx1150-hipblaslt-100401.txt`, present at the pin) and
  to the upstream rule that gfx1150 does **not** take it by default. Toolchain
  pre-check recorded as orientation only.
- 2026-11-15 Architect: **pinned** Strata `baf16363b4403ef0ed4f538f5d5ed11c43fb9535`
  (DEC-006); clone at `/home/kupipi/Documents/git/strata`; provenance in
  `workflow/evidence/HO-STRATA-001/artifacts/pinned-commit.txt`.
- 2026-11-15 Architect: branch `wp/strata-001-gfx1150-build` created at
  `a6166f7ebd48eabaffc4809c76c9460b92441cde`; **PROPOSED → READY** (DoR complete).
- 2026-11-16 `coder-primary`: **accepted** (READY → IN_PROGRESS). DoR validated item by item;
  no `NEEDS_INFO`. Switched the workflow repo to `wp/strata-001-gfx1150-build` before writing.
- 2026-11-16 `coder-primary`: **CODER_DONE**. What was run, in order, and the result:
  - AC-1 pin verified — `HEAD baf16363b4403ef0ed4f538f5d5ed11c43fb9535`, porcelain empty,
    origin `https://github.com/Niko1221/Strata`. No re-clone needed.
  - AC-2 toolchain measured — `gfx1150` / `AMD Radeon 890M Graphics` / Ryzen AI 9 HX 370;
    kernel 7.0.0-42; Linux Mint 22.3; HIP 7.16.26385-0000000 (clang 24); ROCm
    `/opt/rocm/core-10.1`; CMake 3.28.3; g++ 13.3.0; Python 3.14.10; ttm 12050777.
    **hipBLASLt `100401` measured** with `hipblasLtGetVersion` (harness in `/tmp`, not in
    either repo) — not inferred from the header.
  - AC-3 **build exit 0**, `build-hip/strata` present (39,736,088 B, sha256 `d58ee239…f5858`).
    The literal AC-3 configure command **failed exit 1** (`find_package(hip)` could not see the
    ROCm prefix; `hip-config.cmake` is at `/opt/rocm/core-10.1/lib/cmake/hip` and `/opt/rocm` is
    a parent of `core*`). Reconfigured with `-DCMAKE_PREFIX_PATH=/opt/rocm/core-10.1` after
    `rm -rf build-hip` (the upstream comment warns about cached-empty HIP flags) → exit 0,
    `-- Strata: HIP enabled, arch gfx1150`. **No Strata source was modified.**
  - AC-4 `--families` → `qwen4exp qwen35moe`, `--geometry` → `flash_next`, both exit 0 under
    `LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib`. The bare first run exited 127
    (`libhipblas.so.3` not found) — a runtime loader path, not a build defect.
  - AC-5 `python3 strata.py launch --plan --no-tui` → **exit 2**, refused verbatim: "No model
    fits this computer by Strata's rules, and none was chosen…". No model installed, downloaded
    or served; `strata launch` was never run without `--plan`.
  - AC-6 `artifacts/engine-boundary.md` written with headings (a)–(e). **Headless answer: yes** —
    nothing from `apps/`/`serve/` is compiled into the `strata` target
    (`cmake/strata_gpu_engine.cmake:510-513`), `strings` finds 0 references to the Python trees,
    and the binary ran its surface modes with exit 0 from a build dir containing neither.
  - AC-7 table SHA256 `aee2867c…ec5549c` equals the pin record; header `gfx1150 100401` vs
    measured runtime `100401` → **MATCH**; **default is the fallback** on gfx1150
    (`src/prefill/gemm.cu:310-311` returns `nullptr` unless `arch == "gfx1151"` or
    `STRATA_HIPBLASLT_TABLE=on`), opt-in via `STRATA_HIPBLASLT_TUNING` (`gemm.cu:278`, checked
    before the gate). Taken-vs-fallback **not observable without a model run** — stated plainly.
  - AC-8 bundle complete: `manifest.md`, `commands.log`, `test-output.txt`, `hashes.txt`,
    `artifacts/` (16 files). Secrets scan clean; no model weights.
  - Integrity: Strata `git status --porcelain` still empty; `build-hip` ignored by
    `.gitignore:12 build*/`; nothing written in `gfx1150-inference` outside
    `workflow/evidence/HO-STRATA-001/**` and this handoff.
  - **Observations for the Architect (not criteria, no action taken):** (i) `--families` does
    **not** list Qwen3.8-Flash-Next, the family the cited gfx1150 community bench measured —
    relevant to HO-002+; (ii) the documented configure recipe lacks the `CMAKE_PREFIX_PATH` step
    that this host needs — an upstream-docs candidate, filed as a report suggestion only;
    (iii) no `ctest` was run (`--target strata` only, per AC-3).
  - `CODER_TO_QAQC` created: `workflow/handoffs/HO-STRATA-001-QAQC.md`.

