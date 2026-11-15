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
2. Memory management: Ensure effective memory utilization across GPU, CPU, and SSD. Experiment: Benchmark various memory allocation strategies and evaluate their impact on throughput and latency.
3. Performance consistency: Validate consistent performance across different model sizes and architectures. Artifact: Provide a comprehensive set of benchmarks demonstrating performance parity between the new engine and the baseline.
4. Compatibility with Strata: Thoroughly test the integration of the new scheduler with Strata's existing compute/backends.

## First three experiments
1. Small-scale MoE model: Implement a small-scale MoE model using the new scheduler and verify its performance improvement compared to the baseline.
2. Medium-scale MoE model: Scale up the experiment to a medium-sized MoE model and assess the efficiency gains.
3. Large-scale MoE model: Evaluate the performance of the new engine on a large-scale MoE model, focusing on memory management and GPU/CPU interaction.

## Reuse/rewrite
1. Reuse: Utilize the current project's proven GGUF parser, tokenizer, model-spec validator, and claims ledger.
2. Take from llama.cpp: Leverage the dynamic ggml backends provided by llama.cpp.
3. Write new: Develop the differentiating scheduler/residency layer.

## What would change the recommendation
1. Significant performance penalty: If the new scheduler introduces a significant performance penalty, it might be worth considering alternative approaches.
2. Unfeasible memory requirements: If the new scheduler requires an impractical amount of memory, it could necessitate a reconsideration of the approach.

## Criteria comparison
- Capability fit: Strata's existing engine capabilities align well with the project's goals.
- Abstraction fit: The new scheduler fits seamlessly within the existing abstractions.
- Hardware/backend fit: The chosen approach supports the target hardware and backends.
- License/maintenance: The MIT license allows for flexibility while minimizing maintenance costs.
- Testability/evidence: The new engine should provide clear evidence of its performance improvements.
- Time-to-first-result: The chosen approach offers a reasonable timeframe to achieve the first milestone.
```
