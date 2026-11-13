#!/usr/bin/env python3
"""Independent QAQC probes for Phase 7B (tokenizer correctness, Gate G2).

Standalone driver, independent of the pytest suite: it imports the tokenizer
directly and checks the behaviours the 7B brief lists as adversarial checks.

Every check prints a PASS/FAIL line and the script exits non-zero on the first
class of failure. Run from the repository root:

    python3 audit/evidence/G2/7B/qaqc-probes/probe_tokenizer.py
"""

from __future__ import annotations

import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), *[os.pardir] * 5))
sys.path.insert(0, os.path.join(_ROOT, "src"))
sys.path.insert(0, os.path.join(_ROOT, "tests"))

from tokenizer import GGUFTokenizer  # noqa: E402

import json  # noqa: E402

_FIXTURES = os.path.join(_ROOT, "tests", "fixtures")

failures = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global failures
    status = "PASS" if ok else "FAIL"
    line = f"[{status}] {name}"
    if detail:
        line += f" -- {detail}"
    print(line)
    if not ok:
        failures += 1


def build(vocab_file: str) -> GGUFTokenizer:
    vocab = json.load(open(os.path.join(_FIXTURES, vocab_file), encoding="utf-8"))
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


def all_goldens(tok: GGUFTokenizer, golden_file: str, spm: bool) -> int:
    golden = json.load(open(os.path.join(_FIXTURES, golden_file), encoding="utf-8"))
    bad = 0
    for case in golden["cases"]:
        parse_special = "--no-parse-special" not in case.get("reference_flags", [])
        add_bos = case["add_bos"] if spm else False
        got = tok.encode(case["prompt"], add_bos=add_bos, parse_special=parse_special)
        if got != case["token_ids"]:
            bad += 1
            print(f"    mismatch {case['id']}: got {got} want {case['token_ids']}")
    return bad


gpt2 = build("gpt2_vocab.json")
spm = build("stories260k_vocab.json")

eot = gpt2.id_to_token[50256]

# --- 7B-1: special tokens ---------------------------------------------------
check("gpt2 special token encodes as its id",
      gpt2.encode(eot, add_bos=False, parse_special=True) == [50256])
plain_hi = gpt2.encode("hi", add_bos=False)
plain_there = gpt2.encode("there", add_bos=False)
check("mixed text splits around the special token",
      gpt2.encode(f"hi{eot}there", add_bos=False, parse_special=True)
      == plain_hi + [50256] + plain_there)
check("no splitting inside ordinary text",
      gpt2.encode("<|notaspecialtoken|>", add_bos=False, parse_special=True)
      == gpt2.encode("<|notaspecialtoken|>", add_bos=False, parse_special=False))
check("spm control token parses as its id",
      spm.encode("<s>", add_bos=True, parse_special=True) == [1, 1])
check("spm control token literal path unchanged",
      spm.encode("<s>", add_bos=True, parse_special=False)
      == [1, 410, 504, 419, 505])
check("spm control token adjacent to punctuation round-trips",
      spm.decode(spm.encode("a<s>b", add_bos=False, parse_special=True),
                 skip_special_tokens=False) == "a<s>b")

# longest match: synthetic overlapping specials
overlap = GGUFTokenizer(
    tokens=["<pad>", "<pad_word>", "a"],
    bos_token_id=-1, eos_token_id=-1,
    token_types=[4, 4, 1], tokenizer_model="llama",
)
check("overlapping specials: longest match wins",
      overlap.encode("a<pad_word>a", parse_special=True) == [2, 1, 2]
      and overlap.encode("<pad>", parse_special=True) == [0])

# decode round-trips with special tokens
ids_mixed = gpt2.encode(f"hi{eot}there", add_bos=False, parse_special=True)
check("decode skips special tokens", gpt2.decode(ids_mixed, skip_special_tokens=True) == "hithere")
check("decode keeps special tokens", gpt2.decode(ids_mixed, skip_special_tokens=False) == f"hi{eot}there")

# --- 7B-2: add_bos precedence ---------------------------------------------------
md = lambda add: {
    "tokenizer.ggml.tokens": ["<unk>", "<s>", "</s>", "<0x00>", "<0xFF>", "\u2581", "\u2581b", "b"],
    "tokenizer.ggml.token_type": [2, 3, 3, 6, 6, 1, 1, 1],
    "tokenizer.ggml.model": "llama",
    "tokenizer.ggml.bos_token_id": 1,
    "tokenizer.ggml.eos_token_id": 2,
    **({} if add == "absent" else {"tokenizer.ggml.add_bos_token": add}),
}
tok_absent = GGUFTokenizer.from_gguf_metadata(md("absent"))
tok_true = GGUFTokenizer.from_gguf_metadata(md(True))
tok_false = GGUFTokenizer.from_gguf_metadata(md(False))
check("metadata absent -> spm family default (BOS)", tok_absent.encode("b") == [1, 6])
check("metadata true", tok_true.encode("b") == [1, 6])
check("metadata false", tok_false.encode("b") == [6])
check("explicit add_bos=False overrides metadata true", tok_true.encode("b", add_bos=False) == [6])
check("explicit add_bos=True overrides metadata false", tok_false.encode("b", add_bos=True) == [1, 6])
check("gpt2 family default: no BOS", gpt2.encode("Hello world") == [15496, 995])
check("no duplicate BOS on a leading special", tok_true.encode("<s>b", parse_special=True) == [1, 1, 7])
check("empty string respects the BOS decision",
      gpt2.encode("") == [] and spm.encode("") == [1] and spm.encode("", add_bos=False) == [])

# --- 7B-4: unmappable bytes -------------------------------------------------
def raises_value_error(tok: GGUFTokenizer, text: str) -> tuple:
    try:
        tok.encode(text, add_bos=False)
    except ValueError as exc:
        return True, str(exc)
    return False, "no raise"


mini_gpt2 = GGUFTokenizer(tokens=["a", "b"], tokenizer_model="gpt2",
                          bos_token_id=-1, eos_token_id=-1)
ok, msg = raises_value_error(mini_gpt2, "é")
check("gpt2 minimal vocab: missing byte raises", ok and "0xC3" in msg, msg)
ok, msg = raises_value_error(spm, "a\ud800b")
check("lone surrogate raises ValueError, not UnicodeEncodeError", ok and "UTF-8" in msg, msg)

# GPT-2 and SPM goldens: every case, family-independent
bad_gpt2 = all_goldens(gpt2, "gpt2_tokenizer_golden.json", spm=False)
check("all 7A-3 GPT-2 golden cases match", bad_gpt2 == 0, f"{bad_gpt2} mismatches")
bad_spm = all_goldens(spm, "stories260k_tokenizer_golden.json", spm=True)
check("all 7A-3 SPM golden cases match", bad_spm == 0, f"{bad_spm} mismatches")

# double-space / multibyte invariants from the brief's QAQC list
check("spm multibyte emoji byte-fallback golden",
      spm.encode("\U0001f600", add_bos=True) == [1, 410, 243, 162, 155, 131])
check("gpt2 double space golden", gpt2.encode("Hello  world", add_bos=False) == [15496, 220, 995])

print(f"\n{'ALL PROBES PASS' if failures == 0 else f'{failures} PROBE FAILURE(S)'}")
sys.exit(1 if failures else 0)
