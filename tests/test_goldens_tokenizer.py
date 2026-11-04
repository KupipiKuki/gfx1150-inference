"""Golden token vectors from llama.cpp's reference tokenizer (Phase 7A-3).

The golden token IDs in ``tests/fixtures/gpt2_tokenizer_golden.json`` were
produced by **llama.cpp's own tokenizer** (``llama-tokenize``) on the GPT-2
byte-level BPE vocabulary, and by the same tool on the TinyLlama SentencePiece
vocabulary. They are *not* produced by this repository's tokenizer: a golden
that were derived from the implementation under test would only prove that the
implementation agrees with itself.

The provenance of every fixture is in ``tests/fixtures/PROVENANCE.md``.

Two of the cases are known open bugs and are marked
``pytest.mark.xfail(strict=True)``: the special-token encoding and the
``add_bos_token`` handling are 7B work. They are expected to fail until then,
and ``pytest --runxfail`` shows them failing for the expected reason.

The vocabulary fixture is loaded from disk, so the suite runs offline.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
from typing import Any, Dict, List

import pytest

_ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for _p in (os.path.join(_ROOT_DIR, "build"), os.path.join(_ROOT_DIR, "src")):
    if _p not in sys.path and os.path.isdir(_p):
        sys.path.insert(0, _p)

from tokenizer import GGUFTokenizer

# These are golden-vector tests: pure CPU, no extension, no GPU.
pytestmark = pytest.mark.cpu

_FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"


def _load_json(name: str) -> Dict[str, Any]:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


def _build_tokenizer(vocab: Dict[str, Any]) -> GGUFTokenizer:
    """Build the tokenizer under test from a committed vocabulary fixture."""
    token_types = [int(vocab["token_type_default"])] * int(vocab["n_tokens"])
    for index, token_type in vocab["token_types"].items():
        token_types[int(index)] = int(token_type)
    return GGUFTokenizer(
        tokens=list(vocab["tokens"]),
        scores=None,
        bos_token_id=int(vocab["bos_token_id"]),
        eos_token_id=int(vocab["eos_token_id"]),
        merges=list(vocab["merges"]),
        token_types=token_types,
        tokenizer_model=str(vocab["model"]),
    )


_GPT2_VOCAB = _load_json("gpt2_vocab.json")
_GPT2_GOLDEN = _load_json("gpt2_tokenizer_golden.json")
_SPM_VOCAB = _load_json("stories260k_vocab.json")
_SPM_GOLDEN = _load_json("stories260k_tokenizer_golden.json")

_GPT2_CASES = {case["id"]: case for case in _GPT2_GOLDEN["cases"]}
_SPM_CASES = {case["id"]: case for case in _SPM_GOLDEN["cases"]}

#: The cases the reference tokenizer and this repository's tokenizer must
#: already agree on. The special-token and ``add_bos`` cases are excluded:
#: they are the two known open bugs (7B).
_AGREED_CASES = [
    "plain_text",
    "double_space",
    "multibyte_accent",
    "multibyte_greek",
    "multibyte_emoji",
    "punctuation_digits",
    "underscore",
    "contraction_dont",
    "contraction_were",
    "add_bos_disabled",
]

#: The SentencePiece cases the repository's tokenizer already matches. The
#: BOS-absent case has its own test below, which states the metadata argument
#: explicitly.
_SPM_AGREED_CASES = [
    "spm_plain_text_no_bos",
    "spm_double_space",
    "spm_multibyte_accent",
    "spm_multibyte_greek",
    "spm_multibyte_emoji",
    "spm_punctuation_digits",
    "spm_contraction_were",
    "spm_control_token_literal",
]

#: The SentencePiece cases the repository's tokenizer does not match yet.
#: They are kept in the golden -- the family must not be omitted -- and pinned
#: here as strict xfails with the reason, so that G1 stays green and the
#: ``--runxfail`` run shows them failing for that reason.
_SPM_XFAIL_CASES = [
    pytest.param(
        "spm_contraction_dont",
        marks=pytest.mark.xfail(
            strict=True,
            reason=(
                "7B/7C: the repository's SentencePiece path is a greedy longest "
                "match; the reference segments with the unigram scores"
            ),
        ),
    ),
    pytest.param(
        "spm_control_token_parsed",
        marks=pytest.mark.xfail(
            strict=True,
            reason=(
                "7B: a control token in the input is not parsed as its own "
                "token ID"
            ),
        ),
    ),
]


@pytest.mark.parametrize("case_id", _AGREED_CASES)
def test_token_ids_match_the_reference_tokenizer(case_id: str) -> None:
    """The token IDs must equal llama.cpp's, byte for byte.

    The reference encodes without a BOS token for this vocabulary (the
    GPT-2 vocabulary carries no ``tokenizer.ggml.add_bos_token`` key and the
    BPE default is to add none), so the tokenizer is called with
    ``add_bos=False``.
    """
    case = _GPT2_CASES[case_id]
    tokenizer = _build_tokenizer(_GPT2_VOCAB)
    assert tokenizer.encode(case["prompt"], add_bos=False) == case["token_ids"], (
        f"token IDs for {case['prompt']!r} differ from llama.cpp's reference"
    )


@pytest.mark.xfail(
    strict=True,
    reason="7B: the tokenizer ignores tokenizer.ggml.add_bos_token and always adds a BOS",
)
def test_add_bos_default_matches_the_reference_tokenizer() -> None:
    """The default BOS handling must match the reference (known bug, 7B).

    The vocabulary has no ``tokenizer.ggml.add_bos_token`` metadata, so the
    reference adds no BOS token. This repository's tokenizer always prepends
    one, which is the open bug this test pins.
    """
    case = _GPT2_CASES["add_bos_default"]
    tokenizer = _build_tokenizer(_GPT2_VOCAB)
    assert tokenizer.encode(case["prompt"]) == case["token_ids"], (
        "the tokenizer must not add a BOS token when the vocabulary's metadata "
        "does not ask for one"
    )


@pytest.mark.xfail(
    strict=True,
    reason="7B: special tokens in the input are not encoded as their own token IDs",
)
def test_special_token_is_encoded_as_its_id() -> None:
    """A special token in the text must be encoded as that token's ID (7B).

    The reference parses special tokens and emits their ID; this repository's
    tokenizer treats the text as ordinary characters.
    """
    case = _GPT2_CASES["special_token_eot"]
    tokenizer = _build_tokenizer(_GPT2_VOCAB)
    assert tokenizer.encode(case["prompt"], add_bos=False) == case["token_ids"], (
        "a special token in the input must be encoded as its own token ID"
    )


def test_absent_add_bos_metadata_matches_the_reference_tokenizer() -> None:
    """A vocabulary without ``add_bos_token`` metadata: the reference adds a BOS.

    This is the TinyLlama SentencePiece vocabulary, whose GGUF carries no
    ``tokenizer.ggml.add_bos_token`` key at all. The reference adds a BOS for
    this vocabulary type, and so must this repository's tokenizer.
    """
    case = _SPM_CASES["spm_absent_add_bos_metadata"]
    tokenizer = _build_tokenizer(_SPM_VOCAB)
    assert tokenizer.encode(case["prompt"], add_bos=case["add_bos"]) == case["token_ids"], (
        "with the add_bos_token metadata absent, the tokenizer must agree with "
        "the reference on whether a BOS token is added"
    )


@pytest.mark.parametrize("case_id", _SPM_AGREED_CASES)
def test_spm_token_ids_match_the_reference_tokenizer(case_id: str) -> None:
    """The SentencePiece token IDs must equal llama.cpp's, byte for byte.

    The switch the reference used is recorded per case in the golden, because
    this vocabulary type adds a BOS token by default and the repository's
    encoder has to be called with the same switch.
    """
    case = _SPM_CASES[case_id]
    tokenizer = _build_tokenizer(_SPM_VOCAB)
    assert tokenizer.encode(case["prompt"], add_bos=case["add_bos"]) == case["token_ids"], (
        f"token IDs for {case['prompt']!r} differ from llama.cpp's reference"
    )


@pytest.mark.parametrize("case_id", _SPM_XFAIL_CASES)
def test_spm_known_mismatches_are_pinned(case_id: str) -> None:
    """The SentencePiece cases the repository does not match yet (7B/7C).

    They are part of the golden, so the family is covered; the assertions
    state what the reference does, and the repository's tokenizer does not do
    it yet. ``strict=True`` means the suite fails if one of them starts
    passing, so the fix cannot land unnoticed.
    """
    case = _SPM_CASES[case_id]
    tokenizer = _build_tokenizer(_SPM_VOCAB)
    assert tokenizer.encode(case["prompt"], add_bos=case["add_bos"]) == case["token_ids"], (
        f"token IDs for {case['prompt']!r} differ from llama.cpp's reference"
    )


def test_the_vocabulary_fixture_matches_its_recorded_hash() -> None:
    """The committed vocabulary must be the one the golden was produced from."""
    import hashlib

    recorded = _GPT2_GOLDEN["vocab"]["fixture_sha256"]
    digest = hashlib.sha256((_FIXTURES / "gpt2_vocab.json").read_bytes()).hexdigest()
    assert digest == recorded, (
        "tests/fixtures/gpt2_vocab.json does not match the hash recorded in the "
        "golden; the fixture was edited without regenerating the golden"
    )


def test_the_golden_cases_cover_the_required_inputs() -> None:
    """The golden must cover every input class the Phase 7A-3 brief lists."""
    prompts = {case["prompt"] for case in _GPT2_GOLDEN["cases"]}
    for required in (
        "Hello world",
        "Hello  world",
        "café",
        "Ω",
        "\U0001f600",
        "hello, world! 123",
        "a_b",
        "don't",
        "we're",
        "<|endoftext|>",
    ):
        assert required in prompts, f"the golden does not cover {required!r}"


def test_the_sentencepiece_golden_covers_the_required_inputs() -> None:
    """The SentencePiece golden must cover the same input classes.

    The 7A-3 brief requires both a GPT-2 and a SentencePiece family. The
    SentencePiece half was missing (audit condition C-7A3-1), so the coverage
    is asserted for it too rather than only for GPT-2.
    """
    spm_prompts = {case["prompt"] for case in _SPM_GOLDEN["cases"]}
    for required in (
        "Hello world",
        "Hello  world",
        "café",
        "Ω",
        "\U0001f600",
        "hello, world! 123",
        "we're",
        "don't",
        "<s>",
    ):
        assert required in spm_prompts, (
            f"the SentencePiece golden does not cover {required!r}"
        )

    # The BOS switch must be covered for this family too: the reference adds a
    # BOS for this vocabulary type unless --no-bos is passed.
    switches = {case["add_bos"] for case in _SPM_GOLDEN["cases"]}
    assert switches == {True, False}, (
        "the SentencePiece golden must cover both the BOS and the no-BOS case, "
        f"found {sorted(switches)}"
    )


def test_decode_round_trips_the_golden_text() -> None:
    """Decoding the golden IDs must return the original text."""
    for case_id in ("plain_text", "multibyte_accent", "multibyte_emoji", "underscore"):
        case = _GPT2_CASES[case_id]
        tokenizer = _build_tokenizer(_GPT2_VOCAB)
        decoded = tokenizer.decode(case["token_ids"], skip_special_tokens=True)
        assert decoded == case["prompt"], (
            f"decoding the golden IDs for {case['prompt']!r} returned {decoded!r}"
        )
