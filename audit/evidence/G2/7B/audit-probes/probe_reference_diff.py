#!/usr/bin/env python3
"""Auditor differential probe for 7B: candidate vs pinned llama.cpp.

Usage:
    python3 probe_reference_diff.py [path-to-llama-tokenize]

The reference binary is built from
llama.cpp@149f5641b931aaf33697d70f9abc90c3e5300247, the commit that produced
the 7A-3 goldens. If no path is given, $LLAMA_TOKENIZE is used, then the
auditor's local build path. The GGUF is $STORIES260K_GGUF or the auditor's
local copy. The script exits 1 if any case differs.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPO / "src"))

from tokenizer import GGUFTokenizer  # noqa: E402

FIXTURES = REPO / "tests" / "fixtures"
REF = (
    sys.argv[1]
    if len(sys.argv) > 1
    else os.environ.get(
        "LLAMA_TOKENIZE",
        "/tmp/opencode/llama.cpp-149f5641/build/bin/llama-tokenize",
    )
)
GGUF = pathlib.Path(
    os.environ.get("STORIES260K_GGUF", "/tmp/stories260K.gguf")
)


def build_tokenizer() -> GGUFTokenizer:
    v = json.loads((FIXTURES / "stories260k_vocab.json").read_text())
    token_types = [int(v["token_type_default"])] * len(v["tokens"])
    for idx, ttype in v["token_types"].items():
        token_types[int(idx)] = int(ttype)
    return GGUFTokenizer(
        tokens=v["tokens"],
        scores=v.get("scores"),
        bos_token_id=v["bos_token_id"],
        eos_token_id=v["eos_token_id"],
        merges=v["merges"],
        token_types=token_types,
        tokenizer_model=v["model"],
    )


def reference(prompt: str, parse_special: bool) -> list[int]:
    args = [REF, "-m", str(GGUF), "-p", prompt, "--ids", "--no-bos"]
    if not parse_special:
        args.append("--no-parse-special")
    out = subprocess.run(args, capture_output=True, text=True, check=True).stdout
    line = [ln for ln in out.strip().splitlines() if ln.strip().startswith("[")][-1]
    return json.loads(line)


def main() -> int:
    if not pathlib.Path(REF).exists():
        print(f"reference binary not found: {REF}", file=sys.stderr)
        return 2
    if not GGUF.exists():
        print(f"GGUF not found: {GGUF}", file=sys.stderr)
        return 2

    tok = build_tokenizer()
    cases = [
        # (prompt, parse_special)
        ("a<s>b", True),
        ("hi<s>there", True),
        (" <s>", True),
        ("<s>b", True),
        ("hello<s>there", True),
        ("<s></s>", True),
        ("the", False),
        ("and", False),
        ("time", False),
        ("the quick brown fox jumps over the lazy dog", False),
        ("Once upon a time there was a little girl named Lily", False),
    ]

    failures = 0
    for prompt, parse_special in cases:
        ref = reference(prompt, parse_special)
        cand = tok.encode(prompt, add_bos=False, parse_special=parse_special)
        ok = ref == cand
        failures += 0 if ok else 1
        print(f"[{'OK' if ok else 'DIFF'}] {prompt!r} parse_special={parse_special}")
        if not ok:
            print(f"      reference: {ref}")
            print(f"      candidate: {cand}")

    print()
    if failures:
        print(f"RESULT: {failures}/{len(cases)} case(s) differ")
        return 1
    print(f"RESULT: all {len(cases)} cases match")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
