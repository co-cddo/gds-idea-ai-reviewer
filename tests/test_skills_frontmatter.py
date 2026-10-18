"""Validate the metadata used to discover skills in OpenCode."""

from pathlib import Path

import pytest
import yaml

SKILLS_DIR = Path(__file__).resolve().parents[1] / "src" / "ai_reviewer" / "skills"
SKILL_FILES = sorted(SKILLS_DIR.glob("*/SKILL.md"))


def test_skill_files_exist():
    assert SKILL_FILES, "No skill files found to validate"


@pytest.mark.parametrize("skill_path", SKILL_FILES, ids=lambda path: path.parent.name)
def test_skill_frontmatter(skill_path):
    lines = skill_path.read_text(encoding="utf-8").splitlines()
    assert lines and lines[0] == "---", "Skill must start with YAML frontmatter"

    end = next((index for index, line in enumerate(lines[1:], start=1) if line == "---"), None)
    assert end is not None, "Skill frontmatter must have a closing delimiter"

    metadata = yaml.safe_load("\n".join(lines[1:end]))
    assert isinstance(metadata, dict), "Skill frontmatter must be a mapping"
    assert metadata.get("name") == skill_path.parent.name, "Skill name must match its directory"
    description = metadata.get("description")
    assert isinstance(description, str) and description.strip(), "Skill description must be a non-empty string"
