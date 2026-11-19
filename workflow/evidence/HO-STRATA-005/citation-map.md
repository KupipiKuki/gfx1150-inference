# Citation map — HO-STRATA-005 route decision

One row per factual claim in `route-decision.md`. The quoted string or value is the exact evidence used.

| # | Claim in `route-decision.md` | HO ID | Evidence file | Exact quoted string / value |
|---|---|---|---|---|
| 1 | Route 2 is the current least-cost path for gfx1150. | HO-STRATA-001 | `artifacts/verify-pin.txt` | `baf16363b4403ef0ed4f538f5d5ed11c43fb9535` + `git status --porcelain` empty |
| 2 | The upstream pin already builds for gfx1150. | HO-STRATA-001 | `artifacts/build.log` | `cmake --build build-hip --target strata -j$(nproc)` → `Built target strata` (exit 0 at end) |
| 3 | The built engine starts headlessly. | HO-STRATA-001 | `artifacts/engine-boundary.md` | `No trace of them in the binary` + `strata_cli\|strata_control\|serve/server` → **0**; `--families` → `qwen4exp qwen35moe`, exit 0 |
| 4 | Configure fails without `CMAKE_PREFIX_PATH`. | HO-STRATA-001 | `artifacts/configure.log` | `CMake Error at cmake/hip_backend.cmake:58 (find_package): Could not find a package configuration file provided by "hip"` + `configure exit=1` |
| 5 | Configure succeeds with `-DCMAKE_PREFIX_PATH=/opt/rocm/core-10.1`. | HO-STRATA-001 | `artifacts/configure.log` | `cmake -S . -B build-hip … -DCMAKE_PREFIX_PATH=/opt/rocm/core-10.1` + `configure (retry 1) exit=0` |
| 6 | Run-time loader fails without `LD_LIBRARY_PATH`. | HO-STRATA-001 | `artifacts/families.txt` | `./build-hip/strata: error while loading shared libraries: libhipblas.so.3` + `exit:127` |
| 7 | Run-time loader succeeds with `LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib`. | HO-STRATA-001 | `artifacts/families.txt` | `LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib ./build-hip/strata --families` → `qwen4exp qwen35moe` + `exit:0` |
| 8 | `LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib` is required at run time. | HO-STRATA-007 | `manifest.md` §5 | `` `LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib` is required; without it the binary exits 127 with missing shared libraries `` |
| 9 | The gfx1150 hipBLASLt tuning table is present. | HO-STRATA-001 | `artifacts/tuning-table.md` | `Path | tools/hip/gfx1150-hipblaslt-100401.txt` + `146 lines` |
| 10 | The table SHA256 matches the Architect's pin record. | HO-STRATA-001 | `artifacts/tuning-table.md` | `SHA256 | aee2867c096887cccaef8bc04a9ef10adec43da58421edfdaaec04a61ec5549c` |
| 11 | The table header arch is `gfx1150` and version is `100401`. | HO-STRATA-001 | `artifacts/tuning-table.md` | `STRATA_HIPBLASLT_TUNING_V1 gfx1150 100401` |
| 12 | Local hipBLASLt runtime version is `100401`. | HO-STRATA-001 | `artifacts/hipblaslt-version-probe.txt` | `hipblasLtGetVersion = 100401` |
| 13 | On `gfx1150` the table is not taken by default. | HO-STRATA-001 | `artifacts/tuning-table.md` | `if (!table_forced && arch != "gfx1151") return nullptr; // gemm.cu:322` + `plain hipBLAS (fallback), not the table` |
| 14 | Opt-in is via `STRATA_HIPBLASLT_TUNING`. | HO-STRATA-001 | `artifacts/tuning-table.md` | `STRATA_HIPBLASLT_TUNING=/abs/path/gfx1150-hipblaslt-100401.txt` + `getenv is checked before the gfx1151 gate, so it wins on any card` |
| 15 | `strata.py launch --plan` reports `engine_missing: true` for gfx1150. | HO-STRATA-007 | `artifacts/control-plan-qwen36.json` | `"engine_missing": true, "engine_usable": false` |
| 16 | The tested generation path is the engine binary with `--native <GGUF>`. | HO-STRATA-007 | `test-output.txt` | `LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib ./build-hip/strata --native /tmp/opencode/qwen36/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf …` + `exit:0` |
| 17 | The low-tier run used Qwen3.6-35B-A3B `UD-Q4_K_XL`, greedy, 1024 context. | HO-STRATA-007 | `manifest.md` §1 / §4 | `command #6 … --n 32 --max-context 1024` + `One profile only: AMD gfx1150 / Qwen3.6-35B-A3B / UD-Q4_K_XL / greedy / 1024 context cells` |
| 18 | Zero Strata source patches; HO-001 checkout was clean. | HO-STRATA-001 | `artifacts/verify-pin.txt` | `git status --porcelain` → empty + `exit=0` |
| 19 | Zero Strata source patches; HO-007 checkout was clean. | HO-STRATA-007 | `HO-STRATA-007-APPROVAL.md` §2 | `no Strata source change (git -C …/strata status --porcelain empty, HEAD baf16363…)` |
| 20 | The pinned commit is `baf16363b4403ef0ed4f538f5d5ed11c43fb9535`. | HO-STRATA-001 | `artifacts/verify-pin.txt` | `git rev-parse HEAD` → `baf16363b4403ef0ed4f538f5d5ed11c43fb9535` |
| 21 | Route 3 is deferred, not rejected; trigger table is the reversal record. | HO-STRATA-005 | `workflow/handoffs/HO-STRATA-005.md` | `Route 3 is **deferred, not` + `rejected**; the trigger table is the record of what would reopen it` |
| 22 | T1: a requested family needs an engine path the pin lacks. | HO-STRATA-005 | `workflow/handoffs/HO-STRATA-005.md` §5 | `A requested family needs an engine path the pin lacks …` / `the family’s low-tier test fails with a structural error` |
| 23 | T1 ownership: Architect → HO-006. | HO-STRATA-005 | `workflow/handoffs/HO-STRATA-005.md` §5 | `Architect → HO-006` |
| 24 | T2: patch set grows past >5 files or >300 lines. | HO-STRATA-005 | `workflow/handoffs/HO-STRATA-005.md` §5 | `The patch set grows past a small bound (threshold set in the decision, e.g. >5 files or >300 lines)` |
| 25 | T2 check: `git diff --stat` against the pin. | HO-STRATA-005 | `workflow/handoffs/HO-STRATA-005.md` §5 | `git diff --stat` against the pin` |
| 26 | T3: rebase conflicts on 2 of 3 consecutive pin updates, or pin abandoned. | HO-STRATA-005 | `workflow/handoffs/HO-STRATA-005.md` §5 | `Rebasing the overlay against upstream conflicts on 2 of 3 consecutive pin updates, or the pin is abandoned upstream` |
| 27 | T4: a second hardware class enters the critical path. | HO-STRATA-005 | `workflow/handoffs/HO-STRATA-005.md` §5 | `A second hardware class (gfx1100, gfx900/MI25) enters the critical path` |
| 28 | T5: deliverable becomes an independent, machine-gated engine with its own API/CLI contract. | HO-STRATA-005 | `workflow/handoffs/HO-STRATA-005.md` §5 | `The deliverable becomes an independent, machine-gated engine with its own API/CLI contract` |
| 29 | T4/T5 check: scope decision in `DECISIONS.md`. | HO-STRATA-005 | `workflow/handoffs/HO-STRATA-005.md` §5 | `scope decision in DECISIONS.md` |
| 30 | The T2 threshold rationale is that HO-001/007 cost zero patches today. | HO-STRATA-001 | `artifacts/verify-pin.txt` | `git status --porcelain` empty |
| 31 | The T2 threshold rationale is that HO-007 also cost zero patches. | HO-STRATA-007 | `HO-STRATA-007-APPROVAL.md` §2 | `no Strata source change (git -C …/strata status --porcelain empty, HEAD baf16363…)` |
