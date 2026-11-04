# G1 / 7A-3 — Golden data and provenance

**Package:** 7A-3 (G1 item: independent golden data, provenance, and the fixture
manifest)
**Branch:** `wp/7A-3-goldens`
**Base:** `vibe/phase7-220201` @ `a8c3dbe`; branch base commit `34f1686`
**red/green:** the **known-bug goldens are the red** — they fail under
`pytest --runxfail`, for the expected reason (`runxfail.log`). The
plain-text/multibyte/quant/parser goldens and both normal lanes are the green.

---

## The point of this package

Every golden here comes from **outside this repository**. The fixtures are
produced by **llama.cpp's own tools** — its tokenizer (`llama-tokenize`), its
quantizer (`llama-quantize`), and its own NumPy quant implementation and GGUF
reader (`gguf-py`) — and by upstream model files from HuggingFace. Nothing
imports `src/`.

The test that would have made this package worthless is the one the brief
names: a `quantize_*_cpu` → `dequantize_*_cpu` round-trip of this repository's
own code. Such a pair only proves that the implementation agrees with itself.
`tests/test_goldens_quant.py::test_the_expected_values_are_not_self_referential`
asserts that the recorded provenance never names this repository.

### The references, pinned

| reference | pin | used for |
|---|---|---|
| `ggml-org/llama.cpp` | `@149f5641b931aaf33697d70f9abc90c3e5300247` (2026-11-03) | the reference tokenizer, the reference quantizer, the reference NumPy quant and GGUF code (`gguf-py`) |
| `openai-community/gpt2` | `@607a30d783dfa663caf39e06633721c8d4cfcd7e` (MIT) | the GPT-2 byte-level BPE vocabulary |
| `ggml-org/models` | `tinyllamas/stories260K.gguf`, `tinyllamas/stories15M.gguf` (Apache-2.0) | the tiny GGUF fixture, the SentencePiece vocabulary, the source of the quantized blocks |

llama.cpp was built from source on this host; the exact commands are in
`generation-commands.log`.

---

## What was added

### The fixtures (`tests/fixtures/`, 2.7 MiB in total)

| fixture | kind | what it is |
|---|---|---|
| `gpt2_vocab.json` | tokenizer-vector | the GPT-2 vocabulary (50 257 tokens, 50 000 merges) in GGUF metadata form |
| `gpt2_tokenizer_golden.json` | tokenizer-vector | **the golden**: 12 token-ID vectors from llama.cpp |
| `stories260k_vocab.json` | tokenizer-vector | the 512-token SentencePiece vocabulary (for the "metadata absent" case) |
| `stories260k_tokenizer_golden.json` | tokenizer-vector | the golden for that case |
| `q4_0_blocks.bin` / `q4_k_blocks.bin` / `q6_k_blocks.bin` | quant-block | 32 Q4_0 blocks, 16 Q4_K and 16 Q6_K super-blocks, from llama.cpp's own quantizer |
| `quant_golden.json` | quant-block | the expected FP32 values, the block layout and the hashes |
| `tiny_gguf.gguf` | tiny-model | the upstream TinyLlama `stories260K` GGUF, **committed verbatim** |
| `tiny_gguf_expectations.json` | gguf-header | the metadata, the tensor descriptors and the values, as read by llama.cpp |
| `PROVENANCE.md` | — | the registry, with a row per fixture |
| `make_fixtures.py` | — | the generator |

Every fixture is ≤ 2 MB and the total is ≤ 10 MB, as the rules require.

### The tests

| module | lane | what it checks |
|---|---|---|
| `tests/test_goldens_tokenizer.py` | cpu | the token IDs against llama.cpp, the BOS behaviour, the special-token behaviour, the decode round-trip |
| `tests/test_goldens_quant.py` | cpu | the block layout, the CPU dequantization against the reference, the fixture hashes, the non-self-referential provenance |
| `tests/test_goldens_gguf.py` | cpu | the metadata, the tensor descriptors, the alignment, the offsets and the zero-copy values against llama.cpp's reader |
| `tests/test_goldens_gpu.py` | gpu | the same golden blocks through the HIP dequantizers |

All four are registered in `tests/test_harness_contract.py::EXPECTED_LANES`, so
a new module without a deliberate lane choice fails the contract test.

### The manifest

`MANIFEST.in` gains `recursive-include tests/fixtures *` — the fixture globs
only. The 7A-5 `recursive-include tests *.py` rule is untouched.

---

## The red: the two known open bugs

Both are `pytest.mark.xfail(strict=True)`, so G1 stays green, and both are
shown failing under `--runxfail` (`runxfail.log`):

| test | reference | this repository |
|---|---|---|
| `test_add_bos_default_matches_the_reference_tokenizer` | `[15496, 995]` — no BOS, because the GPT-2 vocabulary has no `tokenizer.ggml.add_bos_token` metadata | `[50256, 15496, 995]` — a BOS is always prepended |
| `test_special_token_is_encoded_as_its_id` | `[50256]` — the special token is emitted as its own ID | `[27, 91, 437, 1659, 5239, 91, 29]` — the text is tokenized as ordinary characters |

`strict=True` means the suite **fails** if either test unexpectedly passes, so
the 7B fix cannot land silently.

The "metadata absent" case is covered separately and **passes**: the TinyLlama
SentencePiece vocabulary carries no `tokenizer.ggml.add_bos_token` key either,
but for that vocabulary type the reference adds a BOS — and so does this
repository's tokenizer.

---

## The green

| check | result |
|---|---|
| `pytest -m "not gpu"` | **91 passed, 24 deselected, 2 xfailed**, exit 0 |
| `pytest -m gpu` (on gfx1150) | **24 passed, 93 deselected**, exit 0 |
| `pytest --runxfail` | **2 failed** (exactly the two known bugs), 115 passed |
| `tests/test_cpu_only.py` | **12/12 OK** (standard) |
| `tests/test_cpu_only.py -O` | **12/12 OK** |
| the claims checker / canaries | PASS / 12 of 12 — unchanged |
| the provenance check | **137/137** (`provenance.log`) |
| the sdist contains the fixtures | yes (`sdist-contents.log`) |
| the golden tests in the extracted sdist tree | **36 passed, 2 xfailed**, exit 0 |
| no `src/`, CMake, `setup.py`, `pyproject`, README, PLAN, ledger, baseline or CI change | confirmed by `diffstat.txt` |
| no test deleted, skipped or weakened | confirmed — the existing tests are untouched; the two new xfails are new tests |

The counts before this package were 43 CPU and 18 GPU; they are now 91 and 24
(+48 CPU, +6 GPU), all from the new modules.

### The tolerances are exact

Every golden comparison is **exact**, with no tolerance to widen:

* the token IDs must match llama.cpp's element for element;
* the CPU dequantizers and the HIP kernels reproduce the FP16 rounding of
  llama.cpp's FP32 reference values **bit for bit** (`max |diff| = 0.0`);
* the GGUF metadata, descriptors and values must match llama.cpp's reader
  exactly.

A golden that is not exact would let a broken implementation pass.

---

## Two things worth recording

### The provenance of the Q4_0 bytes is machine-checkable

llama.cpp ships a NumPy implementation of its own Q4_0 quantizer. Re-quantizing
the source tensor with it reproduces the committed bytes **exactly**, which
ties the fixture to `llama-quantize`'s output rather than to a
re-implementation. The check is recorded in `quant_golden.json` and asserted by
`test_the_q4_0_bytes_are_llama_cpp_s_own_quantizer_output`.

For Q4_K and Q6_K the same check is **unavailable** — `gguf-py` has no NumPy
*quantizer* for the K-quants — and the golden says so rather than pretending
otherwise. Their expected values still come from llama.cpp's NumPy
*dequantizer* applied to the bytes `llama-quantize` produced.

### The vocabulary choice is not arbitrary

The repository's tokenizer is a **BPE** implementation (a merge-ranked
priority queue, plus the GPT-2 pre-tokenizer regex). llama.cpp's SentencePiece
vocabularies are **unigram** models with Viterbi segmentation, and the two
disagree: for TinyLlama's `stories260K`, llama.cpp encodes `"don't"` as
`['▁d', 'on', "'", 't']` while this repository produces
`['▁do', 'n', "'", 't']`.

That difference was measured before the fixtures were chosen, not after. It
is why the goldens use a **byte-level BPE** vocabulary — GPT-2 — where
llama.cpp and this repository run the *same* algorithm, and it is why the
SentencePiece vocabulary is used only for the "metadata absent" case, whose
prompt (`"Hello world"`) the two agree on.

This is recorded here because it is the kind of thing that looks like a bug in
the implementation and is not: the repository's tokenizer is not a unigram
SentencePiece model, and no golden was chosen to hide that.

---

## Limitations and follow-ups

1. **The golden vocabulary is large.** `gpt2_vocab.json` is 1.35 MB — 47 % of
   the fixture budget — because a faithful GPT-2 BPE vocabulary is 50 257
   tokens and 50 000 merges. It is within the ≤ 2 MB per-fixture rule, but a
   smaller BPE vocabulary would be preferable if a suitable upstream one
   existed; none of the real ones is smaller.
2. **The Q4_K/Q6_K byte-identity cross-check is unavailable** (see above).
3. **The GPU goldens use the same blocks as the CPU goldens.** A GPU-specific
   block set would not add coverage: the kernel's correctness is what is being
   checked, and the input is the reference's output.
4. **The tiny GGUF fixture is 1.13 MB** and dominates the remaining budget. It
   is a real upstream model committed verbatim, which is why it is that large;
   a generated file would have been smaller but would have had to be generated
   by *something*, and "something" is where the self-reference creeps in.
5. **7B is not started here.** The two xfails are its work; this package only
   pins them.

---

## Rollback

Delete `tests/test_goldens_*.py`, `tests/fixtures/` (except `PROVENANCE.md`,
which is restored to its previous content) and the `MANIFEST.in` line, and
remove the four entries from `EXPECTED_LANES`. Nothing else in the repository
changes, so the rollback cannot affect the build, the CI jobs or any other
package's evidence.

## Claims changed

None. No public claim was added, removed or re-qualified. This package adds
test fixtures, test modules and the fixture manifest rule.
