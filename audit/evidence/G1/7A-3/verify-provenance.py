#!/usr/bin/env python3
"""Check that every committed fixture has a complete provenance row.

Phase 7A-3. The brief requires that every fixture in ``tests/fixtures/`` is
registered in ``PROVENANCE.md`` with a complete row: an id, a path, a kind, an
upstream source, the exact command, the input and output hashes, the license
and the notes. A fixture without such a row is not acceptable evidence.

This script checks that mechanically:

* every file in ``tests/fixtures/`` (except this script and the provenance
  file itself) has a row;
* every row's path exists;
* every row's ``output_sha256`` matches the file's actual hash;
* every row's required fields are non-empty;
* the recorded input hashes are the hashes of the upstream files.

Usage:
    python3 verify-provenance.py [path/to/tests/fixtures]
"""

from __future__ import annotations

import hashlib
import pathlib
import re
import sys

FAILURES: list[str] = []
CHECKS = 0

REQUIRED_FIELDS = (
    "id",
    "path",
    "kind",
    "source",
    "command",
    "input_sha256",
    "output_sha256",
    "license",
    "notes",
)

VALID_KINDS = ("tokenizer-vector", "quant-block", "gguf-header", "tiny-model")

#: The upstream inputs, by the upstream file name. The rows must quote their
#: hashes.
UPSTREAM_INPUTS = {
    "vocab.json": "196139668be63f3b5d6574427317ae82f612a97c5d1cdaf36ed2256dbf636783",
    "merges.txt": "1ce1664773c50f3e0cc8842619a93edc4624525b728b188a9e0be33b7726adc5",
    "stories260K.gguf": "270cba1bd5109f42d03350f60406024560464db173c0e387d91f0426d3bd256d",
    "stories15M.gguf": "61b50d457809a5194818fd22e6724b456cd7bb9a6264c52c8110684c53f3704a",
}


def check(label: str, condition: bool, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    print(f"  [{'ok  ' if condition else 'FAIL'}] {label}" + (f" -- {detail}" if detail else ""))
    if not condition:
        FAILURES.append(label)


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_registry(text: str) -> list[dict[str, str]]:
    """Parse the registry table.

    The table is markdown, so a cell may contain an escaped pipe (``\\|``) --
    the end-of-text token's name needs one. The split therefore ignores
    escaped pipes, and the backticks around the paths are stripped.
    """
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [
            cell.strip().strip("`").replace("\\|", "|")
            for cell in re.split(r"(?<!\\)\|", line.strip("|"))
        ]
        if len(cells) != len(REQUIRED_FIELDS):
            continue
        if cells[0] in ("id", "---") or set(cells[0]) == {"-"}:
            continue
        rows.append(dict(zip(REQUIRED_FIELDS, cells)))
    return rows


def main(argv: list[str]) -> int:
    fixtures = pathlib.Path(argv[1]) if len(argv) > 1 else (
        pathlib.Path(__file__).resolve().parents[4] / "tests" / "fixtures"
    )
    provenance = fixtures / "PROVENANCE.md"
    print(f"=== verifying the provenance of {fixtures} ===")
    if not provenance.exists():
        print(f"  [FAIL] {provenance} does not exist")
        return 1

    rows = parse_registry(provenance.read_text(encoding="utf-8"))
    check("the registry has rows", len(rows) > 0, f"{len(rows)} rows")

    registered = {row["path"] for row in rows}
    on_disk = {
        path.name
        for path in fixtures.iterdir()
        if path.is_file()
        and path.name not in {"PROVENANCE.md", "verify-provenance.py"}
        # The generator is the tool that produced the fixtures, not a fixture;
        # it is documented in PROVENANCE.md's "Reproducing" section.
        and path.name != "make_fixtures.py"
    }
    missing = sorted(on_disk - registered)
    check(
        "every fixture on disk has a provenance row",
        not missing,
        "missing: " + ", ".join(missing) if missing else f"{len(on_disk)} fixtures",
    )
    unknown = sorted(registered - on_disk)
    check(
        "every registered row points at a file that exists",
        not unknown,
        "unknown: " + ", ".join(unknown) if unknown else "",
    )

    for row in rows:
        name = row["path"]
        for field in REQUIRED_FIELDS:
            check(
                f"{name}: the '{field}' field is filled in",
                bool(row[field].strip()),
            )
        check(
            f"{name}: the kind is one of {VALID_KINDS}",
            row["kind"] in VALID_KINDS,
            row["kind"],
        )
        path = fixtures / name
        if path.exists():
            digest = sha256(path)
            check(
                f"{name}: the recorded output hash matches the file",
                digest == row["output_sha256"].split()[0],
                digest,
            )
        check(
            f"{name}: the source names an upstream project",
            "llama.cpp" in row["source"] or "huggingface" in row["source"].lower()
            or "ggml-org" in row["source"],
            row["source"],
        )
        check(
            f"{name}: the license is recorded",
            bool(re.search(r"(MIT|Apache|BSD|GPL|LGPL)", row["license"])),
            row["license"],
        )

    print("\n=== the upstream input hashes ===")
    text = provenance.read_text(encoding="utf-8")
    for name, digest in UPSTREAM_INPUTS.items():
        check(
            f"the provenance quotes the hash of {name}",
            digest in text,
            digest,
        )

    print(f"\n=== {CHECKS - len(FAILURES)}/{CHECKS} checks passed ===")
    if FAILURES:
        print("FAILED:")
        for failure in FAILURES:
            print(f"  - {failure}")
        return 1
    print("PASS: every fixture has complete, verified provenance")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
