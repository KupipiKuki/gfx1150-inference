# HO-STRATA-001-QAQC — independent review of the gfx1150 build, CLI surface, and boundary note

| Field | Value |
|---|---|
| **ID** | HO-STRATA-001-QAQC |
| **Type** | `CODER_TO_QAQC` |
| **State** | **QAQC_REVIEW** (awaiting QAQC acceptance) |
| **Created / updated (UTC)** | 2026-11-16 / 2026-11-16 |
| **From → To** | `coder-primary` → `qaqc` |
| **Work package** | `strata-001-gfx1150-build` (parent: HO-STRATA-001) |
| **Branch / base commit** | `wp/strata-001-gfx1150-build` / `a6166f7ebd48eabaffc4809c76c9460b92441cde` |
| **Priority / timebox** | P0 · QAQC review within 1 working day of CODER_DONE |
| **Evidence root** | `workflow/evidence/HO-STRATA-001/` |

Two checkouts are involved and QAQC must not confuse them:

| Checkout | Path | Branch | What changed |
|---|---|---|---|
| Workflow repo | `/home/kupipi/Documents/git/gfx1150-inference` | `wp/strata-001-gfx1150-build` | `workflow/evidence/HO-STRATA-001/**`, `workflow/handoffs/HO-STRATA-001.md`, this file |
| Strata (read-only input) | `/home/kupipi/Documents/git/strata` | **none** (pinned tree) | **nothing**; only git-ignored `build-hip/` was created |

## 1. What was done

1. Validated the DoR, switched the workflow repo to the work-package branch, and ran AC-1…AC-8 in
   order against the pinned Strata checkout `baf16363b4403ef0ed4f538f5d5ed11c43fb9535`.
2. Recorded the toolchain, including a **measured** hipBLASLt version (`100401`) obtained via
   `hipblasLtGetVersion` from a throwaway harness in `/tmp/opencode/hblt-ver/` (outside both
   repos, nothing installed). This is stronger than reading the header, and it is what makes the
   AC-7 "match" claim a measurement rather than an inference.
3. Configured and built the HIP engine for `gfx1150`; **build exit 0**, `build-hip/strata` present.
   Two host-environment obstacles were hit and are documented rather than hidden:
   - configure needs `-DCMAKE_PREFIX_PATH=/opt/rocm/core-10.1` (the literal AC-3 command exits 1);
   - the built binary needs `LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib` to start (bare run exits 127).
   Neither was "fixed" by editing Strata source, installing a package, or changing the criteria.
4. Captured the engine binary's support surface (`--families`, `--geometry`, `--help`) and the
   Control CLI's `launch --plan` refusal.
5. Wrote the two narrative deliverables: `artifacts/engine-boundary.md` (AC-6, five headings) and
   `artifacts/tuning-table.md` (AC-7).
6. Assembled the evidence bundle and committed on the work-package branch.

**Headline results QAQC should check against the raw logs, not this summary:**

| Item | Result |
|---|---|
| Build | **exit 0**; `build-hip/strata`, 39,736,088 B, sha256 `d58ee2398596d1a100c15d5b9459e24bd86854cb5e5fb7ce88dbc6c7ed9f5858` |
| `--families` | `qwen4exp qwen35moe` (exit 0) |
| `--geometry` | `flash_next` (exit 0) |
| Control `launch --plan --no-tui` | exit **2**, refused: `No model fits this computer by Strata's rules, and none was chosen…` |
| Tuning table | SHA256 `aee2867c…ec5549c`; header `gfx1150 100401` vs runtime `100401` → **MATCH**; **default = fallback** on gfx1150 |
| Headless without `apps/`+`serve/` | **yes** (three lines of evidence in the note) |
| Strata tree | `git status --porcelain` empty |

## 2. Scope (in) — what QAQC reviews

- The evidence bundle under `workflow/evidence/HO-STRATA-001/` against AC-1…AC-8 of
  `workflow/handoffs/HO-STRATA-001.md`.
- The diff on `wp/strata-001-gfx1150-build` versus base `a6166f7e`, for scope and guard rails.
- The two narrative notes for accuracy against the files they cite.

## 3. Out of scope — do not do these

- **Do not modify code, tests, docs, configuration, evidence, or handoffs.** QAQC is read-only
  everywhere except `workflow/reports/qaqc/`.
- **Do not download, install or serve a model.** No `strata launch` without `--plan`. If you think
  the model-run gap is a problem, that is a finding for the report, not a thing to remedy here.
- **Do not install packages or upgrade ROCm** to "make the build cleaner". `ccache` is absent and
  that is fine.
- **Do not edit the Strata checkout**, and do not `git clean` its `build-hip/` for tidiness.
- No 780M / MI25 / gfx1100 / gfx1151 / gfx1201 work or comparison.
- No performance, support, or quality claims; there is no model in this handoff to measure.

## 4. Exact commands QAQC should re-run

Run these yourself and compare against the bundle. Set `OUT` as shown; **do not overwrite the
coder's artifacts** — write your own under `/tmp/opencode/`.

```sh
export OUT=/home/kupipi/Documents/git/gfx1150-inference/workflow/evidence/HO-STRATA-001
mkdir -p /tmp/opencode/qaqc-strata001

# --- AC-1: the pin, and the tree is untouched -------------------------------
cd /home/kupipi/Documents/git/strata
git rev-parse HEAD                    # expect baf16363b4403ef0ed4f538f5d5ed11c43fb9535
git status --porcelain                # expect EMPTY  (build-hip is ignored by .gitignore:12 build*/)
git check-ignore -v build-hip         # expect: .gitignore:12:build*/   build-hip

# --- AC-2: toolchain ---------------------------------------------------------
uname -a; cat /etc/os-release; dpkg -l linux-firmware; rocminfo | head -80
hipcc --version; cmake --version; c++ --version; python3 --version
cat /sys/module/ttm/parameters/pages_limit
grep -E 'HIPBLASLT_VERSION_(MAJOR|MINOR|PATCH)' /opt/rocm/core-10.1/include/hipblaslt/hipblaslt-version.h
# cross-check the coder's measured version (the harness source is quoted in the bundle):
cat $OUT/artifacts/hipblaslt-version-probe.txt

# --- AC-3: the build (RE-RUN THE LITERAL COMMAND FIRST; it is expected to fail) ---
cd /home/kupipi/Documents/git/strata
cmake -S . -B /tmp/opencode/qaqc-strata001/b1 -DCMAKE_BUILD_TYPE=Release \
      -DSTRATA_ENABLE_HIP=ON -DSTRATA_ENABLE_CUDA=OFF -DCMAKE_HIP_ARCHITECTURES=gfx1150
# expect exit 1: "Could not find a package configuration file provided by \"hip\""
# then with the prefix the coder added:
cmake -S . -B /tmp/opencode/qaqc-strata001/b2 -DCMAKE_BUILD_TYPE=Release \
      -DSTRATA_ENABLE_HIP=ON -DSTRATA_ENABLE_CUDA=OFF -DCMAKE_HIP_ARCHITECTURES=gfx1150 \
      -DCMAKE_PREFIX_PATH=/opt/rocm/core-10.1
# expect exit 0 and the line: -- Strata: HIP enabled, arch gfx1150
# Either rebuild into /tmp (long, ~3 min) or verify the coder's binary in place:
ls -l build-hip/strata && sha256sum build-hip/strata && file build-hip/strata

# --- AC-4: engine support surface -------------------------------------------
LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib ./build-hip/strata --families; echo "exit=$?"
LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib ./build-hip/strata --geometry; echo "exit=$?"
# negative check the coder recorded: without the loader path it exits 127
./build-hip/strata --families; echo "exit=$?"

# --- AC-5: Control CLI plan (never without --plan) ----------------------------
cd /home/kupipi/Documents/git/strata
python3 strata.py launch --plan --no-tui; echo "exit=$?"
python3 strata.py launch --plan --no-tui --output json; echo "exit=$?"

# --- AC-6: the boundary claim, checked independently -------------------------
ldd build-hip/strata | head -20
ls build-hip/ | head -20
strings -a build-hip/strata | grep -c 'strata_cli\|strata_control\|serve/server'   # expect 0
sed -n '505,520p' cmake/strata_gpu_engine.cmake      # the `strata` target's sources/links
grep -n 'Popen\|subprocess' serve/server.py | grep -i engine | head              # server spawns the binary
sed -n '30,66p' src/core/device.cu                   # arch gate + wave32 requirement

# --- AC-7: tuning table ------------------------------------------------------
sha256sum tools/hip/gfx1150-hipblaslt-100401.txt
head -2 tools/hip/gfx1150-hipblaslt-100401.txt
sed -n '276,340p' src/prefill/gemm.cu                # the gfx1151-only default gate
sed -n '619,640p' docs/AMD_HIP.md

# --- AC-8: bundle integrity --------------------------------------------------
cd /home/kupipi/Documents/git/gfx1150-inference
ls -R workflow/evidence/HO-STRATA-001/
cd workflow/evidence/HO-STRATA-001 && sha256sum -c <(grep -E '^[0-9a-f]{64}  (manifest|commands|test-output)' hashes.txt)
```

## 5. Evidence required (already produced — verify, do not regenerate)

- `manifest.md`, `commands.log`, `test-output.txt`, `hashes.txt`.
- `artifacts/`: `verify-pin.txt`, `toolchain.txt`, `hipblaslt-version-probe.txt`,
  `configure.log`, `build.log`, `families.txt`, `geometry.txt`, `help.txt`, `launch-plan.txt`,
  `control-launch-help.txt`, `engine-deps.txt`, `boundary-layout.txt`, `tuning-table-raw.txt`,
  `engine-boundary.md`, `tuning-table.md`, and the Architect's `pinned-commit.txt` (kept as-is).
- Expected QAQC output: `workflow/reports/qaqc/HO-STRATA-001-qaqc.md`, PASS → auditor, FAIL →
  `RW-HO-STRATA-001-<n>` back to `coder-primary`.

## 6. Guard rails for QAQC

- Read-only outside `workflow/reports/qaqc/`.
- Do not change acceptance criteria; disagreements go in the report.
- Do not merge, do not push to `main`.
- No secrets in the report; do not paste anything from a credential store.
- Judge the **evidence**, not the summary in this document.

## 7. Known limits and things QAQC should NOT treat as defects

These are deliberate and documented in `manifest.md` §4. If QAQC disagrees, it is a finding about
whether the handoff's criteria were met — but none of them is a hidden failure:

1. **The literal AC-3 configure command exits 1.** Documented and diagnosed; the coder then used
   `-DCMAKE_PREFIX_PATH`. Question for QAQC: is that flag within the handoff's guard rails
   (a configure option, no source edit, no install)? The coder's position is yes — CMake's own
   error text names it, and `docs/AMD_HIP.md:191-192` documents the same class of adaptation.
2. **`--families` needs `LD_LIBRARY_PATH`.** Host environment, not a link defect.
3. **AC-5 exits 2.** AC-5 explicitly permits the refusal; no model exists and none may be fetched.
4. **No model was ever run.** Therefore no claim about generation working on gfx1150 is made, and
   AC-7's "taken vs fallback" half is unobservable. The note says this plainly. The *static*
   reading of `gemm.cu:310-311` is offered as a source fact, labelled as such.
5. **No `ctest`.** AC-3 specifies `--target strata` only. The configure summary's
   `-- strata tests: ON - cpu, hip` means the suite was registered, not built or run.
6. **`--families` omits Qwen3.8-Flash-Next** — flagged to the Architect as an observation for
   HO-002+, not an AC-4 failure.
7. **The hipBLASLt probe harness is in `/tmp`, not in the repo.** Intentional: the guard rails
   confine writes to the evidence directory, and the harness source is quoted verbatim inside the
   artifact so the measurement is reproducible.

## 8. Definition of Ready

- [x] ID/type/from/to/title/work package present
- [x] Branch and base commit named (`wp/strata-001-gfx1150-build` @ `a6166f7e`)
- [x] Scope and out-of-scope explicit (§2, §3)
- [x] Inputs linked and available (evidence bundle + pinned Strata tree)
- [x] Every criterion has a command/check (§4)
- [x] Evidence requirements runnable (§5)
- [x] Guard rails explicit (§6)
- [x] Dependencies resolved or owned (§7 — none blocking)
- [x] Priority/timebox set (P0 · 1 working day)
- [x] No open `NEEDS_INFO` from the receiver

## 9. Definition of Done (for this QAQC handoff)

- [ ] QAQC ran every command in §4 and compared to the bundle
- [ ] Diff on `wp/strata-001-gfx1150-build` checked against scope and guard rails
- [ ] `workflow/reports/qaqc/HO-STRATA-001-qaqc.md` written from the template
- [ ] PASS → auditor, or FAIL → `RW-HO-STRATA-001-<n>` to `coder-primary`
- [ ] No files outside `workflow/reports/qaqc/` modified by QAQC

## 10. Signatures

| Role | Name/agent | Date | Decision |
|---|---|---|---|
| Sender (Primary Coder) | `coder-primary` | 2026-11-16 | CODER_DONE — review requested |
| Receiver (QAQC) | `qaqc` | | |

## 11. Log

- 2026-11-16 `coder-primary`: created; HO-STRATA-001 moved READY → IN_PROGRESS → **CODER_DONE**.
  Evidence at `workflow/evidence/HO-STRATA-001/`. State set to `QAQC_REVIEW` for acceptance.
- 2026-11-16 `coder-primary`: **commit provenance.** Content committed by two parent-session
  commits: `5a64aac` (manifest, hashes, test-output, 14 artifacts, `HO-STRATA-001.md`) and
  `3bb67fc` (`commands.log`, `artifacts/build.log`, `artifacts/configure.log`,
  `HO-STRATA-001.md`, this file). Work package recorded by an explicit commit with the subject
  `HO-STRATA-001: gfx1150 HIP engine builds; surface, boundary and tuning notes`, naming both
  commits. Reason: concurrent commits swept the staged paths before the coder's own commit ran,
  and shared history is not rewritten (§9). The SHA is deliberately not inlined — a commit cannot
  name its own hash; read it with `git log -1 --format=%H wp/strata-001-gfx1150-build`.
  See `manifest.md` §7. Branch `wp/strata-001-gfx1150-build`, base `a6166f7e`, not merged, not
  pushed to `main`.

