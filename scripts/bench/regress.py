#!/usr/bin/env python3
"""Benchmark regression gate (7F-3): compare a bench result to the baseline.

Blocking release gate against the checked-in baseline files
(``scripts/bench/baseline-synthetic.json``, ``audit/evidence/G6/7F/bench/baseline-7b.json``):

    python scripts/bench/regress.py scripts/bench/baseline-synthetic.json result.json

Rules (``scripts/bench/aggregate.py::check_regression``):

* like-for-like only: same schema, GPU, model sha256 and workload label;
* >= 20 measured iterations required in both files;
* FAIL when the median of ``prefill_tok_per_s``, ``decode_tok_per_s`` or
  ``total_tok_per_s`` drops more than ``ALLOWED_REGRESSION_RATIO`` (15%)
  below the baseline;
* FAIL when a per-projection kernel-time median rises more than 15% above
  the baseline.

The 15% ratio is the agreed ratio the 7F-3 brief asks to state; its
justification is documented next to the constant and measured in
``audit/evidence/G6/7F/bench/`` (rerun variance).

Exit codes: ``0`` pass, ``1`` regression/mismatch, ``2`` comparison error.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Dict, Sequence

import os

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))

from aggregate import ALLOWED_REGRESSION_RATIO, check_regression  # noqa: E402


def _load(path: str) -> Dict[str, object]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("baseline", help="checked-in baseline JSON (gfx1150-bench/1)")
    parser.add_argument("result", help="fresh result JSON (gfx1150-bench/1)")
    args = parser.parse_args(argv)

    try:
        baseline = _load(args.baseline)
        result = _load(args.result)
    except (OSError, ValueError) as exc:
        print(f"regress: cannot load payloads: {exc}", file=sys.stderr)
        return 2

    failures = check_regression(baseline, result)
    if failures:
        for failure in failures:
            print(f"REGRESSION: {failure}")
        print(f"RESULT: FAIL (allowed ratio {ALLOWED_REGRESSION_RATIO:.0%})")
        return 1
    print(
        "RESULT: PASS - medians within "
        f"{ALLOWED_REGRESSION_RATIO:.0%} of {args.baseline}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
