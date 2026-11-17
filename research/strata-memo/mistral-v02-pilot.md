```markdown
# Decision Memo: Next Project - Scalable MoE Inference Engine

## Recommendation
- Reuse the current project's evidence/claims substrate (GGUF parser, tokenizer, model-spec validator, claims ledger).
- Adopt an existing engine's compute/backends (e.g., Strata).
- Write only the differentiating scheduler/residency layer.

## Decisive reasons
1. Current project's strengths: The current project's strongest transferable assets include a robust GGUF parser, reference-faithful tokenizer, model-spec validator, and a well-defined claims discipline.
2. Llama.cpp compatibility: Llama.cpp v1.0.0 offers dynamic ggml backends, which can be easily integrated into the project.
3. Hardware support: Strata supports the target discrete gfx1100 host, ensuring compatibility.

## Risks and unknowns
1. GPU/CPU interaction: Verify efficient communication between CPU and GPUs for data exchange and scheduling. Artifact: Successfully run a large-scale MoE model with minimal latency and overhead.
2. Memory management: Ensure effective memory utilization across GPU, CPU, and SSD. Experiment: Benchmark various memory allocation strategies and evaluate their
