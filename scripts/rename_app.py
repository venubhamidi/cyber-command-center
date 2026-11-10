#!/usr/bin/env python3
"""Give the application package its real name, right after creating a repository from the template.

    python scripts/rename_app.py <new_name>        e.g.  python scripts/rename_app.py ccc

Renames the package folder and updates imports, commands, deploy files and CI. Run it once, on a
clean working tree, then run the tests.
"""
from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".py", ".md", ".toml", ".yml", ".yaml", ".example", ".json", ".sh", ".api", ".web", ".conf", ".ts", ".tsx"}
SKIP_DIRS = {".git", "node_modules", "harness", "__pycache__", "dist", ".pytest_cache", ".ruff_cache"}


def main(new: str) -> int:
    if not re.fullmatch(r"[a-z][a-z0-9_]*", new) or new in {"harness", "tests", "scripts", "deploy", "frontend"}:
        print("the name must be a lowercase Python identifier that is not already a top-level folder")
        return 2
    old = tomllib.loads((ROOT / "pyproject.toml").read_text())["tool"]["harness"]["app_package"]
    if old == new:
        print(f"the application package is already '{new}'")
        return 0
    if (ROOT / new).exists():
        print(f"'{new}/' already exists")
        return 2
    (ROOT / old).rename(ROOT / new)

    o = re.escape(old)
    rules = [
        (rf"\bfrom {o}(\.|\s+import\b)", rf"from {new}\1"),            # from app.x import / from app import
        (rf"\bimport {o}\.", f"import {new}."),
        (rf"(-m\s+){o}\.", rf"\1{new}."),                               # python -m app.seed
        (rf"(-m\s+harness\.(?:migrate|evals)\s+){o}\b", rf"\1{new}"),   # python -m harness.migrate app
        (rf"(\"-m\",\s*\"){o}\.", rf"\1{new}."),                        # ["-m", "app.mcp_servers..."]
        (rf"\b{o}\.main:app\b", f"{new}.main:app"),
        (rf"(APP_PACKAGE[=:]\s*(?:\$\{{APP_PACKAGE:-)?){o}\b", rf"\1{new}"),
        (rf"(app_package\s*=\s*\"){o}\"", rf'\1{new}"'),
        (rf"(?<![\w./-]){o}/(?=[A-Za-z_.*])", f"{new}/"),               # paths in docs: app/config.py
        (rf"(\[\"|\"){o}\.plugins\.", rf"\1{new}.plugins."),
    ]
    changed = 0
    for path in ROOT.rglob("*"):
        if not path.is_file() or SKIP_DIRS.intersection(path.relative_to(ROOT).parts):
            continue
        if path.suffix not in TEXT_SUFFIXES and path.name not in {"Dockerfile.api", "Dockerfile.web", ".dockerignore"}:
            continue
        if path == Path(__file__).resolve():
            continue
        text = original = path.read_text()
        for pattern, replacement in rules:
            text = re.sub(pattern, replacement, text)
        if text != original:
            path.write_text(text)
            changed += 1
    print(f"renamed {old}/ to {new}/ and updated {changed} files. Now run: python scripts/check_structure.py && python -m pytest -q")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python scripts/rename_app.py <new_name>")
    sys.exit(main(sys.argv[1]))
