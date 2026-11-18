#!/usr/bin/env python3
"""Compare engine tokenizer (strata_tokenizer.py) with llama.cpp harness output."""
import argparse
import sys
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path('/home/kupipi/Documents/git/strata/tools')))
from strata_tokenizer import Tokenizer

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

    tok = Tokenizer.from_gguf(args.gguf)
    print("| prompt | text | engine ids | harness ids | match | notes |")
    print("|---|---|---|---|---|---|")
    for label, text in PROMPTS:
        engine_ids = tok.encode(text)
        engine_decoded = tok.decode(engine_ids)
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
        for line in out.stdout.splitlines():
            if line.startswith("decode:"):
                harness_decoded = line[7:].strip()
        notes = []
        if engine_ids and harness_ids and engine_ids[0] != harness_ids[0] and harness_ids[0] == 100000:
            notes.append("harness adds BOS 100000")
        match = engine_ids == harness_ids
        print(f"| {label} | {text!r} | {engine_ids} | {harness_ids} | {match} | {', '.join(notes)} |")
        if engine_decoded != text:
            print(f"  engine decode mismatch: {engine_decoded!r}", file=sys.stderr)
        if harness_decoded != text:
            print(f"  harness decode mismatch: {harness_decoded!r}", file=sys.stderr)

if __name__ == "__main__":
    main()
