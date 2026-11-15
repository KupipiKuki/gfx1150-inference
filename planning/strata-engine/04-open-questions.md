# 04 — Open questions the plan cannot answer

These are owner decisions. The planning model should ask for them rather than
invent an answer.

## Hardware

1. **gfx1150 (primary):** the current host; no decision needed. The first
   spike starts here.
2. **780M (next):** the host is available; what is its RAM, and which small MoE
   fits? Is it Linux-only, and is the firmware-reset risk acceptable?
3. **gfx1100 (future):** which card (RX 7900 XTX 24 GB, XT 20 GB, GRE 16 GB)
   and when is it available? The expert-cache ceiling depends on the VRAM size.
4. **MI25 / OCuLink (deferred):** adapters and a hardware build are not ready.
   Revisit only after one card is physically usable; `06` is the test plan.
5. **CI:** gfx1150 now; the 780M as a manual gate until a runner exists. One
   self-hosted runner serializes jobs.

## Model and license

6. **Model family:** Qwen3.6-35B-A3B (the realistic APU target) or a smaller
   Qwen3.6 pack? Which fits the gfx1150 host (91.94 GiB RAM / 45.92 GiB GTT)
   and the 780M host?
7. **Reference:** is there a known-good reference implementation/GGUF pack for
   the chosen model, and under what license? The MI25 work is deferred; do not
   gate the gfx1150/780M model choice on it.
8. **MTP:** does the chosen model have an MTP head, or is speculation
   prompt-lookup only?

## Approach

9. **Route:** Route 2 (modify Strata directly, pinned patch overlay) is the
   starting route; Route 3 (fork + P0–P9) is the escalation. Confirm the
   patch-overlay vs upstream-PR default.
10. **Driver ownership:** use supported ROCm/TheRock builds for gfx1150/gfx1103,
   or build ROCm/LLVM from source? (gfx900 is deferred.) If from source, who
   maintains it and how is it versioned?
11. **Product scope:** is the desktop app/server dropped (engine + CLI only),
    or kept? The app is a large surface and not part of the engine plan.
12. **Windows:** the 780M (and the deferred MI25) are Linux-only in this plan;
    confirm.

## Process and resources

13. **Time budget:** how many hours per week; is the first milestone the
    audit's Stage 1–2 (gfx1150) only, or through Stage 3 (780M)?
14. **Evidence home:** new repository, or a branch in this one? Reuse the
    current claims ledger/checker or start a fresh ledger?
15. **Audit/QAQC:** keep the full ceremony per milestone, or one gate per
    milestone with the ledger + golden rig only?
16. **DeepSeek API:** which context files to upload, the token budget, and
    whether the planning model may ask follow-up questions.

## Decisions already made by the owner

- The next project is Strata-class (MoE + heterogeneous compute + speculation).
- Priority: **gfx1150 first, 780M next, gfx1100 future, MI25 deferred.**
- The 780M host is available for small MoE models.
- The starting route is Route 2 (modify Strata directly, pinned patch overlay);
  P0–P9 is the escalation annex.
- Planning/architecting moves to the DeepSeek API; OpenCode usage is conserved
  for coding models.
- Evidence discipline is non-negotiable.
