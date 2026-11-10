#!/usr/bin/env python3
"""Checks that this repository still honours the harness contract. CI runs it on every change.

    python scripts/check_structure.py

It verifies: the required files exist (deploy files, rules, decision log, evals); harness/ is
unmodified; every setting the application reads is documented in deploy/.env.example; the deploy
files point at the right application package; every agent has an evaluation suite; and the
working practices are in place (docs/working-practices.md, the skills, both glossaries, decision
records, the ticket and pull-request templates, and a well-formed DECISIONS.md).
"""
from __future__ import annotations

import importlib
import re
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

REQUIRED_FILES = [
    "CLAUDE.md", "README.md", "requirements.txt", "requirements-dev.txt", "pyproject.toml", ".dockerignore",
    "deploy/Dockerfile.api", "deploy/docker-compose.yml", "deploy/.env.example",
    "harness/VERSION", "harness/MANIFEST.sha256", "harness/CHANGELOG.md",
    ".github/workflows/ci.yml",
]
REQUIRED_IN_APP = ["__init__.py", "config.py", "main.py", "CLAUDE.md", "DECISIONS.md", "evals/__init__.py",
                   "plugins/__init__.py"]

# Working practices (docs/working-practices.md). Template-owned like the rest of this script.
REQUIRED_PRACTICE_FILES = ["docs/working-practices.md", "CONTEXT.md", "CHANGELOG.md", "docs/adr/README.md",
                           ".github/ISSUE_TEMPLATE/slice.md", ".github/pull_request_template.md"]
REQUIRED_SKILLS = ["grill", "glossary", "adr", "slice", "handoff",
                   "new-endpoint", "new-agent", "new-mcp-tool", "new-plugin", "new-migration"]
DECISION_STATUSES = {"Open", "Decided"}


def glossary_problems(path: Path, rel: str) -> list[str]:
    """Every `## term` heading has text under it, and no term is defined twice."""
    problems, seen, current, has_text = [], set(), None, False
    for line in path.read_text().splitlines() + ["## "]:
        if line.startswith("## "):
            if current is not None and not has_text:
                problems.append(f"{rel}: term '{current}' has no definition under its heading")
            current, has_text = line[3:].strip(), False
            if current in seen:
                problems.append(f"{rel}: term '{current}' is defined twice")
            seen.add(current)
        elif current is not None and line.strip() and not line.startswith("#"):
            has_text = True
    return problems


def decisions_problems(path: Path, rel: str) -> list[str]:
    """Every row of the decision table has a status of Open or Decided (column found by its header)."""
    problems, status_col = [], None
    for line in path.read_text().splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if "Status" in cells:
            status_col = cells.index("Status")
        elif status_col is not None and len(cells) > status_col and not set(cells[status_col]) <= {"-", ":", ""}:
            if cells[status_col] not in DECISION_STATUSES:
                problems.append(f"{rel}: row {cells[0]} has status '{cells[status_col]}'; it must be Open or Decided")
    return problems


def skill_has_description(text: str) -> bool:
    """A SKILL.md starts with YAML front matter that has a non-empty `description:`."""
    if not text.startswith("---"):
        return False
    front_matter = text[3:].split("\n---", 1)[0]
    return re.search(r"^description:\s*\S", front_matter, re.MULTILINE) is not None


def practice_problems(root: Path, app: str) -> list[str]:
    problems = [f"missing file: {f}" for f in REQUIRED_PRACTICE_FILES + [f"{app}/CONTEXT.md"] if not (root / f).is_file()]
    if (root / "docs" / "adr").is_dir() and not list((root / "docs" / "adr").glob("[0-9][0-9][0-9][0-9]-*.md")):
        problems.append("docs/adr/ holds no numbered decision record (NNNN-<slug>.md)")
    for skill in REQUIRED_SKILLS:
        rel = f".claude/skills/{skill}/SKILL.md"
        if not (root / rel).is_file():
            problems.append(f"missing skill: {rel}")
        elif not skill_has_description((root / rel).read_text()):
            problems.append(f"skill {rel} has no description in its front matter")
    for rel in ("CONTEXT.md", f"{app}/CONTEXT.md"):
        if (root / rel).is_file():
            problems += glossary_problems(root / rel, rel)
    if (root / app / "DECISIONS.md").is_file():
        problems += decisions_problems(root / app / "DECISIONS.md", f"{app}/DECISIONS.md")
    return problems


def main() -> int:
    problems: list[str] = []
    app = tomllib.loads((ROOT / "pyproject.toml").read_text()).get("tool", {}).get("harness", {}).get("app_package")
    if not app:
        print("FAIL pyproject.toml: [tool.harness] app_package is not set")
        return 1

    for f in REQUIRED_FILES:
        if not (ROOT / f).is_file():
            problems.append(f"missing file: {f}")
    for f in REQUIRED_IN_APP:
        if not (ROOT / app / f).is_file():
            problems.append(f"missing file: {app}/{f}")
    if not list((ROOT / app / "migrations").glob("*.sql")):
        problems.append(f"no migrations in {app}/migrations/")
    if (ROOT / "frontend").is_dir():
        for f in ("deploy/Dockerfile.web", "deploy/nginx.conf"):
            if not (ROOT / f).is_file():
                problems.append(f"missing file: {f} (the repository has a frontend/)")
    if (ROOT / "deploy" / ".env").exists() and subprocess.run(
            ["git", "ls-files", "--error-unmatch", "deploy/.env"], cwd=ROOT, capture_output=True).returncode == 0:
        problems.append("deploy/.env is committed; it must never be (it holds real settings and secrets)")

    # harness/ must be exactly the released version
    lock = subprocess.run([sys.executable, str(ROOT / "scripts" / "harness_lock.py"), "--check"],
                          capture_output=True, text=True)
    if lock.returncode != 0:
        problems += [line.removeprefix("FAIL ") for line in lock.stdout.splitlines() if line.startswith("FAIL")]

    env_example = (ROOT / "deploy" / ".env.example").read_text() if (ROOT / "deploy" / ".env.example").exists() else ""
    declared = re.search(r"^APP_PACKAGE=(\S+)", env_example, re.MULTILINE)
    if not declared or declared.group(1) != app:
        problems.append(f"deploy/.env.example must contain APP_PACKAGE={app}")

    try:
        config = importlib.import_module(f"{app}.config")
        for name in type(config.settings).model_fields:
            if not re.search(rf"^#?\s*APP_{name.upper()}=", env_example, re.MULTILINE):
                problems.append(f"setting APP_{name.upper()} is not documented in deploy/.env.example")
        if not hasattr(config, "MIGRATIONS_DIR") or not hasattr(config, "ROLE_PERMISSIONS"):
            problems.append(f"{app}/config.py must define MIGRATIONS_DIR and ROLE_PERMISSIONS")
    except Exception as exc:  # noqa: BLE001
        problems.append(f"cannot import {app}.config: {type(exc).__name__}: {exc}")

    # every agent must have an evaluation suite
    try:
        suites = importlib.import_module(f"{app}.evals").EVAL_SUITES
        evaluated = {s.agent_factory().spec.agent_id for s in suites.values()}
        for path in (ROOT / app / "agents").glob("*.py"):
            for agent_id in re.findall(r'agent_id="([^"]+)"', path.read_text()):
                if agent_id not in evaluated:
                    problems.append(f"agent '{agent_id}' ({app}/agents/{path.name}) has no evaluation suite in {app}/evals")
        for name, suite in suites.items():
            if not list(Path(suite.cases_dir).glob("*.json")):
                problems.append(f"evaluation suite '{name}' has no cases")
    except Exception as exc:  # noqa: BLE001
        problems.append(f"cannot load {app}.evals: {type(exc).__name__}: {exc}")

    problems += practice_problems(ROOT, app)

    for p in problems:
        print(f"FAIL {p}")
    if problems:
        return 1
    print(f"structure OK: application '{app}', harness {(ROOT / 'harness' / 'VERSION').read_text().strip()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
