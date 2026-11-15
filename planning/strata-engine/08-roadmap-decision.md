# 08 — Roadmap decision: gfx1150 first, 780M next, MI25 deferred

**Date:** 2026-11-15
**Owner decision:** adopted as the starting route.
**Basis:** `07-plan-audit.md` (Route 2 before Route 3) and the owner's priority.

## 1. Priority

| Order | Target | Status | Why |
|---|---|---|---|
| **1** | **gfx1150** (Radeon 890M, current host) | **primary** | It is the machine we run on; it is what matters. |
| **2** | **gfx1103** (780M) | next | Host available, **32 GB unified**; small-MoE test and dense continuation; the same APU profile as gfx1150. Not an end-target host. |
| 3 | gfx1100 (RX 7900) | future | No card yet; Strata already supports it as a maintainer-tested target. |
| 4 | gfx900 (5× MI25) | **deferred** | Adapters and a hardware build are not ready; not a priority. `06` stays as the test plan. |

## 2. Model strategy (see `09-model-strategy.md`)

- **gfx1150 spike:** Mixtral 8x7B Q4_K_M first (architecture-adjacent to the
  8x22B end target); fall back to Qwen3-30B-A3B if Strata needs a model-family
  change.
- **780M 32 GB:** Qwen3-30B-A3B or Qwen1.5-MoE-A2.7B; Mixtral 8x7B only as a
  low-RAM/SSD stress test.
- **End targets** (Qwen Next, DeepSeek v2/V4, Mistral 8x22B): gfx1150 and
  gfx1100 only. The 780M is the small-model lab.

## 3. Route

- **Start with Route 2:** modify Strata directly for gfx1150/780M, as a
  **pinned patch overlay** on a pinned Strata commit; upstream PRs are
  optional, not assumed.
- **The audit's 4-stage lean plan is the primary roadmap**
  (`07-plan-audit.md` §2): baseline → gfx1150 tune → gfx1103 promote →
  evidence/packaging.
- **Route 3 (fork + P0–P9) is the escalation annex**, triggered only if:
  1. Strata's iGPU/APU memory handling is structurally rigid, or upstream
     rejects/breaks the gfx1150/gfx1103 patches;
  2. gfx1100 or gfx900 enters the active critical path; or
  3. the deliverable becomes an independent, machine-gated research engine
     rather than a tuned Strata deployment.

## 4. First action — gfx1150 Stage 1 spike (time-box 1–2 days)

1. Pin a Strata commit; record ROCm/HIP/LLVM/kernel/`linux-firmware` versions
   (`rocminfo`, `hipcc --version`).
2. Build for gfx1150: `-DCMAKE_HIP_ARCHITECTURES=gfx1150`; record every
   setup/CMake friction point. Verify whether
   `gfx1150-hipblaslt-100401.txt` matches the local hipBLASLt version or
   silently falls back.
3. `strata launch --plan`; run **Mixtral 8x7B Q4_K_M** (fallback
   Qwen3-30B-A3B) with the iGPU flags; verify `strata --families` first.
4. Record: prompt/decode tok/s, token counts, GTT/RAM, `dmesg`, table
   match/fallback, build time, and the exact model pack/hash.
5. Check the engine boundary: can it run without `apps/`/`serve/`? Does the
   CLI work? Is the scheduler separable if we later need Route 3?

**Gate:** reproducible build + clean run + baseline table + a Route 2 vs
Route 3 decision. If the build/run is blocked, document the blocker and switch
to the patch overlay; if the engine is structurally rigid, escalate to Route 3.

## 5. Second action — 780M Stage 3

After the gfx1150 build works, use the same tree on the 780M with
`STRATA_EXPERIMENTAL_GFX1103=1` and `gfx1103-hipblaslt-100401.txt`:

- a small MoE that fits the 780M's RAM;
- the firmware preflight (gc 11.0.1 MES reset risk) and
  `STRATA_ARENA_PIN_GIB` comparison;
- per-card baseline, no `dmesg` resets across a sustained run.

**Gate:** both APUs build from the same path; per-card baselines recorded;
no resets.

## 6. Deferred / not now

- **MI25:** no work until the OCuLink adapters and the hardware build exist.
  `06-mi25-feasibility.md` is the plan for that day; it is not a Strata task.
- **gfx1100:** no work until a card is available; Strata already supports it.
- **P0–P9 capability framework:** not the starting plan; keep it as the
  escalation annex for when gfx1100/gfx900 enters the critical path.

## 7. Open decisions

- **Model/pack for the gfx1150 spike:** Mixtral 8x7B Q4_K_M (recommended,
  architecture-adjacent to 8x22B) vs Qwen3-30B-A3B (smaller, faster).
- **780M RAM/model fit:** which small MoE fits that host.
- **Pin the Strata commit** and choose patch overlay vs upstream PR as the
  default maintenance path.
