| prompt | text | engine ids | harness ids | match | notes |
|---|---|---|---|---|---|
| P1 | 'The capital of France is' | ["N/A — This model splits text with a rule Strata doesn't have yet ('olmo'), so it isn't loaded: running it with the wrong rule would change what it reads."] | [510, 5347, 273, 6181, 310] | False | engine tokenizer refuses 'olmo' pre-tokenizer |
| P2 | 'def add(a, b):\n    return' | ["N/A — This model splits text with a rule Strata doesn't have yet ('olmo'), so it isn't loaded: running it with the wrong rule would change what it reads."] | [1545, 823, 9, 66, 13, 270, 2262, 187, 50274, 2309] | False | engine tokenizer refuses 'olmo' pre-tokenizer |
| P3 | 'Three primary colors are' | ["N/A — This model splits text with a rule Strata doesn't have yet ('olmo'), so it isn't loaded: running it with the wrong rule would change what it reads."] | [11831, 3625, 9830, 403] | False | engine tokenizer refuses 'olmo' pre-tokenizer |

**BOS convention:** tokenizer.ggml.add_bos_token=False, BOS id 50279. Harness uses llama_tokenize with add_special=false, so no BOS is prepended. The engine tokenizer at this pin does not load the 'olmo' pre-tokenizer, so no engine-side id list is available for comparison.
