# Route 2 confirmation and Route 3 trigger table

**Handoff:** HO-STRATA-005  
**Profile:** AMD Radeon 890M (`gfx1150`), Ryzen AI 9 HX 370, ROCm `/opt/rocm/core-10.1`, HIP 7.16.26385, hipBLASLt 1.4.1 (`100401`). For the generation run: Qwen3.6-35B-A3B `UD-Q4_K_XL`, greedy, 1024 context cells.  
**Basis:** recorded evidence from HO-STRATA-001 and HO-STRATA-007 only; no new measurement, build, model run or download.

## 1. Decision: confirm Route 2

Route 2 (modify Strata directly, pinned patch overlay; upstream PRs optional) is the current least-cost path for gfx1150. The evidence shows the upstream pin already builds, starts headlessly, and runs one low-tier `qwen35moe` generation without any Strata source patch.

## 2. Current cost of Route 2

| Cost item | What the evidence shows | Source |
|---|---|---|
| **Configure-time path** | `cmake` fails unless `-DCMAKE_PREFIX_PATH=/opt/rocm/core-10.1` is supplied; the literal command exits 1 with `Could not find a package configuration file provided by "hip"`. | HO-001 `artifacts/configure.log` |
| **Run-time loader path** | The built `strata` binary exits 127 with `error while loading shared libraries: libhipblas.so.3` unless `LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib` is set. | HO-001 `artifacts/families.txt`; HO-007 `manifest.md` §5 |
| **hipBLASLt tuning table** | `tools/hip/gfx1150-hipblaslt-100401.txt` is present, its SHA256 matches the pin, and both the arch (`gfx1150`) and version (`100401`) header fields match the local runtime. On `gfx1150` the table is **not** taken by default; the source path returns `nullptr` unless `STRATA_HIPBLASLT_TUNING` is set. | HO-001 `artifacts/tuning-table.md` |
| **`--native` one-shot path** | `strata.py launch --plan …` reports `"engine_missing": true` and `"engine_usable": false` for gfx1150, so the tested path is the engine binary invoked directly with `--native <GGUF>`. | HO-007 `artifacts/control-plan-qwen36.json` |
| **Strata source patches** | **Zero.** Both HO-001 and HO-007 ran with `git status --porcelain` empty on the Strata checkout at `baf16363b4403ef0ed4f538f5d5ed11c43fb9535`. | HO-001 `artifacts/verify-pin.txt`; HO-007-APPROVAL.md §2 |

The cost of Route 2 today is therefore an **environment contract** (two path variables) plus a **pinned commit**, not a maintained patch set.

## 3. Route 3 triggers

Route 3 (fork + P0–P9 capability framework) is **deferred, not rejected**. The table below records the conditions that would reopen it. Each trigger is measurable, names the check that evaluates it, and names the handoff or role that owns the response.

| # | Trigger | Check | Owner if fired | Why it is measurable |
|---|---|---|---|---|
| **T1** | A requested family needs an engine path the pin lacks (new attention kernel, kernel variant, or quant type) and the change cannot be expressed as a localized patch. | Run the family's low-tier test; failure must be a **structural** error (missing kernel/attention path, unsupported GGUF architecture) rather than a configuration error. | Architect → HO-006 or new HO | The result is a pass/fail exit code plus the engine's error string; DEC-003 keeps the three test beds fixed, so the test is repeatable. |
| **T2** | The patch set grows past a small bound: **>5 files or >300 inserted lines** across the overlay. | `git diff --stat` against the pinned commit (`baf16363`). | Architect | A file/line count is a direct `git` output. Rationale for the threshold: HO-001/007 establish that the gfx1150 path costs zero source patches today; a patch larger than one small feature or build fix begins to behave like a maintained fork overlay and raises rebase/review risk. The number is a defensible working threshold, not a measured bound. |
| **T3** | Rebasing the overlay against upstream conflicts on **2 of 3 consecutive pin updates**, or the pin is abandoned upstream. | Rebase log per pin bump; count consecutive conflicts. | Architect | Each pin update produces a rebase record with conflict markers or a clean result; 2-of-3 is a countable sequence. |
| **T4** | A second hardware class (`gfx1100`, `gfx900`/MI25, or later `gfx1201`) enters the critical path. | A scope decision in `DECISIONS.md` names the second hardware class as required. | Owner via Auditor | The decision is a dated, signed record; no inference from benchmarks is needed. |
| **T5** | The deliverable becomes an **independent, machine-gated engine** with its own API/CLI contract. | A scope decision in `DECISIONS.md` declares the engine an independent product/API boundary. | Owner | Same as T4: the trigger is the existence of a recorded scope decision. |

## 4. Reversal cost

If Route 2 is confirmed now and a trigger fires later, the following is lost or must be paid again:

- **Clean upstream baseline.** Every patch applied after confirmation becomes inventory that must be migrated to a fork or reapplied to a new pin.
- **Pin stability.** The longer Route 2 runs, the more likely a forced pin bump (T3) invalidates existing patches.
- **Evidence transfer.** HO-001 and HO-007 remain valid as recorded evidence, but any post-confirmation patches are not proven on Route 3; they must be re-validated on the forked tree.

The reversal cost is therefore **rebase + re-validation of the patch inventory**, not loss of the existing gfx1150 baseline.

## 5. Limitations

- No performance, throughput, quality or support claim is made.
- Every number carries the profile listed at the top of this document.
- Route 3 is deferred; this document does not cost or plan it.
