"""Prove HO-001 basename-fallback and HO-007 bundle-dir-relative legacy spellings verify correctly."""
import re
from pathlib import Path
import hashlib


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for ch in iter(lambda: f.read(65536), b""):
            h.update(ch)
    return h.hexdigest()


def verify_bundle(bundle: Path):
    ok = mismatch = missing = 0
    root = Path(".")
    for raw in (bundle / "hashes.txt").read_text().splitlines():
        line = raw.rstrip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("  ", 1)
        if len(parts) != 2:
            continue
        digest, fpath = parts
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            continue
        target = None
        p = Path(fpath)
        if p.is_absolute():
            if p.is_file():
                target = p
        else:
            cand = root / fpath
            if cand.is_file():
                target = cand
            if target is None:
                cand = bundle / fpath
                if cand.is_file():
                    target = cand
                if target is None and fpath.startswith("./"):
                    cand = bundle / fpath[2:]
                    if cand.is_file():
                        target = cand
            if target is None:
                name = p.name
                for c in bundle.rglob(name):
                    if c.is_file() and sha256(c) == digest:
                        target = c
                        break
        if target is None:
            missing += 1
        else:
            if sha256(target) == digest:
                ok += 1
            else:
                mismatch += 1
    return ok, mismatch, missing


b7 = Path("workflow/evidence/HO-STRATA-007")
ok7, mis7, miss7 = verify_bundle(b7)
print(f"HO-007 verified from bundle dir: ok={ok7} problems={mis7 + miss7}")

b1 = Path("workflow/evidence/HO-STRATA-001")
ok1, mis1, miss1 = verify_bundle(b1)
print(f"HO-001 verified with basename fallback: ok={ok1} mismatch={mis1} missing={miss1}")
