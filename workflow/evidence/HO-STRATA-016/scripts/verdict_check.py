#!/usr/bin/env python3
"""verdict_check.py — HO-STRATA-016 verdict-consistency check (audit A12).

Every artifact the manifest cites as PASS must contain its own verdict line.
Each row names: the AC, the artifact file, and the predicate that must hold
(substring count >= n, or a regex count).  Exits 1 if any row fails.

Run from the repository root:
    python3 workflow/evidence/HO-STRATA-016/scripts/verdict_check.py
"""
import re
import sys
from pathlib import Path

B = Path(__file__).resolve().parent.parent  # bundle dir

# (AC, description, file, predicate)
CHECKS = [
    ("AC-1", "build exit 0 + signed binary + oracle dump intact", "artifacts/ac1-build.txt",
     lambda t: "exit: 0" in t
               and "d58ee2398596d1a100c15d5b9459e24bd86854cb5e5fb7ce88dbc6c7ed9f5858  build-hip/strata" in t
               and "a4c56b9d9189468aeaf1b89637ed4f14f9107b5aaaf75cd4b0e324b6d1c3fc49" in t),
    ("AC-2", "reference set exists, P1 reproduces the signed run1 IDs", "artifacts/token_parity.txt",
     lambda t: "8913 13 185 40619 317 254 6077 280 7239 13 185 40619 317 254 6077 280" in t
               and "Mismatches total: 0" in t),
    ("AC-3", "token parity zero mismatches", "artifacts/token_parity.txt",
     lambda t: t.count("| 0 |") == 3 and "Mismatches total: 0" in t),
    ("AC-4", "KL ceiling PASS on all three prompts", "artifacts/kl_summary.txt",
     lambda t: t.count("DEC-047 ceiling: mean <= 1e-2 and no step > 1e-1 -> PASS") == 3),
    ("AC-5", "two runs per prompt byte-identical", "artifacts/determinism.txt",
     lambda t: t.count("byte-identical") == 3 and t.count("token line identical") == 3),
    ("AC-6", "build-deepseek --families lists deepseek", "artifacts/flip.txt",
     lambda t: "qwen4exp qwen35moe deepseek\n" in t),
    ("AC-6", "native run without --parity-run emits AC-3 tokens", "artifacts/flip.txt",
     lambda t: "(no --parity-run)" in t and t.count("gen: 8913 13 185 40619 317 254 6077 280 7239 13 185 40619 317 254 6077 280") == 1),
    ("AC-6", "build-hip --families does NOT list deepseek", "artifacts/flip.txt",
     lambda t: "qwen4exp qwen35moe\ndeepseek" not in t and "\nqwen4exp qwen35moe\n" in t),
    ("AC-6", "build-hip --native refuses (exit 2, named)", "artifacts/flip.txt",
     lambda t: "no shard of the model holds per_layer_token_embd.weight" in t
               and t.count("exit: 2") == 1),
    ("AC-7", "no-dump run exits 0 and writes no dump file", "artifacts/ac7-nodump.txt",
     lambda t: "nodump exit: 0" in t and "no unexpected files written by the no-dump run" in t
               and "stray .bin check: none (exit 2 = no match)" in t),
    ("AC-8", "Qwen regression: 32 IDs bit-identical to HO-007", "artifacts/qwen_regression.txt",
     lambda t: "gen: 11751 11 264 3177 34756 364 1141 25438 57902 1680 430 279 242476 300 21262 11 279 9440 46890 15849 11 321 279 42027 9141 368 54832 13 11751 369 1048 10919" in t
               and "32 IDs bit-identical to HO-007" in t),
    ("AC-8", "model_family_test ALL PASSED, exit 0", "artifacts/model_family_test.txt",
     lambda t: "ALL PASSED" in t and "mft exit: 0" in t),
    ("AC-8", "gguf_geometry_test all passed, exit 0", "artifacts/gguf_geometry_test.txt",
     lambda t: "gguf_geometry_test: all passed" in t and "ggt exit: 0" in t),
    ("AC-9", "geometry assertions: 11 fields, none FAIL", "artifacts/flip.txt",
     lambda t: t.count("(want ") >= 11 and "FAIL" not in t),
    ("AC-12", "block-0 input assertion vs token_embd present and ok", "artifacts/flip.txt",
     lambda t: "block-0 input assertion: 21 positions, residual vs direct token_embd row dequant (type 12): max abs diff 0.000000e+00 ok" in t),
    ("AC-12", "block-0 assertion in every engine run", "artifacts/runs/engine_p1_tokens.txt",
     lambda t: "block-0 input assertion: 21 positions" in t),
    ("AC-12", "block-0 assertion P2", "artifacts/runs/engine_p2_tokens.txt",
     lambda t: "block-0 input assertion: 26 positions" in t),
    ("AC-12", "block-0 assertion P3", "artifacts/runs/engine_p3_tokens.txt",
     lambda t: "block-0 input assertion: 20 positions" in t),
    ("AC-10", "patch applies on baf16363 + 0001 + 0002 + 0003", "patches/apply-check.txt",
     lambda t: "0001 apply exit: 0" in t and "0002 apply exit: 0" in t
               and "0003 apply exit: 0" in t and "0004 apply --check exit: 0" in t),
    ("AC-10", "cumulative stat recorded", "artifacts/patch-stat.txt",
     lambda t: "15 files changed, 1782 insertions" in t),
    ("AC-2", "oracle context: margins table covers 3x16 steps", "artifacts/margins.txt",
     lambda t: len(re.findall(r"^\| \d+ \|", t, re.M)) >= 96 and "min margin" in t),
]


def main() -> int:
    fails = 0
    for ac, desc, rel, pred in CHECKS:
        path = B / rel
        if not path.exists():
            print(f"FAIL  {ac}  {desc}  ({rel} missing)")
            fails += 1
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        ok = False
        try:
            ok = bool(pred(text))
        except Exception as exc:  # a broken predicate is a FAIL, not a crash
            print(f"FAIL  {ac}  {desc}  (predicate error: {exc})")
            fails += 1
            continue
        if ok:
            print(f"PASS  {ac}  {desc}  ({rel})")
        else:
            print(f"FAIL  {ac}  {desc}  ({rel} does not contain its verdict)")
            fails += 1
    print(f"\nchecks: {len(CHECKS)}, failures: {fails}")
    print("RESULT: " + ("PASS" if fails == 0 else "FAIL"))
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
