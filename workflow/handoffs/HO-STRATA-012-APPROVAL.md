# Architect approval — HO-STRATA-012

| Field | Value |
|---|---|
| **Handoff** | HO-STRATA-012 — DeepSeek S1–S3 |
| **Architect** | architect (session model; WAIVER-001 seat) |
| **Date (UTC)** | 2026-11-20 |
| **Decision** | **SIGNED** → state `DONE`; recorded as **DEC-037** |
| **Evidence** | `workflow/evidence/HO-STRATA-012/` (bundle assembled at `66267d2`) |
| **Branch / base** | `wp/strata-012-deepseek-s1` / `main` `8ce28c4` |

## 1. Result

The engine now recognizes `deepseek`, reads its geometry from metadata and can
inventory its tensors — and refuses to run it by name:

```text
DeepSeek-MoE-16B-base (architecture 'deepseek') is recognised by Strata
but this build does not run it yet
```

Verified by three parties: `--inspect` matches all 12 geometry fields and finds
**363** tensors; `--native` refuses with exit 2 and no PLE text; `--families`
remains `qwen4exp qwen35moe`; the Qwen regression is bit-identical; the signed
binary was never touched.

The patch is **6 files / 234 insertions / 31 deletions**, exported and
`git apply --check` clean against `baf16363`.

## 2. Gates

| Gate | Verdict |
|---|---|
| Coder | CODER_DONE |
| Deviation | `DR-1` raised at the T2 file bound; **approved** (DEC-034) |
| QAQC | **PASS** on the Claude Sonnet seat (DEC-036) |
| Audit | **PASS (WAIVED)** with four record-only conditions, all closed here |

## 3. T2, and what it actually bought

The trigger fired on the file count (6 > 5) at 234 lines. The review found
metadata, geometry, a read-only inspection mode and tests — no kernel, no forward
path. **The auditor corrected the record:** the sixth file is needed by
`--inspect`, not by the `--native` refusal (`generate.cpp` never calls
`check_architecture`). The conclusion stands; the rationale in DEC-034 is amended
below so the reasoning is not left wrong.

The overlay inventory is now **6 files / 234 insertions**, tracked cumulatively.
The next increment that touches kernels, or pushes past 300 inserted lines,
starts a fresh review with a Route 3 comparison on the table.

## 4. Findings

| # | Finding | Disposition |
|---|---|---|
| **F1** | `model_family_not_supported` is family-generic; dropping the CUDA/HIP/SYCL suffix also changes the `qwen35moe` guard text | **Accepted scope** — text only, Qwen run path untouched (regression exact). Recorded here so it is not absorbed silently. Fix when that function is next touched. |
| **F2** | `check_architecture_deepseek` only checks presence/numeric; ranges are checked in `geometry_from_gguf` | **Carried to S4**, where a loader will exercise it. |
| **F3** | The mismatch fixture was reused rather than regenerated | **Closed** — recipe added to the manifest; the 10.8 GB copy is deleted. |
| **A1** | Pins said "(this bundle's commit)" with no SHA or digest | **Closed** — pinned at `66267d2` with digests. |
| **A2** | DEC-034 attributed the sixth file to the refusal instead of `--inspect` | **Closed** — corrected in DEC-037's note. |
| **A3** | DEC-035 typo `d58ee359…` | **Closed** — corrected to `d58ee239…`. |
| **A4** | Handoff/QAQC/STATUS states stale | **Closed** — mirrored (DEC-018). |

## 5. Limits

S1–S3 proves recognition, geometry and inventory. It does **not** run DeepSeek:
`model_family_runs()` is unchanged, so there is no forward path, no token
generation, and no baseline. OT-STRATA-001 checkpoint 4 stays open until S4.

S4 is the first work that touches kernels and the first that can produce a
DeepSeek number. It is **not authorized here**.

| Role | Signature | Date |
|---|---|---|
| Architect | architect | 2026-11-20 |
