#!/usr/bin/env python3
"""Canary tests for the claims checker (``scripts/qa/check_claims.py``).

Phase 7A-6 work package. Audit trace: AUD-3 ("a negative canary that removes a
claim and confirms failure"), brief §3 item 6.

Each canary mutates a *copy* of the tree, runs the checker against it, and
asserts that the mutation is detected. The real working tree is never modified.

Canaries
--------

``not_yet_claim``
    An unqualified ``NOT YET`` claim appears in ``README.md``. Default mode must
    fail: the literal is no longer confined to the qualified site the ledger
    recorded.
``unqualified_q4_k_m``
    An unqualified ``Q4_K_M`` claim appears in ``README.md``. Default mode must
    fail.
``unqualified_qwen2``
    An unqualified ``qwen2`` claim appears in ``README.md``. Default mode must
    fail.
``missing_evidence``
    A ``VERIFIED`` row's evidence file is removed. Default mode must fail.
``generic_literal``
    A claim whose literal does not match the claim is replaced by a generic
    one. The checker must reject the generic literal: the negative test
    (removing the claim from the document) has to fail, which a generic literal
    cannot do.
``strict_detects_baseline``
    ``--strict`` must fail on the seeded baseline, i.e. it must ignore the
    baseline rather than tolerate it.
``baseline_is_exact``
    The seeded baseline must hold exactly ``EXPECTED_BASELINE_ENTRIES`` entries,
    each resolving to a real unqualified site, with no wildcards.

Usage::

    python3 scripts/qa/canary_claims.py            # run every canary
    python3 scripts/qa/canary_claims.py --verbose  # show each checker's output

Exit codes: ``0`` all canaries behaved as required, ``1`` a canary was not
detected, ``2`` the harness itself failed.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Callable, Sequence

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CHECKER = os.path.join(REPO_ROOT, "scripts", "qa", "check_claims.py")

#: The seeded baseline is expected to hold exactly these entries.
#: 7C-4 removed the resolved "10 README.md qwen2" entry (15 -> 14); 7D removed the
#: resolved rows 14/18/19/20/30 entries (14 -> 6) after qualifying them in place or
#: withdrawing the claim. Update this constant whenever a claim is qualified/removed
#: and its baseline entry is deleted.
EXPECTED_BASELINE_ENTRIES = 6

#: Directories that are never needed in a canary tree.
IGNORED_TREE_ITEMS = shutil.ignore_patterns(
    ".git", "__pycache__", "*.pyc", "*.pyo", ".pytest_cache", "build"
)


class CanaryError(Exception):
    """Raised when the harness cannot set up or run a canary."""


class Tree:
    """A throw-away copy of the repository, safe to mutate."""

    def __init__(self, root: str) -> None:
        self.root = root

    @classmethod
    def create(cls, parent: str) -> "Tree":
        """Copy the repository so that every evidence path still resolves."""
        root = tempfile.mkdtemp(prefix="claims-canary-", dir=parent)
        try:
            shutil.copytree(REPO_ROOT, root, ignore=IGNORED_TREE_ITEMS, dirs_exist_ok=True)
        except OSError as exc:
            shutil.rmtree(root, ignore_errors=True)
            raise CanaryError(f"cannot copy the tree: {exc}") from exc
        return cls(root)

    @classmethod
    def create_clean(cls, parent: str) -> "Tree":
        """Build a minimal tree with one VERIFIED claim and an empty baseline.

        This is the tree the ``strict_clean`` canary runs against: it has
        nothing to complain about, so ``--strict`` must exit 0 and say PASS.
        """
        root = tempfile.mkdtemp(prefix="claims-canary-clean-", dir=parent)
        tree = cls(root)
        tree.write(
            "README.md",
            "# Demo\n\n"
            "The CPU parser suite passes.\n"
            "\n"
            "```bash\n"
            "python3 tests/test_cpu_only.py\n"
            "```\n",
        )
        tree.write(
            "IMPLEMENTATION_PLAN.md",
            "# Demo plan\n\n"
            "| Phase | Status |\n"
            "|---|---|\n"
            "| 1 | CPU parser suite | Complete |\n",
        )
        tree.write(
            os.path.join("audit", "CLAIMS_LEDGER.md"),
            "# Claims Ledger\n"
            "\n"
            "| ID | Claim | Status | Public match (literal) | Qualified in place? "
            "| Evidence | Scope / limit |\n"
            "|---|---|---|---|---|---|---|\n"
            "| 1 | CPU parser suite passes | **VERIFIED** | `tests/test_cpu_only.py` "
            "| n/a | `audit/evidence/demo/cpu-suite.log` | demo platform |\n",
        )
        tree.write(
            os.path.join("audit", "claims_baseline.txt"),
            "# Known claim violations (ratchet baseline)\n"
            "# Format: <claim-id> <path> <literal>\n"
            "# Empty: nothing is ratcheted.\n",
        )
        tree.write(
            os.path.join("audit", "evidence", "demo", "cpu-suite.log"),
            "demo evidence\n",
        )
        return tree

    def destroy(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def path(self, relative: str) -> str:
        return os.path.join(self.root, relative)

    def read(self, relative: str) -> str:
        with open(self.path(relative), "r", encoding="utf-8") as handle:
            return handle.read()

    def write(self, relative: str, content: str) -> None:
        target = self.path(relative)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as handle:
            handle.write(content)

    def append(self, relative: str, content: str) -> None:
        with open(self.path(relative), "a", encoding="utf-8") as handle:
            handle.write(content)

    def remove(self, relative: str) -> None:
        os.remove(self.path(relative))

    def run_checker(self, *args: str) -> tuple[int, str]:
        """Run the checker against this tree and return ``(exit_code, output)``."""
        command = [sys.executable, CHECKER, "--root", self.root, *args]
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
        return completed.returncode, completed.stdout + completed.stderr


# --------------------------------------------------------------------------- #
# Canary mutations
# --------------------------------------------------------------------------- #


def canary_not_yet_claim(tree: Tree) -> tuple[bool, str]:
    """Inject an unqualified NOT YET claim into README.md."""
    tree.append(
        "README.md",
        "\n- Supports `chat special-token encoding` for the Llama-3 chat template.\n",
    )
    code, output = tree.run_checker()
    detected = code != 0 and "chat special-token encoding" in output
    return detected, output


def canary_unqualified_q4_k_m(tree: Tree) -> tuple[bool, str]:
    """Inject an unqualified Q4_K_M claim into README.md."""
    tree.append(
        "README.md",
        "\n- Real `Q4_K_M` GGUF inference is supported end to end.\n",
    )
    code, output = tree.run_checker()
    detected = code != 0 and "Q4_K_M" in output
    return detected, output


def canary_unqualified_qwen2(tree: Tree) -> tuple[bool, str]:
    """Inject an unqualified qwen2 claim into README.md."""
    tree.append(
        "README.md",
        "\n- `qwen2` models are supported for text generation.\n",
    )
    code, output = tree.run_checker()
    detected = code != 0 and "qwen2" in output
    return detected, output


def canary_missing_evidence(tree: Tree) -> tuple[bool, str]:
    """Remove the evidence file a VERIFIED row points at."""
    ledger = tree.read(os.path.join("audit", "CLAIMS_LEDGER.md"))
    marker = "audit/evidence/G0/7.0-baseline/sdist-install.log"
    if marker not in ledger:
        raise CanaryError(f"evidence marker {marker!r} not found in the ledger")
    tree.remove(marker)
    code, output = tree.run_checker()
    detected = code != 0 and "missing-evidence" in output
    return detected, output


def canary_generic_literal(tree: Tree) -> tuple[bool, str]:
    """A generic literal must not survive the negative test.

    The negative test removes a claim from the public document and requires the
    checker to notice. A claim-specific literal (``sdist``) disappears with the
    claim; a generic one (``GPU``) does not, so the checker must reject the
    generic literal outright.
    """
    ledger_path = os.path.join("audit", "CLAIMS_LEDGER.md")
    ledger = tree.read(ledger_path)
    generic = "| 1 | Builds and installs from the sdist | **VERIFIED** | `sdist` |"
    specific = "| 1 | Builds and installs from the sdist | **VERIFIED** | `GPU` |"
    if generic not in ledger:
        raise CanaryError("claim 1 row not found in the ledger")
    tree.write(ledger_path, ledger.replace(generic, specific, 1))
    code, output = tree.run_checker()
    detected = code != 0 and "generic-literal" in output
    return detected, output


def canary_strict_detects_baseline(tree: Tree) -> tuple[bool, str]:
    """--strict must ignore the baseline and fail on the seeded violations."""
    code, output = tree.run_checker("--strict")
    detected = code != 0 and "strict" in output
    return detected, output


def canary_baseline_is_exact(tree: Tree) -> tuple[bool, str]:
    """The baseline must hold exactly the reviewed entries, no wildcards."""
    entries = []
    for line in tree.read(os.path.join("audit", "claims_baseline.txt")).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        entries.append(stripped)
    if len(entries) != EXPECTED_BASELINE_ENTRIES:
        return False, (
            f"baseline holds {len(entries)} entries, expected "
            f"{EXPECTED_BASELINE_ENTRIES}"
        )
    for entry in entries:
        if any(char in entry for char in "*?["):
            return False, f"wildcard in baseline entry {entry!r}"
    code, output = tree.run_checker("--json")
    if code != 0:
        return False, f"default mode failed on the seeded baseline:\n{output}"
    try:
        payload = json.loads(output)
    except json.JSONDecodeError as exc:
        return False, f"checker did not emit JSON: {exc}\n{output}"
    if payload.get("expired_baseline"):
        return False, (
            "baseline entries no longer resolve: "
            f"{payload['expired_baseline']}"
        )
    if not payload.get("ok"):
        return False, f"checker reported not-ok:\n{output}"
    return True, f"{EXPECTED_BASELINE_ENTRIES} exact entries, all resolving"


def canary_expired_baseline_entry(tree: Tree) -> tuple[bool, str]:
    """An expired baseline entry must be reported, and only warned about.

    A baseline entry for a claim whose unqualified site moved or was qualified
    is stale bookkeeping: default mode must keep passing (it is a warning, not
    a failure) but must say so, so the entry can be removed.
    """
    baseline_path = os.path.join("audit", "claims_baseline.txt")
    # Claim 30's unqualified site is in IMPLEMENTATION_PLAN.md; naming README.md
    # is stale bookkeeping for a claim that does exist.
    tree.append(baseline_path, "30 README.md 500 MB\n")
    code, output = tree.run_checker("--json")
    try:
        payload = json.loads(output)
    except json.JSONDecodeError as exc:
        return False, f"checker did not emit JSON: {exc}\n{output}"
    expired = payload.get("expired_baseline", [])
    reported = any(
        entry["claim_id"] == 30 and entry["path"] == "README.md" for entry in expired
    )
    if not reported:
        return False, f"the stale entry was not reported as expired:\n{output}"
    if code != 0:
        return False, f"an expired entry must warn, not fail:\n{output}"
    return True, "expired entry reported as a warning, exit code 0"


def canary_wrong_lane(tree: Tree) -> tuple[bool, str]:
    """An unqualified claim in the wrong document must be detected.

    The handoff scans both ``README.md`` and ``IMPLEMENTATION_PLAN.md``. A
    claim that is unqualified in the plan document is just as public as one in
    the README, so the checker must not let it through.
    """
    tree.append(
        "IMPLEMENTATION_PLAN.md",
        "\n- `qwen2` models are supported for text generation.\n",
    )
    code, output = tree.run_checker()
    detected = code != 0 and "qwen2" in output
    return detected, output

def canary_nested(tree: Tree) -> tuple[bool, str]:
    """A qualifier in the parent bullet must not cover a nested assertion.

    The handoff requires the inline qualification to be in the *same*
    paragraph/bullet as the match. An assertion in a nested bullet whose
    qualifier sits in the parent bullet is still unqualified.
    """
    readme = tree.read("README.md")
    marker = "- **Verified release scope:**"
    if marker not in readme:
        raise CanaryError("the 'Verified release scope' bullet was not found")
    nested = (
        "- **Verified release scope:** text-only llama-family GGUFs.\n"
        "  - `qwen2` models are supported for text generation.\n"
    )
    tree.write("README.md", readme.replace(marker, nested, 1))
    code, output = tree.run_checker()
    detected = code != 0 and "qwen2" in output
    return detected, output


def canary_strict_clean(tree: Tree) -> tuple[bool, str]:
    """``--strict`` must say PASS on a clean ledger.

    The strict mode is the G6 release gate: its human-readable output is a
    release artifact, so it must report the run's actual outcome. On a tree
    with nothing to complain about, ``--strict`` must exit 0 and say PASS.
    """
    code, output = tree.run_checker("--strict")
    if code != 0:
        return False, f"--strict exited {code} on a clean tree:\n{output}"
    if "RESULT: PASS" not in output:
        return False, f"--strict did not report RESULT: PASS:\n{output}"
    if "RESULT: FAIL" in output:
        return False, f"--strict reported RESULT: FAIL on a clean tree:\n{output}"
    json_code, json_output = tree.run_checker("--strict", "--json")
    if json_code != 0:
        return False, f"--strict --json exited {json_code}:\n{json_output}"
    try:
        payload = json.loads(json_output)
    except json.JSONDecodeError as exc:
        return False, f"--strict --json did not emit JSON: {exc}\n{json_output}"
    if not payload.get("ok"):
        return False, f"--strict --json reported ok=false:\n{json_output}"
    return True, "--strict exits 0, reports RESULT: PASS, and JSON ok=true"


def canary_id3_claim_removed(tree: Tree) -> tuple[bool, str]:
    """Removing the ID 3 claim from the README must fail the check.

    ID 3 ("GPU kernel/layer/E2E suites pass") is a VERIFIED row: its literal
    *locates* the claim in the public documents and its evidence path is the
    proof. The literal must therefore vanish together with the claim -- if
    deleting the claim's lines left the literal resolving somewhere else, the
    literal would not be enforcing the claim at all.

    The lines removed are exactly the ones the claim's literal selects, read
    from the ledger, so the test tracks the ledger rather than hard-coding a
    line number.
    """
    ledger = tree.read(os.path.join("audit", "CLAIMS_LEDGER.md"))
    row = next(
        (line for line in ledger.splitlines() if line.startswith("| 3 |")),
        None,
    )
    if row is None:
        raise CanaryError("claim 3 row not found in the ledger")
    literals = re.findall(r"`([^`]+)`", row.split("|")[4])
    if not literals:
        raise CanaryError("claim 3 has no public-match literal")
    literal = literals[0]

    readme = tree.read("README.md")
    lines = readme.splitlines(keepends=True)
    kept = [line for line in lines if literal not in line]
    removed = len(lines) - len(kept)
    if removed == 0:
        raise CanaryError(
            f"the ID 3 claim lines ({literal!r}) were not found in README.md"
        )
    tree.write("README.md", "".join(kept))
    code, output = tree.run_checker()
    detected = code != 0 and "unresolved-literal" in output
    return detected, output


CANARIES: tuple[tuple[str, Callable[[Tree], tuple[bool, str]], str], ...] = (
    ("not_yet_claim", canary_not_yet_claim, "copy"),
    ("unqualified_q4_k_m", canary_unqualified_q4_k_m, "copy"),
    ("unqualified_qwen2", canary_unqualified_qwen2, "copy"),
    ("missing_evidence", canary_missing_evidence, "copy"),
    ("generic_literal", canary_generic_literal, "copy"),
    ("strict_detects_baseline", canary_strict_detects_baseline, "copy"),
    ("baseline_is_exact", canary_baseline_is_exact, "copy"),
    ("expired_baseline_entry", canary_expired_baseline_entry, "copy"),
    ("wrong_lane", canary_wrong_lane, "copy"),
    ("nested_bullet", canary_nested, "copy"),
    ("strict_clean", canary_strict_clean, "clean"),
    ("id3_claim_removed", canary_id3_claim_removed, "copy"),
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="print the checker's output for every canary",
    )
    args = parser.parse_args(argv)

    failures = 0
    for name, canary, tree_kind in CANARIES:
        factory = Tree.create_clean if tree_kind == "clean" else Tree.create
        tree = factory(tempfile.gettempdir())
        try:
            detected, output = canary(tree)
        except CanaryError as exc:
            print(f"FAIL {name}: harness error: {exc}")
            failures += 1
            continue
        finally:
            tree.destroy()

        if detected:
            print(f"PASS {name}: the mutation was detected")
            if args.verbose:
                print(output)
        else:
            print(f"FAIL {name}: the mutation was NOT detected")
            print(output)
            failures += 1

    total = len(CANARIES)
    if failures:
        print(f"\nRESULT: FAIL - {failures} of {total} canaries were not detected")
        return 1
    print(f"\nRESULT: PASS - all {total} canaries behaved as required")
    return 0


if __name__ == "__main__":
    sys.exit(main())
