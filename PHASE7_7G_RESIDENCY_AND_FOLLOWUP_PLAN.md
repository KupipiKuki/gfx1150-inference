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

## 0.1 Thesis check (2026-11-13): has the direction drifted?

The stated purpose is *"a platform for gfx1100-class hardware that operates
like Strata"* (https://github.com/Niko1221/Strata): run a much larger model than
the card's VRAM by sharing the work across the whole PC.

**What Strata actually does** (from its `docs/HOW_IT_WORKS.md`):

| Tier | Strata | This project |
|---|---|---|
| Model class | **MoE** — 24,576 experts, **10 active per token** | **dense only** — no expert/router code exists |
| GPU (VRAM) | hot experts (adaptive cache) + dense parts + KV + MTP head + output head | per-tensor H2D copies, no persistent weight residency |
| RAM | all experts pinned; **the CPU computes the experts the GPU lacks, concurrently with the GPU** | all weights in the host page cache; **no CPU compute path** |
| SSD | 28.8 GB n-gram table, a few rows per token | the GGUF file itself, re-read per token in STREAM mode |
| Speculation | the model's own **MTP** draft (2.4–3.2 tok/pass) + **prompt/n-gram lookup** drafting | **none** |
| Prefill | chunked to 8192 tokens; **next layer's experts stream over PCIe while the current layer's attention runs** | chunked prefill exists, but measured **copy/compute overlap = 0.000 ms** |

**So yes — the direction drifted, in three specific and identifiable ways:**

1. **Dense instead of MoE.** Strata's capacity claim is only plausible because
   the *active* parameter count per token is tiny. A dense 220B model needs
   ~141 GiB of weights touched **per token**; an MoE of the same total size with
   ~3B active parameters needs only the active experts. We optimized the dense
   case, so our ceiling is "as many dense bytes as RAM holds".
2. **One device instead of two.** Strata's central trick is CPU compute running
   *in parallel* with the GPU. We are GPU-only and pay H2D latency serially —
   measured today: layer copy 5.34 ms > kernel 3.76 ms, overlap 0.000 ms.
3. **The gate never measured the thesis.** G0–G6 measured correctness,
   honesty, claims hygiene and CI — none of them asked *"how many model bytes
   can we run per GB of RAM?"*, so the work optimized for the axis that was
   measured.

**What is *not* wasted.** The substrate is exactly what any Strata-like path
needs (and Strata itself borrows the same ideas from llama.cpp/ggml): a
fail-closed GGUF parser, a reference-faithful tokenizer, a forward path
verified against llama.cpp, explicit streams with per-layer hipEvent timing
(7E), a residency/eviction policy (7D), telemetry (7F), and a claims ledger
that forbids the "70B without OOM" style of claim. The 7E machinery
(copy/compute overlap, ping-pong prefetch, per-projection timing) is precisely
what Strata's "next layer streams while attention runs" needs — ours is
implemented but yields 0.000 ms of overlap. Re-alignment is an **addition on a
verified base**, not a rewrite.

**Recommended path (staged, each with its own gate):**

| Stage | Work | Why |
|---|---|---|
| S1 | 7G-1 + 7G-2 (cap + real overlap) | prerequisite for *every* path below; the overlap machinery is Strata's core mechanism |
| S2 | **n-gram / prompt-lookup drafting** | Strata's own "prompt lookup" mechanism: no model change, no new kernels, measurable with the existing telemetry + golden discipline |
| S3 | **capacity metric in the release gate** | make "max supported dense model size (measured)" a tracked number, so the thesis is measured rather than asserted |
| S4 | **CPU compute fallback for overflow layers** | port dequant+dot to the CPU so RAM/SSD latency is hidden by parallel CPU work (Strata's trick); also fixes the serial-copy problem |
| S5 | **MoE support** (routing, grouped GEMM, adaptive expert cache, CPU expert fallback) | the only path to "100B+ on small hardware" as Strata means it |
| S6 | **ADR: hardware target** — stay on gfx1150 (unified memory: RAM and VRAM are one pool, so the three-tier story degenerates) or re-target gfx1100 (discrete 8–16 GB VRAM + separate RAM, where the Strata architecture is physically meaningful and testable) | this decision changes which of S4/S5 is worth doing, and it needs a host we do not currently have |

**The honest reframing of the ambition:** on *dense* models, the reachable ceiling
on this box is ~85 GiB resident after the budget split (≈ 120B at 4-bit
mixed) at ~2.6 tok/s pinned; a dense 220B is not a proposition here. The
Strata-class proposition is **"a ~100B+ MoE with ~3B active params"** — a
different model class from the dense models we have tested. Choosing that
target explicitly (and saying so in the goal statement) is what re-aligns the
project; otherwise we should retire the 70B/220B language and state plainly
what we support.

---

---

## 1. Work packages

Per the handoff rule ("each gets its own work package and gate; do not
bundle"), Phase 7G is split into three packages with three gates:

| ID | Package | Gate | Depends on |
|---|---|---|---|
| **7G-0** | G6 carry-forwards + release hygiene | G7-0 | — (maintenance) |
| **7G-1** | **Bounded weight residency** (hybrid pin/stream with a GB/% cap) | G7-1 | 7G-0 |
| **7G-2** | Streaming-path throughput (prefetch/overlap) + stream-lane benchmark | G7-2 | 7G-1 (uses its cap) |
| **7G-3** | **Large-model capacity**: split the RAM/GTT budgets, add a max-model-size report, and run the stress ladder | G7-3 | 7G-1, 7G-2 |

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

### 7G-3 — Large-model capacity (Gate G7-3)

**Question this package answers:** *how large a model can this harness actually
run, and what stops it from running a 70B/100B/220B-class GGUF?*

**Measured on this host (2026-11-13, merged `main`):**

| Reading | Value |
|---|---|
| RAM total / MemAvailable | **91.94 / 89.46 GiB** |
| GTT free (device-visible UMA share) | **45.92 GiB** |
| Current weight budget (`min` of the readable sources, minus KV/activations/margin) | **45.11 GiB** |
| Bytes/param, Q4_K_M (mixed Q4_K+Q6_K) | ~0.69 |

| Model (Q4_K_M) | Weights | Fits RAM (89.5 GiB)? | Fits **current** budget (45.1 GiB)? |
|---|---|---|---|
| 32B | 20.6 GiB | yes | yes |
| **70B** | **45.0 GiB** | yes | *barely* |
| **100B** | **64.3 GiB** | yes | **no** |
| **220B** | **141.4 GiB** | **no** | no |

**Root cause of the limit — it is not the hardware.** `compute_weight_budget`
takes `available = min(GTT free, MemAvailable, cgroup)`. On a unified-memory
APU the GTT share (~45.9 GiB) is half of RAM, so the **weights** (which live in
the *host* page cache and are copied H2D per tensor) are budgeted against
**device** memory. That conflates two different budgets and throws away ~44 GiB
of usable host RAM.

**Work items**

1. **Split the budgets** (`src/memory_budget.py`):
   - `host_resident_budget` — where the weights may live: `MemAvailable` /
     cgroup (minus KV/activations/margin). This is the 7G-1 cap's basis.
   - `device_budget` — what the GPU may hold: GTT free minus the KV pool,
     the activation estimate, and the per-tensor staging peak.
   - `compute_weight_budget` keeps its current `min()` semantics **only** for
     the device-side reservation; the residency decision switches to the host
     budget. Keep the old behaviour available behind an explicit flag for
     reproducibility of the G0–G6 evidence.
   - Consequence to verify: a 70B Q4_K_M must pin with headroom, and a 100B
     Q4_K_M must become reachable with an explicit cap.
2. **Reservation order**: size and reserve the device KV pool + activations
   **before** pinning weights, so a big model cannot eat the GTT and then fail
   the KV allocation late. Fail fast with the numbers.
3. **`--max-model-size-report` (dry run)**: given a GGUF, print weights bytes,
   bytes/param, resident requirement, per-tensor device footprint, KV size at
   the requested context, expected SSD bytes/token and expected tok/s per
   policy, and the host's theoretical maximum model size; refuse clearly when
   even streaming cannot work.
4. **Stress ladder** (evidence, one row per rung; claims ledger updated only
   for what actually ran):

   | Rung | Model | Download | Purpose |
   |---|---|---|---|
   | L0 | 7B Q4_K_M (done) | 0.7 GB | baseline (already recorded) |
   | L1 | 13–20B Q4_K_M | ~14 GB | larger shapes, still fully resident |
   | L2 | **70B** Q4_K_M | ~48 GB | the classic case; needs the budget split |
   | L3 | **100–120B** Q4_K_M | ~70–83 GB | needs the RAM-based budget + 7G-1 cap |
   | L4 | **220B** | ~141 GB | **streaming-only on this box — not a usable configuration** |

   Protocol per rung: fixed prompt, `temperature=0`, fixed seed, ≥20
   iterations, median/p95, plus SSD bytes/token, measured resident bytes,
   GTT peak, and tok/s; artifact under `audit/evidence/G7/7G-3/`.
5. **220B-scale without a 141 GiB download** — a **sparse synthetic fixture**
   with 220B-scale *shapes* (e.g. 80 layers × hidden 8192 × intermediate
   28672), written as a sparse file (apparent ~141 GiB, ~0 bytes on disk). It
   exercises the parser, 64-bit offsets, per-tensor staging, KV sizing and the
   streaming path at 220B scale. **Capacity/robustness only — no correctness
   claim** (the weights are not a real model).
6. **Large-model audit items**: 64-bit offset/element-count handling for >4 GiB
   tensors and >2^31 elements; per-tensor device footprint for wide FFN
   (hidden 8192 × intermediate 28672 fp16 ≈ 470 MB per tensor — the
   staging peak must be reserved); `embed_tokens` for large vocabularies; KV
   bytes/token for 80-layer GQA models (e.g. 327 KB/token → 1.3 GB at 4K
   context, 10.5 GB at 32K).
7. **Claims discipline**: ledger IDs 18 (70B "without OOM") and 19 (8-hour
   endurance) stay **UNVERIFIED** until a real run exists. A streamed 220B run
   is a *robustness* record, not a support claim.

**Exit (G7-3):** the RAM/GTT budgets are split and documented; the max-model
report is implemented and exercised; the ladder rungs that were actually run are
recorded with their artifacts; the 220B-scale synthetic capacity test passed;
claims reflect exactly what ran.

**Note on the 220B rung.** A 220B Q4_K_M GGUF is ~141.4 GiB of weights; this
host has 89.5 GiB of usable RAM, so even after every change it can only run
**streaming-only**, re-reading the whole model per token (~141 GiB/token ≈
14 s/token at ~10 GB/s NVMe ≈ 0.07 tok/s). That is a capacity/robustness
result, not a usable configuration, and it must never be published as
"220B-class support". The realistic ceilings on this box are **~85 GiB resident
(≈ 120B at Q4_K_M)** once the budget split lands, and **~45 GiB today**.

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
   - **7G-3:** `src/memory_budget.py` (budget split), `src/weight_loader.py`
     (reservation order), `src/inference.py` (report mode, CLI), `src/kv_cache.py`
     (sizing), `scripts/bench/**`, `tests/**`, `audit/evidence/G7/7G-3/**`,
     docs. Synthetic fixtures are generated by a script under `scripts/bench/`
     (never committed as multi-GiB files).
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
4. **220B rung:** download a real ~141 GiB GGUF (feasible on this disk but slow
   and streaming-only), or rely on the sparse 220B-shaped synthetic fixture for
   capacity and reserve the real run for the 70B rung? Recommendation:
   synthetic for 220B, real for 70B/100B.
5. **Budget split compatibility:** the G0–G6 evidence was recorded under the
   conflated `min()` budget. Splitting it changes what "AUTO" means — keep the
   old behaviour behind an explicit flag, or re-record the affected baselines?
   Recommendation: keep an explicit `--residency-budget-source {host,device,min}`
   so the historical numbers stay reproducible.
6. **Visibility of the new knobs:** a new public CLI surface — one knob
   (`--max-resident-mb`) plus a percentage form is enough; avoid adding
   `--residency hybrid` as a separate spelling if the cap implies it.

---

**Approval:** owner authorization is required before any 7G implementation
branch is cut. G7-1 is the substantive package; 7G-0 can proceed in parallel
with G7-1 review since it is maintenance only.
