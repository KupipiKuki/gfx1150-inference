#!/usr/bin/env python3
"""Reproduce the QAQC 7A-6 probes and emit a full transcript.

7A-6 follow-up, condition C-7A6-2. The QAQC probe log that shipped with the
7A-6 bundle is a *summary*, not a transcript: several probes say "see earlier
run", one records the wrong exit code, and one reports a removal count of 0
while finding stale scopes. QAQC's scratch tree (`/tmp/opencode/qaqc-76/`) was
ephemeral and is gone, so the transcript is reproduced here from scratch.

Usage::

    python3 audit/evidence/G1/7A-6-followup/reproduce-probes.py > <transcript>

Every probe runs against a throw-away copy of the tree (``--root`` isolation),
except the explicitly live probes, which restore what they touch. The
repository is never left modified.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Callable

REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")
)
CHECKER = os.path.join(REPO_ROOT, "scripts", "qa", "check_claims.py")
CANARIES = os.path.join(REPO_ROOT, "scripts", "qa", "canary_claims.py")

IGNORE = shutil.ignore_patterns(".git", "__pycache__", "*.pyc", "build")


def section(title: str) -> None:
    print(f"--- {title} ---")


def run(cmd: list[str], cwd: str | None = None) -> tuple[int, str]:
    completed = subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, check=False
    )
    return completed.returncode, completed.stdout + completed.stderr


def copy_tree() -> str:
    root = tempfile.mkdtemp(prefix="probe-")
    shutil.copytree(REPO_ROOT, root, ignore=IGNORE, dirs_exist_ok=True)
    return root


def checker(root: str, *args: str) -> tuple[int, str]:
    return run([sys.executable, CHECKER, "--root", root, *args])


def result_line(output: str) -> str:
    for line in output.splitlines():
        if line.startswith("RESULT:"):
            return line
    return "(no RESULT line)"


def edit(path: str, old: str, new: str) -> bool:
    with open(path, "r", encoding="utf-8") as handle:
        text = handle.read()
    if old not in text:
        return False
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text.replace(old, new, 1))
    return True


def append(path: str, text: str) -> None:
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(text)


# --------------------------------------------------------------------------- #
# B — verification runs
# --------------------------------------------------------------------------- #


def probe_b() -> None:
    section("B1 default mode")
    code, out = checker(REPO_ROOT)
    print(result_line(out))
    print(f"exit: {code}")

    section("B2 strict mode")
    code, out = checker(REPO_ROOT, "--strict")
    print(result_line(out))
    print(f"exit: {code}")

    section("B3 json mode")
    code, out = checker(REPO_ROOT, "--json")
    payload = json.loads(out)
    print(
        f"ok={payload['ok']} claims={payload['claims']} "
        f"violations={len(payload['violations'])} "
        f"baselined={sum(1 for v in payload['violations'] if v['baselined'])} "
        f"unaccounted={sum(1 for v in payload['violations'] if not v['baselined'])} "
        f"expired={len(payload['expired_baseline'])} "
        f"findings={len(payload['findings'])} warnings={len(payload['warnings'])}"
    )
    print(f"exit: {code}")

    section("B4 canaries")
    code, out = run([sys.executable, CANARIES])
    print(result_line(out))
    print(f"exit: {code}")

    section("B5 pytest lanes")
    for args in (["-m", "not gpu"], ["-m", "gpu"], []):
        code, out = run(
            [sys.executable, "-m", "pytest", "-q", *args],
            cwd=REPO_ROOT,
        )
        tail = [l for l in out.splitlines() if "passed" in l or "failed" in l]
        print("  " + (tail[-1] if tail else out.strip().splitlines()[-1:]))
        print(f"  exit: {code}")

    section("B6 cpu suite unittest")
    for args in ([], ["-O"]):
        code, out = run([sys.executable, *args, "tests/test_cpu_only.py"], cwd=REPO_ROOT)
        print("  " + (out.strip().splitlines()[-1] if out.strip() else ""))
        print(f"  exit: {code}")

    section("B7 ci-cpu.yml YAML")
    try:
        import yaml  # type: ignore

        with open(os.path.join(REPO_ROOT, ".github/workflows/ci-cpu.yml")) as handle:
            doc = yaml.safe_load(handle)
        steps = doc["jobs"]["cpu-smoke"]["steps"]
        print(f"valid; {len(steps)} steps in cpu-smoke")
    except ImportError:
        print("valid (pyyaml unavailable; structural check only)")
    except Exception as exc:  # pragma: no cover - diagnostic path
        print(f"INVALID: {exc}")

    section("B8 baseline byte-identical to the 7A-6 candidate")
    code, out = run(
        [
            "git", "diff", "--stat", "994d629", "--", "audit/claims_baseline.txt",
        ],
        cwd=REPO_ROOT,
    )
    print(out.strip() or "  no diff")
    print(f"exit: {code}")

    section("B9 true diffstat of the follow-up")
    code, out = run(
        ["git", "diff", "--shortstat", "b626c94", "HEAD"], cwd=REPO_ROOT
    )
    print("  " + out.strip())
    print(f"  exit: {code}")


# --------------------------------------------------------------------------- #
# A — adversarial probes
# --------------------------------------------------------------------------- #


def probe_a1() -> None:
    section("A1 live NOT-YET canary (handoff §7): inject -> fail -> restore -> green")
    readme = os.path.join(REPO_ROOT, "README.md")
    with open(readme, "rb") as handle:
        original = handle.read()
    append(readme, "\n- Supports `chat special-token encoding` for the Llama-3 chat template.\n")
    code, out = checker(REPO_ROOT)
    new_lines = [l for l in out.splitlines() if "NEW VIOLATION" in l]
    print(f"  exit: {code} (expect 1)")
    print(f"  NEW VIOLATION lines: {len(new_lines)}")
    with open(readme, "wb") as handle:
        handle.write(original)
    code, out = checker(REPO_ROOT)
    print(f"  after restore exit: {code}")
    with open(readme, "rb") as handle:
        restored = handle.read()
    print(f"  README byte-identical after restore: {restored == original}")


def probe_a2() -> None:
    section("A2 line-precision attack (2nd unqualified qwen2 in a baselined path)")
    root = copy_tree()
    try:
        append(os.path.join(root, "README.md"), "\n- `qwen2` models are supported.\n")
        code, out = checker(root)
        for line in out.splitlines():
            if "NEW VIOLATION" in line or line.startswith("RESULT"):
                print("  " + line)
        print(f"  exit: {code} (expect 1)")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def probe_a3() -> None:
    section("A3 baseline is load-bearing (delete entry 10)")
    root = copy_tree()
    try:
        path = os.path.join(root, "audit/claims_baseline.txt")
        edit(path, "10 README.md qwen2\n", "")
        code, out = checker(root)
        for line in out.splitlines():
            if "NEW VIOLATION" in line or "baselined," in line or line.startswith("RESULT"):
                print("  " + line)
        print(f"  exit: {code} (expect 1)")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def probe_a4() -> None:
    section("A4 wildcard baseline entry")
    root = copy_tree()
    try:
        append(os.path.join(root, "audit/claims_baseline.txt"), "10 README.md q*en2\n")
        code, out = checker(root)
        print("  " + (out.strip().splitlines()[-1] if out.strip() else ""))
        print(f"  exit: {code} (expect 2)")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def probe_a5() -> None:
    section("A5 malformed baseline entry")
    root = copy_tree()
    try:
        append(os.path.join(root, "audit/claims_baseline.txt"), "not a valid entry\n")
        code, out = checker(root)
        print("  " + (out.strip().splitlines()[-1] if out.strip() else ""))
        print(f"  exit: {code} (expect 2)")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def probe_a6() -> None:
    section("A6 invalid status in a ledger row")
    root = copy_tree()
    try:
        path = os.path.join(root, "audit/CLAIMS_LEDGER.md")
        edit(path, "| **UNVERIFIED** |", "| **SOMETIMES** |")
        code, out = checker(root)
        for line in out.splitlines():
            if "invalid-status" in line or line.startswith("RESULT"):
                print("  " + line)
        print(f"  exit: {code} (expect 1)")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def probe_a7() -> None:
    section("A7 duplicate claim ID")
    root = copy_tree()
    try:
        path = os.path.join(root, "audit/CLAIMS_LEDGER.md")
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
        rows = [l for l in text.splitlines() if l.startswith("| 30 |")]
        if rows:
            text = text.replace(rows[0], rows[0] + "\n" + rows[0], 1)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text)
        code, out = checker(root)
        print("  " + (out.strip().splitlines()[-1] if out.strip() else ""))
        print(f"  exit: {code} (expect 2)")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def probe_a8() -> None:
    section("A8 escaped-pipe (\\|) literal cell parses to 7 columns")
    root = copy_tree()
    try:
        path = os.path.join(root, "audit/CLAIMS_LEDGER.md")
        edit(path, "| `Q4_K_M` |", "| `a\\|b` |")
        code, out = checker(root, "--json")
        payload = json.loads(out)
        print(f"  claims parsed: {payload['claims']} (expect 30)")
        print(f"  exit: {code} (1: the substituted literal does not resolve)")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def probe_a9() -> None:
    section("A9 drift: line inserted at README top")
    root = copy_tree()
    try:
        path = os.path.join(root, "README.md")
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("<!-- drift -->\n" + text)
        code, out = checker(root)
        warnings = [l for l in out.splitlines() if "drift" in l]
        print(f"  drift warnings: {len(warnings)}")
        print(f"  {result_line(out)}")
        print(f"  exit: {code} (expect 0)")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def probe_a10() -> None:
    section("A10 qualifier-bullet deletion in a copy")
    root = copy_tree()
    try:
        path = os.path.join(root, "README.md")
        with open(path, "r", encoding="utf-8") as handle:
            lines = handle.readlines()
        kept = [l for l in lines if "**Verified release scope:**" not in l]
        removed = len(lines) - len(kept)
        with open(path, "w", encoding="utf-8") as handle:
            handle.writelines(kept)
        code, out = checker(root)
        stale = len([l for l in out.splitlines() if "stale-scope" in l])
        unresolved = len([l for l in out.splitlines() if "unresolved-literal" in l])
        print(f"  lines removed: {removed}")
        print(f"  stale-scope findings: {stale}")
        print(f"  unresolved-literal findings: {unresolved}")
        print(f"  total findings: {stale + unresolved}")
        print(f"  {result_line(out)}")
        print(f"  exit: {code} (expect 1)")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def probe_a11() -> None:
    section("A11 claims-check.log vs the run it documents")
    log = os.path.join(REPO_ROOT, "audit/evidence/G1/7A-6/claims-check.log")
    if not os.path.exists(log):
        print("  claims-check.log not present")
        return
    with open(log, "r", encoding="utf-8") as handle:
        recorded = handle.read()
    body = recorded.split("\n\n", 1)[1] if "\n\n" in recorded else recorded

    # The log documents the 7A-6 candidate (994d629). Rebuild that candidate's
    # view -- its README predates the auditor's prep commit efe34fc, which
    # added one line to the README project tree -- and compare.
    root = copy_tree()
    try:
        for relative in (
            "README.md",
            "IMPLEMENTATION_PLAN.md",
            "audit/CLAIMS_LEDGER.md",
            "audit/claims_baseline.txt",
            "scripts/qa/check_claims.py",
        ):
            code, out = run(["git", "show", f"994d629:{relative}"], cwd=REPO_ROOT)
            if code != 0:
                print(f"  could not read {relative} at 994d629: exit {code}")
                return
            target = os.path.join(root, relative)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "w", encoding="utf-8") as handle:
                handle.write(out)
        _, live = run(
            [sys.executable, os.path.join(root, "scripts/qa/check_claims.py"),
             "--root", root],
        )
        print(
            "  recorded body == the 7A-6 candidate's output: "
            f"{body.strip() == live.strip()}"
        )
        _, current = checker(REPO_ROOT)
        print(
            "  recorded body == the follow-up tree's output: "
            f"{body.strip() == current.strip()}"
        )
        print("  (the follow-up tree differs: prep commit efe34fc added one line")
        print("   to the README project tree, so the recorded line numbers moved)")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def probe_c() -> None:
    section("C canary mutation-test")
    # Mutation 1: force the exit code to 0 (the checker never fails).
    root = copy_tree()
    try:
        path = os.path.join(root, "scripts/qa/check_claims.py")
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
        text = text.replace(
            "    return 1 if _failed(report, args.strict) else 0", "    return 0"
        )
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        code, out = run([sys.executable, os.path.join(root, "scripts/qa/canary_claims.py")])
        failing = [l for l in out.splitlines() if l.startswith("FAIL ")]
        print(f"  mutation 'force exit 0': canaries failing: {len(failing)}")
        for line in failing:
            print(f"    {line.split(':')[0]}")
        print(f"  exit: {code} (expect 1)")
    finally:
        shutil.rmtree(root, ignore_errors=True)

    # Mutation 2: force the checker to report failure for every run. This is
    # the mutation the C-7A6-1 defect would have caused on a clean tree, and
    # the one the positive `strict_clean` canary must catch.
    root = copy_tree()
    try:
        path = os.path.join(root, "scripts/qa/check_claims.py")
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
        text = text.replace(
            'f"RESULT: {\'FAIL\' if failed else \'PASS\'} - "\n            f"{len(report.violations)} unqualified occurrence(s) "',
            'f"RESULT: FAIL - "\n            f"{len(report.violations)} unqualified occurrence(s) "',
        )
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        code, out = run([sys.executable, os.path.join(root, "scripts/qa/canary_claims.py")])
        failing = [l for l in out.splitlines() if l.startswith("FAIL ")]
        print(f"  mutation 'always report FAIL': canaries failing: {len(failing)}")
        for line in failing:
            print(f"    {line.split(':')[0]}")
        print(f"  exit: {code} (expect 1)")
    finally:
        shutil.rmtree(root, ignore_errors=True)

    # Mutation 3: the checker does nothing at all (no output, always exit 0).
    # Every canary must fail, the positive one included.
    root = copy_tree()
    try:
        path = os.path.join(root, "scripts/qa/check_claims.py")
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
        text = text.replace(
            "    if args.json:\n        print(_render_json(report, args.strict))\n"
            "    else:\n        print(_render(report, args.strict))\n",
            "",
        )
        text = text.replace(
            "    return 1 if _failed(report, args.strict) else 0", "    return 0"
        )
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        code, out = run([sys.executable, os.path.join(root, "scripts/qa/canary_claims.py")])
        failing = [l for l in out.splitlines() if l.startswith("FAIL ")]
        print(f"  mutation 'checker does nothing': canaries failing: {len(failing)}")
        for line in failing:
            print(f"    {line.split(':')[0]}")
        print(f"  exit: {code} (expect 1)")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def main() -> int:
    print("# 7A-6 QAQC probe reproduction — full transcript")
    print("# Produced by audit/evidence/G1/7A-6-followup/reproduce-probes.py")
    print(f"# tree: {REPO_ROOT}")
    print(f"# HEAD: {run(['git', 'rev-parse', 'HEAD'], cwd=REPO_ROOT)[1].strip()}")
    print()
    probe_b()
    print()
    probe_a1()
    probe_a2()
    probe_a3()
    probe_a4()
    probe_a5()
    probe_a6()
    probe_a7()
    probe_a8()
    probe_a9()
    probe_a10()
    probe_a11()
    print()
    probe_c()
    return 0


if __name__ == "__main__":
    sys.exit(main())
