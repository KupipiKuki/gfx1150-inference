# HO-STRATA-001 — gfx1150 build, support check, and engine boundary

| Field | Value |
|---|---|
| **ID** | HO-STRATA-001 |
| **Type** | ARCHITECT_TO_CODER |
| **State** | PROPOSED |
| **Created / updated (UTC)** | 2026-11-15 / 2026-11-15 |
| **From → To** | Architect → Primary Coder |
| **Work package** | gfx1150 build/support baseline |
| **Branch / base commit** | `wp/strata-001-gfx1150-build` in the Strata checkout / **TBD — pin the Strata commit at execution** |
| **Priority / timebox** | P0 · 1 working day |

## 1. Scope (in)

- Clone the pinned Strata commit into a separate checkout (not the
  `gfx1150-inference` repository).
- Record the toolchain: `rocminfo`, `hipcc --version`, kernel,
  `linux-firmware`, Python, CMake, C++ compiler.
- Configure and build for gfx1150:
  `-DCMAKE_HIP_ARCHITECTURES=gfx1150`, `-DSTRATA_ENABLE_HIP=ON`,
  `-DSTRATA_ENABLE_CUDA=OFF`.
- Record `strata --families` and `strata launch --plan`.
- Inspect the engine boundary: the `src/`, `include/` engine vs `apps/`,
  `serve/`, `strata_cli/`; can the engine run without the app/server?
- Record whether `gfx1150-hipblaslt-100401.txt` matches the local hipBLASLt
  version and whether it is taken or falls back.

## 2. Out of scope

- Downloading or running models (HO-STRATA-002/003/004).
- Modifying Strata source; record blockers instead.
- The 780M, MI25, gfx1100.
- Performance or support claims.
- The P0–P9 capability framework.

## 3. Inputs

| Input | Path / source | Status |
|---|---|---|
| Strata repository | `https://github.com/Niko1221/Strata` | available |
| Strata AMD doc | `docs/AMD_HIP.md` | available |
| Strata engine doc | `docs/HOW_IT_WORKS.md`, `AGENTS.md` | available |
| Workflow | `workflow/ENGINEERING_WORKFLOW.md`, `HANDOFF_CONTRACT.md` | available |

## 4. Acceptance criteria

| # | Criterion | Command / check | Expected |
|---|---|---|---|
| 1 | Pinned commit recorded | `git rev-parse HEAD` in the Strata checkout | 40-char SHA in the manifest |
| 2 | Toolchain recorded | `rocminfo`, `hipcc --version`, `uname -a`, firmware | raw output in the evidence |
| 3 | gfx1150 build | `cmake -S . -B build-hip -DSTRATA_ENABLE_HIP=ON -DSTRATA_ENABLE_CUDA=OFF -DCMAKE_HIP_ARCHITECTURES=gfx1150` + `cmake --build build-hip` | exit 0 or a documented blocker with the log |
| 4 | Support surface | `strata --families`, `strata launch --plan` | output recorded; supported/unsupported families named |
| 5 | Engine boundary | read `src/`, `include/`, `serve/`, `apps/` | a one-page note: engine vs app/server; can it run headless? |
| 6 | Tuning table | check the table header vs hipBLASLt | match/fallback recorded with the version |
| 7 | Evidence | `workflow/evidence/HO-STRATA-001/` | manifest complete; no secrets |

## 5. Evidence required

- `workflow/evidence/HO-STRATA-001/manifest.md`
- `commands.log`, `test-output.txt`, `artifacts/` (build log, `--families`,
  `--plan`), `hashes.txt` (pinned SHA, table hash).
- No model weights; no secrets.

## 6. Guard rails

- Do not modify the Strata source in this handoff; record build blockers.
- Do not download models.
- Do not touch the `gfx1150-inference` repo; use a separate Strata checkout.
- Do not claim performance or support; this is a build/support spike.
- No secrets/tokens in the repo or logs.

## 7. Dependencies / blockers

| Dependency | Owner | Status | Needed by |
|---|---|---|---|
| Strata commit to pin | Architect | open | before READY |
| Network for clone/build | Coder | assumed | execution |

## 8. Definition of Ready

- [x] ID/type/from/to/title/work package present
- [ ] Branch and base commit named — **pin the Strata commit before READY**
- [x] Scope and out-of-scope explicit
- [x] Inputs linked
- [x] Every criterion has a command/check
- [x] Evidence requirements runnable
- [x] Guard rails explicit
- [x] Dependencies named
- [x] Priority/timebox set
- [x] No open `NEEDS_INFO`

## 9. Definition of Done

- [ ] Pinned SHA and toolchain recorded
- [ ] Build attempted; exit 0 or a documented blocker
- [ ] `--families`/`--plan` recorded
- [ ] Engine-boundary note written
- [ ] Tuning-table match/fallback recorded
- [ ] Evidence manifest complete
- [ ] Handoff updated; HO-STRATA-002 created (or a blocker/deviation raised)

## 10. Signatures

| Role | Name/agent | Date | Decision |
|---|---|---|---|
| Sender (Architect) | | | |
| Receiver (Coder) | | | |

## 11. Log

- 2026-11-15 Auditor: owner task OT-STRATA-001 intake; this handoff drafted.
- 2026-11-15 Architect: PROPOSED; pin the Strata commit to reach READY.
