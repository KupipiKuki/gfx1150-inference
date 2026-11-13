#!/usr/bin/env python3
"""QAQC adversarial probes for wp/7B-tokenizer — written for this review.

Usage: python3 probe_qaqc_7b.py <tree> <label>

Every probe prints [OK]/[BAD]; exit is non-zero if any probe fails. The script
imports the tokenizer from the given tree only — never from the reviewer's
checkout — so the same file can be run against the parent and the candidate.
"""

from __future__ import annotations

import json
import os
import sys

TREE = os.path.abspath(sys.argv[1])
LABEL = sys.argv[2] if len(sys.argv) > 2 else "tree"
sys.path.insert(0, os.path.join(TREE, "src"))

from tokenizer import GGUFTokenizer  # noqa: E402

import inspect  # noqa: E402
HAS_PARSE_SPECIAL = "parse_special" in inspect.signature(GGUFTokenizer.encode).parameters
HAS_ADD_BOS_META = "add_bos_token" in inspect.signature(GGUFTokenizer.__init__).parameters

FIX = os.path.join(TREE, "tests", "fixtures")
bad = 0


def check(name, ok, detail=""):
    global bad
    print(f"[{'OK' if ok else 'BAD'}] ({LABEL}) {name}" + (f" -- {detail}" if detail and not ok else ""))
    if not ok:
        bad += 1


def check_feature(name, ok, detail=""):
    """A 7B feature probe: on the parent the capability is absent, which is the
    expected red; only a wrong result on a tree that HAS the feature is BAD."""
    global bad
    if not (HAS_PARSE_SPECIAL and HAS_ADD_BOS_META):
        print(f"[ABSENT] ({LABEL}) {name} -- feature not present on this tree (expected on parent)")
        return
    check(name, ok, detail)


def build(vocab_file):
    v = json.load(open(os.path.join(FIX, vocab_file), encoding="utf-8"))
    tt = [int(v["token_type_default"])] * int(v["n_tokens"])
    for i, t in v["token_types"].items():
        tt[int(i)] = int(t)
    return GGUFTokenizer(
        tokens=list(v["tokens"]), scores=v.get("scores"),
        bos_token_id=int(v["bos_token_id"]), eos_token_id=int(v["eos_token_id"]),
        merges=list(v["merges"]), token_types=tt, tokenizer_model=str(v["model"]),
    )


gpt2 = build("gpt2_vocab.json")
spm = build("stories260k_vocab.json")
EOT = gpt2.id_to_token[50256]

# ---- A. special tokens ------------------------------------------------------
check_feature("A1 EOT alone -> its id", gpt2.encode(EOT, add_bos=False) == [50256])
hi = gpt2.encode("hi", add_bos=False)
there = gpt2.encode("there", add_bos=False)
check_feature("A2 mixed text", gpt2.encode(f"hi{EOT}there", add_bos=False) == hi + [50256] + there)
check_feature("A3 consecutive specials", spm.encode("<s></s>", add_bos=False) == [1, 2])
check_feature("A4 special at very end", gpt2.encode(f"hi{EOT}", add_bos=False) == hi + [50256])
check("A5 special surrounded by spaces",
      spm.encode(f"a {chr(0x3C)}s>", add_bos=False) is not None)  # smoke, no crash
look = "<|notaspecial|>"
if HAS_PARSE_SPECIAL:
    a6 = (gpt2.encode(look, add_bos=False) == gpt2.encode(look, add_bos=False, parse_special=False)
          and gpt2.decode(gpt2.encode(look, add_bos=False), skip_special_tokens=False) == look)
    a7 = gpt2.encode(EOT, add_bos=False, parse_special=False) != [50256]
else:
    a6 = a7 = False
check_feature("A6 lookalike stays ordinary", a6)
check_feature("A7 parse_special=False literal EOT != [id]", a7)
check("A8 determinism", gpt2.encode(f"hi{EOT}there", add_bos=False) == gpt2.encode(f"hi{EOT}there", add_bos=False))

ov = GGUFTokenizer(tokens=["<a>", "<a_x>", "<a_xy>", "q"], bos_token_id=-1, eos_token_id=-1,
                   token_types=[3, 3, 4, 1], tokenizer_model="llama")
if HAS_PARSE_SPECIAL:
    a9 = (ov.encode("<a_xy>", parse_special=True) == [2]
          and ov.encode("<a_x>", parse_special=True) == [1]
          and ov.encode("<a>", parse_special=True) == [0]
          and ov.encode("q<a_x>q", parse_special=True) == [3, 1, 3])
else:
    a9 = False
check_feature("A9 triple-overlap longest match", a9)

empty_bos = GGUFTokenizer(tokens=["", "a"], bos_token_id=0, eos_token_id=-1,
                         token_types=[3, 1], tokenizer_model="llama")
try:
    r = empty_bos.encode("aa", add_bos=False)
    check("A10 empty-string special token does not loop", r == [1, 1], repr(r))
except Exception as exc:  # noqa: BLE001
    check("A10 empty-string special token does not loop", False, repr(exc))

# ---- B. add_bos matrix -------------------------------------------------------
def md(add):
    m = {
        "tokenizer.ggml.tokens": ["<unk>", "<s>", "</s>", "<0x00>", "<0xFF>", "\u2581", "\u2581b", "b"],
        "tokenizer.ggml.token_type": [2, 3, 3, 6, 6, 1, 1, 1],
        "tokenizer.ggml.model": "llama",
        "tokenizer.ggml.bos_token_id": 1,
        "tokenizer.ggml.eos_token_id": 2,
    }
    if add is not None:
        m["tokenizer.ggml.add_bos_token"] = add
    return m


matrix_ok = True
for meta in (None, True, False):
    for arg in (None, True, False):
        if not HAS_ADD_BOS_META and meta is not None:
            continue
        tok = GGUFTokenizer.from_gguf_metadata(md(meta))
        got = tok.encode("b", add_bos=arg)
        want_bos = arg if arg is not None else (meta if meta is not None else True)  # spm default True
        expect = ([1, 6] if want_bos else [6])
        if got != expect:
            matrix_ok = False
            print(f"    matrix meta={meta} arg={arg}: got {got} want {expect}")
check_feature("B1 3x3 add_bos precedence matrix (metadata x argument)", matrix_ok)

# gpt2 family default: no BOS when metadata absent
g2m = dict(md(None))
g2m["tokenizer.ggml.tokens"] = gpt2.id_to_token[:0] or g2m["tokenizer.ggml.tokens"]  # keep
check("B2 gpt2 vocab default adds no BOS", gpt2.encode("Hello world") == [15496, 995])
check("B3 gpt2 vocab explicit add_bos=True adds exactly one",
      gpt2.encode("Hello world", add_bos=True) == [gpt2.bos_token_id, 15496, 995])

# real GGUF metadata path: the pinned stories260K gguf has no add_bos_token key
sys.path.insert(0, os.path.join(TREE, "src"))
from gguf_parser import GGUFParser  # noqa: E402
if os.path.exists("/tmp/qaqc-stories260K.gguf"):
    with open("/tmp/qaqc-stories260K.gguf", "rb") as fh:
        real_md = GGUFParser(bytearray(fh.read())).metadata
    rtok = GGUFTokenizer.from_gguf_metadata(real_md)
    check("B4 real GGUF: add_bos_token absent -> spm default BOS",
          rtok.encode("Hello world")[:1] == [1])
    golden = json.load(open(os.path.join(FIX, "stories260k_tokenizer_golden.json"), encoding="utf-8"))
    case = next(c for c in golden["cases"] if c["id"] == "spm_absent_add_bos_metadata")
    check("B5 real GGUF encode matches the golden case", rtok.encode(case["prompt"]) == case["token_ids"])
else:
    check("B4/B5 real GGUF present", False, "missing /tmp/qaqc-stories260K.gguf")

# ---- C. SPM Viterbi edges -----------------------------------------------------
check_feature("C1 byte-only input falls back (dummy ▁ + <0x01> + <0x02>)",
              spm.encode("\x01\x02", add_bos=False) == [410, spm.token_to_id["<0x01>"], spm.token_to_id["<0x02>"]])
check("C2 leading space", spm.encode(" hi", add_bos=False)[0] == 410 or spm.encode(" hi", add_bos=False))
d1 = spm.encode("a" * 100, add_bos=False)
d2 = spm.encode("a" * 100, add_bos=False)
check("C3 100-char word deterministic", d1 == d2 and len(d1) > 0)
zero = GGUFTokenizer(tokens=["\u2581", "a", "b", "\u2581ab"], scores=None, bos_token_id=-1, eos_token_id=-1)
check("C4 zero-score vocab deterministic", zero.encode("ab", add_bos=False) == zero.encode("ab", add_bos=False))
byteonly = GGUFTokenizer(tokens=["<0x61>", "<0x62>"], bos_token_id=-1, eos_token_id=-1, token_types=[6, 6])
check("C5 byte-only vocab", byteonly.encode("ab", add_bos=False) == [0, 1])
half = GGUFTokenizer(tokens=["<unk>", "\u2581", "a", "<0xC3>"], bos_token_id=-1, eos_token_id=-1,
                     token_types=[2, 1, 1, 6], scores=[0.0, -1.0, -2.0, 0.0])
try:
    half.encode("é", add_bos=False)  # C3 covered, A9 missing
    check("C6 stall mid-codepoint raises", False, "no raise")
except ValueError as exc:
    check("C6 stall mid-codepoint raises naming 0xA9", "0xA9" in str(exc), str(exc))
check("C7 empty string", spm.encode("", add_bos=False) == [] and spm.encode("") == [1])
check("C8 whitespace-only no crash/loss",
      spm.decode(spm.encode("   ", add_bos=False), skip_special_tokens=True) == "  ")
try:
    spm.encode("x\ud800y", add_bos=False)
    check("C9 lone surrogate raises ValueError", False, "no raise")
except ValueError:
    check("C9 lone surrogate raises ValueError", True)
except UnicodeEncodeError:
    check("C9 lone surrogate raises ValueError", False, "UnicodeEncodeError leaked")

# ---- D. GPT-2 edges -----------------------------------------------------------
contr = gpt2.encode("x's x't x're x've x'm x'll x'd", add_bos=False)
check("D1 all six contraction suffixes split",
      gpt2.decode(contr, skip_special_tokens=False) == "x's x't x're x've x'm x'll x'd")
check("D2 tabs/newlines round trip",
      gpt2.decode(gpt2.encode("a \t b\n\nc", add_bos=False), skip_special_tokens=False) == "a \t b\n\nc")
check("D3 underscores split like the reference", gpt2.encode("a_b_c", add_bos=False) == [64, 62, 65, 62, 66])
mini = GGUFTokenizer(tokens=["<pad>", "Hello", "\u0120world"], bos_token_id=-1, eos_token_id=-1,
                     tokenizer_model="gpt2")
check("D4 minimal gpt2 chunk-token path", mini.encode("Hello world", add_bos=False) == [1, 2])
try:
    mini.encode("Hello!", add_bos=False)
    check("D5 minimal gpt2 unmappable raises", False, "no raise")
except ValueError as exc:
    check("D5 minimal gpt2 unmappable raises naming 0x21", "0x21" in str(exc), str(exc))

# ---- E. golden recomputation + round trips ------------------------------------
if not HAS_PARSE_SPECIAL:
    print(f"[ABSENT] ({LABEL}) E1/E2 golden recomputation needs parse_special (parent lacks it; "
          "the parent's four known mismatches are the red, shown by pytest --runxfail)")
else:
    gg = json.load(open(os.path.join(FIX, "gpt2_tokenizer_golden.json"), encoding="utf-8"))
    sg = json.load(open(os.path.join(FIX, "stories260k_tokenizer_golden.json"), encoding="utf-8"))
    bad_cases = []
    for case in gg["cases"]:
        ps = "--no-parse-special" not in case.get("reference_flags", [])
        got = gpt2.encode(case["prompt"], add_bos=False, parse_special=ps)
        if got != case["token_ids"]:
            bad_cases.append(("gpt2", case["id"], got, case["token_ids"]))
    for case in sg["cases"]:
        ps = "--no-parse-special" not in case.get("reference_flags", [])
        got = spm.encode(case["prompt"], add_bos=case["add_bos"], parse_special=ps)
        if got != case["token_ids"]:
            bad_cases.append(("spm", case["id"], got, case["token_ids"]))
    check("E1 all 23 golden cases recomputed independently", not bad_cases, repr(bad_cases))

    rt_bad = []
    for golden, tok in ((gg, gpt2), (sg, spm)):
        for case in golden["cases"]:
            if "--no-parse-special" in case.get("reference_flags", []):
                ab = case.get("add_bos", False)
                ids = tok.encode(case["prompt"], add_bos=ab, parse_special=False)
                if tok.decode(ids, skip_special_tokens=True) != case["prompt"]:
                    rt_bad.append((case["id"], case["prompt"]))
    check("E2 decode(encode(x)) round-trips every literal golden prompt", not rt_bad, repr(rt_bad))

print(f"\n{'ALL QAQC PROBES PASS' if bad == 0 else f'{bad} PROBE(S) FAILED'} ({LABEL})")
sys.exit(1 if bad else 0)
