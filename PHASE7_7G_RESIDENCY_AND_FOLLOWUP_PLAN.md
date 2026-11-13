# Phase 7G — Bounded weight residency + follow-up plan (proposal)

**Author:** DeepSeek V4.1 Flash (primary auditor)
**Date:** 2026-11-13
**Base:** `main` @ `c68cb27` (G6 signed, Phase 7F released)
**Status:** **PROPOSAL — not authorized.** Owner approval required before any
implementation branch is cut.
**Related:** `PHASE7_IMPLEMENTATION_HANDOFF.md` §7G, `audit/G6_SIGNOFF_2026-11-12.md`
(G6-QF-1…4), `audit/AUDIT_7F_CI_STATUS_2026-11-11.md`.

---

## 0. Answer to the question that triggered this plan

**No — a "cap my RAM usage and stream the rest from SSD" argument does not
exist today.** What exists:

| Control | Present? | Scope |
|---|---|---|
| `--residency {auto,pin,stream}` | ✅ | **all-or-nothing**: the *whole* model is pinned in the host page cache, or the *whole* model is streamed |
| `--residency-budget-mb <MB>` | ✅ | overrides the *computed* weight budget (absolute MB only, used to flip AUTO between pin/stream) |
| `--max-kv-bytes <bytes>` | ✅ | caps the **KV cache** (device bytes), not the weights |
| `--max-resident-mb` / `--max-resident-pct` (weights) | ❌ | **missing** |
| **Partial (hybrid) residency** — keep N bytes resident, stream the remainder | ❌ | **missing** |

Consequence, measured on this host today (Mistral-7B Q4_K_M, 4.37 GB weights,
32 layers, 16 decode tokens, merged `main` binary):

| Policy | decode tok/s | SSD bytes read | major faults | layer kern / copy / **overlap** (ms) |
|---|---|---|---|---|
| `auto` → PIN_ALL | **2.63** | 4.19 GB (one cold load) | 31,971 | 3.71 / 4.44 / 0.29 |
| `stream` | **0.42** | **62.8 GB** | 479,790 | 3.76 / 5.34 / **0.000** |

`stream` re-reads the **entire model per token** (62.8 GB / 16 tokens ≈ 3.93
GB/token) and the layer copy (5.34 ms) exceeds the kernel time (3.76 ms) with
**zero** copy/compute overlap. `auto` pins because the measured budget on this
host is 45.3 GiB ("weight bytes 667078656 fit the budget 48621942272"), so a
7B model is never streamed here by default. The user therefore has exactly two
choices today — "all in RAM" or "all from SSD" — and no way to say *"keep 2 GB
resident and stream the remaining 2.4 GB"*.

This plan adds that third option, plus the carry-forwards.

---

## 1. Work packages

Per the handoff rule ("each gets its own work package and gate; do not
bundle"), Phase 7G is split into three packages with three gates:

| ID | Package | Gate | Depends on |
|---|---|---|---|
| **7G-0** | G6 carry-forwards + release hygiene | G7-0 | — (maintenance) |
| **7G-1** | **Bounded weight residency** (hybrid pin/stream with a GB/% cap) | G7-1 | 7G-0 |
| **7G-2** | Streaming-path throughput (prefetch/overlap) + stream-lane benchmark | G7-2 | 7G-1 (uses its cap) |

### 7G-0 — G6 carry-forwards and release hygiene (Gate G7-0)

No new capability; close what G6 recorded plus the release chores.

| Item | Action |
|---|---|
| G6-QF-1 | `test_measured_rss_delta_pin_vs_stream` flake: `fsync` the synthetic fixture; fall back from a failed `MADV_PAGEOUT` to `MADV_DONTNEED`; if the kernel still retains the pages, make the major-fault proof a documented `pytest.skip` (the 7D claim is best-effort) |
| G6-QF-2 | Runner fragility: keep the registration valid; align the 03:00 UTC nightly cron with the host's ~03:38 UTC boot (or keep the host awake); document the re-registration procedure in the runbook |
| G6-QF-3 | Thin decisive-margin evidence: add prompts whose first steps are decisive, or require a minimum number of decisive steps |
| G6-QF-4 | `ci-gpu.yml` triggers only on `pull_request`/`schedule`/`dispatch`, so a protected-branch **push** can never satisfy the required GPU check (deadlock, observed live). Add a `push` trigger for the GPU lane, or document "protected branches are PR-only" |
| Hygiene | Remove the stale `refs/heads/vibe/phase7-220201` target from ruleset `26990297` (keep `main` protected with the four checks); merge the release-state docs PR (`main` = `c68cb27`, phase branch retired) |
| Hygiene | Repo visibility decision: it is private for the runner phase. Before going public, remove the self-hosted runner or enable *Require approval for all outside collaborators* |

**Exit:** all four QFs closed or explicitly re-deferred with a written reason;
the release-state record is on `main`; the ruleset lists only live branches.

### 7G-1 — Bounded weight residency (Gate G7-1) — the new feature

**Goal:** the user caps how much of the model's weights may stay resident in
host RAM — by **absolute MB/GB** or by a **percentage of the measured
available memory** — and the remainder is streamed from SSD.

**User-facing surface**

```
--max-resident-mb <MB>     # absolute cap on resident weight bytes
--max-resident-pct <P>    # percent of the measured available memory (0 < P <= 100)
--residency hybrid        # explicit form; a cap implies hybrid
```

Precedence (explicit, documented, tested):
`--max-resident-mb` > `--max-resident-pct` > the measured budget (today's
`AUTO` behaviour, unchanged when no cap is given).

Semantics: the cap applies to the **weights**; the KV cache keeps its own
`--max-kv-bytes` cap. The two are reported separately and never silently
share a pool. "Available memory" is the 7D measured budget
(`compute_weight_budget`: GTT free ∩ host `MemAvailable` ∩ cgroup v2/v1,
minus KV/activation estimates and the safety margin) — the same sources as
today, so no new measurement surface is invented.

**Implementation**

1. `src/memory_budget.py`
   - `ResidencyPolicy.HYBRID = "hybrid"`.
   - `resolve_resident_cap(explicit_mb, explicit_pct, sources, …) -> ResidentCap`
     (bytes, source ∈ {explicit_mb, explicit_pct, measured}, measured_available_bytes).
     `pct` → `floor(pct/100 × available)`, clamped to `[0, available]`; `pct=0`
     means "stream everything"; `mb` → bytes; both must be ≥ 0 and the CLI
     rejects a negative/NaN value.
   - `select_resident_layers(weight_bytes, layer_spans, cap)` → deterministic
     selection (documented **prefix** of layers, plus the always-resident
     embedding/output tensors accounted separately) returning
     `(resident_layers, resident_bytes, streamed_layers, streamed_bytes)`.
     Determinism matters: the same inputs must always give the same split.
   - `measure_resident_bytes(spans)` → **mincore**-based resident byte count
     over the model's file spans (`ctypes` on Linux; documented fallback to
     tracked accounting with a warning). This is what makes the cap
     *measurable* rather than advisory.
2. `src/weight_loader.py`
   - Per-layer residency: resident layers are never evicted; streamed layers
     keep today's `release_layer` eviction (`posix_fadvise(DONTNEED)` + PTE
     drop, best-effort).
   - A **reclaim pass** when the tracked resident bytes exceed the cap:
     evict the non-resident spans (`_evict_spans`) and re-measure.
   - `release_layer()` honors the per-layer decision (no eviction for
     resident layers) — the 7D eviction semantics are unchanged for the
     `stream` policy.
3. `src/inference.py`
   - CLI wiring and engine plumbing; `--max-resident-mb/--max-resident-pct`.
   - **Fail fast** when the cap cannot hold even one layer: a clear error
     naming the minimum viable cap (bytes of the largest layer).
   - **Warn, don't fail** when an explicit cap exceeds the measured budget
     (same posture as the existing `PIN_ALL` over-budget warning) and when
     `mincore` is unavailable (cap becomes tracked-only, stated in telemetry).
4. Telemetry — bump the schema to **`gfx1150-stats/2`**:
   - `residency`: `effective` (`pin_all|hybrid|stream`), `cap_bytes`,
     `cap_source`, `measured_available_bytes`, `resident_bytes_current`,
     `resident_bytes_peak`, `resident_bytes_measured` (mincore),
     `resident_layer_count`, `streamed_layer_count`, `streamed_bytes`,
     `enforcement` (`mincore-verified` | `tracked-only`).
   - `io`: `ssd_read_bytes_per_token`, `model_file_resident_bytes`.
   - Prompt safety unchanged; the `--stats` human rendering extended.
5. Tests
   - Unit: cap precedence (MB > pct > measured), pct math and clamping
     (0, 100, fractional), selection determinism, mincore accounting,
     fail-fast on an impossible cap, warning on an over-budget cap.
   - Property: after a run, the **measured** resident bytes ≤ cap (+ a stated
     tolerance for kernel-managed pages).
   - Integration: the 7B model with a 2 GiB cap → telemetry reports the cap
     honored and `ssd_read_bytes_per_token ≈ weight_bytes − resident`.
   - Regression: `AUTO`/`PIN_ALL`/`STREAM` behaviour and every G0–G6 claim
     unchanged (the existing 527/45 test lanes must stay green).
6. Claims — a new ledger row, honest about the limits:
   *"bounded weight residency: the engine keeps at most the requested weight
   bytes resident in the host page cache and streams the remainder; enforced
   best-effort and verified with `mincore` on Linux; the kernel may retain
   additional pages and the SSD path is I/O-bound."* No throughput claim
   without the bench evidence below.
7. Bench (evidence, not a product claim): cap sweep on the 7B model,
   R ∈ {0, 2 GiB, 4 GiB, all} → record decode tok/s, SSD bytes/token, measured
   resident bytes; checked-in baseline + the agreed 15% regression ratio; the
   sweep table becomes the trade-off curve a user can reason from.

**Exit (G7-1):** the cap is enforced and *measured*; precedence and failure
modes are tested and documented; telemetry reports cap/actual/streamed bytes;
claims ledger and README updated with the qualified wording; CPU + GPU lanes
green; evidence complete under `audit/evidence/G7/7G-1/`.

### 7G-2 — Streaming-path throughput (Gate G7-2)

Uses 7G-1's cap to make the SSD path usable.

1. **Prefetch + overlap.** Measured today: layer copy 5.34 ms > kernel
   3.76 ms, overlap **0.000 ms** → the SSD path is copy-bound and serial.
   Work: issue `POSIX_FADV_WILLNEED` (and an async read) for layer *N+1* while
   layer *N* computes, and overlap the H2D copy with the kernel where the
   dependency allows. Target: overlap > 0 and a measurable tok/s gain at a
   fixed cap; the pre-change numbers above are the baseline.
2. **Benchmark gating.** Today only the `AUTO`/pinned 7B lane is gated; add a
   **stream-lane** bench (fixed cap) to the same regression gate so the SSD
   path cannot silently rot.
3. **Docs.** State plainly that on a 45 GiB-budget host a 7B model is pinned by
   default (measured: 2.63 tok/s, 4.19 GB read) and that streaming is opt-in
   or forced by the budget (measured: 0.42 tok/s, 62.8 GB read per 16 tokens)
   — plus the new cap as the middle ground.

**Exit (G7-2):** overlap measured > 0 with a recorded tok/s delta; the
stream lane is gated; the README/plan carry the measured trade-off curve
without an unqualified throughput claim; evidence complete.

---

## 2. Sequencing, files, and discipline

1. 7G-0 (maintenance) → 7G-1 (cap) → 7G-2 (throughput). One package per
   branch, one gate each; no bundling.
2. Allowed files per package:
   - **7G-0:** `tests/**`, `src/kernels/attention.hip` (only the
     `MADV_PAGEOUT` fallback), `src/weight_loader.py` (only the eviction
     fallback), `.github/workflows/**`, `audit/**`, docs.
   - **7G-1:** `src/memory_budget.py`, `src/weight_loader.py`,
     `src/inference.py` (CLI + telemetry only), `src/python_bindings/**` only
     if the Python-visible signature must grow (then it is a new public knob —
     document it), `tests/**`, `scripts/bench/**`, `audit/**`, docs.
   - **7G-2:** `src/kernels/attention.hip` (prefetch plumbing), `src/weight_loader.py`,
     `scripts/bench/**`, `tests/**`, `audit/**`, docs.
   - **Forbidden everywhere:** kernel math, tokenizer/model-family/7D policy
     changes, weakening of existing tests, unqualified claims.
3. Evidence discipline (unchanged): every claim needs a command and an
   artifact under `audit/evidence/G7/<package>/`; the claims ledger gains a
   row per new user-visible guarantee; the strict gate stays release-blocking
   with an empty baseline.
4. QAQC adversarial checks for 7G-1 (proposed): verify the cap with
   `mincore`/`smaps` **outside** the engine; verify the precedence rules by
   running all three cap forms; verify that a smaller cap never increases the
   resident set; verify the fail-fast error names a viable minimum; verify
   the telemetry never contains the prompt; verify the AUTO/PIN/STREAM
   regression lanes are unchanged.

---

## 3. Open questions for the owner

1. **Cap semantics for the resident subset:** prefix layers (deterministic,
   simple) vs. a spread/"hottest" heuristic. Recommendation: prefix first,
   measure, revisit with data.
2. **Default cap:** should `AUTO` gain a default cap (e.g. 50% of the
   measured budget) once 7G-1 lands? That changes today's "pin if it fits"
   behaviour and therefore the G6/G7 evidence — recommendation: keep `AUTO`
   unchanged, make the cap explicit.
3. **Enforcement strictness:** if `mincore` is unavailable, is a tracked-only
   cap acceptable (warn + telemetry), or should the engine refuse to start?
   Recommendation: warn + telemetry, never fail the run.
4. **Visibility of the new knobs:** a new public CLI surface — one knob
   (`--max-resident-mb`) plus a percentage form is enough; avoid adding
   `--residency hybrid` as a separate spelling if the cap implies it.

---

**Approval:** owner authorization is required before any 7G implementation
branch is cut. G7-1 is the substantive package; 7G-0 can proceed in parallel
with G7-1 review since it is maintenance only.
