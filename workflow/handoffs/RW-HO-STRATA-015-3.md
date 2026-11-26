# RW-HO-STRATA-015-3 — evidence-only rework: derive the drift, do not assert it

| Field | Value |
|---|---|
| **ID** | RW-HO-STRATA-015-3 |
| **Original handoff** | HO-STRATA-015 (S4b) |
| **Issued by** | Architect, on audit finding **A17** (audit report, § Delta (RW-2)) |
| **To** | `coder-primary` |
| **Date (UTC)** | 2026-11-26 |
| **State** | ISSUED |
| **Scope** | evidence only — the gate, the bound, the reference, the prompt, the cells and the already-correct `3.36e-6 / 7.95e-5` prose are **not** in scope |

## 1. The failed criterion

`artifacts/router-margin-19-1.txt` is the artifact that substantiates DEC-046's
justification. Its **margin** is right (`3.357388e-06` / `7.948442e-05`, matching
the audit). Its **drift line is wrong by ~902×**:

```text
rel L2 = 6.427215e-02   max abs = 8.231678e-01     (in the artifact)
rel L2 = 7.123e-05      max abs = 5.703e-04        (truth)
```

Cause: it compares the oracle's **`ffn_inp-19`** (the residual *after* block 19's
attention) against the **free dump's slot 19**, which is the residual *entering*
block 19 (`l_out-18`) — different points in the block, so the difference is the
attention branch, not drift. The correct counterpart of `ffn_inp-19` is the
*engine's* `ffn_inp-19`, which exists in the free DIAG log.

Two derived numbers in the prose are therefore unsupported: `+1.385e-4` (the gap
shift, `1.74×` the margin) and `3.84e-5` (the engine's arithmetic movement of
expert 40's logit at identical input). The audit computed both; the bundle must
compute them.

## 2. Required fix (this and nothing else)

1. **Commit the engine's own `ffn_inp-19` for position 1** as a bundle artifact
   (`artifacts/runs/engine-ffn_inp-19.bin`, 8 KB) or the 3 KB free-DIAG log it
   came from, so the drift is computable from the bundle alone.
2. **Compute the drift as `||engine ffn_inp-19 − oracle ffn_inp-19|| / ||oracle
   ffn_inp-19||`** — same node on both sides. Expect `≈7.123e-05`
   (max abs `≈5.703e-04`). If your value differs materially, **stop and report**
   rather than adjusting prose.
3. **Derive, do not hardcode**: `compute_router_margin.py` must compute the
   33↔40 logit-gap shift caused by that drift (`≈+1.385e-4`, i.e. `≈1.74×` the
   margin) and the engine's own expert-40 logit movement at identical input
   (`≈3.84e-5`, max over 64 `≈4.25e-5`) from the dumps it reads, and print them.
   Prose keeps those numbers only if the script reproduces them.
4. **Make it runnable from the bundle**: defaults to the committed artifacts
   (no `/tmp`-only argument required); with no arguments it must run and print the
   same output that is committed.
5. Regenerate `artifacts/router-margin-19-1.txt`, rebuild `test-output.txt` **after**
   the final capture (DEC-041 §2), rehash, `check_bundle.py --strict` → PASS,
   verdict-consistency re-run, `git status --porcelain` clean, and a §11 log line.

## 3. Evidence required to close

- The regenerated artifact, with the drift line at `≈7.1e-05` and the two derived
  numbers computed in-script.
- Proof of bundle-only runnability: `cd` to the repo root on a clean tree, invoke
  the script **with no arguments**, and `cmp` its output to the committed artifact.
- `check_bundle --strict` verdict + count, hash count, `B6-pins` row count,
  verdict-consistency result.
- Commit SHA.

## 4. Guard rails

Do not change the gate (`1.569942e-04`), the 5e-3 bound, the reference, the prompt,
the positions, the cell counts, `src/**`, the Strata tree, `DECISIONS.md`, the QAQC
or audit reports, or the corrected margins (`3.36e-6` / `7.95e-5`) — those are right.
If a computation contradicts the audit's numbers, report it; do not edit the prose
to fit. A second failure on this criterion escalates to the architect.
