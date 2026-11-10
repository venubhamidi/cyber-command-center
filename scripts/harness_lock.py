#!/usr/bin/env python3
"""Fingerprint of the harness/ folder.

    python scripts/harness_lock.py           write harness/MANIFEST.sha256   (harness maintainers only)
    python scripts/harness_lock.py --check   fail if harness/ differs from the manifest

Application repositories never edit harness/. The check proves a repository's harness is exactly
the released version named in harness/VERSION. In the template repository, changing the harness
means: bump VERSION, add a CHANGELOG entry, re-run this script.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

HARNESS = Path(__file__).resolve().parents[1] / "harness"
MANIFEST = HARNESS / "MANIFEST.sha256"


def fingerprint() -> str:
    lines = []
    for path in sorted(HARNESS.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and path != MANIFEST:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            lines.append(f"{digest}  {path.relative_to(HARNESS).as_posix()}")
    return "\n".join(lines) + "\n"


def check() -> list[str]:
    if not MANIFEST.exists():
        return ["harness/MANIFEST.sha256 is missing"]
    recorded = dict(reversed(line.split("  ", 1)) for line in MANIFEST.read_text().splitlines() if line)
    actual = dict(reversed(line.split("  ", 1)) for line in fingerprint().splitlines() if line)
    problems = [f"harness/{f} was modified" for f in recorded if f in actual and actual[f] != recorded[f]]
    problems += [f"harness/{f} was deleted" for f in recorded if f not in actual]
    problems += [f"harness/{f} was added" for f in actual if f not in recorded]
    return problems


if __name__ == "__main__":
    if "--check" in sys.argv:
        problems = check()
        for p in problems:
            print(f"FAIL {p}")
        if problems:
            print("harness/ does not match its manifest. Application repositories must not edit harness/;\n"
                  "put the change in your application, or make it in the template repository and upgrade.")
            sys.exit(1)
        print(f"harness {(HARNESS / 'VERSION').read_text().strip()} matches its manifest")
    else:
        MANIFEST.write_text(fingerprint())
        print(f"wrote {MANIFEST.relative_to(HARNESS.parent)}")
