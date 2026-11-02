#!/usr/bin/env python3
"""Claims-ledger enforcement for gfx1150-inference.

Phase 7A-6 work package. Audit trace: AUD-3 (G0 audit), T-7 (claims ledger had no
enforcement), C-AUD-3. Implements the enforcement contract in
``PHASE7_IMPLEMENTATION_HANDOFF.md`` §10.

Model
-----

The ledger's main table is the source of truth. Each row carries:

``Status``
    ``VERIFIED`` / ``PARTIAL`` / ``NOT YET`` / ``UNVERIFIED`` / ``REMOVED``.
``Public match (literal)``
    One or more backticked phrases the claim depends on.
``Qualified in place?``
    ``**<flag>** (<scope>) -- prose``.

    *flag* is ``yes`` / ``no`` / ``partial`` / ``n/a``: is the claim qualified
    where it is published?

    *scope* is a machine-readable inventory of every place where the claim's
    literal occurs in the public documents::

        **no** (unqualified: README.md:10; context: PLAN.md:25,165) -- prose

    Three kinds of site are recorded:

    ``unqualified:``
        the claim is asserted here **without** a caveat. These are the ratchet
        items: each needs a matching ``(claim-id, path, literal)`` entry in
        ``audit/claims_baseline.txt``.
    ``qualified:``
        the claim is asserted here and qualified in place.
    ``context:``
        the literal occurs here but the text does not assert this claim
        (planning/status prose). The row's "Scope / limit" column explains why.

    Every occurrence of the literal must be inventoried in exactly one of the
    three lists. An occurrence the ledger does not know about is a new,
    unreviewed assertion of the claim, so a violation cannot hide behind a line
    shift or a second mention of the same literal.

Checks
------

1. The ledger parses; every row has a valid status, flag, scope and literal.
2. A ``VERIFIED`` row cites evidence that exists on disk, and its literal still
   resolves in a public document.
3. Every occurrence of an unproven claim's literal in ``README.md`` /
   ``IMPLEMENTATION_PLAN.md`` is inventoried in the row's scope.
   * Not inventoried -> new violation.
   * Inventoried as ``unqualified`` -> ratchet item; tolerated only while the
     exact ``(claim-id, path, literal)`` triple is in the baseline.
   * Inventoried as ``qualified``/``context`` -> not a violation.
4. Every scope site still contains the literal: the ledger must follow the
   documents. A site that drifted is reported so its line reference can be
   refreshed.
5. No row uses a known-generic literal (``GPU``, ``pip install``, ...): those
   do not enforce their claim (AUD-3, brief pitfall 3).

``--strict`` ignores the baseline entirely and fails on every unqualified
site: that is the G6 release gate, where the baseline must be empty and every
unqualified site must be gone.

The checker uses the standard library only, so it runs in the CPU CI job, which
does not install pytest.

Usage::

    python3 scripts/qa/check_claims.py                # default (baseline-aware)
    python3 scripts/qa/check_claims.py --strict       # release gate (G6)
    python3 scripts/qa/check_claims.py --json         # machine-readable output
    python3 scripts/qa/check_claims.py --root DIR     # check a copy of the tree

Exit codes: ``0`` clean, ``1`` violations found, ``2`` checker error.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Iterable, Sequence

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

LEDGER_RELPATH = os.path.join("audit", "CLAIMS_LEDGER.md")
BASELINE_RELPATH = os.path.join("audit", "claims_baseline.txt")

#: The documents that make public claims.
PUBLIC_DOCS = ("README.md", "IMPLEMENTATION_PLAN.md")

VALID_STATUSES = ("VERIFIED", "PARTIAL", "NOT YET", "UNVERIFIED", "REMOVED")

FLAG_YES = "yes"
FLAG_NO = "no"
FLAG_PARTIAL = "partial"
FLAG_NA = "n/a"
VALID_FLAGS = (FLAG_YES, FLAG_NO, FLAG_PARTIAL, FLAG_NA)

#: Statuses whose claims are not (yet) proven. Their literals are inventoried.
UNPROVEN_STATUSES = ("PARTIAL", "NOT YET", "UNVERIFIED")

#: Marker for a row that has no public literal at all (planning/audit text only).
NO_PUBLIC_LITERAL = "no public literal"

#: Literals that are too generic to enforce their claim (AUD-3, pitfall 3).
GENERIC_LITERALS = (
    "GPU",
    "pip install",
    "llama-family",
    "test_cpu_only.py",
)

#: Ledger table header; parsing starts here and stops at the first non-table line.
LEDGER_HEADER = "| ID | Claim | Status |"

_BASELINE_LINE = re.compile(r"^\s*(\d+)\s+(\S+)\s+(.+?)\s*$")

#: A scope site: ``PATH:LINE``.
_SCOPE_SITE = re.compile(r"^([A-Za-z0-9_./-]+):(\d+)$")

#: A continuation line number for the previous path: ``LINE``.
_SCOPE_LINE = re.compile(r"^(\d+)$")

#: The parenthesised scope group that follows the flag.
_SCOPE_GROUP = re.compile(r"^\(([^()]*)\)")

#: Scope labels and the attribute they set.
_LABEL_UNQUALIFIED = "unqualified"
_LABEL_QUALIFIED = "qualified"
_LABEL_CONTEXT = "context"
_SCOPE_LABELS = (_LABEL_UNQUALIFIED, _LABEL_QUALIFIED, _LABEL_CONTEXT)


class CheckerError(Exception):
    """Raised for a malformed ledger/baseline that makes the check meaningless."""


@dataclass(frozen=True)
class Site:
    """One inventoried occurrence of a claim's literal."""

    path: str
    line_no: int
    kind: str
    """``unqualified``, ``qualified`` or ``context``."""

    @property
    def unqualified(self) -> bool:
        return self.kind == _LABEL_UNQUALIFIED

    def __str__(self) -> str:
        return f"{self.path}:{self.line_no}"


@dataclass(frozen=True)
class Claim:
    """One row of the claims ledger's main table."""

    id: int
    claim: str
    status: str
    literals: tuple[str, ...]
    flag: str
    sites: tuple[Site, ...]
    evidence: str
    scope_note: str
    line_no: int

    @property
    def is_scanned(self) -> bool:
        """True when the row's literal is inventoried in the public documents."""
        return self.status in UNPROVEN_STATUSES and bool(self.literals)

    @property
    def unqualified_sites(self) -> tuple[Site, ...]:
        return tuple(s for s in self.sites if s.unqualified)


@dataclass
class Violation:
    """A public occurrence of an unqualified claim."""

    claim_id: int
    path: str
    literal: str
    line_no: int
    baselined: bool = False
    kind: str = "unqualified"
    """``unqualified`` for an inventoried ratchet item, ``unaccounted`` for an
    occurrence the ledger does not know about."""


@dataclass
class Finding:
    """A problem the checker reports."""

    kind: str
    detail: str
    claim_id: int | None = None


@dataclass
class Report:
    """Everything the checker learned, for rendering or JSON output."""

    claims: list[Claim] = field(default_factory=list)
    violations: list[Violation] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    expired_baseline: list[tuple[int, str, str]] = field(default_factory=list)

    @property
    def new_violations(self) -> list[Violation]:
        return [v for v in self.violations if not v.baselined]


# --------------------------------------------------------------------------- #
# Ledger parsing
# --------------------------------------------------------------------------- #


def _split_table_row(line: str) -> list[str]:
    """Split a Markdown table row into cells, honouring ``\\|`` escapes."""
    protected = line.replace("\\|", "\x00")
    cells = protected.split("|")
    if cells and cells[0].strip() == "":
        cells = cells[1:]
    if cells and cells[-1].strip() == "":
        cells = cells[:-1]
    return [c.replace("\x00", "\\|").strip() for c in cells]


def _extract_literals(cell: str) -> tuple[str, ...]:
    """Return every backticked phrase in a "Public match (literal)" cell."""
    if NO_PUBLIC_LITERAL in cell.lower():
        return ()
    return tuple(re.findall(r"`([^`]+)`", cell))


def _parse_scope_group(text: str) -> list[Site]:
    """Parse the scope group that follows the flag.

    Grammar::

        group := '(' label ':' site { ',' site } { ';' label ':' site { ',' site } } ')'
        label := 'unqualified' | 'qualified' | 'context'
        site  := PATH ':' LINE | LINE

    A bare ``LINE`` continues the previous path, so ``PLAN.md:25,165`` means
    ``PLAN.md:25`` and ``PLAN.md:165``.

    Returns the list of sites, in the order they appear.
    """
    match = _SCOPE_GROUP.match(text)
    if not match:
        return []

    sites: list[Site] = []
    seen_labels: set[str] = set()
    current_path: str | None = None

    for chunk in match.group(1).split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        label, sep, rest = chunk.partition(":")
        label = label.strip().lower()
        if not sep or label not in _SCOPE_LABELS:
            raise CheckerError(
                f"unreadable scope group {match.group(0)!r}: expected one of "
                f"{', '.join(_SCOPE_LABELS)} labels"
            )
        if label in seen_labels:
            raise CheckerError(f"duplicate scope label {label!r} in {match.group(0)!r}")
        seen_labels.add(label)
        current_path = None
        for token in (t.strip() for t in rest.split(",")):
            if not token:
                continue
            site_match = _SCOPE_SITE.match(token)
            if site_match:
                current_path = site_match.group(1)
                line_no = int(site_match.group(2))
            else:
                line_match = _SCOPE_LINE.match(token)
                if not line_match or current_path is None:
                    raise CheckerError(
                        f"unreadable scope site {token!r}: expected 'PATH:LINE'"
                    )
                line_no = int(line_match.group(1))
            sites.append(Site(path=current_path, line_no=line_no, kind=label))

    return sites


def _extract_flag_and_scope(cell: str) -> tuple[str, list[Site]]:
    """Return ``(flag, sites)`` from a "Qualified in place?" cell.

    The cell begins with the flag, optionally followed by the parenthesised
    scope group, then free prose explaining the decision.
    """
    cell = cell.strip()
    flag = ""
    match = None
    for candidate in VALID_FLAGS:
        # The flag is the leading token, optionally wrapped in Markdown emphasis
        # ("**no**"). The emphasis is matched explicitly rather than with an
        # optional group, so the match always consumes it.
        match = re.match(
            r"^(?:\*\*\s*)?"
            + re.escape(candidate)
            + r"(?:\s*\*\*)?(?![A-Za-z0-9_])",
            cell,
            re.IGNORECASE,
        )
        if match:
            flag = candidate
            break
    if not flag:
        return "", []

    rest = cell[match.end():].lstrip()
    return flag, _parse_scope_group(rest)


def parse_ledger(path: str) -> list[Claim]:
    """Parse the main claims table from the ledger.

    Only the main table is parsed: parsing starts at the
    ``| ID | Claim | Status |`` header and stops at the first line that is not
    a table row. The ratchet sub-tables further down the file are prose about
    the baseline, not claims.
    """
    try:
        with open(path, "r", encoding="utf-8") as handle:
            lines = handle.read().splitlines()
    except OSError as exc:
        raise CheckerError(f"cannot read ledger {path}: {exc}") from exc

    try:
        start = next(i for i, line in enumerate(lines) if line.startswith(LEDGER_HEADER))
    except StopIteration:
        raise CheckerError(
            f"{path}: main ledger table header {LEDGER_HEADER!r} not found"
        ) from None

    claims: list[Claim] = []
    seen_ids: set[int] = set()
    for index in range(start + 2, len(lines)):
        line = lines[index]
        if not line.startswith("|"):
            break  # end of the main table
        cells = _split_table_row(line)
        if len(cells) != 7:
            raise CheckerError(
                f"{path}:{index + 1}: expected 7 columns, found {len(cells)}: {line!r}"
            )
        try:
            claim_id = int(cells[0])
        except ValueError:
            raise CheckerError(
                f"{path}:{index + 1}: ID is not an integer: {cells[0]!r}"
            ) from None
        if claim_id in seen_ids:
            raise CheckerError(f"{path}:{index + 1}: duplicate claim ID {claim_id}")
        seen_ids.add(claim_id)

        flag, sites = _extract_flag_and_scope(cells[4])
        claims.append(
            Claim(
                id=claim_id,
                claim=cells[1],
                status=cells[2].strip().strip("*").strip(),
                literals=_extract_literals(cells[3]),
                flag=flag,
                sites=tuple(sites),
                evidence=cells[5],
                scope_note=cells[6],
                line_no=index + 1,
            )
        )

    if not claims:
        raise CheckerError(f"{path}: main ledger table is empty")
    return claims


def parse_baseline(path: str) -> list[tuple[int, str, str]]:
    """Parse the ratchet baseline into ``(claim-id, path, literal)`` triples.

    Comments and blank lines are ignored. A malformed entry is an error: a
    wildcard or a sloppy line would silently widen the ratchet, which is exactly
    what the baseline exists to prevent.
    """
    try:
        with open(path, "r", encoding="utf-8") as handle:
            lines = handle.read().splitlines()
    except OSError as exc:
        raise CheckerError(f"cannot read baseline {path}: {exc}") from exc

    entries: list[tuple[int, str, str]] = []
    for index, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _BASELINE_LINE.match(stripped)
        if not match:
            raise CheckerError(
                f"{path}:{index}: malformed baseline entry "
                f"(expected '<claim-id> <path> <literal>'): {stripped!r}"
            )
        claim_id = int(match.group(1))
        path_text = match.group(2)
        literal = match.group(3)
        if any(ch in literal for ch in "*?["):
            raise CheckerError(
                f"{path}:{index}: wildcard entries are not allowed: {stripped!r}"
            )
        entries.append((claim_id, path_text, literal))
    return entries


# --------------------------------------------------------------------------- #
# Scanning
# --------------------------------------------------------------------------- #


def _read_doc(path: str) -> list[str]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read().splitlines()
    except OSError as exc:
        raise CheckerError(f"cannot read {path}: {exc}") from exc


def _evidence_paths(evidence_cell: str) -> list[str]:
    """Extract repo-relative evidence paths from an Evidence cell.

    Only backticked tokens that look like paths are considered; prose such as
    ``verification §3.2`` is ignored.
    """
    return [
        token
        for token in re.findall(r"`([^`]+)`", evidence_cell)
        if "/" in token and re.search(r"\.[A-Za-z0-9]+$", token)
    ]


def _occurrences(doc_lines: Sequence[str], literal: str) -> list[int]:
    return [i for i, line in enumerate(doc_lines, 1) if literal in line]


def _match_sites_to_occurrences(
    sites: Sequence[Site], occurrences: Sequence[int]
) -> tuple[dict[Site, int], list[int]]:
    """Match scope sites to the occurrences of the claim's literal.

    Equal counts mean the document may simply have shifted (a line inserted
    above the site), so the two lists are paired in order and the difference is
    reported as drift. Unequal counts mean something was really added or
    removed: only exact line matches are honoured and the remainder is
    returned, so a new occurrence can never be absorbed as drift.
    """
    if len(sites) == len(occurrences):
        return dict(zip(sites, occurrences)), []

    matches: dict[Site, int] = {}
    remaining_occ = list(occurrences)
    for site in sites:
        if site.line_no in remaining_occ:
            remaining_occ.remove(site.line_no)
            matches[site] = site.line_no
    return matches, remaining_occ


def scan_claims(
    claims: Sequence[Claim],
    baseline: Iterable[tuple[int, str, str]],
    docs: dict[str, list[str]],
    root: str,
) -> Report:
    """Scan the public documents and collect violations, findings and warnings."""
    report = Report(claims=list(claims))
    baselined = set(baseline)

    for claim in claims:
        # --- row integrity -------------------------------------------------
        if claim.status not in VALID_STATUSES:
            report.findings.append(
                Finding(
                    "invalid-status",
                    f"claim {claim.id}: unknown status {claim.status!r} "
                    f"(expected one of {', '.join(VALID_STATUSES)})",
                    claim.id,
                )
            )
            continue
        if not claim.flag:
            report.findings.append(
                Finding(
                    "invalid-flag",
                    f"claim {claim.id}: unreadable 'Qualified in place?' flag "
                    f"(expected one of {', '.join(VALID_FLAGS)})",
                    claim.id,
                )
            )
            continue

        for literal in claim.literals:
            if literal in GENERIC_LITERALS:
                report.findings.append(
                    Finding(
                        "generic-literal",
                        f"claim {claim.id}: literal {literal!r} is too generic to "
                        f"enforce the claim; use a claim-specific phrase",
                        claim.id,
                    )
                )

        if claim.status == "VERIFIED":
            for evidence_path in _evidence_paths(claim.evidence):
                if not os.path.exists(os.path.join(root, evidence_path)):
                    report.findings.append(
                        Finding(
                            "missing-evidence",
                            f"claim {claim.id}: VERIFIED but evidence path does not "
                            f"exist: {evidence_path}",
                            claim.id,
                        )
                    )
            # A VERIFIED claim's literal must still resolve publicly, otherwise
            # the row is stale: the claim was removed from the public docs.
            for literal in claim.literals:
                if not any(_occurrences(lines, literal) for lines in docs.values()):
                    report.findings.append(
                        Finding(
                            "unresolved-literal",
                            f"claim {claim.id}: public match {literal!r} does not "
                            f"appear in any public document",
                            claim.id,
                        )
                    )
            if claim.sites:
                report.findings.append(
                    Finding(
                        "unexpected-scope",
                        f"claim {claim.id}: a VERIFIED row needs no scope sites",
                        claim.id,
                    )
                )
            continue

        if claim.flag == FLAG_NA:
            # Not published publicly: there is nothing to scan.
            if claim.sites:
                report.findings.append(
                    Finding(
                        "unexpected-scope",
                        f"claim {claim.id}: flag is 'n/a' but scope sites are named",
                        claim.id,
                    )
                )
            continue

        if not claim.is_scanned:
            # No public literal: a planning/audit row, nothing to scan.
            if claim.sites:
                report.findings.append(
                    Finding(
                        "unexpected-scope",
                        f"claim {claim.id}: flag is '{claim.flag}' but scope sites "
                        f"are named",
                        claim.id,
                    )
                )
            continue

        # --- scope integrity ----------------------------------------------
        for site in claim.sites:
            if site.path not in docs:
                report.findings.append(
                    Finding(
                        "unknown-scope-path",
                        f"claim {claim.id}: scope names {site.path!r}, which is not "
                        f"a public document",
                        claim.id,
                    )
                )

        if claim.flag == FLAG_NO and not claim.unqualified_sites:
            report.findings.append(
                Finding(
                    "missing-scope",
                    f"claim {claim.id}: flag is 'no' but no unqualified site is named",
                    claim.id,
                )
            )
        if claim.flag == FLAG_PARTIAL and not claim.unqualified_sites:
            report.warnings.append(
                f"claim {claim.id}: flag is 'partial' with no unqualified site; the "
                f"caveat wording is incomplete (a wording task, not a ratchet item)"
            )
        if claim.flag == FLAG_YES and claim.unqualified_sites:
            report.findings.append(
                Finding(
                    "unexpected-scope",
                    f"claim {claim.id}: flag is 'yes' but an unqualified site is named",
                    claim.id,
                )
            )

        # --- occurrence inventory ------------------------------------------
        # Every occurrence of the literal must be accounted for by a scope
        # site. Occurrences that no site claims are new assertions of the
        # claim that nobody reviewed, and they fail the default mode.
        occ_lines: dict[str, list[int]] = {path: [] for path in docs}
        literal_at: dict[tuple[str, int], set[str]] = {}
        for literal in claim.literals:
            for path, doc_lines in docs.items():
                for line_no in _occurrences(doc_lines, literal):
                    if line_no not in occ_lines[path]:
                        occ_lines[path].append(line_no)
                    literal_at.setdefault((path, line_no), set()).add(literal)

        for path in docs:
            sites_here = sorted(
                (s for s in claim.sites if s.path == path), key=lambda s: s.line_no
            )
            occ_here = sorted(occ_lines[path])

            matches, leftover_occ = _match_sites_to_occurrences(sites_here, occ_here)

            for site in sites_here:
                if site not in matches:
                    report.findings.append(
                        Finding(
                            "stale-scope",
                            f"claim {claim.id}: scope {site} no longer contains the "
                            f"literal; the claim moved or was qualified",
                            claim.id,
                        )
                    )
                elif matches[site] != site.line_no:
                    report.warnings.append(
                        f"claim {claim.id}: scope {site} drifted to "
                        f"{path}:{matches[site]}; refresh the line reference"
                    )

            # Occurrences with no site: a new assertion nobody reviewed.
            for line_no in leftover_occ:
                literals_here = sorted(literal_at[(path, line_no)])
                report.violations.append(
                    Violation(
                        claim_id=claim.id,
                        path=path,
                        literal=literals_here[0],
                        line_no=line_no,
                        baselined=False,
                        kind="unaccounted",
                    )
                )

            # Inventoried unqualified sites are the ratchet items.
            for site in sites_here:
                if not site.unqualified or site not in matches:
                    continue
                line_no = matches[site]
                literals_here = sorted(literal_at[(path, line_no)])
                literal = next(
                    (lit for lit in literals_here if (claim.id, path, lit) in baselined),
                    literals_here[0],
                )
                report.violations.append(
                    Violation(
                        claim_id=claim.id,
                        path=path,
                        literal=literal,
                        line_no=line_no,
                        baselined=(claim.id, path, literal) in baselined,
                        kind="unqualified",
                    )
                )

        # A literal that vanished entirely: the ledger must follow the docs.
        for literal in claim.literals:
            if not any(_occurrences(lines, literal) for lines in docs.values()):
                report.findings.append(
                    Finding(
                        "unresolved-literal",
                        f"claim {claim.id}: public match {literal!r} does not "
                        f"appear in any public document",
                        claim.id,
                    )
                )

    # Baseline entries that no longer correspond to an unqualified site.
    live_unqualified: set[tuple[int, str]] = set()
    for claim in claims:
        for site in claim.unqualified_sites:
            live_unqualified.add((claim.id, site.path))
    for claim_id, path_text, literal in baseline:
        if (claim_id, path_text) not in live_unqualified:
            report.expired_baseline.append((claim_id, path_text, literal))

    # Baseline entries whose literal does not belong to the claim they name.
    claim_literals = {claim.id: claim.literals for claim in claims}
    for claim_id, path_text, literal in baseline:
        literals = claim_literals.get(claim_id)
        if literals is None:
            report.findings.append(
                Finding(
                    "baseline-unknown-claim",
                    f"baseline: entry {claim_id} {path_text} {literal!r} names a "
                    f"claim that is not in the ledger",
                )
            )
        elif literal not in literals:
            report.findings.append(
                Finding(
                    "baseline-literal-mismatch",
                    f"baseline: entry {claim_id} {path_text} {literal!r} does not "
                    f"match the claim's public match "
                    f"({', '.join(repr(lit) for lit in literals)})",
                )
            )

    return report


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #


def _render(report: Report, strict: bool) -> str:
    out: list[str] = []
    out.append("=== Claims ledger check ===")
    out.append(
        f"mode:        {'strict (baseline ignored)' if strict else 'default (baseline-aware)'}"
    )
    out.append(f"claims:      {len(report.claims)} rows parsed")
    out.append("")

    out.append("--- unqualified public claims (the ratchet) ---")
    if not report.violations:
        out.append("  none")
    else:
        by_claim: dict[int, list[Violation]] = {}
        for violation in report.violations:
            by_claim.setdefault(violation.claim_id, []).append(violation)
        for claim_id in sorted(by_claim):
            group = by_claim[claim_id]
            claim = next(c for c in report.claims if c.id == claim_id)
            state = "BASELINED" if all(v.baselined for v in group) else "NEW"
            out.append(f"  claim {claim_id} [{state}]: {claim.claim}")
            for violation in group:
                if violation.kind == "unaccounted":
                    marker = "NEW VIOLATION (not inventoried in the ledger)"
                else:
                    marker = "baselined" if violation.baselined else "NEW VIOLATION"
                out.append(
                    f"      {violation.path}:{violation.line_no}  "
                    f"{violation.literal!r}  ({marker})"
                )
    out.append("")

    out.append("--- baseline entries that no longer match a violation ---")
    if not report.expired_baseline:
        out.append("  none")
    else:
        for claim_id, path_text, literal in report.expired_baseline:
            out.append(
                f"  claim {claim_id}: {path_text} {literal!r} - expired, remove it"
            )
    out.append("")

    if report.warnings:
        out.append("--- warnings ---")
        for warning in report.warnings:
            out.append(f"  {warning}")
        out.append("")

    out.append("--- findings ---")
    if not report.findings:
        out.append("  none")
    else:
        for finding in report.findings:
            out.append(f"  [{finding.kind}] {finding.detail}")
    out.append("")

    if strict:
        failed = _failed(report, strict)
        out.append(
            f"RESULT: {'FAIL' if failed else 'PASS'} - "
            f"{len(report.violations)} unqualified occurrence(s) "
            f"(strict mode ignores the baseline)"
        )
    else:
        failed = _failed(report, strict)
        new_count = len(report.new_violations)
        out.append(
            f"RESULT: {'FAIL' if failed else 'PASS'} - "
            f"{new_count} new violation(s), "
            f"{len(report.violations) - new_count} baselined, "
            f"{len(report.expired_baseline)} expired baseline entry(ies), "
            f"{len(report.findings)} finding(s)"
        )
    return "\n".join(out)


def _failed(report: Report, strict: bool) -> bool:
    """True when the run must fail: the single source of truth for the exit code."""
    if strict:
        return bool(report.violations) or bool(report.findings)
    return bool(report.new_violations) or bool(report.findings)


def _render_json(report: Report, strict: bool) -> str:
    payload = {
        "mode": "strict" if strict else "default",
        "ok": not _failed(report, strict),
        "claims": len(report.claims),
        "violations": [
            {
                "claim_id": v.claim_id,
                "path": v.path,
                "line": v.line_no,
                "literal": v.literal,
                "baselined": v.baselined,
                "kind": v.kind,
            }
            for v in report.violations
        ],
        "expired_baseline": [
            {"claim_id": cid, "path": p, "literal": lit}
            for cid, p, lit in report.expired_baseline
        ],
        "findings": [
            {"kind": f.kind, "detail": f.detail, "claim_id": f.claim_id}
            for f in report.findings
        ],
        "warnings": report.warnings,
    }
    return json.dumps(payload, indent=2, sort_keys=True)


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #


def run(root: str) -> Report:
    """Run the check against a tree and return the report."""
    ledger_path = os.path.join(root, LEDGER_RELPATH)
    baseline_path = os.path.join(root, BASELINE_RELPATH)
    claims = parse_ledger(ledger_path)
    baseline = parse_baseline(baseline_path)
    docs = {
        name: _read_doc(os.path.join(root, name))
        for name in PUBLIC_DOCS
        if os.path.exists(os.path.join(root, name))
    }
    return scan_claims(claims, baseline, docs, root)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--strict",
        action="store_true",
        help="ignore the baseline entirely and fail on every violation (G6 release gate)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit machine-readable JSON instead of the human-readable output",
    )
    parser.add_argument(
        "--root",
        default=REPO_ROOT,
        help="root of the tree to check (default: this repository)",
    )
    args = parser.parse_args(argv)

    try:
        report = run(args.root)
    except CheckerError as exc:
        print(f"check_claims: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(_render_json(report, args.strict))
    else:
        print(_render(report, args.strict))

    return 1 if _failed(report, args.strict) else 0

if __name__ == "__main__":
    sys.exit(main())
