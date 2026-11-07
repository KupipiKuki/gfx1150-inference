#!/usr/bin/env python3
"""QAQC source scan: no NULL-stream reliance and no stream-less kernel
launches in the layer path (7E). Exit 0 clean; exit 1 findings.

Checks:
1. No `hipStreamWaitEvent(0` anywhere in src/kernels/** (NULL-stream waits).
2. Every `hipLaunchKernelGGL` in every `launch_*_device` body (the layer-path
   helpers) passes an explicit stream token (not the literal `0`) as the 5th
   macro argument.
3. The device-resident KV-attention helper uses hipMemcpyAsync on its stream
   for the D2D KV writes (not blocking hipMemcpy).
"""
import re
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
KDIR = ROOT / "src" / "kernels"
fail: list[str] = []

for hip in sorted(KDIR.glob("*.hip")):
    src = hip.read_text()
    for m in re.finditer(r"hipStreamWaitEvent\(\s*0\s*,", src):
        fail.append(f"{hip.name}: hipStreamWaitEvent(0, ...) at char {m.start()}")

def balanced_end(s, start):  # start = index of '('
    depth = 0
    i = start
    while i < len(s):
        if s[i] == "(":
            depth += 1
        elif s[i] == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return len(s)

def macro_args(src, open_idx):
    """Split the balanced arg list of hipLaunchKernelGGL at top-level commas."""
    end = balanced_end(src, open_idx)
    body = src[open_idx + 1 : end]
    args, depth, cur = [], 0, []
    for ch in body:
        if ch in "(<[":
            depth += 1
        elif ch in ")>]":
            depth -= 1
        if ch == "," and depth == 0:
            args.append("".join(cur).strip()); cur = []
        else:
            cur.append(ch)
    args.append("".join(cur).strip())
    return args

device_sig = re.compile(r"void\s+(launch_\w+_device|launch_forward_layer_cached_fp16)\s*\(")
for hip in sorted(KDIR.glob("*.hip")):
    src = hip.read_text()
    for sig in device_sig.finditer(src):
        # body of this function (until the matching close brace at depth 0)
        bstart = src.index("{", sig.end())
        i, depth = bstart, 0
        while i < len(src):
            if src[i] == "{":
                depth += 1
            elif src[i] == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        body = src[bstart:i]
        fname = sig.group(1)
        for m in re.finditer(r"hipLaunchKernelGGL\s*\(", body):
            args = macro_args(body, m.end() - 1)
            if len(args) < 5:
                fail.append(f"{hip.name}:{fname}: hipLaunchKernelGGL has {len(args)} args (<5)")
                continue
            stream_tok = args[4].strip()
            if stream_tok == "0":
                fail.append(
                    f"{hip.name}:{fname}: stream-less hipLaunchKernelGGL "
                    f"(5th arg is literal 0) at body offset {m.start()}"
                )
        # blocking hipMemcpy in the device-resident attention helper (D2D KV)
        if fname.startswith("launch_gqa_attention_cached_fp16_device"):
            if re.search(r"hipMemcpy\(", body):
                fail.append(f"{hip.name}:{fname}: blocking hipMemcpy in D2D KV path")

print("=== stream source scan (layer path) ===")
if fail:
    for finding in fail:
        print("  FAIL:", finding)
    print(f"RESULT: FAIL - {len(fail)} finding(s)")
    sys.exit(1)
print("  OK: no hipStreamWaitEvent(0, ...)")
print("  OK: all launch_*_device kernel launches use an explicit stream token")
print("  OK: D2D KV writes use hipMemcpyAsync on the given stream")
print("RESULT: PASS")
sys.exit(0)
