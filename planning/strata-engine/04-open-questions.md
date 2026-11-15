# 04 — Open questions the plan cannot answer

These are owner decisions. The planning model should ask for them rather than
invent an answer.

## Hardware

1. **gfx1100:** which card (RX 7900 XTX 24 GB, XT 20 GB, GRE 16 GB), when is it
   available for development and for CI? The expert-cache ceiling depends on
   the VRAM size.
2. **780M:** which machine/APU (Ryzen 7040/8040/200), is it Linux-only, and is
   the firmware-reset risk acceptable on that host?
3. **MI25 (stretch):** which existing build hosts the five cards, how many
   OCuLink ports/bifurcation, PSU and cooling, above-4G and IOMMU? Is the first
   test llama.cpp HIP or a legacy ROCm stack? Is a no-go acceptable (repurpose
   the cards) without blocking the Strata plan?
4. **OCuLink topology:** one host with all five cards, or several hosts with
   one or two each? The answer changes the power, cooling and bandwidth
   budget and whether a multi-GPU test is meaningful.
5. **CI:** one self-hosted runner per card, or a single host that swaps cards?
   The current project learned that one runner serializes jobs.

## Model and license

6. **Model family:** Qwen3.8-Flash-Next (the Strata default) or
   Qwen3.6-35B-A3B (the smaller MoE), or both? Which fits the 16 GB target?
7. **Reference:** is there a known-good reference implementation/GGUF pack for
   the chosen model, and under what license? The MI25/gfx900 build may not
   support the Qwen3.6 family at all.
8. **MTP:** does the chosen model have an MTP head, or is speculation
   prompt-lookup only?

## Approach

9. **Fork vs thin layer:** P0.1. The recommendation is B (fork the Strata
   engine), C as fallback; confirm.
10. **Driver ownership:** use supported ROCm/TheRock builds, or build ROCm/LLVM
   from source for gfx1103/gfx900? If from source, who maintains it and how is
   it versioned?
11. **Product scope:** is the desktop app/server dropped (engine + CLI only),
    or kept? The app is a large surface and not part of the engine plan.
12. **Windows:** the 780M (and the MI25 stretch) are Linux-only in this plan;
    confirm.

## Process and resources

13. **Time budget:** how many hours per week, and which phases are must-have
    (P0–P4) vs optional (P5–P8) for the first milestone?
14. **Evidence home:** new repository, or a branch in this one? Reuse the
    current claims ledger/checker or start a fresh ledger?
15. **Audit/QAQC:** keep the full ceremony per milestone, or one gate per
    milestone with the ledger + golden rig only?
16. **DeepSeek API:** which context files to upload, the token budget, and
    whether the planning model may ask follow-up questions.

## Decisions already made by the owner

- The next project is Strata-class (MoE + heterogeneous compute + speculation).
- The 780M is an early-inclusion target with a special ROCm/build path; the
  five MI25 cards are a stretch/general-LLM experiment, not a Strata
  critical-path target.
- Planning/architecting moves to the DeepSeek API; OpenCode usage is conserved
  for coding models.
- Evidence discipline is non-negotiable.
