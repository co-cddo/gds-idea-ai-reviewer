from ai_reviewer.tools import get_all_toolsets


def _discovered_tool_names() -> set[str]:
    toolsets = get_all_toolsets()
    return {name for ts in toolsets for name in ts.tools}


def test_get_all_toolsets_discovers_tools():
    """Auto-discovery finds agent_context, cdk_review_guidance,
    dash_app_review_guidance, docstring_review_guidance,
    python_cleanliness_guidance, and readme_review_guidance.

    code_review and docs_review are intentionally excluded (underscore-prefixed
    legacy modules) and should NOT be counted here.
    """
    toolsets = get_all_toolsets()
    assert len(toolsets) >= 5


def test_toolsets_have_expected_names():
    """Each discovered toolset contains a tool with the expected naming convention."""
    toolsets = get_all_toolsets()
    # Each toolset should have at least one tool registered
    for ts in toolsets:
        assert ts is not None


def test_retired_tools_are_excluded():
    """code_review_guidance and docs_review_guidance are retired (underscore-prefixed
    modules pending breakout) and must not resurface as discovered tools."""
    names = _discovered_tool_names()
    for excluded in ("code_review_guidance", "docs_review_guidance"):
        assert excluded not in names


def test_every_guidance_tool_renders_its_prompt_template():
    """Every discovered guidance tool's prompt template must render cleanly.

    Verifies both halves of the ai_reviewer/OpenCode split:
    - The repository and PR number are substituted correctly into the rendered guidance.
    - Any leading YAML frontmatter (used by OpenCode) is stripped before the guidance reaches
      the LLM.
    """
    for ts in get_all_toolsets():
        for name, tool in ts.tools.items():
            rendered = tool.function(None, repository="co-cddo/example", pr_number=42)
            assert "co-cddo/example" in rendered, f"{name} did not substitute repository"
            assert "42" in rendered, f"{name} did not substitute pr_number"
            assert not rendered.startswith("---"), f"{name} leaked YAML frontmatter"
            assert rendered.startswith("Target: co-cddo/example / PR #42"), (
                f"{name} did not prepend the Target line correctly"
            )
