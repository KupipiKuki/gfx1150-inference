# v0.2 output vs the auditor memo — comparison (2026-11-15)

Run: `Mistral-7B-Instruct-v0.2-Q4_K_M`, revised prompt, 432 words, 41 lines,
closing Markdown fence present, no degeneration.

## Verdict

Structurally compliant and the headline recommendation matches the auditor
(**hybrid**). The reasoning is shallow and partly misleading: it misses the
decisive abstraction-fit argument, treats a fork as maintenance-free, and
proposes a scaling ladder instead of M0 decision experiments. Treat it as a
surface checklist, not as the decision memo.

## Point by point

| Section | v0.2 output | Auditor memo | Assessment |
|---|---|---|---|
| Recommendation | hybrid: reuse substrate, adopt an engine ("e.g., Strata"), write the scheduler/residency layer | D hybrid, **B first**, C fallback | matches the shape; does not commit to B vs C |
| Decisive reasons | assets, "llama.cpp backends easily integrated", Strata gfx1100 | hard parts already exist; llama.cpp is the stable substrate, not the scheduler; the current asset is evidence discipline | reason 2 is weak; "easily integrated" is unverified; misses the abstraction argument |
| Risks | generic GPU/CPU, memory, performance consistency, Strata compatibility | Strata modularity, marketing vs implementation, AMD maturity, model/license, hardware availability, fork drift | misses every decision-critical unknown |
| Experiments | small → medium → large MoE | run Strata on the Strix Halo APU; llama.cpp v1.0.0 on gfx1100; read the Strata engine boundary | a scaling ladder, not cheap/M0-relevant; assumes the decision is made |
| Reuse/rewrite | current substrate; llama.cpp backends; new scheduler | current parser/tokenizer/goldens/ledger; llama.cpp GGUF/backends/model coverage/speculation; Strata expert cache/CPU fallback; new policy | misses Strata's expert cache/CPU fallback and llama.cpp's model/speculation |
| What would flip | performance penalty; impractical memory | Strata not separable → C; llama.cpp already has expert offload → C; no gfx1100 host → B; license/attribution | generic; misses the decisive flips |
| Abstraction fit | "the new scheduler fits seamlessly" | the per-layer Python boundary and dense-only layout are the wrong base | **direct contradiction**; the model asserts the opposite without evidence |
| License/maintenance | MIT "minimizing maintenance costs" | MIT is fine, but a 7k-commit active fork creates drift | unsupported; the model understates fork cost |
| Honesty | no invented stars/licenses/benchmarks; some overclaims ("seamless", "minimizing") | explicit unknowns and flip conditions | model stays within facts but does not mark UNKNOWN |

## What this tells us

- The 7B model can follow the requested structure and echo the supplied facts.
  It does not perform the decisive systems trade-off analysis.
- The failure is reasoning, not formatting: v0.3 degenerated on a table; v0.2
  produces a plausible but thin memo that would lead the owner to skip the
  Strata modularity check and under-estimate fork drift.
- To get a better model memo, the prompt would need to force a B-vs-C choice,
  require the modularity check as a named unknown, ban generic risks, and ask
  for a cost estimate per option. A stronger model would likely help more than
  another prompt revision.

The auditor memo in `auditor-memo.md` remains the decision input. The v0.2
output is useful as a list of the surface concerns and as evidence that the
engine handles the long prompt correctly.
