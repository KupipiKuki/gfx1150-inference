#!/usr/bin/env python3
"""check_bundle.py — evidence-packaging invariant checker.

Usage:
    python3 workflow/tools/check_bundle.py <bundle-dir> [--json]
    python3 workflow/tools/check_bundle.py --all [--json] [--strict]
    python3 workflow/tools/check_bundle.py --self-test

Exit codes:
    0  no FAIL findings
    1  at least one FAIL finding
    2  usage error

Output is deterministic: no timestamps, no absolute paths, stable ordering.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

CODES = [
    "B1-structure",
    "B2-hash-verify",
    "B2-legacy-path",
    "B2-external",
    "B2-external-unverifiable",
    "B2-path-spelling",
    "B2-hash-mismatch",
    "B2-missing",
    "B2-prose",
    "B2-malformed",
    "B3-hash-coverage",
    "B3-path-spelling",
    "B3-unlisted",
    "B4-tracked",
    "B5-not-ignored",
    "B6-pins",
    "B7-secrets",
    "B8-read-only",
]

STRICT_UPGRADE_CODES = {
    "B2-legacy-path",
    "B2-external",
    "B2-prose",
    "B3-path-spelling",
}

SECRETS_RE = re.compile(
    r"ghp_[A-Za-z0-9_]{36,}|"
    r"github_pat_[A-Za-z0-9_]{22,}|"
    r"sk-[A-Za-z0-9]{48,}|"
    r"AKIA[0-9A-Z]{16}|"
    r"xox[baprs]-[0-9A-Za-z\-_]+|"
    r"-----BEGIN\s+[^\n]*PRIVATE\s+KEY-----",
    re.IGNORECASE,
)

SECRETS_KV_RE = re.compile(
    r"(?i)(?:api[_-]?key|token|secret)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{20,}",
)

ALLOW_SECRET_RE = re.compile(r"check_bundle:\s*allow-secret\s+(.+)")

# Well-formed sha256sum line: 64 hex lowercase digits followed by exactly two spaces.
HASH_LINE_RE = re.compile(r"^([0-9a-f]{64})  (.+)$")
# A line that looks like it wanted to be a hash but has the wrong separator.
HASH_MALFORMED_RE = re.compile(r"^[0-9a-fA-F]{64}\s*.+$")


def run(cmd: List[str], cwd: Optional[Path] = None, check: bool = False) -> subprocess.CompletedProcess:
    """Run a subprocess and return its result."""
    return subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=check,
    )


def repo_root(cwd: Optional[Path] = None) -> Path:
    """Return the git repository root containing cwd."""
    result = run(["git", "rev-parse", "--show-toplevel"], cwd=cwd)
    if result.returncode != 0:
        raise RuntimeError("not a git repository")
    return Path(result.stdout.strip())


def git_status_porcelain(cwd: Optional[Path] = None) -> str:
    """Return `git status --porcelain` output."""
    result = run(["git", "status", "--porcelain"], cwd=cwd)
    if result.returncode != 0:
        raise RuntimeError("git status failed")
    return result.stdout


def rel_to_repo(path: Path, root: Path) -> str:
    """Return the relative path of `path` from repo `root`, using forward slashes."""
    return path.resolve().relative_to(root.resolve()).as_posix()


def normalize_listed_path(fpath: str, bundle_dir: Path, root: Path) -> str:
    """Return a normalized repo-relative string for a listed path.

    Relative paths keep their POSIX form with leading './' removed.
    Absolute paths are returned unchanged so they never match a repo-relative
    disk file path.
    """
    p = Path(fpath)
    if p.is_absolute():
        return fpath
    rel = fpath
    if rel.startswith("./"):
        rel = rel[2:]
    return rel


def sha256_file(path: Path) -> str:
    """SHA-256 of a file, in hex."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Finding:
    def __init__(self, code: str, status: str, message: str, path: Optional[str] = None):
        self.code = code
        self.status = status  # PASS, WARN, FAIL
        self.message = message
        self.path = path

    def __repr__(self) -> str:
        return f"Finding({self.code}, {self.status}, {self.message})"


def finding_pass(code: str, message: str, path: Optional[str] = None) -> Finding:
    return Finding(code, "PASS", message, path)


def finding_warn(code: str, message: str, path: Optional[str] = None) -> Finding:
    return Finding(code, "WARN", message, path)


def finding_fail(code: str, message: str, path: Optional[str] = None) -> Finding:
    return Finding(code, "FAIL", message, path)


def apply_strict(findings: List[Finding]) -> None:
    """Upgrade selected WARN codes to FAIL when --strict is given."""
    for f in findings:
        if f.status == "WARN" and f.code in STRICT_UPGRADE_CODES:
            f.status = "FAIL"


def check_b1_structure(bundle_dir: Path, root: Path) -> List[Finding]:
    findings: List[Finding] = []
    rel = rel_to_repo(bundle_dir, root)

    manifest = bundle_dir / "manifest.md"
    hashes = bundle_dir / "hashes.txt"

    if not manifest.exists():
        findings.append(finding_warn("B1-structure", "no manifest.md; skipped", rel))
        return findings

    findings.append(finding_pass("B1-structure", "manifest.md exists", rel))

    if not hashes.exists():
        findings.append(finding_fail("B1-structure", "hashes.txt missing", rel))
    else:
        findings.append(finding_pass("B1-structure", "hashes.txt exists", rel))

    # "manifest declares commands" if it references commands.log
    manifest_text = manifest.read_text(encoding="utf-8", errors="replace")
    if "commands.log" in manifest_text:
        commands_log = bundle_dir / "commands.log"
        if not commands_log.exists():
            findings.append(finding_fail("B1-structure", "manifest declares commands but commands.log missing", rel))
        else:
            findings.append(finding_pass("B1-structure", "commands.log exists", rel))

    return findings


def check_b2_hash_verify(
    bundle_dir: Path, root: Path
) -> Tuple[List[Finding], Set[str], Set[str], Set[str]]:
    """Verify hashes.txt lines.

    Returns (findings, resolved_paths, exact_paths, listed_basenames).
    resolved_paths: repo-relative paths of actual files a listed line resolved to.
    exact_paths: normalized listed path strings that literally match a disk file.
    listed_basenames: basenames of every listed hash line.
    """
    findings: List[Finding] = []
    rel = rel_to_repo(bundle_dir, root)
    hashes = bundle_dir / "hashes.txt"

    resolved_paths: Set[str] = set()
    exact_paths: Set[str] = set()
    listed_basenames: Set[str] = set()

    if not hashes.exists():
        return findings, resolved_paths, exact_paths, listed_basenames

    root_resolved = root.resolve()
    bundle_resolved = bundle_dir.resolve()

    for raw_line in hashes.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.rstrip()
        if not line or line.startswith("#"):
            continue

        match = HASH_LINE_RE.match(line)
        if not match:
            if HASH_MALFORMED_RE.match(line):
                findings.append(finding_fail("B2-malformed", f"malformed hashes.txt line: {line!r}", rel))
            else:
                findings.append(finding_warn("B2-prose", f"not a hash line: {line!r}", rel))
            continue

        digest, fpath = match.group(1), match.group(2)
        listed_basenames.add(Path(fpath).name)
        normalized = normalize_listed_path(fpath, bundle_dir, root)

        target: Optional[Path] = None
        resolved_repo_path: Optional[str] = None
        mismatch_at_exact_or_legacy = False

        # a) path exists relative to the repo root (canonical). Absolute paths
        # that resolve inside the repo are treated as canonical as well.
        if target is None:
            if Path(fpath).is_absolute():
                repo_target = Path(fpath)
                try:
                    repo_target.resolve().relative_to(root_resolved)
                    is_repo_path = True
                except ValueError:
                    is_repo_path = False
            else:
                repo_target = root / fpath
                is_repo_path = True

            if is_repo_path and repo_target.exists() and repo_target.is_file():
                actual = sha256_file(repo_target)
                if actual == digest:
                    target = repo_target
                    resolved_repo_path = rel_to_repo(repo_target, root)
                    exact_paths.add(normalized)
                    findings.append(finding_pass("B2-hash-verify", f"ok: {fpath}", rel))
                else:
                    findings.append(
                        finding_fail(
                            "B2-hash-mismatch",
                            f"{fpath} (actual: {actual})",
                            rel,
                        )
                    )
                    mismatch_at_exact_or_legacy = True

        # b) path exists relative to the bundle dir (legacy spelling).
        if target is None and not mismatch_at_exact_or_legacy and not Path(fpath).is_absolute():
            bundle_target = bundle_dir / fpath
            if bundle_target.exists() and bundle_target.is_file():
                actual = sha256_file(bundle_target)
                if actual == digest:
                    target = bundle_target
                    resolved_repo_path = rel_to_repo(bundle_target, root)
                    findings.append(
                        finding_pass("B2-hash-verify", f"ok: {fpath}", rel)
                    )
                    findings.append(
                        finding_warn("B2-legacy-path", f"{fpath}", rel)
                    )
                else:
                    findings.append(
                        finding_fail(
                            "B2-hash-mismatch",
                            f"{fpath} (actual: {actual})",
                            rel,
                        )
                    )
                    mismatch_at_exact_or_legacy = True

        # c/c') absolute path outside the repo.
        if target is None and Path(fpath).is_absolute():
            abs_target = Path(fpath)
            try:
                abs_resolved = abs_target.resolve()
            except (OSError, RuntimeError):
                abs_resolved = abs_target
            try:
                is_inside_repo = abs_resolved.relative_to(root_resolved) is not None
            except ValueError:
                is_inside_repo = False
            if not is_inside_repo:
                if abs_target.exists() and abs_target.is_file():
                    try:
                        actual = sha256_file(abs_target)
                    except (OSError, PermissionError):
                        actual = None
                    if actual == digest:
                        findings.append(
                            finding_pass("B2-hash-verify", f"ok: {fpath}", rel)
                        )
                        findings.append(
                            finding_warn("B2-external", f"{fpath}", rel)
                        )
                    elif actual is not None:
                        findings.append(
                            finding_fail(
                                "B2-hash-mismatch",
                                f"{fpath} (actual: {actual})",
                                rel,
                            )
                        )
                    else:
                        findings.append(
                            finding_warn("B2-external-unverifiable", f"{fpath}", rel)
                        )
                else:
                    findings.append(
                        finding_warn("B2-external-unverifiable", f"{fpath}", rel)
                    )
                continue

        # d/d') basename fallback under the bundle dir.
        if target is None and not mismatch_at_exact_or_legacy:
            basename = Path(fpath).name
            candidates = sorted(p for p in bundle_dir.rglob(basename) if p.is_file())
            if candidates:
                # Prefer the first candidate whose digest matches; otherwise
                # report mismatch against the first candidate.
                matched = None
                mismatch_actual = None
                for cand in candidates:
                    actual = sha256_file(cand)
                    if actual == digest:
                        matched = cand
                        break
                    if mismatch_actual is None:
                        mismatch_actual = actual
                if matched is not None:
                    target = matched
                    resolved_repo_path = rel_to_repo(matched, root)
                    actual_path = rel_to_repo(matched, root)
                    findings.append(
                        finding_pass("B2-hash-verify", f"ok: {fpath}", rel)
                    )
                    findings.append(
                        finding_warn(
                            "B2-path-spelling",
                            f"{fpath} -> {actual_path}",
                            rel,
                        )
                    )
                else:
                    findings.append(
                        finding_fail(
                            "B2-hash-mismatch",
                            f"{fpath} (actual: {mismatch_actual})",
                            rel,
                        )
                    )
            else:
                findings.append(finding_fail("B2-missing", f"{fpath}", rel))

        if resolved_repo_path is not None:
            resolved_paths.add(resolved_repo_path)

    return findings, resolved_paths, exact_paths, listed_basenames


def check_b3_hash_coverage(
    bundle_dir: Path,
    root: Path,
    resolved_paths: Set[str],
    exact_paths: Set[str],
    listed_basenames: Set[str],
) -> List[Finding]:
    findings: List[Finding] = []
    rel = rel_to_repo(bundle_dir, root)

    coverage_warns: List[Finding] = []
    coverage_fails: List[Finding] = []

    for current in sorted(bundle_dir.rglob("*")):
        if not current.is_file():
            continue
        fpath = rel_to_repo(current, root)
        if fpath.endswith("hashes.txt"):
            continue
        if fpath in exact_paths:
            continue
        if fpath in resolved_paths:
            coverage_warns.append(
                finding_warn(
                    "B3-path-spelling",
                    f"{fpath}",
                    rel,
                )
            )
            continue
        basename = current.name
        if basename in listed_basenames:
            coverage_warns.append(
                finding_warn(
                    "B3-path-spelling",
                    f"{fpath}",
                    rel,
                )
            )
        else:
            coverage_fails.append(
                finding_fail(
                    "B3-unlisted",
                    f"{fpath}",
                    rel,
                )
            )

    findings.extend(coverage_warns)
    findings.extend(coverage_fails)

    if not coverage_warns and not coverage_fails:
        findings.append(finding_pass("B3-hash-coverage", "all files listed", rel))

    return findings


def check_b4_tracked(bundle_dir: Path, root: Path) -> List[Finding]:
    findings: List[Finding] = []
    rel = rel_to_repo(bundle_dir, root)

    files: List[Path] = []
    for p in sorted(bundle_dir.rglob("*")):
        if p.is_file():
            files.append(p)

    untracked: List[str] = []
    for f in files:
        fpath = rel_to_repo(f, root)
        result = run(["git", "ls-files", "--error-unmatch", fpath], cwd=root)
        if result.returncode != 0:
            untracked.append(fpath)

    if untracked:
        for fpath in untracked:
            findings.append(finding_fail("B4-tracked", f"not tracked: {fpath}", rel))
    else:
        findings.append(finding_pass("B4-tracked", "all files tracked", rel))

    status = run(["git", "status", "--porcelain", rel], cwd=root)
    if status.stdout.strip():
        findings.append(finding_fail("B4-tracked", f"git status not clean for bundle", rel))
    else:
        findings.append(finding_pass("B4-tracked", "git status clean", rel))

    return findings


def check_b5_not_ignored(bundle_dir: Path, root: Path) -> List[Finding]:
    findings: List[Finding] = []
    rel = rel_to_repo(bundle_dir, root)

    ignored: List[str] = []
    for f in sorted(bundle_dir.rglob("*")):
        if not f.is_file():
            continue
        fpath = rel_to_repo(f, root)
        result = run(["git", "check-ignore", fpath], cwd=root)
        if result.returncode == 0:
            ignored.append(fpath)

    if ignored:
        for fpath in ignored:
            findings.append(finding_fail("B5-not-ignored", f"matched by .gitignore: {fpath}", rel))
    else:
        findings.append(finding_pass("B5-not-ignored", "no bundle file ignored", rel))

    return findings


def _repo_for_pin(repository: str, root: Path) -> Optional[Path]:
    if repository == "gfx1150-inference":
        return root
    if repository == "strata":
        strata = Path("/home/kupipi/Documents/git/strata")
        if strata.exists():
            return strata
    return None


def check_b6_pins(bundle_dir: Path, root: Path) -> List[Finding]:
    findings: List[Finding] = []
    rel = rel_to_repo(bundle_dir, root)
    notes = bundle_dir / "hashes-notes.txt"

    if not notes.exists():
        return findings

    rows = _parse_commit_pins_table(notes.read_text(encoding="utf-8", errors="replace"))
    if not rows:
        return findings

    for row in rows:
        repo_name = row.get("repository", "").strip()
        commit_ref = row.get("commit", "").strip()
        fpath = row.get("path", "").strip()
        digest = row.get("digest", "").strip()
        cmd = row.get("command", "").strip()

        # Only verify pins whose command explicitly uses `git show <commit>:<path>`.
        # Tree/binary pins (e.g. "Strata source tree", signed binary) use other
        # commands and are informational.
        if not re.search(r"git\s+show\s+[0-9a-fA-F]+:\S+\s*\\?\|\s*sha256sum", cmd):
            continue
        if not fpath or not commit_ref:
            continue

        repo = _repo_for_pin(repo_name, root)
        if repo is None:
            findings.append(finding_warn("B6-pins", f"unknown repository '{repo_name}' for {fpath}", rel))
            continue

        # Resolve commit.
        rev = run(["git", "rev-parse", "--verify", f"{commit_ref}^{{commit}}"], cwd=repo)
        if rev.returncode != 0:
            findings.append(finding_fail("B6-pins", f"unresolvable commit '{commit_ref}' for {fpath}", rel))
            continue
        commit_full = rev.stdout.strip()

        # Resolve commit:path.
        show = run(["git", "show", f"{commit_full}:{fpath}"], cwd=repo)
        if show.returncode != 0:
            findings.append(finding_fail("B6-pins", f"unresolvable {commit_ref}:{fpath}", rel))
            continue

        blob = show.stdout.encode("utf-8")
        actual = sha256_bytes(blob)

        is_abbreviated = "…" in digest or "..." in digest
        is_full = re.fullmatch(r"[0-9a-f]{64}", digest) is not None

        if is_full:
            if actual != digest:
                findings.append(finding_fail("B6-pins", f"digest mismatch for {commit_ref}:{fpath}", rel))
            else:
                findings.append(finding_pass("B6-pins", f"pin ok: {commit_ref}:{fpath}", rel))
        elif is_abbreviated:
            findings.append(finding_warn("B6-pins", f"abbreviated digest for {commit_ref}:{fpath}", rel))
        else:
            findings.append(finding_warn("B6-pins", f"no comparable digest for {commit_ref}:{fpath}", rel))

    return findings


def _column_index(header: List[str], prefix: str) -> Optional[int]:
    for i, h in enumerate(header):
        if h.lower().strip().startswith(prefix.lower()):
            return i
    return None


def _split_md_row(line: str) -> List[str]:
    """Split a markdown table row on unescaped pipes and strip backticks."""
    parts = re.split(r"(?<!\\)\|", line.strip().strip("|"))
    cleaned = []
    for p in parts:
        p = p.strip()
        if p.startswith("`") and p.endswith("`") and len(p) >= 2:
            p = p[1:-1].strip()
        cleaned.append(p)
    return cleaned


def _parse_commit_pins_table(text: str) -> List[Dict[str, str]]:
    """Parse the '## Commit pins' markdown table in hashes-notes.txt."""
    rows: List[Dict[str, str]] = []
    lines = text.splitlines()
    in_section = False
    header: List[str] = []
    num_cols: Optional[int] = None
    for raw in lines:
        line = raw.strip()
        if line.startswith("##"):
            in_section = "commit pin" in line.lower()
            header = []
            num_cols = None
            continue
        if not in_section:
            continue
        if not line.startswith("|"):
            continue
        cells = _split_md_row(line)
        if all(set(c) <= {"-", ":", " "} for c in cells):
            # separator line sets the canonical column count
            num_cols = len(cells)
            continue
        if not header:
            header = cells
            # Header may contain an unescaped pipe (e.g. "Digest (git show ... | sha256sum)");
            # merge trailing cells into the last header cell.
            if num_cols and len(header) > num_cols:
                header = header[: num_cols - 1] + [" | ".join(header[num_cols - 1 :])]
            continue
        if num_cols and len(cells) != num_cols:
            continue
        if not num_cols:
            continue

        cmd_idx = _column_index(header, "command")
        digest_idx = _column_index(header, "digest")
        file_idx = _column_index(header, "file")
        repo_idx = _column_index(header, "repository")
        commit_idx = _column_index(header, "commit")

        row: Dict[str, str] = {}
        cmd = cells[cmd_idx] if cmd_idx is not None else ""
        m = re.search(r"git\s+show\s+([0-9a-fA-F]+):(\S+)", cmd)
        if m:
            row["commit"] = m.group(1)
            row["path"] = m.group(2)
        else:
            row["commit"] = cells[commit_idx] if commit_idx is not None else ""
            row["path"] = cells[file_idx] if file_idx is not None else ""
        row["digest"] = cells[digest_idx] if digest_idx is not None else ""
        row["repository"] = cells[repo_idx] if repo_idx is not None else ""
        row["command"] = cmd
        rows.append(row)
    return rows


def check_b7_secrets(bundle_dir: Path, root: Path) -> List[Finding]:
    findings: List[Finding] = []
    rel = rel_to_repo(bundle_dir, root)

    found_any = False
    for f in sorted(bundle_dir.rglob("*")):
        if not f.is_file():
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        fpath = rel_to_repo(f, root)
        for lineno, line in enumerate(text.splitlines(), start=1):
            allow_reason = None
            m_allow = ALLOW_SECRET_RE.search(line)
            if m_allow:
                allow_reason = m_allow.group(1)

            matches = list(SECRETS_RE.finditer(line)) + list(SECRETS_KV_RE.finditer(line))
            for m in matches:
                found_any = True
                msg = f"{fpath}:{lineno}: potential secret"
                if allow_reason:
                    findings.append(finding_warn("B7-secrets", f"{msg} (allowed: {allow_reason})"))
                else:
                    findings.append(finding_fail("B7-secrets", msg))

    if not found_any:
        findings.append(finding_pass("B7-secrets", "no credential-shaped strings"))

    return findings


def check_b8_read_only(before: str, after: str, bundle_dir: Path, root: Path) -> List[Finding]:
    rel = rel_to_repo(bundle_dir, root)
    if before != after:
        return [finding_fail("B8-read-only", "git status changed during run", rel)]
    return [finding_pass("B8-read-only", "git status unchanged", rel)]


def check_bundle(bundle_dir: Path, root: Path, before_status: str, strict: bool = False) -> List[Finding]:
    """Run all checks on a bundle directory and return findings."""
    findings: List[Finding] = []

    b1 = check_b1_structure(bundle_dir, root)
    findings.extend(b1)
    # If no manifest, the remaining checks are skipped (B1 already warned).
    if not (bundle_dir / "manifest.md").exists():
        if strict:
            apply_strict(findings)
        return findings

    b2_findings, resolved_paths, exact_paths, listed_basenames = check_b2_hash_verify(bundle_dir, root)
    findings.extend(b2_findings)
    findings.extend(check_b3_hash_coverage(bundle_dir, root, resolved_paths, exact_paths, listed_basenames))
    findings.extend(check_b4_tracked(bundle_dir, root))
    findings.extend(check_b5_not_ignored(bundle_dir, root))
    findings.extend(check_b6_pins(bundle_dir, root))
    findings.extend(check_b7_secrets(bundle_dir, root))

    after_status = git_status_porcelain(root)
    findings.extend(check_b8_read_only(before_status, after_status, bundle_dir, root))

    if strict:
        apply_strict(findings)

    return findings


def format_findings_text(findings: List[Finding]) -> List[str]:
    lines: List[str] = []
    for f in findings:
        msg = f"{f.status} {f.code} {f.message}"
        lines.append(msg)
    return lines


def bundle_result(findings: List[Finding]) -> Tuple[str, int, int]:
    total = len(findings)
    warns = sum(1 for f in findings if f.status == "WARN")
    fails = sum(1 for f in findings if f.status == "FAIL")
    result = "FAIL" if fails else "PASS"
    return result, total, warns


def print_bundle_text(findings: List[Finding], bundle_name: Optional[str] = None) -> None:
    for line in format_findings_text(findings):
        print(line)
    result, total, warns = bundle_result(findings)
    prefix = f"{bundle_name}: " if bundle_name else ""
    print(f"{prefix}RESULT: {result} ({total} checks, {warns} warnings)")


def findings_to_json(findings: List[Finding], bundle_name: Optional[str] = None) -> Dict:
    result, total, warns = bundle_result(findings)
    return {
        "bundle": bundle_name,
        "checks": [
            {
                "code": f.code,
                "status": f.status,
                "message": f.message,
                "path": f.path,
            }
            for f in findings
        ],
        "result": result,
        "total": total,
        "warnings": warns,
    }


def cmd_single(bundle_dir: Path, json_mode: bool, strict: bool = False) -> int:
    root = repo_root(cwd=bundle_dir)
    before = git_status_porcelain(root)
    findings = check_bundle(bundle_dir, root, before, strict=strict)
    if json_mode:
        print(json.dumps(findings_to_json(findings, bundle_name=bundle_dir.name), sort_keys=True, indent=2))
    else:
        print_bundle_text(findings)
    fails = sum(1 for f in findings if f.status == "FAIL")
    return 1 if fails else 0


def cmd_all(json_mode: bool, strict: bool = False) -> int:
    root = repo_root()
    before = git_status_porcelain(root)
    evidence_dir = root / "workflow" / "evidence"
    bundles = sorted(p for p in evidence_dir.glob("HO-*") if p.is_dir())

    all_findings: List[Finding] = []
    all_json: List[Dict] = []
    any_fail = False

    for bundle in bundles:
        findings = check_bundle(bundle, root, before, strict=strict)
        any_fail = any_fail or any(f.status == "FAIL" for f in findings)
        if json_mode:
            all_json.append(findings_to_json(findings, bundle_name=bundle.name))
        else:
            print_bundle_text(findings, bundle_name=bundle.name)
            print()
        all_findings.extend(findings)

    result, total, warns = bundle_result(all_findings)
    if json_mode:
        print(json.dumps({"bundles": all_json, "result": result, "total": total, "warnings": warns}, sort_keys=True, indent=2))
    else:
        print(f"RESULT: {result} ({total} checks, {warns} warnings)")
    fails = sum(1 for f in all_findings if f.status == "FAIL")
    return 1 if fails else 0


# ---------------------------------------------------------------------------
# Self-test fixtures
# ---------------------------------------------------------------------------


def _git_init(repo: Path) -> None:
    run(["git", "init"], cwd=repo, check=True)
    run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    run(["git", "config", "user.name", "Test"], cwd=repo, check=True)


def _git_commit_all(repo: Path, message: str) -> None:
    run(["git", "add", "-A"], cwd=repo, check=True)
    run(["git", "commit", "-m", message], cwd=repo, check=True)


def _write_hashes(bundle: Path, entries: List[Tuple[str, str]]) -> None:
    with open(bundle / "hashes.txt", "w", encoding="utf-8") as f:
        for digest, fpath in entries:
            f.write(f"{digest}  {fpath}\n")


def _write_manifest(bundle: Path) -> None:
    (bundle / "manifest.md").write_text("# Manifest\n\ncommands.log\n", encoding="utf-8")


def _run_tool(repo: Path, bundle: Path, strict: bool = False) -> Tuple[int, str]:
    tool = Path(__file__).resolve()
    cmd = [sys.executable, str(tool)]
    if strict:
        cmd.append("--strict")
    cmd.append(str(bundle))
    result = run(cmd, cwd=repo)
    return result.returncode, result.stdout


def _assert_contains(stdout: str, code: str, status: str) -> None:
    needle = f"{status} {code}"
    if needle not in stdout:
        raise AssertionError(f"expected {status} {code} in output:\n{stdout}")


def _assert_not_contains(stdout: str, code: str, status: str) -> None:
    needle = f"{status} {code}"
    if needle in stdout:
        raise AssertionError(f"unexpected {status} {code} in output:\n{stdout}")


def fixture_hash_edited(repo: Path) -> Tuple[int, str]:
    bundle = repo / "bundle"
    bundle.mkdir()
    _write_manifest(bundle)
    artifact = bundle / "artifact.txt"
    artifact.write_text("original", encoding="utf-8")
    _git_commit_all(repo, "initial")
    digest = sha256_file(artifact)
    _write_hashes(bundle, [(digest, "bundle/artifact.txt")])
    _git_commit_all(repo, "hashes")
    artifact.write_text("tampered", encoding="utf-8")
    return _run_tool(repo, bundle)


def fixture_extra_artifact(repo: Path) -> Tuple[int, str]:
    bundle = repo / "bundle"
    bundle.mkdir()
    _write_manifest(bundle)
    a1 = bundle / "a.txt"
    a1.write_text("a", encoding="utf-8")
    a2 = bundle / "b.txt"
    a2.write_text("b", encoding="utf-8")
    _git_commit_all(repo, "initial")
    _write_hashes(bundle, [(sha256_file(a1), "bundle/a.txt")])
    _git_commit_all(repo, "hashes")
    return _run_tool(repo, bundle)


def fixture_untracked(repo: Path) -> Tuple[int, str]:
    bundle = repo / "bundle"
    bundle.mkdir()
    _write_manifest(bundle)
    artifact = bundle / "artifact.txt"
    artifact.write_text("data", encoding="utf-8")
    # do not add/commit
    _git_init(repo)
    return _run_tool(repo, bundle)


def fixture_ignored(repo: Path) -> Tuple[int, str]:
    bundle = repo / "bundle"
    bundle.mkdir()
    _write_manifest(bundle)
    (repo / ".gitignore").write_text("*.log\n", encoding="utf-8")
    log = bundle / "commands.log"
    log.write_text("log line\n", encoding="utf-8")
    tracked = bundle / "manifest.md"
    _git_commit_all(repo, "initial")
    digest = sha256_file(log)
    _write_hashes(bundle, [(digest, "bundle/commands.log"), (sha256_file(tracked), "bundle/manifest.md")])
    _git_commit_all(repo, "hashes")
    return _run_tool(repo, bundle)


def fixture_bad_pin(repo: Path) -> Tuple[int, str]:
    bundle = repo / "bundle"
    bundle.mkdir()
    _write_manifest(bundle)
    artifact = bundle / "artifact.txt"
    artifact.write_text("data", encoding="utf-8")
    _git_commit_all(repo, "initial")
    notes = bundle / "hashes-notes.txt"
    commit = run(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip()
    notes.write_text(
        "## Commit pins\n\n"
        "| File | Repository | Commit | Command | Digest |\n"
        "|---|---|---|---|---|\n"
        f"| missing.txt | gfx1150-inference | {commit} | git show {commit}:missing.txt \\| sha256sum | abcd1234…efgh |\n",
        encoding="utf-8",
    )
    _git_commit_all(repo, "notes")
    return _run_tool(repo, bundle)


def fixture_secret(repo: Path) -> Tuple[int, str]:
    bundle = repo / "bundle"
    bundle.mkdir()
    _write_manifest(bundle)
    log = bundle / "commands.log"
    log.write_text("token ghp_123456789012345678901234567890123456\n", encoding="utf-8")
    _git_commit_all(repo, "initial")
    _write_hashes(bundle, [(sha256_file(log), "bundle/commands.log"), (sha256_file(bundle / "manifest.md"), "bundle/manifest.md")])
    _git_commit_all(repo, "hashes")
    return _run_tool(repo, bundle)


def fixture_clean(repo: Path) -> Tuple[int, str]:
    bundle = repo / "bundle"
    bundle.mkdir()
    _write_manifest(bundle)
    log = bundle / "commands.log"
    log.write_text("plain log\n", encoding="utf-8")
    _git_commit_all(repo, "initial")
    _write_hashes(bundle, [(sha256_file(log), "bundle/commands.log"), (sha256_file(bundle / "manifest.md"), "bundle/manifest.md")])
    _git_commit_all(repo, "hashes")
    return _run_tool(repo, bundle)


def fixture_bundle_relative(repo: Path) -> Tuple[int, str]:
    """Listed path uses './' prefix relative to bundle dir."""
    bundle = repo / "bundle"
    bundle.mkdir()
    _write_manifest(bundle)
    artifact = bundle / "artifact.txt"
    artifact.write_text("bundle-relative data\n", encoding="utf-8")
    _git_commit_all(repo, "initial")
    _write_hashes(bundle, [(sha256_file(artifact), "./artifact.txt")])
    _git_commit_all(repo, "hashes")
    return _run_tool(repo, bundle)


def fixture_absolute_external(repo: Path) -> Tuple[int, str]:
    """Listed paths are absolute and outside the repo."""
    bundle = repo / "bundle"
    bundle.mkdir()
    _write_manifest(bundle)
    artifact = bundle / "artifact.txt"
    artifact.write_text("local data\n", encoding="utf-8")
    external = repo.parent / "external.txt"
    external.write_text("external data\n", encoding="utf-8")
    _git_commit_all(repo, "initial")
    digest_ext = sha256_file(external)
    _write_hashes(
        bundle,
        [
            (sha256_file(artifact), "bundle/artifact.txt"),
            (digest_ext, str(external)),
            ("0" * 64, str(repo.parent / "missing-external.txt")),
        ],
    )
    _git_commit_all(repo, "hashes")
    return _run_tool(repo, bundle)


def fixture_prose(repo: Path) -> Tuple[int, str]:
    """hashes.txt contains pin records and an N/A prose line."""
    bundle = repo / "bundle"
    bundle.mkdir()
    _write_manifest(bundle)
    artifact = bundle / "artifact.txt"
    artifact.write_text("data\n", encoding="utf-8")
    _git_commit_all(repo, "initial")
    _write_hashes(bundle, [(sha256_file(artifact), "bundle/artifact.txt")])
    with open(bundle / "hashes.txt", "a", encoding="utf-8") as f:
        f.write("strata HEAD              abcdef1234…deadbeef   (git -C /path rev-parse HEAD)\n")
        f.write("N/A — no model, dataset or prompt was used in this handoff.\n")
    _git_commit_all(repo, "hashes")
    return _run_tool(repo, bundle)


def fixture_basename_spelling(repo: Path) -> Tuple[int, str]:
    """Listed basename only; actual file lives under artifacts/."""
    bundle = repo / "bundle"
    bundle.mkdir()
    (bundle / "artifacts").mkdir()
    _write_manifest(bundle)
    artifact = bundle / "artifacts" / "artifact.txt"
    artifact.write_text("nested data\n", encoding="utf-8")
    _git_commit_all(repo, "initial")
    _write_hashes(bundle, [(sha256_file(artifact), "artifact.txt")])
    _git_commit_all(repo, "hashes")
    return _run_tool(repo, bundle)


def fixture_malformed_separator(repo: Path) -> Tuple[int, str]:
    """A 64-hex line with a broken separator."""
    bundle = repo / "bundle"
    bundle.mkdir()
    _write_manifest(bundle)
    artifact = bundle / "artifact.txt"
    artifact.write_text("data\n", encoding="utf-8")
    _git_commit_all(repo, "initial")
    _write_hashes(bundle, [(sha256_file(artifact), "bundle/artifact.txt")])
    with open(bundle / "hashes.txt", "a", encoding="utf-8") as f:
        # sha256sum binary-mode marker '*' instead of the text-mode two-space separator.
        f.write(f"{sha256_file(artifact)} *bundle/artifact.txt\n")
    _git_commit_all(repo, "hashes")
    return _run_tool(repo, bundle)


FIXTURES: List[Tuple[str, callable, Optional[str], str]] = [
    ("hash-edited", fixture_hash_edited, "B2-hash-mismatch", "FAIL"),
    ("extra-artifact", fixture_extra_artifact, "B3-unlisted", "FAIL"),
    ("untracked", fixture_untracked, "B4-tracked", "FAIL"),
    ("ignored", fixture_ignored, "B5-not-ignored", "FAIL"),
    ("bad-pin", fixture_bad_pin, "B6-pins", "FAIL"),
    ("secret", fixture_secret, "B7-secrets", "FAIL"),
    ("clean", fixture_clean, None, "PASS"),
    ("bundle-relative", fixture_bundle_relative, "B2-legacy-path", "WARN"),
    ("absolute-external", fixture_absolute_external, "B2-external", "WARN"),
    ("prose", fixture_prose, "B2-prose", "WARN"),
    ("basename-spelling", fixture_basename_spelling, "B2-path-spelling", "WARN"),
    ("malformed-separator", fixture_malformed_separator, "B2-malformed", "FAIL"),
]


def cmd_self_test() -> int:
    failures = 0
    with tempfile.TemporaryDirectory(prefix="check_bundle_self_test_") as td:
        base = Path(td)
        for name, func, code, status in FIXTURES:
            repo = base / name
            repo.mkdir()
            _git_init(repo)
            try:
                exitcode, stdout = func(repo)
            except Exception as exc:
                print(f"FAIL {name}: fixture raised {exc}")
                failures += 1
                continue

            if code is not None:
                try:
                    _assert_contains(stdout, code, status)
                except AssertionError as exc:
                    print(f"FAIL {name}: {exc}")
                    failures += 1
                    continue
            else:
                if "RESULT: PASS" not in stdout:
                    print(f"FAIL {name}: expected RESULT: PASS, got:\n{stdout}")
                    failures += 1
                    continue

            # Strict-mode variant for bundle-relative fixture.
            if name == "bundle-relative":
                try:
                    _, strict_stdout = _run_tool(repo, repo / "bundle", strict=True)
                    _assert_contains(strict_stdout, "B2-legacy-path", "FAIL")
                    # Under strict the overall result must be FAIL.
                    if "RESULT: FAIL" not in strict_stdout:
                        raise AssertionError("expected RESULT: FAIL under --strict")
                except AssertionError as exc:
                    print(f"FAIL {name} --strict: {exc}")
                    failures += 1
                    continue

            print(f"PASS {name}")

    if failures:
        print(f"RESULT: FAIL ({failures} fixture(s) failed)")
        return 1
    print("RESULT: PASS (all fixtures behaved as expected)")
    return 0


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Evidence-packaging invariant checker.",
        epilog="Exit codes: 0 = no FAIL, 1 = FAIL present, 2 = usage error.",
    )
    parser.add_argument("bundle", nargs="?", help="path to an evidence bundle directory")
    parser.add_argument("--all", action="store_true", help="check every workflow/evidence/HO-* bundle")
    parser.add_argument("--self-test", action="store_true", help="run negative-control fixtures")
    parser.add_argument("--json", action="store_true", help="emit stable JSON output")
    parser.add_argument("--strict", action="store_true", help="upgrade legacy/path-spelling/prose warnings to FAIL")

    args = parser.parse_args(argv)

    if args.self_test:
        if args.bundle or args.all or args.json or args.strict:
            parser.error("--self-test takes no other options")
        return cmd_self_test()

    if args.all:
        if args.bundle:
            parser.error("cannot combine --all with a bundle path")
        return cmd_all(json_mode=args.json, strict=args.strict)

    if not args.bundle:
        parser.error("specify a bundle directory, --all, or --self-test")

    bundle_path = Path(args.bundle)
    if not bundle_path.is_dir():
        print(f"FAIL usage: not a directory: {args.bundle}", file=sys.stderr)
        return 2

    return cmd_single(bundle_path, json_mode=args.json, strict=args.strict)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
