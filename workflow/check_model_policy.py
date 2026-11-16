#!/usr/bin/env python3
"""Check the role-model exclusivity policy for the five workflow agents.

Reads `.opencode/agents/<role>.md` frontmatter and verifies:
  R1  architect family is exclusive
  R2  auditor family is exclusive
  R4/R5 qaqc family differs from the coder family/families
  R6  every role has an explicit model (strict mode)
Variants (`#high`) are collapsed, and the model ID's first `-` token is the
family (e.g. `deepseek-v4-pro` -> `deepseek`); R7/§5 of MODEL_POLICY.md.

Approved exceptions live in `workflow/model_policy.json` and are reported as
WAIVED, never as PASS.

Exit codes: 0 valid/pending/waived, 1 violation, 2 strict + unassigned.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROLES = ("architect", "coder-primary", "coder-secondary", "qaqc", "auditor")
EXCLUSIVE = ("architect", "auditor")


def agent_model(path: pathlib.Path) -> str | None:
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    for line in parts[1].splitlines():
        if line.strip().startswith("model:"):
            value = line.split(":", 1)[1].strip().strip("'\"")
            return value or None
    return None


def family_of(model: str | None) -> str | None:
    if not model:
        return None
    model_id = model.split("/")[-1].split("#", 1)[0].strip()
    return model_id.split("-", 1)[0] or model_id


def load_waivers(root: pathlib.Path) -> list[dict]:
    path = root / "workflow" / "model_policy.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data.get("waivers", [])


def waiver_for(waivers: list[dict], a: str, b: str, family: str) -> dict | None:
    for waiver in waivers:
        if waiver.get("family") != family:
            continue
        if {waiver.get("role"), waiver.get("conflicts_with")} == {a, b}:
            return waiver
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="fail if any role has no explicit model")
    parser.add_argument("--agents-dir", default=None, help="override .opencode/agents")
    args = parser.parse_args()

    root = pathlib.Path(__file__).resolve().parent.parent
    agents_dir = pathlib.Path(args.agents_dir) if args.agents_dir else root / ".opencode" / "agents"

    models = {role: agent_model(agents_dir / f"{role}.md") for role in ROLES}
    families = {role: family_of(model) for role, model in models.items()}
    waivers = load_waivers(root)

    print("role                 model                                      family")
    print("-------------------- ------------------------------------------ --------")
    for role in ROLES:
        print(f"{role:20} {models[role] or '<unset>':42} {families[role] or '-'}")

    pending = [role for role in ROLES if not models[role]]
    violations: list[str] = []
    waived: dict[tuple[str, str, tuple[str, str]], tuple[str, str, str, dict]] = {}

    def check_pair(a: str, b: str, family: str, rule: str) -> None:
        waiver = waiver_for(waivers, a, b, family)
        if waiver:
            key = (waiver.get("id", "waiver"), family, tuple(sorted((a, b))))
            waived[key] = (a, b, family, waiver)
            return
        violations.append(
            f"{a} and {b} both use family '{family}' ({rule})"
        )

    for exclusive in EXCLUSIVE:
        if families[exclusive] is None:
            continue
        for role in ROLES:
            if role == exclusive or families[role] is None:
                continue
            if families[role] == families[exclusive]:
                check_pair(exclusive, role, families[exclusive], "R1/R2: exclusive role")

    for coder in ("coder-primary", "coder-secondary"):
        if families["qaqc"] is not None and families[coder] is not None and families["qaqc"] == families[coder]:
            check_pair("qaqc", coder, families["qaqc"], "R4/R5: coder cannot check its own work")

    if waived:
        print("\nWAIVED (approved exception — not PASS)")
        for a, b, family, waiver in waived.values():
            print(
                f"  - {waiver.get('id', 'waiver')}: {a}/{b} share family '{family}' — "
                f"{waiver.get('reason', 'no reason recorded')}"
            )
            print(f"    expires: {waiver.get('expires', 'not recorded')}")

    if violations:
        print("\nVIOLATIONS")
        for violation in violations:
            print(f"  - {violation}")
        return 1

    if pending:
        print(f"\nPENDING: {len(pending)} role(s) have no explicit model: {', '.join(pending)}")
        print("Apply MODEL_POLICY.md when the active agent is free.")
        return 2 if args.strict else 0

    if waived:
        print("\nRESULT: WAIVED — policy exception in force (not PASS).")
        print("Remove the waiver and rerun `--strict` when the APIs are available.")
        return 0

    print("\nPASS: role-model exclusivity holds (R1, R2, R4, R6).")
    print("Reminder: the auditor must be the project's strongest reasoning model (R3).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
