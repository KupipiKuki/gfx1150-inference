# QAQC Report — Work package 7A-3 (Golden data and provenance)

**Role:** QAQC (independent session, per handoff §1 and `PHASE7_7A-3_BRIEF.md`)
**Date:** 2026-11-04
**Tree tested:** work commit `2c59c5e935ce85afacee48cda17a0129bc9926c0` on `wp/7A-3-goldens`
(tip `a9c5785`; prep/brief `34f1686`; base `a8c3dbe` — all merged 7A packages). CI
verified against the **public GitHub API**; goldens independently cross-validated
against the pinned upstream vocabulary.
**Probes:** `probe-commands.log` (this directory).

---

## Verdict

**PASS.** This is the correctness-evidence package the whole phase exists for, and it
meets the hardest requirement in the handoff — **independent golden data** — with
provenance that is complete, pinned, and machine-checked. Every comparison is exact;
the two known 7B bugs are pinned by `xfail(strict=True)` goldens whose `--runxfail`
failures I reproduced for the expected reasons; the fixtures load offline from a fresh
clone; the sdist ships them; the CI run is green on the real runner; and the scope is
exactly the brief's. No conditions.

## 1. Independence — the non-negotiable, verified three ways

1. **Generation path**: `make_fixtures.py` imports only stdlib + NumPy and drives
   llama.cpp's own binaries (`llama-tokenize`, `llama-quantize`) and its own `gguf-py`
   reader; **zero references to `src/`** (grep-verified). The expected GGUF
   expectations are read by llama.cpp's reader, not this repo's parser.
2. **Provenance registry**: every fixture has a row with pinned upstream revisions
   (llama.cpp `@149f5641`, GPT-2 `@607a30d7` MIT, TinyLlama GGUFs Apache-2.0), exact
   commands, input and output hashes. The committed `verify-provenance.py` passes
   **137/137**, and I independently confirmed the committed files' sha256s against the
   registry rows — including the two rows my own first parsing pass fumbled (my bug;
   the hashes match exactly).
3. **Cross-validation against upstream data**: I decoded every golden token-ID
   vector back to text through the *committed upstream GPT-2 vocabulary* using the
   standard published byte-level decoder — **all 12 cases round-trip exactly**, and
   the canonical published IDs match (`Hello world` → [15496, 995], `Ġ`-space handling,
   `<|endoftext|>` = 50256). The goldens are genuine, not invented.

Also verified: `tiny_gguf.gguf` is the **upstream stories260K GGUF committed
verbatim** (its input and output hashes are identical — self-consistent by
construction); the Q4_0 blocks carry a machine-checkable byte-identity cross-check
(llama.cpp's NumPy requantizer reproduces them byte for byte), and the registry
honestly states that this cross-check is unavailable for Q4_K/Q6_K (gguf-py has no
NumPy quantizer for them) rather than implying more than is proven.

## 2. The red evidence — reproduced for the expected reasons

- Exactly **2 xfails, both `strict=True`**, with the 7B reasons:
  `add_bos` default handling and special-token encoding.
- `pytest --runxfail`: **both fail** — `test_add_bos_default…` and
  `test_special_token_is_encoded_as_its_id` — matching `runxfail.log`. These are the
  tests 7B must turn green.
- The passing goldens are exact: token IDs element-for-element; CPU dequantizers and
  the HIP kernels reproduce llama.cpp's FP32-reference FP16 rounding **bit for bit**
  (`np.array_equal`, `max_err == 0.0` — verified in the GPU golden test I ran on
  gfx1150); GGUF metadata/descriptors/values exact.

## 3. Suites, lanes, and CI — all green, all verified

| Check | Result |
|---|---|
| `pytest -m "not gpu"` | **91 passed / 24 deselected / 2 xfailed** (arithmetic verified: 43 prior + 38 golden CPU items + 12 new lane-contract items = 93) |
| `pytest -m gpu` (gfx1150) | **24 passed** (18 prior + 6 GPU golden items) |
| `test_cpu_only.py` normal / `-O` | 12/12 both |
| claims checker / canaries | PASS (0/17/0/0) / 12/12 |
| Fresh clone, offline, golden modules only | **36 passed / 2 xfailed** (matches `fresh-clone.log`) |
| sdist ships the fixtures | **13 fixture entries**, incl. `tiny_gguf.gguf`, all goldens, `make_fixtures.py` (matches `sdist-contents.log`) |
| **CI run 41749187809** | **API-verified: success**, head = the work commit — the CPU lane is green on ubuntu-latest/Python 3.12 with the 2.7 MiB of fixtures aboard, xfail-stable |
| Lane contract | all 4 new modules registered in `EXPECTED_LANES` (3 × cpu, `test_goldens_gpu.py` = gpu) — the 7A-1 follow-up's warning heeded |

## 4. Scope and record hygiene

Only `tests/**` (4 new modules + `EXPECTED_LANES`), `tests/fixtures/**` (10 fixtures +
registry + generator), `MANIFEST.in` (**fixture globs only** — the 7A-5 `tests *.py`
rule untouched, as the brief required), and the evidence bundle. Restricted diff
(src, CMake, setup.py, pyproject, README, PLAN, scripts/qa, ledger, baseline, CI):
**empty**. No test deleted, skipped, or weakened. `candidate-sha.txt` = the work
commit. Fixture sizes: each ≤ 2 MB, total 2.75 MB ≤ 10 MB (the size-table correction
in the evidence commit was made as a proper new commit).

## 5. Observations (no action required)

1. **QAQC probe erratum**: my first two hash-check passes used a naive row-parsing
   regex and misread the input/output hash columns for two rows; the committed
   `verify-provenance.py` (structural parser) was right all along, and manual
   `sha256sum` confirmed every row. Documented in the transcript for the record.
2. The commit message records two honest engineering judgments worth the auditor's
   attention: the GPT-2 byte-level BPE vocabulary was chosen because the repo's
   tokenizer is a BPE implementation (llama.cpp's SentencePiece vocabs are unigram
   and disagree on contractions — measured before choosing); and the Q4_K/Q6_K
   byte-identity cross-check is unavailable and stated as such.
3. The goldens deliberately do **not** cover a SentencePiece-tokenization golden
   (only the metadata-absent `add_bos` case uses the stories260k vocab) — a gap that
   is a consequence of the BPE choice, worth remembering when 7B/7C scope model
   families.

## 6. Disposition

**7A-3 passes QAQC unconditionally.** The goldens are independent, exactly pinned,
machine-checkable, and genuinely red where the known bugs live — everything the G1
exit criteria demanded of this package. With 7A-1, 7A-3, 7A-5, 7A-6, 7A-7, 7A-8
(+follow-ups) all QAQC-passed, **only 7A-4 (deterministic fuzz) remains open for G1**.
G1 remains unsigned; 7B stays blocked until G1 and these goldens — which now exist.

**QAQC sign-off:** 2026-11-04. Probes: `probe-commands.log` (this directory).
Scratch retained at `/tmp/opencode/qaqc-73/`.
