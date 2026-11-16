#!/usr/bin/env python3
"""Check the role-model exclusivity policy for the five workflow agents.

Reads `.opencode/agents/<role>.md` frontmatter and verifies:
  R1  architect model is exclusive
  R2  auditor model is exclusive
  R4/R5 qaqc base model differs from the coder base model(s)
  R6  every role has an explicit model (strict mode)
Variants (`#high`) are collapsed to the base model for R1/R2/R4 (R7).

Exit codes: 0 valid or pending (non-strict), 1 violation, 2 strict + unassigned.
"""
from __future__ import annotations

import argparse
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


def base(model: str | None) -> str | None:
    if not model:
        return None
    return model.split("#", 1)[0].strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="fail if any role has no explicit model")
    parser.add_argument("--agents-dir", default=None, help="override .opencode/agents")
    args = parser.parse_args()

    root = pathlib.Path(__file__).resolve().parent.parent
    agents_dir = pathlib.Path(args.agents_dir) if args.agents_dir else root / ".opencode" / "agents"

    models = {role: agent_model(agents_dir / f"{role}.md") for role in ROLES}
    bases = {role: base(model) for role, model in models.items()}

    print("role                 model")
    print("-------------------- ------------------------------------------------")
    for role in ROLES:
        print(f"{role:20} {models[role] or '<unset>'}")

    pending = [role for role in ROLES if not models[role]]
    violations: list[str] = []

    for exclusive in EXCLUSIVE:
        if bases[exclusive] is None:
            continue
        for role in ROLES:
            if role == exclusive or bases[role] is None:
                continue
            if bases[role] == bases[exclusive]:
                violations.append(
                    f"{exclusive} model '{bases[exclusive]}' is also used by {role} "
                    f"(R1/R2: exclusive role)"
                )

    for coder in ("coder-primary", "coder-secondary"):
        if bases["qaqc"] is not None and bases[coder] is not None and bases["qaqc"] == bases[coder]:
            violations.append(
                f"qaqc model '{bases['qaqc']}' is the same base as {coder} "
                f"(R4/R5: the coder cannot check its own work)"
            )

    if violations:
        print("\nVIOLATIONS")
        for violation in violations:
            print(f"  - {violation}")
        return 1

    if pending:
        print(f"\nPENDING: {len(pending)} role(s) have no explicit model: {', '.join(pending)}")
        print("Apply MODEL_POLICY.md when the active agent is free.")
        return 2 if args.strict else 0

    print("\nPASS: role-model exclusivity holds (R1, R2, R4, R6).")
    print("Reminder: the auditor must be the project's strongest reasoning model (R3).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
