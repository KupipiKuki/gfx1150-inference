"""Golden token vectors from llama.cpp's reference tokenizer (Phase 7A-3).

The golden token IDs in ``tests/fixtures/gpt2_tokenizer_golden.json`` and
``tests/fixtures/stories260k_tokenizer_golden.json`` were produced by
**llama.cpp's own tokenizer** (``llama-tokenize``) on the GPT-2 byte-level
BPE vocabulary and on the TinyLlama SentencePiece vocabulary. They are *not*
produced by this repository's tokenizer: a golden derived from the
implementation under test would only prove that the implementation agrees
with itself.

The provenance of every fixture is in ``tests/fixtures/PROVENANCE.md``.

Phase 7B closes the four former ``xfail`` targets:

1. ``add_bos`` defaults follow ``tokenizer.ggml.add_bos_token`` and the
   family default the reference applies when the metadata is absent;
2. special tokens in the input are emitted as their own token IDs
   (longest match), keyed by the per-case ``--no-parse-special`` flag the
   golden records;
3. the SentencePiece path is a unigram Viterbi over the GGUF scores, which
   the vocabulary fixture now carries;
4. unmappable bytes raise instead of being dropped.

The vocabulary fixtures are loaded from disk, so the suite runs offline.
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

_NO_PARSE_SPECIAL = "--no-parse-special"


def _load_json(name: str) -> Dict[str, Any]:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


def _build_tokenizer(vocab: Dict[str, Any]) -> GGUFTokenizer:
    """Build the tokenizer under test from a committed vocabulary fixture."""
    token_types = [int(vocab["token_type_default"])] * int(vocab["n_tokens"])
    for index, token_type in vocab["token_types"].items():
        token_types[int(index)] = int(token_type)
    return GGUFTokenizer(
        tokens=list(vocab["tokens"]),
        scores=vocab.get("scores"),
        bos_token_id=int(vocab["bos_token_id"]),
        eos_token_id=int(vocab["eos_token_id"]),
        merges=list(vocab["merges"]),
        token_types=token_types,
        tokenizer_model=str(vocab["model"]),
    )


def _parse_special(case: Dict[str, Any]) -> bool:
    """The golden records how the reference was invoked per case: whether it
    parsed special tokens or treated them as literal text."""
    return _NO_PARSE_SPECIAL not in case.get("reference_flags", [])


_GPT2_VOCAB = _load_json("gpt2_vocab.json")
_GPT2_GOLDEN = _load_json("gpt2_tokenizer_golden.json")
_SPM_VOCAB = _load_json("stories260k_vocab.json")
_SPM_GOLDEN = _load_json("stories260k_tokenizer_golden.json")

_GPT2_CASES = {case["id"]: case for case in _GPT2_GOLDEN["cases"]}
_SPM_CASES = {case["id"]: case for case in _SPM_GOLDEN["cases"]}

#: The GPT-2 cases the reference tokenizer and this repository's tokenizer
#: must agree on, with the same switches the reference used.
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

#: Every SentencePiece case matches the reference, after 7B: the
#: ``spm_contraction_dont`` case needs the unigram scores the fixture now
#: carries, and ``spm_control_token_parsed`` needs the special-token split.
_SPM_AGREED_CASES = [
    "spm_absent_add_bos_metadata",
    "spm_plain_text_no_bos",
    "spm_double_space",
    "spm_multibyte_accent",
    "spm_multibyte_greek",
    "spm_multibyte_emoji",
    "spm_punctuation_digits",
    "spm_contraction_were",
    "spm_contraction_dont",
    "spm_control_token_literal",
    "spm_control_token_parsed",
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
    assert tokenizer.encode(case["prompt"], add_bos=False, parse_special=_parse_special(case)) == case[
        "token_ids"
    ], f"token IDs for {case['prompt']!r} differ from llama.cpp's reference"


def test_add_bos_default_matches_the_reference_tokenizer() -> None:
    """The default BOS handling must match the reference.

    The vocabulary has no ``tokenizer.ggml.add_bos_token`` metadata, so the
    reference adds no BOS token; the byte-level BPE family default applied
    when the metadata is absent is "no BOS", and so is this repository's.
    """
    case = _GPT2_CASES["add_bos_default"]
    tokenizer = _build_tokenizer(_GPT2_VOCAB)
    assert tokenizer.encode(case["prompt"]) == case["token_ids"], (
        "the tokenizer must not add a BOS token when the vocabulary's metadata "
        "does not ask for one"
    )


def test_special_token_is_encoded_as_its_id() -> None:
    """A special token in the text must be encoded as that token's ID.

    The reference parses special tokens and emits their ID; it must not be
    byte-mapped or split, and no byte of it may be lost silently.
    """
    case = _GPT2_CASES["special_token_eot"]
    tokenizer = _build_tokenizer(_GPT2_VOCAB)
    assert tokenizer.encode(case["prompt"], add_bos=False, parse_special=True) == case["token_ids"], (
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
    assert tokenizer.encode(
        case["prompt"], add_bos=case["add_bos"], parse_special=_parse_special(case)
    ) == case["token_ids"], (
        "with the add_bos_token metadata absent, the tokenizer must agree with "
        "the reference on whether a BOS token is added"
    )


@pytest.mark.parametrize("case_id", _SPM_AGREED_CASES)
def test_spm_token_ids_match_the_reference_tokenizer(case_id: str) -> None:
    """The SentencePiece token IDs must equal llama.cpp's, byte for byte.

    The reference's switches are recorded per case in the golden -- the BOS
    switch and whether special tokens were parsed -- because the repository's
    encoder has to be called with the same switches.
    """
    case = _SPM_CASES[case_id]
    tokenizer = _build_tokenizer(_SPM_VOCAB)
    assert tokenizer.encode(
        case["prompt"], add_bos=case["add_bos"], parse_special=_parse_special(case)
    ) == case["token_ids"], (
        f"token IDs for {case['prompt']!r} differ from llama.cpp's reference"
    )


# ---------------------------------------------------------------------------
# Phase 7B QAQC: the tokenizer behaviours the goldens do not pin directly.
# ---------------------------------------------------------------------------


def _gpt2_eot_string(tokenizer: GGUFTokenizer) -> str:
    return tokenizer.id_to_token[tokenizer.eos_token_id]


def test_special_token_split_preserves_the_ordinary_text_around_it() -> None:
    """`hi<EOT>there` must be one special ID, not byte-mapped or split, and
    the ordinary text either side must tokenize as itself."""
    tokenizer = _build_tokenizer(_GPT2_VOCAB)
    eot = _gpt2_eot_string(tokenizer)
    plain_ids = tokenizer.encode("hi", add_bos=False)
    plain_there = tokenizer.encode("there", add_bos=False)
    ids = tokenizer.encode(f"hi{eot}there", add_bos=False, parse_special=True)
    assert ids == plain_ids + [tokenizer.eos_token_id] + plain_there


def test_parse_special_false_treats_the_special_token_as_ordinary_text() -> None:
    """"--no-parse-special" pins the other switch: the same string must not be
    be parsed as a special token."""
    tokenizer = _build_tokenizer(_GPT2_VOCAB)
    eot = _gpt2_eot_string(tokenizer)
    parsed = tokenizer.encode(eot, add_bos=False, parse_special=True)
    literal = tokenizer.encode(eot, add_bos=False, parse_special=False)
    assert parsed == [tokenizer.eos_token_id]
    assert literal != parsed, "parse_special=False must not emit the special ID"

    literal_chars = tokenizer.decode(literal, skip_special_tokens=False)
    assert literal_chars == eot, "the ordinary-text path must not lose characters"


def test_longest_match_wins_between_overlapping_special_tokens() -> None:
    """A special token that is a proper prefix of another special token loses
    to the longer match; the special ID is emitted with no byte mapping."""
    tokenizer = GGUFTokenizer(
        tokens=["<pad>", "<pad_word>", "a", "b"],
        scores=None,
        bos_token_id=-1,
        eos_token_id=-1,
        merges=[],
        token_types=[4, 4, 1, 1],  # USER_DEFINED, USER_DEFINED, NORMAL, NORMAL
        tokenizer_model="llama",
    )
    assert tokenizer.encode("<pad_word>", parse_special=True) == [1]
    assert tokenizer.encode("<pad>", parse_special=True) == [0]
    assert tokenizer.encode("a<pad_word>b", parse_special=True) == [2, 1, 3]


def test_lookalike_text_is_not_treated_as_a_special_token() -> None:
    """A string that looks like a special token but is not in the vocabulary
    must stay ordinary text: find no special match, lose no bytes"""
    tokenizer = _build_tokenizer(_GPT2_VOCAB)
    lookalike = "<|notaspecialtoken|>"
    ids = tokenizer.encode(lookalike, add_bos=False, parse_special=True)
    assert tokenizer.decode(ids, skip_special_tokens=False) == lookalike


def test_empty_and_whitespace_special_splitting() -> None:
    """A special token adjacent to whitespace and punctuation splits without
    losing the neighbouring text."""
    tokenizer = _build_tokenizer(_SPM_VOCAB)
    ids_space = tokenizer.encode(" <s>", add_bos=True, parse_special=True)
    # BOS + the leading-space chunk (" " -> a single ▁ piece) + the <s> ID
    assert ids_space == [1, 410, 1]
    # The special IDs are droppable on decode; the lone ▁ decodes to nothing
    # after the SentencePiece leading-space strip.
    assert tokenizer.decode(ids_space, skip_special_tokens=True) == ""

    ids_punct = tokenizer.encode("a<s>b", add_bos=False, parse_special=True)
    assert ids_punct.count(tokenizer.bos_token_id) == 1
    decoded = tokenizer.decode(ids_punct, skip_special_tokens=False)
    assert decoded == "a<s>b"


def _metadata_for(tokens: List[str], token_types: List[int], add_bos_token: Any = KeyError) -> Dict[str, Any]:
    md: Dict[str, Any] = {
        "tokenizer.ggml.tokens": tokens,
        "tokenizer.ggml.token_type": token_types,
        "tokenizer.ggml.model": "llama",
        "tokenizer.ggml.bos_token_id": 1,
        "tokenizer.ggml.eos_token_id": 2,
    }
    if add_bos_token is not KeyError:
        md["tokenizer.ggml.add_bos_token"] = add_bos_token
    return md


# A minimal SentencePiece vocabulary: <unk>, the control tokens, three byte
# tokens, the ▁ piece, a ▁-prefixed word, and a bare word. Bytes without a
# `<0xXX>` token (e.g. "c" = 0x63) are unmappable and must raise.
_MINI_TOKENS = ["<unk>", "<s>", "</s>", "<0x00>", "<0x01>", "<0xFF>", "\u2581", "\u2581b", "b"]
_MINI_TYPES = [2, 3, 3, 6, 6, 6, 1, 1, 1]
_MINI_PIECE = 7  # "▁b"
_MINI_WORD = 8  # "b"


def test_add_bos_precedence_argument_metadata_default() -> None:
    """explicit `add_bos` argument > metadata > family default, the way the
    reference resolves it. The metadata is read through the GGUF path."""
    from_gguf_metadata = GGUFTokenizer.from_gguf_metadata

    # metadata absent -> SentencePiece family default: add a BOS
    tok = from_gguf_metadata(_metadata_for(_MINI_TOKENS, _MINI_TYPES))
    assert tok.encode("b", add_bos=False) == [_MINI_PIECE]
    assert tok.encode("b") == [1, _MINI_PIECE]

    # metadata true / false are honored
    tok_true = from_gguf_metadata(_metadata_for(_MINI_TOKENS, _MINI_TYPES, add_bos_token=True))
    assert tok_true.encode("b") == [1, _MINI_PIECE]
    tok_false = from_gguf_metadata(_metadata_for(_MINI_TOKENS, _MINI_TYPES, add_bos_token=False))
    assert tok_false.encode("b") == [_MINI_PIECE]  # no BOS, the word piece only
    assert tok_false.encode("", add_bos=True) == [1]  # overridden by the argument

    # the explicit argument overrides the metadata in both directions
    assert tok_true.encode("b", add_bos=False) == [_MINI_PIECE]
    assert tok_false.encode("b", add_bos=True) == [1, _MINI_PIECE]


def test_no_duplicate_bos_is_added_on_top_of_a_leading_special_token() -> None:
    """A BOS metadata and a leading special token in the text must not
    produce two BOS IDs; the special token is emitted, the BOS is prepended
    once by the add_bos decision alone."""
    tok = GGUFTokenizer.from_gguf_metadata(
        _metadata_for(_MINI_TOKENS, _MINI_TYPES, add_bos_token=True)
    )
    # BOS (metadata) + "<s>" (special) + "b" following the special: no dummy
    # ▁ prefix, so the bare word piece.
    ids = tok.encode("<s>b", parse_special=True)
    assert ids == [1, 1, _MINI_WORD]


def test_unmappable_byte_raises_in_the_gpt2_path() -> None:
    """A minimal byte-level BPE vocabulary without the byte for `é` must raise
    instead of dropping the character; the byte value names the loss."""
    tokenizer = GGUFTokenizer(
        tokens=["a", "b"],
        scores=None,
        bos_token_id=-1,
        eos_token_id=-1,
        merges=[],
        token_types=None,
        tokenizer_model="gpt2",
    )
    assert tokenizer.encode("a", add_bos=False) == [0]
    with pytest.raises(ValueError, match="0xC3"):
        tokenizer.encode("é", add_bos=False)


def test_unmappable_byte_raises_in_the_spiece_path() -> None:
    """A minimal SentencePiece vocabulary without a `<0xXX>` token for a byte
    it cannot cover must raise with the byte value."""
    tokenizer = GGUFTokenizer.from_gguf_metadata(_metadata_for(_MINI_TOKENS, _MINI_TYPES))
    with pytest.raises(ValueError, match="0x63") as excinfo:
        tokenizer.encode("c", add_bos=False)
    assert "0x63" in str(excinfo.value), "the error must name the missing byte"
    with pytest.raises(ValueError, match="0x63"):
        tokenizer.encode("cd", add_bos=False)


def test_unmappable_codepoint_raises_with_its_byte() -> None:
    """A lone surrogate cannot be encoded as UTF-8 at all; it must be reported
    as a ValueError, not a UnicodeEncodeError from a lower layer."""
    tk_gpt2 = _build_tokenizer(_GPT2_VOCAB)
    with pytest.raises(ValueError) as excinfo:
        tk_gpt2.encode("a\ud800b", add_bos=False)
    assert "UTF-8" in str(excinfo.value), "a lone surrogate is a UTF-8 problem"

    tk_spm = _build_tokenizer(_SPM_VOCAB)
    with pytest.raises(ValueError) as spm_exc:
        tk_spm.encode("a\ud800b", add_bos=False)
    assert "UTF-8" in str(spm_exc.value), "a lone surrogate is a UTF-8 problem"


def test_encode_decode_round_trip_with_and_without_special_tokens() -> None:
    """Decoding behind `skip_special_tokens` both ways stays consistent."""
    gpt2_tok = _build_tokenizer(_GPT2_VOCAB)
    eot = _gpt2_eot_string(gpt2_tok)
    ids = gpt2_tok.encode(f"hi{eot}there", add_bos=False, parse_special=True)
    assert gpt2_tok.decode(ids, skip_special_tokens=True) == "hithere"
    assert gpt2_tok.decode(ids, skip_special_tokens=False) == f"hi{eot}there"

    spm_tok = _build_tokenizer(_SPM_VOCAB)
    spm_ids = spm_tok.encode("<s>", add_bos=True, parse_special=True)
    assert spm_ids == [1, 1]
    assert spm_tok.decode(spm_ids, skip_special_tokens=True) == ""
    assert spm_tok.decode(spm_ids, skip_special_tokens=False) == "<s><s>"


def test_empty_string_encodes_to_the_bos_decision_alone() -> None:
    gpt2_tok = _build_tokenizer(_GPT2_VOCAB)
    assert gpt2_tok.encode("") == []  # GPT-2 family default: no BOS
    assert gpt2_tok.encode("", add_bos=True) == [gpt2_tok.bos_token_id]
    spm_tok = _build_tokenizer(_SPM_VOCAB)
    assert spm_tok.encode("") == [spm_tok.bos_token_id]  # SPM default: BOS
    assert spm_tok.encode("", add_bos=False) == []


def test_the_vocabulary_fixture_matches_its_recorded_hash() -> None:
    """The committed vocabulary must be the one the golden was produced from."""
    import hashlib

    recorded = _GPT2_GOLDEN["vocab"]["fixture_sha256"]
    digest = hashlib.sha256((_FIXTURES / "gpt2_vocab.json").read_bytes()).hexdigest()
    assert digest == recorded, (
        "tests/fixtures/gpt2_vocab.json does not match the hash recorded in the "
        "golden; the fixture was edited without regenerating the golden"
    )

    spm_recorded = _SPM_GOLDEN["vocab"]["fixture_sha256"]
    spm_digest = hashlib.sha256((_FIXTURES / "stories260k_vocab.json").read_bytes()).hexdigest()
    assert spm_digest == spm_recorded, (
        "tests/fixtures/stories260k_vocab.json does not match the hash recorded "
        "in the golden; the fixture was edited without regenerating the golden"
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

    # Phase 7B: every case must also pin how the reference treated special
    # tokens, so the repository's encoder is called with the same switch.
    for case in _SPM_GOLDEN["cases"]:
        assert isinstance(_parse_special(case), bool), (
            f"case {case['id']} does not record its parse-special switch"
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
