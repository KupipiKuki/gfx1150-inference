#!/usr/bin/env python3
"""OLMoE tokenizer parity table. Mirrors tokenize_compare.py but records an
engine tokenizer failure (UnknownPreTokenizer 'olmo') as a finding instead of
stopping."""
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path('/home/kupipi/Documents/git/strata/tools')))
from strata_tokenizer import Tokenizer, UnknownPreTokenizer

PROMPTS = [
    ("P1", "The capital of France is"),
    ("P2", "def add(a, b):\n    return"),
    ("P3", "Three primary colors are"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gguf", required=True)
    ap.add_argument("--harness", required=True)
    args = ap.parse_args()

    try:
        tok = Tokenizer.from_gguf(args.gguf)
        engine_ok = True
    except UnknownPreTokenizer as e:
        tok = None
        engine_ok = False
        engine_init_error = str(e)

    print("| prompt | text | engine ids | harness ids | match | notes |")
    print("|---|---|---|---|---|---|")
    for label, text in PROMPTS:
        if engine_ok:
            try:
                engine_ids = tok.encode(text)
                engine_decoded = tok.decode(engine_ids)
            except Exception as e:
                engine_ids = [f"error: {e}"]
                engine_decoded = ""
        else:
            engine_ids = [f"N/A — {engine_init_error}"]
            engine_decoded = ""

        out = subprocess.run(
            [args.harness, "--model", args.gguf, "--prompt", text],
            capture_output=True, text=True,
            env={"LD_LIBRARY_PATH": "/tmp/opencode/llama.cpp/build/bin"},
        )
        harness_ids = []
        for line in out.stdout.splitlines():
            if line.startswith("ids:"):
                harness_ids = [int(x) for x in line[4:].split()]
        harness_decoded = ""
        marker = "decode: "
        idx = out.stdout.find(marker)
        if idx != -1:
            harness_decoded = out.stdout[idx + len(marker):].rstrip("\n")

        notes = []
        if not engine_ok:
            notes.append("engine tokenizer refuses 'olmo' pre-tokenizer")
        if harness_ids and 50279 in harness_ids:
            notes.append("harness emits BOS 50279")
        match = (engine_ids == harness_ids) if engine_ok else False
        print(f"| {label} | {text!r} | {engine_ids} | {harness_ids} | {match} | {', '.join(notes)} |")
        if engine_ok and engine_decoded != text:
            print(f"  engine decode mismatch: {engine_decoded!r}", file=sys.stderr)
        if harness_decoded != text:
            print(f"  harness decode mismatch: {harness_decoded!r}", file=sys.stderr)

    print()
    print("**BOS convention:** tokenizer.ggml.add_bos_token=False, BOS id 50279. "
          "Harness uses llama_tokenize with add_special=false, so no BOS is prepended. "
          "The engine tokenizer at this pin does not load the 'olmo' pre-tokenizer, "
          "so no engine-side id list is available for comparison.")


if __name__ == "__main__":
    main()
