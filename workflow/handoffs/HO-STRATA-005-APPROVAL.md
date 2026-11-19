# Architect approval — HO-STRATA-005

| Field | Value |
|---|---|
| **Handoff** | HO-STRATA-005 — confirm Route 2 and define the Route 3 triggers |
| **Architect** | architect (DeepSeek session model, WAIVER-001 seat) |
| **Date (UTC)** | 2026-11-17 |
| **Decision** | **SIGNED** → state `DONE`; recorded as **DEC-021** |
| **Evidence** | `workflow/evidence/HO-STRATA-005/` at `01d568d` |
| **Branch / base** | `wp/strata-005-route-decision` / `8c1a291` |

## 1. Criteria trace

| # | Criterion | Evidence | Architect |
|---|---|---|---|
| 1 | Route 2 confirmed with its current cost enumerated (two env requirements, opt-in table, `--native`, zero patches) | `route-decision.md` §2 | PASS |
| 2 | Every factual sentence cites an HO ID + evidence file | `citation-map.md` — 31 rows, all resolve | PASS |
| 3 | Five measurable Route 3 triggers with check and owner | `route-decision.md` §3 (T1–T5) | PASS |
| 4 | Reversal cost stated | `route-decision.md` §4 | PASS |
| 5 | No new measurement, build, model run or download | diff `8c1a291..01d568d`: docs + evidence only | PASS |
| 6 | Decision recorded in `DECISIONS.md` as DEC-021 | this signoff | PASS |
| 7 | No performance/support/quality claim; one profile per number | `route-decision.md` header + §5 | PASS |

## 2. Architect verification

Independently checked against the merged evidence (not the summary):

- **Zero patches** — `verify-pin.txt` shows `git status --porcelain` empty at
  `baf16363…`; `HO-STRATA-007-APPROVAL.md` §2 records the same for the run. Both
  the build and the generation were patch-free.
- **Configure-time requirement** — `configure.log:28` carries the literal
  `Could not find a package configuration file provided by "hip"` and
  `exit=1`; the retry with `-DCMAKE_PREFIX_PATH` succeeds.
- **Run-time requirement** — `test-output.txt:32925` carries
  `libhipblas.so.3: cannot open shared object file`; `families.txt` shows
  `exit:127` without `LD_LIBRARY_PATH`.
- **Opt-in table** — `tuning-table.md` records the version/arch match and
  `gemm.cu:322`'s `if (!table_forced && arch != "gfx1151") return nullptr;`,
  i.e. plain hipBLAS is the default on gfx1150.
- **`--native` path** — `control-plan-qwen36.json` records
  `engine_missing: true` / `engine_usable: false`; the engine rejects
  `generate` with `unknown argument: generate` (exit 2).
- **Hashes** — `sha256sum -c workflow/evidence/HO-STRATA-005/hashes.txt` →
  **19/19 OK**, exit 0.

## 3. QAQC / audit

Recorded as `N/A — no code, no measurement, no artifact claim` in the handoff
§10. The integrity of this decision rests on citations, and the architect
verified each material one against the merged bundles above. A QAQC re-run would
re-read the same files without adding independence, and the auditor gate exists
to test claims backed by artifacts — there are none here. This is a disclosed
exception, not an omission.

## 4. Decision recorded

**DEC-021** in `workflow/DECISIONS.md`:

- Route 2 (pinned patch overlay) **confirmed**.
- Route 3 **deferred, not rejected**; the five triggers T1–T5 are adopted as the
  reopening conditions, with the T2 bound (>5 files or >300 inserted lines
  against the pin) as a working threshold, not a measured bound.
- The reversal cost is rebase + re-validation of the patch inventory; the gfx1150
  baseline itself does not expire.

## 5. Limits

- This is a decision, not a plan: no fork work, no P0–P9, no family support.
- HO-002/003/004 stay `BLOCKED` (DEC-016); HO-006 stays `DEFERRED`. The trigger
  table does not unblock them — T1 firing would *start* that conversation.
- The gfx1150 baseline remains one profile (`Qwen3.6-35B-A3B`, `UD-Q4_K_XL`,
  greedy, 1024 context); no performance, throughput, quality or support claim is
  made for any route.

| Role | Signature | Date |
|---|---|---|
| Architect | architect (DeepSeek session model, WAIVER-001 seat) | 2026-11-17 |
