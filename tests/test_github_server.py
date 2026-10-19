"""Tests for the GitHub MCP server tool allowlist."""

from importlib.resources import files

import pytest

from ai_reviewer.github_server import GITHUB_TOOLS, get_github_server

WRITE_TOOLS = {
    "create_or_update_file",
    "push_files",
    "delete_file",
    "merge_pull_request",
    "create_pull_request",
    "create_branch",
    "issue_write",
}

# Tool names that no longer exist in the upstream GitHub MCP server.
REMOVED_TOOLS = ("get_pull_request_diff", "get_pull_request", *WRITE_TOOLS)

ACTIVE_PROMPTS = ("agent_prompt.md", "agent_context.md")


def _transport():
    return get_github_server("dummy-token").client.transport


def test_allowlist_is_passed_to_server():
    transport = _transport()

    assert "GITHUB_TOOLS" in transport.args
    assert transport.env["GITHUB_TOOLS"].split(",") == list(GITHUB_TOOLS)


def test_token_is_still_passed_to_server():
    transport = _transport()

    assert "GITHUB_PERSONAL_ACCESS_TOKEN" in transport.args
    assert transport.env["GITHUB_PERSONAL_ACCESS_TOKEN"] == "dummy-token"


def test_allowlist_has_no_write_tools_other_than_review():
    assert not WRITE_TOOLS & set(GITHUB_TOOLS)
    assert "pull_request_review_write" in GITHUB_TOOLS


def test_read_only_flag_is_not_used():
    # --read-only would also drop pull_request_review_write, so reviews could not be posted.
    transport = _transport()

    assert "--read-only" not in transport.args
    assert "GITHUB_READ_ONLY" not in transport.env


@pytest.mark.parametrize("prompt_file", ACTIVE_PROMPTS)
def test_prompts_do_not_reference_unavailable_tools(prompt_file):
    text = files("ai_reviewer.prompts").joinpath(prompt_file).read_text()

    for tool in REMOVED_TOOLS:
        assert tool not in text, f"{prompt_file} references unavailable tool {tool!r}"
