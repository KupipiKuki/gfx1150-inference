"""Prove B3-unlisted suffix bypass and B6-pins reworded-command bypass are caught."""
import os, subprocess, sys, tempfile, shutil
from pathlib import Path

tool = Path("workflow/tools/check_bundle.py").resolve()


def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def git_init(repo):
    run(["git", "init"], cwd=repo)
    run(["git", "config", "user.email", "test@example.com"], cwd=repo)
    run(["git", "config", "user.name", "Test"], cwd=repo)


def commit_all(repo, msg):
    run(["git", "add", "-A"], cwd=repo)
    run(["git", "commit", "-m", msg], cwd=repo)


def sha256_file(p):
    import hashlib
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for ch in iter(lambda: f.read(65536), b""):
            h.update(ch)
    return h.hexdigest()


def write_hashes(bundle, entries):
    with open(bundle/"hashes.txt", "w") as f:
        for d, p in entries:
            f.write(f"{d}  {p}\n")


def make_clean_bundle(repo):
    bundle = repo / "bundle"
    bundle.mkdir()
    (bundle/"manifest.md").write_text("# Manifest\n\ncommands.log\n")
    (bundle/"commands.log").write_text("log\n")
    (bundle/"artifact.txt").write_text("data\n")
    return bundle


base = Path(tempfile.mkdtemp(prefix="bypass_proof_"))

try:
    print("=== Probe 1: unlisted artifacts/notes-hashes.txt must FAIL B3-unlisted ===")
    repo1 = base / "suffix"
    repo1.mkdir()
    git_init(repo1)
    bundle1 = make_clean_bundle(repo1)
    art1 = bundle1 / "artifacts"
    art1.mkdir()
    (art1/"notes-hashes.txt").write_text("notes\n")
    commit_all(repo1, "initial")
    write_hashes(bundle1, [
        (sha256_file(bundle1/"artifact.txt"), "bundle/artifact.txt"),
        (sha256_file(bundle1/"manifest.md"), "bundle/manifest.md"),
        (sha256_file(bundle1/"commands.log"), "bundle/commands.log"),
    ])
    commit_all(repo1, "hashes")
    r1 = run([sys.executable, str(tool), str(bundle1)], cwd=repo1)
    print(r1.stdout)
    assert "FAIL B3-unlisted" in r1.stdout, "expected B3-unlisted FAIL"
    print("PASS: B3 suffix bypass is caught\n")

    print("=== Probe 2: full wrong digest with reworded command must FAIL B6-pins ===")
    repo2 = base / "reworded"
    repo2.mkdir()
    git_init(repo2)
    bundle2 = make_clean_bundle(repo2)
    bundle2.joinpath("artifact.txt").write_text("pinned data\n")
    commit_all(repo2, "initial")
    commit = run(["git", "rev-parse", "HEAD"], cwd=repo2).stdout.strip()
    notes2_text = (
        "## Commit pins\n\n"
        "| File | Repository | Commit | Command | Digest |\n"
        "|---|---|---|---|---|\n"
        f"| bundle/artifact.txt | gfx1150-inference | {commit} | "
        f"git cat-file -p {commit}:bundle/artifact.txt \\| sha256sum | "
        f"{'0'*64} |\n"
    )
    (bundle2/"hashes-notes.txt").write_text(notes2_text)
    write_hashes(bundle2, [
        (sha256_file(bundle2/"artifact.txt"), "bundle/artifact.txt"),
        (sha256_file(bundle2/"manifest.md"), "bundle/manifest.md"),
        (sha256_file(bundle2/"commands.log"), "bundle/commands.log"),
        (sha256_file(bundle2/"hashes-notes.txt"), "bundle/hashes-notes.txt"),
    ])
    commit_all(repo2, "notes")
    r2 = run([sys.executable, str(tool), str(bundle2)], cwd=repo2)
    print(r2.stdout)
    assert "FAIL B6-pins" in r2.stdout and "B3-unlisted" not in r2.stdout, "expected only B6-pins FAIL"
    print("PASS: B6 reworded wrong-digest pin is caught\n")

    print("=== Control: correct pin with reworded command still passes ===")
    repo3 = base / "control"
    repo3.mkdir()
    git_init(repo3)
    bundle3 = make_clean_bundle(repo3)
    bundle3.joinpath("artifact.txt").write_text("good data\n")
    commit_all(repo3, "initial")
    commit3 = run(["git", "rev-parse", "HEAD"], cwd=repo3).stdout.strip()
    digest3 = sha256_file(bundle3/"artifact.txt")
    notes3_text = (
        "## Commit pins\n\n"
        "| File | Repository | Commit | Command | Digest |\n"
        "|---|---|---|---|---|\n"
        f"| bundle/artifact.txt | gfx1150-inference | {commit3} | "
        f"git cat-file -p {commit3}:bundle/artifact.txt \\| sha256sum | "
        f"{digest3} |\n"
    )
    (bundle3/"hashes-notes.txt").write_text(notes3_text)
    write_hashes(bundle3, [
        (sha256_file(bundle3/"artifact.txt"), "bundle/artifact.txt"),
        (sha256_file(bundle3/"manifest.md"), "bundle/manifest.md"),
        (sha256_file(bundle3/"commands.log"), "bundle/commands.log"),
        (sha256_file(bundle3/"hashes-notes.txt"), "bundle/hashes-notes.txt"),
    ])
    commit_all(repo3, "notes")
    r3 = run([sys.executable, str(tool), str(bundle3)], cwd=repo3)
    print(r3.stdout)
    assert "PASS B6-pins" in r3.stdout, "expected B6-pins PASS"
    assert "RESULT: PASS" in r3.stdout, "expected overall PASS"
    print("PASS: reworded command with correct digest is accepted\n")
finally:
    shutil.rmtree(base, ignore_errors=True)
