"""Every SKILL.md must carry valid YAML frontmatter so OpenCode can load it.

OpenCode silently skips a skill whose frontmatter fails to parse (for example an
unquoted `description:` containing ": "), so the failure is invisible without this test.
"""

import re
from pathlib import Path

import pytest
import yaml

import ai_reviewer.skills

SKILLS_DIR = Path(ai_reviewer.skills.__file__).parent
SKILL_FILES = sorted(SKILLS_DIR.glob("*/SKILL.md"))

_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


def _load_frontmatter(path: Path) -> dict:
    match = _FRONTMATTER_RE.match(path.read_text(encoding="utf-8"))
    assert match, f"{path.parent.name}: no YAML frontmatter block at the start of SKILL.md"
    frontmatter = yaml.safe_load(match.group(1))
    assert isinstance(frontmatter, dict), f"{path.parent.name}: frontmatter is not a YAML mapping"
    return frontmatter


def test_skills_are_found():
    assert len(SKILL_FILES) >= 5


@pytest.mark.parametrize("skill_file", SKILL_FILES, ids=lambda p: p.parent.name)
def test_skill_frontmatter_is_valid(skill_file: Path):
    frontmatter = _load_frontmatter(skill_file)

    for key in ("name", "description"):
        value = frontmatter.get(key)
        assert isinstance(value, str) and value.strip(), f"{skill_file.parent.name}: `{key}` must be a non-empty string"

    assert frontmatter["name"] == skill_file.parent.name, "`name` must match the skill's directory name"
