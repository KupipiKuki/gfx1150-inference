# 04 — Open questions the plan cannot answer

These are owner decisions. The planning model should ask for them rather than
invent an answer.

## Hardware

1. **gfx1100:** which card (RX 7900 XTX 24 GB, XT 20 GB, GRE 16 GB), when is it
   available for development and for CI? The expert-cache ceiling depends on
   the VRAM size.
2. **780M:** which machine/APU (Ryzen 7040/8040/200), is it Linux-only, and is
   the firmware-reset risk acceptable on that host?
3. **MI25:** how many cards, is a 300 W data-center card acceptable in the
   host, and is a legacy/custom ROCm stack allowed? Is CPU-only acceptable if
   the gfx900 toolchain cannot be made stable?
4. **CI:** one self-hosted runner per card, or a single host that swaps cards?
   The current project learned that one runner serializes jobs.

## Model and license

5. **Model family:** Qwen3.8-Flash-Next (the Strata default) or
   Qwen3.6-35B-A3B (the smaller MoE), or both? Which fits the 16 GB target?
6. **Reference:** is there a known-good reference implementation/GGUF pack for
   the chosen model, and under what license? The MI25/gfx900 build may not
   support the Qwen3.6 family at all.
7. **MTP:** does the chosen model have an MTP head, or is speculation
   prompt-lookup only?

## Approach

8. **Fork vs thin layer:** P0.1. The recommendation is B (fork the Strata
   engine), C as fallback; confirm.
9. **Driver ownership:** use supported ROCm/TheRock builds, or build ROCm/LLVM
   from source for gfx1103/gfx900? If from source, who maintains it and how is
   it versioned?
10. **Product scope:** is the desktop app/server dropped (engine + CLI only),
    or kept? The app is a large surface and not part of the engine plan.
11. **Windows:** 780M/MI25 are Linux-only in this plan; confirm.

## Process and resources

12. **Time budget:** how many hours per week, and which phases are must-have
    (P0–P4) vs optional (P5–P8) for the first milestone?
13. **Evidence home:** new repository, or a branch in this one? Reuse the
    current claims ledger/checker or start a fresh ledger?
14. **Audit/QAQC:** keep the full ceremony per milestone, or one gate per
    milestone with the ledger + golden rig only?
15. **DeepSeek API:** which context files to upload, the token budget, and
    whether the planning model may ask follow-up questions.

## Decisions already made by the owner

- The next project is Strata-class (MoE + heterogeneous compute + speculation).
- The 780M and MI25 are early-inclusion targets with special ROCm builds.
- Planning/architecting moves to the DeepSeek API; OpenCode usage is conserved
  for coding models.
- Evidence discipline is non-negotiable.
