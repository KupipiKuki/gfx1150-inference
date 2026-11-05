#!/usr/bin/env python3
"""QAQC adversarial probes for 7A-9 (BLOCKER-7A4-1) — independent of the coder's tests.

Usage: python3 probe_nested_array.py <tree-with-src> <parent|candidate>

Every probe builds its own buffer and parses it with the gguf_parser found
under <tree-with-src>. The expected behaviour differs by mode:

  parent    — the pre-fix parser: shallow nested arrays are ACCEPTED, deep
              ones raise RecursionError, valid arrays parse.
  candidate — the fixed parser: every nested array raises ValueError with
              the "must not be an array" message, valid arrays still parse,
              and all pre-existing rejection classes are unchanged.

Exit code 0 means every probe matched its mode's expectation.
"""

import hashlib
import struct
import sys

sys.path.insert(0, sys.argv[1].rstrip("/") + "/src")

import gguf_parser  # noqa: E402
from gguf_parser import GGUFParser  # noqa: E402

MODE = sys.argv[2]
GGUF_MAGIC = b"GGUF"
_STRING, _ARRAY = 8, 9

failures = []


def check(name, ok, detail=""):
    print(f"  [{'OK' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        failures.append(name)


def nested_header(depth, count=1):
    """A header whose metadata array has an ARRAY element type, nested `depth` times."""
    value = struct.pack("<IQ", _STRING, 1) + struct.pack("<Q", 1) + b"x"
    for _ in range(depth):
        value = struct.pack("<IQ", _ARRAY, count) + value
    metadata = struct.pack("<Q", 1) + b"k" + struct.pack("<I", _ARRAY) + value
    return GGUF_MAGIC + struct.pack("<IQQ", 3, 0, 1) + metadata


def kv_buffer(vtype, value_bytes):
    metadata = struct.pack("<Q", 1) + b"k" + struct.pack("<I", vtype) + value_bytes
    return GGUF_MAGIC + struct.pack("<IQQ", 3, 0, 1) + metadata


def parse_outcome(buf):
    """Return ('valueerror', msg) | ('recursionerror',) | ('accepted', parser)."""
    try:
        return ("accepted", GGUFParser(buf))
    except ValueError as exc:
        return ("valueerror", str(exc))
    except RecursionError:
        return ("recursionerror",)


print(f"mode={MODE} tree={sys.argv[1]}")

# --- 1. shallow nesting: depths 1, 2, 5 -----------------------------------
print("1. shallow nested arrays (depths 1, 2, 5)")
for depth in (1, 2, 5):
    outcome = parse_outcome(nested_header(depth))
    if MODE == "parent":
        check(f"depth {depth} accepted (pre-fix behaviour)", outcome[0] == "accepted", str(outcome[0]))
    else:
        check(
            f"depth {depth} -> ValueError 'must not be an array'",
            outcome[0] == "valueerror" and "must not be an array" in outcome[1],
            str(outcome[:2]),
        )

# --- 2. nested array with count=0 ------------------------------------------
print("2. nested array with count=0 (the check must precede the count check)")
outcome = parse_outcome(nested_header(3, count=0))
if MODE == "parent":
    check("count=0 accepted pre-fix", outcome[0] == "accepted", str(outcome[0]))
else:
    check("count=0 -> ValueError", outcome[0] == "valueerror", str(outcome[:2]))

# --- 3. the minimized example from the blocker report ----------------------
print("3. the minimized example: _nested_array_header(992)")
buf = nested_header(992)
digest = hashlib.sha256(buf).hexdigest()
check("length is 11,962 bytes", len(buf) == 11_962, f"{len(buf)} bytes")
check(
    "sha256 matches the blocker report",
    digest == "28fe58bf8fee9e0d9e0987b3cc2e09922ffb968f9f8809de34c7305d086bbebb",
    digest,
)
outcome = parse_outcome(buf)
if MODE == "parent":
    check("parent raises RecursionError at depth 992", outcome[0] == "recursionerror", str(outcome[0]))
else:
    check("candidate raises ValueError at depth 992", outcome[0] == "valueerror", str(outcome[:2]))

# --- 4. deep nesting, no recursion ----------------------------------------
print("4. deep nesting (depth 5000, ~60 KiB) must not recurse")
outcome = parse_outcome(nested_header(5000))
if MODE == "parent":
    check("parent raises RecursionError at depth 5000", outcome[0] == "recursionerror", str(outcome[0]))
else:
    check("candidate raises ValueError at depth 5000", outcome[0] == "valueerror", str(outcome[:2]))

# --- 5. truncated nested header --------------------------------------------
print("5. truncated nested header (20 bytes) -> ValueError, never RecursionError")
outcome = parse_outcome(nested_header(1000)[:20])
check("truncated -> ValueError", outcome[0] == "valueerror", str(outcome[:2]))

# --- 6. valid arrays still parse (regression) -------------------------------
print("6. valid arrays of every scalar element type still parse")
import io  # noqa: E402

cases = {
    "int32": (5, [1, -2, 3]),
    "string": (_STRING, ["a", "bc", ""]),
    "uint64": (10, [0, 2**63]),
    "bool": (7, [True, False]),
    "float32": (6, [1.5, -0.25]),
    "uint32": (4, [0, 4294967295]),
}
for label, (elem, items) in cases.items():
    buf = io.BytesIO()
    gguf_parser.write_synthetic_gguf(
        buf,
        metadata={"general.alignment": (4, 32), "k": (9, (elem, items))},
        tensors=[],
    )
    outcome = parse_outcome(buf.getvalue())
    ok = outcome[0] == "accepted" and outcome[1].metadata["k"] == items
    check(f"array of {label} parses with correct values", ok, str(outcome[:1]))

# empty array
buf = io.BytesIO()
gguf_parser.write_synthetic_gguf(buf, metadata={"k": (9, (5, []))}, tensors=[])
outcome = parse_outcome(buf.getvalue())
check("empty array parses", outcome[0] == "accepted" and outcome[1].metadata["k"] == [], str(outcome[:1]))

# --- 7. pre-existing rejection classes unchanged ----------------------------
print("7. pre-existing rejection classes unchanged")
# huge count, valid element type
outcome = parse_outcome(kv_buffer(_ARRAY, struct.pack("<IQ", 5, (1 << 63) - 1)))
check(
    "huge count -> 'exceeds remaining buffer' ValueError",
    outcome[0] == "valueerror" and "exceeds remaining buffer" in outcome[1],
    str(outcome[:2]),
)
# unknown element type
outcome = parse_outcome(kv_buffer(_ARRAY, struct.pack("<IQ", 99, 1) + b"\x00" * 4))
check(
    "unknown element type 99 -> 'Unsupported' ValueError",
    outcome[0] == "valueerror" and "Unsupported" in outcome[1],
    str(outcome[:2]),
)
# truncated mid-array
outcome = parse_outcome(kv_buffer(_ARRAY, struct.pack("<IQ", 5, 3) + b"\x01\x02"))
check("truncated array body -> ValueError", outcome[0] == "valueerror", str(outcome[:2]))
# bad magic
outcome = parse_outcome(b"XXXX" + struct.pack("<IQQ", 3, 0, 0))
check("bad magic -> ValueError", outcome[0] == "valueerror", str(outcome[:2]))

print()
if failures:
    print(f"RESULT: {len(failures)} probe(s) UNEXPECTED: {failures}")
    sys.exit(1)
print("RESULT: all probes matched the expected behaviour for mode=" + MODE)
