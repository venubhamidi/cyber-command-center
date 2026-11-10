"""scripts/check_structure.py: the working-practices part of the repository contract.

Each rule has a test that breaks a copy of the repository in one way and expects one failure.
The functions are called directly on the copy; the script's main() is run once on the real tree.
"""
from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = tomllib.loads((ROOT / "pyproject.toml").read_text())["tool"]["harness"]["app_package"]

_spec = importlib.util.spec_from_file_location("check_structure", ROOT / "scripts" / "check_structure.py")
check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check)

PRACTICE_PATHS = ["docs", ".claude", ".github", "CONTEXT.md", "CHANGELOG.md", f"{APP}/CONTEXT.md", f"{APP}/DECISIONS.md"]


@pytest.fixture
def copy(tmp_path: Path) -> Path:
    """A copy of just the files the practices rules look at."""
    for rel in PRACTICE_PATHS:
        src, dst = ROOT / rel, tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dst) if src.is_dir() else shutil.copy(src, dst)
    return tmp_path


def problems(root: Path) -> list[str]:
    return check.practice_problems(root, APP)


def test_the_real_repository_passes():
    assert problems(ROOT) == []
    assert subprocess.run([sys.executable, str(ROOT / "scripts" / "check_structure.py")]).returncode == 0


@pytest.mark.parametrize("missing", ["docs/working-practices.md", "CONTEXT.md", "CHANGELOG.md", f"{APP}/CONTEXT.md",
                                     "docs/adr/README.md", ".github/ISSUE_TEMPLATE/slice.md",
                                     ".github/pull_request_template.md"])
def test_required_practice_file_missing_is_reported(copy: Path, missing: str):
    (copy / missing).unlink()
    assert [p for p in problems(copy) if missing in p] and len(problems(copy)) == 1


def test_adr_folder_with_no_numbered_record_is_reported(copy: Path):
    for f in (copy / "docs" / "adr").glob("[0-9]*.md"):
        f.unlink()
    assert problems(copy) == ["docs/adr/ holds no numbered decision record (NNNN-<slug>.md)"]


@pytest.mark.parametrize("skill", check.REQUIRED_SKILLS)
def test_missing_skill_is_reported(copy: Path, skill: str):
    shutil.rmtree(copy / ".claude" / "skills" / skill)
    assert problems(copy) == [f"missing skill: .claude/skills/{skill}/SKILL.md"]


def test_skill_without_description_is_reported(copy: Path):
    path = copy / ".claude" / "skills" / "grill" / "SKILL.md"
    path.write_text("---\nname: grill\n---\n# grill\n")
    assert problems(copy) == ["skill .claude/skills/grill/SKILL.md has no description in its front matter"]


def test_skill_with_empty_description_is_reported(copy: Path):
    path = copy / ".claude" / "skills" / "grill" / "SKILL.md"
    path.write_text("---\nname: grill\ndescription:   \n---\n# grill\n")
    assert problems(copy) == ["skill .claude/skills/grill/SKILL.md has no description in its front matter"]


def test_glossary_term_without_definition_is_reported(copy: Path):
    path = copy / "CONTEXT.md"
    path.write_text(path.read_text() + "\n## orphan\n\n## another\nHas a definition.\n")
    assert problems(copy) == ["CONTEXT.md: term 'orphan' has no definition under its heading"]


def test_glossary_duplicate_term_is_reported(copy: Path):
    path = copy / APP / "CONTEXT.md"
    first_term = next(line[3:].strip() for line in path.read_text().splitlines() if line.startswith("## "))
    path.write_text(path.read_text() + f"\n## {first_term}\nA second definition of the same word.\n")
    assert problems(copy) == [f"{APP}/CONTEXT.md: term '{first_term}' is defined twice"]


def test_decision_row_with_unknown_status_is_reported(copy: Path):
    path = copy / APP / "DECISIONS.md"
    path.write_text(path.read_text() + "| D-099 | Pending | Something? | nothing | |\n")
    assert problems(copy) == [f"{APP}/DECISIONS.md: row D-099 has status 'Pending'; it must be Open or Decided"]


def test_decision_row_status_column_is_found_by_header(tmp_path: Path, copy: Path):
    path = copy / APP / "DECISIONS.md"
    path.write_text("# Log\n\n| ID | Raised by | Status | Question |\n|---|---|---|---|\n"
                    "| D-001 | PRD | Decided | fine |\n| D-002 | PRD | Maybe | not fine |\n")
    assert problems(copy) == [f"{APP}/DECISIONS.md: row D-002 has status 'Maybe'; it must be Open or Decided"]
