# Strata-engine planning pack

Resources for turning the Strata-class decision into a detailed, phased
implementation plan. Written to be uploaded to the DeepSeek API; the prompt is
in `05-deepseek-prompt.md`.

## Read in this order

1. `00-context-brief.md` — goal, non-goals, constraints, success criteria.
2. `01-hardware-matrix.md` — gfx1100, 780M (gfx1103), MI25 (gfx900), gfx1150,
   gfx906 reference; ROCm and Strata support; risks.
3. `02-capability-abstraction.md` — the descriptor/probe/build/dispatch design
   that makes a new card a data change, not a recode.
4. `03-phased-plan.md` — P0–P9 with work packages and gates.
5. `04-open-questions.md` — the owner decisions the planner must ask for.
6. `05-deepseek-prompt.md` — the planning prompt and the red-team pass.
7. `06-mi25-feasibility.md` — the separate 5× MI25 / OCuLink general-LLM
   feasibility test (stretch goal, not on the Strata critical path).

## The hardware facts that shape the plan

- **780M (gfx1103)** is a supported-ISA, **build-and-tune** problem. Strata has
  a Linux opt-in path (`RADEON_780M.md`, `STRATA_EXPERIMENTAL_GFX1103=1`,
  `gfx1103-hipblaslt-100401.txt`), ROCm 7.1+ has gfx1103 rocBLAS, and the
  measured prompt gain is 90 → 187 tok/s with the table (277 with the WMMA
  opt-ins). The risks are the shared-memory budget and documented firmware GPU
  resets on some hosts.
- **MI25 (gfx900) is a stretch goal, not a critical-path target.** You own five
  16 GB MI25 cards (80 GB aggregate) for $200, connected over **OCuLink**. They
  are a general-LLM-software experiment first: if llama.cpp/ROCm can use them,
  they become a cheap multi-GPU lab; if not, they are repurposed and the Strata
  plan does not block on them. `06-mi25-feasibility.md` is the separate test
  plan. The Strata critical path is **gfx1100 + 780M + gfx1150**.

## How to use the pack with DeepSeek

1. Upload all seven files (about 8K words; well within a large context).
2. Paste the prompt from `05-deepseek-prompt.md`.
3. Answer the "decisions needed" list before accepting the plan; the pack marks
   what is UNKNOWN on purpose.
4. Run the red-team prompt as a second pass.
5. Keep the resulting `PLAN.md` in the repo; use OpenCode for the coding
   phases, not for the architecture pass.

## What the pack deliberately does not do

- It does not pick the model or the gfx1100 card; those are owner decisions.
- It does not claim the MI25 works; `06-mi25-feasibility.md` is the gate, and
  the Strata plan treats the MI25 as a stretch goal.
- It does not replace P0; the ADR is still the first gate.
