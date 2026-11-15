# 08 — Roadmap decision: Strata on gfx1150; 780M split to gfx-inference

**Date:** 2026-11-15
**Owner decision:** adopted as the starting route.
**Basis:** `07-plan-audit.md` (Route 2 before Route 3), `10-project-split.md`,
and the owner's priority.

## 1. Priority

| Order | Target | Status | Why |
|---|---|---|---|
| **1** | **gfx1150** (Radeon 890M) | **primary** | The machine we run on; it is what matters. |
| 2 | gfx1100 (RX 7900) | future | No card yet; Strata already supports it as a maintainer-tested target. |
| 3 | gfx900 (5× MI25) | **deferred** | Adapters and a hardware build are not ready; not a priority. |
| — | **780M (gfx1103)** | **separate project** | Full continuation of `gfx-inference` (dense), not Strata. See `10-project-split.md`. |

## 2. Project split

- **Strata:** gfx1150 now; gfx1100 future; MI25 deferred. The 780M is **out of
  scope** until it is logical to add a small-MoE consumer later.
- **gfx-inference continuation:** the 780M (32 GB unified) runs the dense
  engine; Phase 8 (`GFX_ARCH`, kernel audit, 780M validation) is its plan.
  Separate branch, separate evidence trail.

## 3. Model strategy (see `09-model-strategy.md`)

Three gfx1150 test beds, one per family:

1. **Mixtral 8x7B** (Mistral; architecture-adjacent to 8x22B) — first.
2. **Qwen3-30B-A3B** (Qwen; fallback Qwen1.5-MoE-A2.7B) — second.
3. **DeepSeek-V2-Lite** (v2-adjacent) or **DeepSeek-MoE-16B** (safe general
   MoE) — third.

End targets (Qwen Next, DeepSeek v2/V4, Mistral 8x22B) are gfx1150 now,
gfx1100 later. The 780M is not an end-target host.

## 4. Route

- **Route 2:** modify Strata directly, pinned patch overlay; upstream PRs
  optional.
- The audit's 4-stage lean plan (`07` §2) is the primary roadmap for gfx1150.
- **Route 3 (fork + P0–P9)** is the escalation annex, triggered only if the
  Strata engine is structurally rigid, upstream breaks the patches, gfx1100/
  gfx900 enters the critical path, or the deliverable becomes an independent
  machine-gated engine.

## 5. First action — gfx1150 Stage 1 spike (time-box 1–2 days)

1. Pin a Strata commit; record ROCm/HIP/LLVM/kernel/`linux-firmware`.
2. `strata --families` / `docs/MODELS.md`: check support for
   Mixtral/Qwen/DeepSeek before downloading.
3. Build for gfx1150: `-DCMAKE_HIP_ARCHITECTURES=gfx1150`; record every
   setup/CMake friction point and whether `gfx1150-hipblaslt-100401.txt`
   matches the local hipBLASLt.
4. Run the three test beds one at a time (Mixtral first) with the iGPU flags;
   record prompt/decode tok/s, GTT/RAM, `dmesg`, table match, model hash.
5. Check the engine boundary: can it run without `apps/`/`serve/`? Does the
   CLI work?

**Gate:** reproducible build + clean run + one baseline per family + a
Route 2 vs Route 3 decision. If the build/run is blocked, document the blocker
and switch to the patch overlay; if the engine is structurally rigid, escalate.

## 6. Deferred / not now

- **MI25:** no work until the OCuLink adapters and a hardware build exist.
- **gfx1100:** no work until a card is available.
- **780M:** separate dense project (`gfx-inference` continuation), not Strata.
- **P0–P9 capability framework:** escalation annex; not the starting plan.

## 7. Open decisions

- **Test order and DeepSeek choice:** Mixtral → Qwen → DeepSeek-V2-Lite (if
  supported) or DeepSeek-MoE-16B.
- **780M continuation scope:** start the dense Phase 8 now, or after the
  gfx1150 Strata spike.
- **Patch default:** pinned patch overlay vs upstream PR.
