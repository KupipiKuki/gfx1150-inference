# Claims Ledger

Every public claim about capability, correctness, or performance must appear here with a reproducible evidence pointer. A claim without evidence is either removed or labelled **UNVERIFIED** before a release.

**Status vocabulary:** `VERIFIED` (reproduced by QAQC on the recorded platform) · `PARTIAL` (true for a narrower scope than the wording implies) · `NOT YET` (planned, not implemented) · `UNVERIFIED` (asserted but not reproduced) · `REMOVED` (withdrawn).

**Rules**
- Scope must name model family, quantization, context, hardware, and software versions.
- Performance claims require the benchmark artifact and the exact command (`audit/evidence/<gate>/...`).
- `UNVERIFIED` claims must not appear in README/marketing; `NOT YET` claims must be inline-qualified where mentioned; `PARTIAL` claims must state the limit inline.
- Update this file in the same PR as the claim change.
- Enforcement: `scripts/qa/check_claims.py` (added in 7A-6). Default CI mode is baseline-aware; `--strict` is release-blocking at G6 with an empty `audit/claims_baseline.txt`.

| ID | Claim | Status | Public match (literal) | Qualified in place? | Evidence | Scope / limit |
|---|---|---|---|---|---|---|
| 1 | Builds and installs from the sdist | **VERIFIED** | `pip install` | n/a | `audit/evidence/G0/7.0-baseline/sdist-install.log` | gfx1150 host, ROCm 10.1 (HIP 7.16.26385), Python 3.14.10; **full** clean-venv install with real HIP build, not only `GFX1150_SKIP_CMAKE=1` |
| 2 | CPU-only suite passes (12 tests) | **VERIFIED** | `test_cpu_only.py` | n/a | `audit/evidence/G0/7.0-baseline/cpu-suite.log` | 12/12 normal, 12/12 under `-O`; also 12/12 from the installed sdist in a clean venv |
| 3 | GPU kernel/layer/E2E suites pass | **VERIFIED** | `GPU` | n/a | `audit/evidence/G0/7.0-baseline/gpu-suite.log` | gfx1150, ROCm 10.1; all five suites exit 0 (synthetic models) |
| 4 | `Q4_0`/`Q4_K`/`Q8_0` kernels match reference | **VERIFIED** | `llama-family` | n/a | `audit/evidence/G0/7.0-baseline/gpu-suite.log`, `tests/test_gguf_and_q4.py`, `tests/test_phase5_scale.py` | synthetic data; tolerance as tested (max err ≤ `6.1e-5`) |
| 5 | `Q6_K` tensor support (CPU + kernels) | **VERIFIED** | `Q6_K` | n/a | `audit/evidence/G0/7.0-baseline/gpu-suite.log`, `tests/test_phase5_scale.py` | synthetic; real-GGUF Q6_K golden pending (7F-2). CPU path is `dequantize_q6_k_cpu` in `src/gguf_parser.py` |
| 6 | Real `Q4_K_M` GGUF end-to-end | **PARTIAL** | `Q4_K_M` | **no** — README L10 lists `Q4_K_M` in the goal sentence unqualified; L108 scopes the verified release to `Q4_0`/`Q4_K`/`Q8_0`. Baseline entry required until 7C-4. | `audit/evidence/G0/7.0-baseline/gpu-suite.log` (recipe tensor types wired) | all recipe tensor types wired; **no real GGUF fixture or logit golden yet**. See baseline entry `6 README.md Q4_K_M` |
| 7 | GPT-2 byte-level `Ġ` plain-text tokenization | **VERIFIED** | `GPT-2` | n/a | `tests/test_cpu_only.py` V-6, `audit/VERIFICATION_2026-11-01.md` §4 | plain text, multibyte, double spaces only; **not** special tokens (see ID 8) |
| 8 | Chat special tokens (e.g. `im_start`) | **NOT YET** | `chat special-token encoding` | **yes** — README: "chat special-token encoding and `add_bos_token` are not implemented" | 7B-1 | not implemented; encode emits byte tokens. README qualifies it inline; the literal `<im_start>` itself does not appear in README/PLAN |
| 9 | `tokenizer.ggml.add_bos_token` respected | **NOT YET** | `add_bos_token` | **yes** — README: "`add_bos_token` are not implemented" | 7B-2 | `generate()` currently hardcodes `add_bos=True`. PLAN L241 lists it as planned 7B work (a task description, not a capability claim) |
| 10 | Qwen2 support | **NOT YET** | `qwen2` | **no** — README L107 says "Supports … GPT-2 / Llama-3 / Qwen2 byte-level … BPE vocabularies" in one bullet; the L108 qualification is in the next bullet, which violates the same-bullet rule. Baseline entry required until 7B/7C. | 7B/7C | metadata only; chat/BOS correctness open. See baseline entry `10 README.md qwen2` |
| 11 | Phi-3 support | **NOT YET** | `phi3` | **yes** — same README bullet as ID 10 | 7C-2 | metadata only; fused `attn_qkv` missing |
| 12 | Gemma support | **NOT YET** | `gemma` | **yes** — same README bullet as ID 10 | 7C-3 | metadata only; embedding scale, soft-cap, `key_length` missing |
| 13 | 983 tok/s / 4.4× E2E speedup | **UNVERIFIED** | `983` | **partial** — PLAN L266 qualifies ("983.4 tok/s synthetic E2E, owner-verified"); **PLAN L209 is unqualified** | 7F-3 | synthetic 2-layer; G0 measured `849.3 tok/s` (decode `866.5`) — does not reproduce 983. Must be re-recorded or removed by G6 |
| 14 | Bounded RAM for 70B models | **UNVERIFIED** | `bounded memory` | **no** — README L12 and PLAN L17 are unqualified | 7D-1/7D-2 | `MADV_DONTNEED` does not bound page cache; residency policy pending. Baseline entries held for both files |
| 15 | One synchronization per token | **NOT YET** | *(no public literal — planning/audit text only)* | n/a — not asserted publicly | 7E | current path relies on NULL-stream waits. Literal lives only in the handoff/audit, not in README/PLAN |
| 16 | PEP 639 license metadata | **NOT YET** | *(no public literal — planning/audit text only)* | n/a — not asserted publicly | 7G | `license = { file = ... }` still deprecated. Literal lives only in audit docs, not README/PLAN |
| 17 | Collision-safe package namespace | **NOT YET** | *(no public literal — planning/audit text only)* | n/a — not asserted publicly | 7G | six top-level modules. Literal lives only in audit docs, not README/PLAN |
| 18 | 7B–70B models on gfx1150 without OOM | **PARTIAL** | `7B–70B` | **no** — README L10 / PLAN L12 are unqualified | 7D-2, 7F-2 | goal statement; 70B path exists but residency is not budgeted (ID 14) and no real 70B GGUF was ever run |
| 19 | 8-hour unattended runtimes | **UNVERIFIED** | `8-hour runtimes` | **no** — README L12 / PLAN L15 are unqualified | 7F-3, 7F-4 | no endurance/long-run test exists; needs a timed soak + telemetry (7F-4) |
| 20 | Active RAM caps for 7B–70B (≤1.5–4.5 GB) | **UNVERIFIED** | `Active RAM Cap` | **no** — PLAN performance-targets table is unqualified | 7D-2, 7F-3 | target table, not a measurement; the `MADV_DONTNEED` mechanism does not enforce these caps |
| 21 | `MADV_DONTNEED` reclaims page-cache for 70B | **PARTIAL** | `reclaim clean file-backed page-cache` | **partial** — README describes the intent ("to advise the Linux kernel to reclaim clean file-backed page-cache pages"), but does not state that it does not bound RSS | 7D-1 | advice is issued, but `MADV_DONTNEED` on a read-only file mapping is best-effort and does not bound total RAM; mechanism must become `posix_fadvise(POSIX_FADV_DONTNEED)` / `MADV_PAGEOUT` |
| 22 | Single active engine per process (thread-guarded) | **VERIFIED** | `permitted per process` | n/a | `audit/evidence/G0/7.0-baseline/gpu-suite.log`, `src/python_bindings/bindings.cpp` (`g_hip_workspace_mutex`), `src/kv_cache.py` (raises if a GPU-resident KV cache is already active) | enforced at runtime; **no automated test asserts the rejection path** — add one in 7A |
| 23 | KV offload keeps persistent GPU KV pool at 0 bytes | **VERIFIED** | `persistent GPU KV pool usage at` | n/a | `audit/evidence/G0/7.0-baseline/gpu-suite.log` (`test_phase5_scale.py` asserts `device_bytes == 0` for both CPU-offload and mmap modes) | synthetic models; real-GGUF golden pending (7F-2) |
| 24 | Sequential multi-prompt batching (`generate_batch`) | **VERIFIED** | `generate_batch` | n/a | `audit/evidence/G0/7.0-baseline/gpu-suite.log` (`test_phase5_scale.py` exercises `generate_batch`) | synthetic models; sequential only, no concurrent batching |
| 25 | RoPE layout compat (llama adjacent-pair + NeoX) | **VERIFIED** | `rope.neox` | n/a | `audit/evidence/G0/7.0-baseline/gpu-suite.log` (`test_layer.py` covers both styles) | synthetic tensors |
| 26 | 1.12 TFLOPS matmul throughput | **UNVERIFIED** | `1.12 TFLOPS` | **no** — PLAN L45/L53/L261 unqualified | 7F-3 | G0 measured **1.02 TFLOPS** on this host. Different ROCm (10.1 vs 7.0.0 at verification) and a different host state; must be re-recorded on a fixed baseline or removed |
| 27 | 983.4 tok/s / 1107.9 tok/s decode E2E | **UNVERIFIED** | `983.4 tok/s` | **no** — PLAN L209 unqualified (L266 is qualified) | 7F-3 | G0 measured 849.3 tok/s (decode 866.5). See ID 13 |
| 28 | Fused Q4_0 matmul 0.50 ms @ 1×4096×4096 | **UNVERIFIED** | `0.50 ms` | **no** — PLAN L81 unqualified | 7F-3 | G0 measured 0.75 ms for M=1/N=4096/K=4096. Re-record or remove |
| 29 | Q4_K 1×1024×8192 in 2.76 ms | **UNVERIFIED** | `2.76 ms` | **no** — PLAN L178 unqualified | 7F-3 | G0 measured 1.00 ms. Re-record or remove |
| 30 | Resident RAM delta < 500 MB while streaming | **UNVERIFIED** | `500 MB` | **no** — PLAN L79 unqualified | 7D-1, 7F-3 | no measurement artifact exists; the check was never automated |

**Last updated:** 2026-11-01 (G0 baseline freeze). Update during 7.0 and at every gate.

### G0 ledger corrections (2026-11-01)

The seeded ledger was reviewed line-by-line against the live `README.md` and
`IMPLEMENTATION_PLAN.md`. Corrections applied at G0:

1. **Broken match literals fixed.** The seeded rows 4 and 8 carried match strings that
   could not be located in any public document (row 4: `Q4_0`, `Q4_K`, `Q8_0`; row 8:
   `<|im_start|>`). Row 8's literal also contained unescaped `|` characters that break
   Markdown table parsing and the `check_claims.py` column split. Both now use literals
   that exist verbatim in a public document.
2. **Rows 15–17 re-scoped.** These are planning/audit items, not public claims; their
   literals exist only in the handoff and audit reports. They are marked
   *(no public literal)* so the checker does not treat an absent string as a live
   unqualified claim, but they remain tracked for their owning packages (7E, 7G).
3. **Rows 8–12 qualification flags corrected.** The seeded table recorded the
   qualification as a quoted phrase that does not exist in the README. The README does
   qualify these claims inline, in a different wording — the flag and the quoted text now
   match the actual prose.
4. **Thirteen uncovered public claims added (IDs 18–30).** The seeded ledger covered 17
   rows; a systematic scan of every assertive statement in README and PLAN found 13
   additional public claims with no ledger row. These include the 7B–70B scope, the
   8-hour runtime, the Active RAM Cap table, all four stale performance figures, and the
   `MADV_DONTNEED` mechanism. Uncovered claims are exactly what the seeded ledger was
   supposed to prevent.

**Stale performance numbers.** IDs 26–29 record that four performance figures published
in `IMPLEMENTATION_PLAN.md` do not reproduce at G0 (1.12 vs 1.02 TFLOPS; 983.4 vs 849.3
tok/s; 0.50 vs 0.75 ms; 2.76 vs 1.00 ms). They are single-run synthetic measurements from
an earlier host state and ROCm version. They are `UNVERIFIED` and must be re-recorded by
7F-3 or removed before release. They are **not** added to the ratchet baseline: the
correct outcome is to delete them, not to tolerate them.

## Baseline policy

`audit/claims_baseline.txt` may list known violations during 7A–7E, one per line:

```
<claim-id> <path> <literal>
```

Every entry targets `G6`. It is a ratchet, not a waiver: default CI tolerates only exact entries, and `--strict` ignores the file entirely. At G6 the file must be empty and `check_claims.py --strict` must pass.

The `phi3`/`gemma` bullet was qualified inline on 2026-11-01 (metadata-only support), so it should not need a baseline entry. The `bounded memory` claim (ID 14) remains the known baseline item until 7D corrects the mechanism and wording.

### G0 additions to the ratchet

The G0 review found two additional unqualified public claims that the seeded baseline did
not cover. The auditor reclassified them to `Qualified in place? = no` and seeded them in
`audit/claims_baseline.txt`; 7A-6 verifies and maintains that baseline:

| Claim ID | Path | Literal | Why it is tolerated until G6 | Target |
|---|---|---|---|---|
| 6 | `README.md` | `Q4_K_M` | README L10 lists `Q4_K_M` in the project-goal sentence without a qualifier, while L108 scopes the verified release to `Q4_0`/`Q4_K`/`Q8_0`. 7C-4 publishes the compatibility matrix that settles it. | G6 |
| 10 | `README.md` | `qwen2` | README L107 says "Supports both SentencePiece … and GPT-2 / Llama-3 / Qwen2 byte-level … BPE vocabularies", which reads as a support claim. L108 qualifies it in the next bullet, but the handoff requires the qualifier to be in the *same* bullet. 7B/7C close the gap. | G6 |

Both are cheap to fix in README wording and should be **removed from the baseline** once
7B/7C rewrite those bullets — the ratchet only tolerates them until the wording is
correct. IDs 13, 14, 18, 19, 20, 26, 27, 28, 29, 30 are likewise candidates for cheap
inline qualification; the handoff's ratchet rule (`check_claims.py` default mode tolerates
only exact baseline entries) means each one must either be qualified in place or appear in
`audit/claims_baseline.txt`. The auditor seeded those entries (15 exact lines, including
both files for multi-path claims); 7A-6 must verify them and reject any entry that hides a
claim which could be fixed cheaply.
