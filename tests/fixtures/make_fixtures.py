#!/usr/bin/env python3
"""Generate the Phase 7A-3 golden fixtures from independent upstream sources.

The fixtures in this directory are **not** produced by this repository's own
encoder or decoder. They come from two independent upstreams:

* **llama.cpp** (``ggml-org/llama.cpp``) supplies the reference tokenizer and
  the reference quantizer. This script drives llama.cpp's own ``llama-tokenize``
  and ``llama-quantize`` binaries, and uses llama.cpp's own ``gguf-py`` package
  (the reference GGUF reader/writer and the reference NumPy quant
  implementation) to read metadata and to compute the expected dequantized
  values.
* **HuggingFace** supplies the source vocabularies and the source models:
  ``openai-community/gpt2`` (a byte-level BPE vocabulary) and
  ``ggml-org/models`` (the TinyLlama ``stories260K`` / ``stories15M`` GGUF
  models).

Nothing here imports ``src/``: the fixtures must not depend on the code they
are used to test.

Requirements
------------

* llama.cpp built from source, with ``build/bin/llama-tokenize`` and
  ``build/bin/llama-quantize`` (``--llama-cpp <llama.cpp checkout>``);
* llama.cpp's ``gguf-py`` importable (add ``<llama.cpp>/gguf-py`` to
  ``PYTHONPATH``, or pass ``--gguf-py <path>``);
* the upstream files (downloaded separately; their URLs and hashes are in
  ``PROVENANCE.md``).

Usage
-----

::

    # tokenizer vectors
    python3 make_fixtures.py tokenizer \\
        --llama-cpp /path/to/llama.cpp \\
        --gpt2-vocab gpt2-vocab.json --gpt2-merges gpt2-merges.txt \\
        --spm-gguf stories260K.gguf \\
        --out .

    # quantized blocks
    python3 make_fixtures.py quant \\
        --llama-cpp /path/to/llama.cpp \\
        --model stories15M.gguf --out .

    # the tiny GGUF's structural expectations
    python3 make_fixtures.py gguf-expectations \\
        --gguf tiny_gguf.gguf --out .
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import subprocess
import sys
from typing import Any

import numpy as np

SCHEMA_VOCAB = "gfx1150-inference/tokenizer-vocab/1"
SCHEMA_GOLDEN = "gfx1150-inference/tokenizer-golden/1"
SCHEMA_QUANT = "gfx1150-inference/quant-golden/1"
SCHEMA_GGUF = "gfx1150-inference/gguf-expectations/1"

#: The GPT-2 (byte-level BPE) prompts. They cover the cases the Phase 7A-3
#: brief lists: plain text, double spaces, multibyte text, punctuation,
#: digits, an underscore, contractions, a special token, and the BOS switch.
GPT2_CASES: list[tuple[str, str, str, bool]] = [
    # (case id, prompt, how the reference is invoked, whether the reference
    #  parses special tokens)
    ("plain_text", "Hello world", "", False),
    ("double_space", "Hello  world", "", False),
    ("multibyte_accent", "café", "", False),
    ("multibyte_greek", "Ω", "", False),
    ("multibyte_emoji", "\U0001f600", "", False),
    ("punctuation_digits", "hello, world! 123", "", False),
    ("underscore", "a_b", "", False),
    ("contraction_dont", "don't", "", False),
    ("contraction_were", "we're", "", False),
    ("add_bos_disabled", "Hello world", "--no-bos", False),
    ("add_bos_default", "Hello world", "", False),
    ("special_token_eot", "<|endoftext|>", "", True),
]

#: The SentencePiece (TinyLlama) cases. Its GGUF carries no
#: ``tokenizer.ggml.add_bos_token`` key at all, so the reference adds a BOS
#: token for this vocabulary type; the ``--no-bos`` case pins the other
#: switch.
#:
#: The last two cases are the ones the repository's SentencePiece path cannot
#: match yet. They are kept in the golden -- the family must not be omitted --
#: and the test module pins them as strict xfails with the reason.
SPM_CASES: list[tuple[str, str, str, bool, bool]] = [
    # (case id, prompt, extra reference flags, parse special, add bos)
    ("spm_absent_add_bos_metadata", "Hello world", "", False, True),
    ("spm_plain_text_no_bos", "Hello world", "--no-bos", False, False),
    ("spm_double_space", "Hello  world", "", False, True),
    ("spm_multibyte_accent", "café", "", False, True),
    ("spm_multibyte_greek", "Ω", "", False, True),
    ("spm_multibyte_emoji", "\U0001f600", "", False, True),
    ("spm_punctuation_digits", "hello, world! 123", "", False, True),
    ("spm_contraction_were", "we're", "", False, True),
    ("spm_contraction_dont", "don't", "", False, True),
    ("spm_control_token_literal", "<s>", "", False, True),
    ("spm_control_token_parsed", "<s>", "", True, True),
]


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_gguf_py(gguf_py: str | None) -> Any:
    if gguf_py:
        sys.path.insert(0, gguf_py)
    try:
        import gguf  # noqa: PLC0415
    except ModuleNotFoundError:
        print(
            "error: llama.cpp's gguf-py package is required.\n"
            "       Pass --gguf-py <llama.cpp>/gguf-py or set PYTHONPATH to it.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return gguf


def llama_bin(llama_cpp: pathlib.Path, name: str) -> pathlib.Path:
    path = llama_cpp / "build" / "bin" / name
    if not path.exists():
        path = llama_cpp / "bin" / name
    if not path.exists():
        print(f"error: {name} not found under {llama_cpp}", file=sys.stderr)
        raise SystemExit(2)
    return path


def run_tokenize(binary: pathlib.Path, model: pathlib.Path, prompt: str, extra: list[str]) -> list[int]:
    """Run llama.cpp's reference tokenizer and return the token IDs."""
    env = dict(os.environ)
    env["LD_LIBRARY_PATH"] = str(binary.parent) + os.pathsep + env.get("LD_LIBRARY_PATH", "")
    completed = subprocess.run(
        [str(binary), "-m", str(model), "-p", prompt, "--ids", *extra],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    for line in completed.stdout.splitlines():
        line = line.strip()
        if line.startswith("["):
            return json.loads(line)
    raise RuntimeError(f"no token IDs in the output of llama-tokenize:\n{completed.stdout}")


def write_json(path: pathlib.Path, payload: Any, compact: bool = False) -> None:
    if compact:
        # The vocabularies are large; pretty-printing them would add hundreds
        # of kilobytes of whitespace to a file that is read as data.
        text = json.dumps(payload, separators=(",", ":")) + "\n"
    else:
        text = json.dumps(payload, indent=2) + "\n"
    path.write_text(text, encoding="utf-8")
    print(f"wrote {path} ({path.stat().st_size} bytes)")


# ---------------------------------------------------------------------------
# tokenizer fixtures
# ---------------------------------------------------------------------------


def build_vocab_gguf(gguf: Any, tokens: list[str], merges: list[str], types: list[int],
                     bos: int, eos: int, out: pathlib.Path) -> None:
    writer = gguf.GGUFWriter(out, "gpt2")
    writer.add_name("vocab-only")
    writer.add_tokenizer_model("gpt2")
    writer.add_tokenizer_pre("gpt-2")
    writer.add_token_list(tokens)
    writer.add_token_merges(merges)
    writer.add_token_types(types)
    writer.add_bos_token_id(bos)
    writer.add_eos_token_id(eos)
    writer.write_header_to_file()
    writer.write_kv_data_to_file()
    writer.close()


def cmd_tokenizer(args: argparse.Namespace) -> int:
    gguf = load_gguf_py(args.gguf_py)
    tokenize_bin = llama_bin(args.llama_cpp, "llama-tokenize")
    out_dir: pathlib.Path = args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    # -- the GPT-2 vocabulary -------------------------------------------------
    vocab = json.loads(args.gpt2_vocab.read_text(encoding="utf-8"))
    merge_lines = [
        line
        for line in args.gpt2_merges.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    ]
    n_tokens = max(vocab.values()) + 1
    tokens = [""] * n_tokens
    for token, index in vocab.items():
        tokens[index] = token
    types = [1] * n_tokens  # gguf.TokenType.NORMAL
    types[vocab["<|endoftext|>"]] = 3  # gguf.TokenType.CONTROL
    eot = vocab["<|endoftext|>"]

    vocab_payload = {
        "schema": SCHEMA_VOCAB,
        "id": "gpt2",
        "model": "gpt2",
        "pre": "gpt-2",
        "bos_token_id": eot,
        "eos_token_id": eot,
        "n_tokens": n_tokens,
        "n_merges": len(merge_lines),
        "token_type_default": 1,
        "token_types": {"50256": 3},
        "tokens": tokens,
        "merges": merge_lines,
    }
    vocab_path = out_dir / "gpt2_vocab.json"
    write_json(vocab_path, vocab_payload, compact=True)

    scratch = out_dir / ".gpt2-vocab.gguf"
    build_vocab_gguf(gguf, tokens, merge_lines, types, eot, eot, scratch)

    cases = []
    for case_id, prompt, extra, parse_special in GPT2_CASES:
        flags = []
        if extra:
            flags.append(extra)
        if not parse_special:
            flags.append("--no-parse-special")
        ids = run_tokenize(tokenize_bin, scratch, prompt, flags)
        cases.append(
            {
                "id": case_id,
                "prompt": prompt,
                "reference_flags": flags,
                "token_ids": ids,
            }
        )
        print(f"  {case_id:<32} {prompt!r:<20} -> {ids}")

    golden_payload = {
        "schema": SCHEMA_GOLDEN,
        "id": "gpt2",
        "reference": {
            "project": "ggml-org/llama.cpp",
            "tool": "llama-tokenize",
            "command": (
                "llama-tokenize -m gpt2-vocab.gguf -p <prompt> --ids "
                "[--no-bos] [--no-parse-special]"
            ),
        },
        "vocab": {
            "id": "gpt2",
            "upstream": "openai-community/gpt2",
            "upstream_revision": args.gpt2_revision,
            "vocab_json_sha256": sha256(args.gpt2_vocab),
            "merges_txt_sha256": sha256(args.gpt2_merges),
            "fixture_sha256": sha256(vocab_path),
            "n_tokens": n_tokens,
        },
        "cases": cases,
    }
    write_json(out_dir / "gpt2_tokenizer_golden.json", golden_payload)
    scratch.unlink()

    # -- the SentencePiece vocabulary ---------------------------------------
    reader = gguf.GGUFReader(str(args.spm_gguf))
    spm_tokens = list(reader.fields["tokenizer.ggml.tokens"].contents())
    spm_types = list(reader.fields["tokenizer.ggml.token_type"].contents())
    spm_scores = [float(s) for s in reader.fields["tokenizer.ggml.scores"].contents()]
    spm_bos = int(reader.fields["tokenizer.ggml.bos_token_id"].contents())
    spm_eos = int(reader.fields["tokenizer.ggml.eos_token_id"].contents())
    spm_special = {
        str(index): int(ttype)
        for index, ttype in enumerate(spm_types)
        if int(ttype) != 1
    }
    spm_payload = {
        "schema": SCHEMA_VOCAB,
        "id": "stories260k",
        "model": "llama",
        "pre": "default",
        "bos_token_id": spm_bos,
        "eos_token_id": spm_eos,
        "n_tokens": len(spm_tokens),
        "n_merges": 0,
        # The unigram scores the reference tokenizer segments with. Without
        # them a unigram Viterbi is degenerate (the greedy segmentations of
        # `don't` and `we're` differ), so they are part of the vocabulary
        # fixture, not of the golden.
        "scores": spm_scores,
        "token_type_default": 1,
        "token_types": spm_special,
        "tokens": spm_tokens,
        "merges": [],
    }
    spm_vocab_path = out_dir / "stories260k_vocab.json"
    write_json(spm_vocab_path, spm_payload, compact=True)

    # The upstream GGUF is used as-is: it already carries the SentencePiece
    # model type and the unigram scores, so the reference tokenizer runs on
    # exactly the bytes that are recorded in the provenance.
    spm_scratch = args.spm_gguf
    spm_cases = []
    for case_id, prompt, extra, parse_special, add_bos in SPM_CASES:
        flags = []
        if extra:
            flags.append(extra)
        if not parse_special:
            flags.append("--no-parse-special")
        ids = run_tokenize(tokenize_bin, spm_scratch, prompt, flags)
        spm_cases.append(
            {
                "id": case_id,
                "prompt": prompt,
                "reference_flags": flags,
                # Whether the reference adds a BOS token for this case. It is
                # recorded per case because the test has to call the
                # repository's encoder with the same switch.
                "add_bos": add_bos,
                "token_ids": ids,
            }
        )
        print(f"  {case_id:<32} {prompt!r:<20} -> {ids}")
    write_json(
        out_dir / "stories260k_tokenizer_golden.json",
        {
            "schema": SCHEMA_GOLDEN,
            "id": "stories260k",
            "reference": {
                "project": "ggml-org/llama.cpp",
                "tool": "llama-tokenize",
                "command": (
                    "llama-tokenize -m stories260K.gguf -p <prompt> --ids "
                    "[--no-bos] [--no-parse-special]"
                ),
                "add_bos": (
                    "the reference adds a BOS token for this vocabulary unless "
                    "--no-bos is passed; each case records the switch it used"
                ),
            },
            "vocab": {
                "id": "stories260k",
                "upstream": "ggml-org/models",
                "upstream_revision": args.spm_revision,
                "source_gguf_sha256": sha256(args.spm_gguf),
                "fixture_sha256": sha256(spm_vocab_path),
                "n_tokens": len(spm_tokens),
                "add_bos_token_metadata": "absent",
            },
            "cases": spm_cases,
        },
    )
    return 0


# ---------------------------------------------------------------------------
# quantized block fixtures
# ---------------------------------------------------------------------------

QUANT_TARGETS = [
    # (quant type, source tensor, number of blocks to keep)
    ("Q4_0", "blk.0.attn_q.weight", 32),
    ("Q4_K", "blk.0.ffn_down.weight", 16),
    ("Q6_K", "blk.0.ffn_down.weight", 16),
]

GGML_TYPES = {"Q4_0": 2, "Q4_K": 12, "Q6_K": 14}  # gguf.GGMLQuantizationType


def cmd_quant(args: argparse.Namespace) -> int:
    gguf = load_gguf_py(args.gguf_py)
    quantize_bin = llama_bin(args.llama_cpp, "llama-quantize")
    out_dir: pathlib.Path = args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    source = gguf.GGUFReader(str(args.model))
    source_tensors = {tensor.name: tensor for tensor in source.tensors}

    entries = []
    for quant_type, tensor_name, n_blocks in QUANT_TARGETS:
        quantized_path = out_dir / f".{quant_type}.gguf"
        env = dict(os.environ)
        env["LD_LIBRARY_PATH"] = (
            str(quantize_bin.parent) + os.pathsep + env.get("LD_LIBRARY_PATH", "")
        )
        command = [
            str(quantize_bin),
            "--allow-requantize",
            "--output-tensor-type",
            "F16",
            str(args.model),
            str(quantized_path),
            quant_type,
        ]
        print(f"  quantizing -> {quant_type}: {' '.join(command)}")
        subprocess.run(command, check=True, capture_output=True, text=True, env=env)

        reader = gguf.GGUFReader(str(quantized_path))
        tensor = next(t for t in reader.tensors if t.name == tensor_name)
        expected_type = GGML_TYPES[quant_type]
        if int(tensor.tensor_type) != expected_type:
            raise RuntimeError(
                f"{tensor_name} was not quantized to {quant_type} "
                f"(type {tensor.tensor_type})"
            )
        data = tensor.data
        block_bytes = {
            "Q4_0": 18,
            "Q4_K": 144,
            "Q6_K": 210,
        }[quant_type]
        nbytes = n_blocks * block_bytes
        # `tensor.data` is a memmap of (rows, bytes_per_row); the flat byte
        # view is the tensor's bytes in file order.
        raw = np.ascontiguousarray(data).reshape(-1)[:nbytes].tobytes()

        binary_path = out_dir / f"{quant_type.lower()}_blocks.bin"
        binary_path.write_bytes(raw)
        print(f"  wrote {binary_path} ({len(raw)} bytes)")

        # The expected values: llama.cpp's own NumPy reference implementation.
        qclass = getattr(gguf, quant_type)
        blocks = np.frombuffer(raw, dtype=np.uint8).reshape(n_blocks, block_bytes)
        expected = qclass.dequantize_blocks(blocks).reshape(-1)

        # Cross-check: re-quantizing the source tensor with llama.cpp's own
        # NumPy quantizer must reproduce llama.cpp's bytes exactly. This is
        # only possible for the types llama.cpp implements in `gguf-py`
        # (Q4_K has no NumPy quantizer there); for the others the result is
        # recorded as unavailable rather than silently skipped.
        source_tensor = source_tensors[tensor_name]
        weights_per_block = {"Q4_0": 32, "Q4_K": 256, "Q6_K": 256}[quant_type]
        source_values = np.asarray(source_tensor.data, dtype=np.float32).reshape(-1)
        source_values = source_values[: n_blocks * weights_per_block].reshape(n_blocks, -1)
        try:
            requantized = qclass.quantize_blocks(source_values)
            byte_identical: Any = bool(np.array_equal(requantized, blocks))
        except NotImplementedError:
            byte_identical = "unavailable (llama.cpp has no NumPy quantizer for this type)"

        entries.append(
            {
                "quant_type": quant_type,
                "fixture": binary_path.name,
                "source_tensor": tensor_name,
                "source_model": args.model.name,
                "source_model_sha256": sha256(args.model),
                "n_blocks": n_blocks,
                "block_size_bytes": block_bytes,
                "weights_per_block": weights_per_block,
                "block_bytes_sha256": sha256_bytes(raw),
                "numpy_requantize_is_byte_identical": byte_identical,
                "expected_fp32": [float(x) for x in expected],
            }
        )
        quantized_path.unlink()

    write_json(
        out_dir / "quant_golden.json",
        {
            "schema": SCHEMA_QUANT,
            "reference": {
                "project": "ggml-org/llama.cpp",
                "blocks": "llama-quantize",
                "expected_values": "gguf-py (llama.cpp's own NumPy quant reference)",
            },
            "command": (
                "llama-quantize --allow-requantize --output-tensor-type F16 "
                "<model.gguf> <out.gguf> <Q4_0|Q4_K|Q6_K>"
            ),
            "entries": entries,
        },
    )
    return 0


# ---------------------------------------------------------------------------
# the tiny GGUF's structural expectations
# ---------------------------------------------------------------------------


def cmd_gguf_expectations(args: argparse.Namespace) -> int:
    gguf = load_gguf_py(args.gguf_py)
    reader = gguf.GGUFReader(str(args.gguf))

    metadata: dict[str, Any] = {}
    for key, field in reader.fields.items():
        if key.startswith("GGUF."):
            continue
        value = field.contents()
        if isinstance(value, (bytes, bytearray)):
            value = value.decode("utf-8", "replace")
        if isinstance(value, list) and len(value) > 16:
            metadata[key] = {
                "type": "array",
                "length": len(value),
                "first": [
                    v.decode("utf-8", "replace") if isinstance(v, (bytes, bytearray)) else v
                    for v in value[:4]
                ],
            }
        elif isinstance(value, list):
            metadata[key] = {
                "type": "array",
                "length": len(value),
                "first": [
                    v.decode("utf-8", "replace") if isinstance(v, (bytes, bytearray)) else v
                    for v in value[:4]
                ],
            }
        else:
            metadata[key] = value

    tensors = []
    for tensor in reader.tensors:
        entry = {
            "name": tensor.name,
            "type": tensor.tensor_type.name,
            "ne": [int(x) for x in tensor.shape],
            "n_bytes": int(tensor.n_bytes),
            "offset": int(tensor.data_offset),
            "n_elements": int(tensor.n_elements),
        }
        if tensor.tensor_type.name in ("F32", "F16"):
            dtype = np.float32 if tensor.tensor_type.name == "F32" else np.float16
            values = np.frombuffer(tensor.data, dtype=dtype)[:8]
            entry["first_values"] = [float(x) for x in values]
        tensors.append(entry)

    write_json(
        args.out,
        {
            "schema": SCHEMA_GGUF,
            "source_gguf": args.gguf.name,
            "source_gguf_sha256": sha256(args.gguf),
            "reference": {
                "project": "ggml-org/llama.cpp",
                "tool": "gguf-py (llama.cpp's own GGUF reader)",
            },
            "metadata": metadata,
            "tensors": tensors,
        },
    )
    return 0


# ---------------------------------------------------------------------------


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    tokenizer = sub.add_parser("tokenizer", help="the tokenizer vector fixtures")
    tokenizer.add_argument("--gguf-py", default=None, help="path to llama.cpp's gguf-py package")
    tokenizer.add_argument("--llama-cpp", required=True, type=pathlib.Path)
    tokenizer.add_argument("--gpt2-vocab", required=True, type=pathlib.Path)
    tokenizer.add_argument("--gpt2-merges", required=True, type=pathlib.Path)
    tokenizer.add_argument("--gpt2-revision", required=True)
    tokenizer.add_argument("--spm-gguf", required=True, type=pathlib.Path)
    tokenizer.add_argument("--spm-revision", required=True)
    tokenizer.add_argument("--out", required=True, type=pathlib.Path)
    tokenizer.set_defaults(func=cmd_tokenizer)

    quant = sub.add_parser("quant", help="the quantized block fixtures")
    quant.add_argument("--gguf-py", default=None, help="path to llama.cpp's gguf-py package")
    quant.add_argument("--llama-cpp", required=True, type=pathlib.Path)
    quant.add_argument("--model", required=True, type=pathlib.Path)
    quant.add_argument("--out", required=True, type=pathlib.Path)
    quant.set_defaults(func=cmd_quant)

    expectations = sub.add_parser(
        "gguf-expectations", help="the tiny GGUF's structural expectations"
    )
    expectations.add_argument("--gguf-py", default=None, help="path to llama.cpp's gguf-py package")
    expectations.add_argument("--gguf", required=True, type=pathlib.Path)
    expectations.add_argument("--out", required=True, type=pathlib.Path)
    expectations.set_defaults(func=cmd_gguf_expectations)

    args = parser.parse_args(argv[1:])
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
