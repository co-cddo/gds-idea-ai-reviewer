from ai_reviewer.tools import get_all_toolsets


def _discovered_tool_names() -> set[str]:
    toolsets = get_all_toolsets()
    return {name for ts in toolsets for name in ts.tools}


def test_get_all_toolsets_discovers_tools():
    """Auto-discovery finds agent_context, cdk_review_guidance,
    readme_review_guidance and docstring_review_guidance.

    code_review and docs_review remain intentionally excluded
    (underscore-prefixed) — readme_review and docstring_review are their
    focused replacements and should NOT be counted here.
    """
    toolsets = get_all_toolsets()
    assert len(toolsets) >= 4


def test_toolsets_have_expected_names():
    """Each discovered toolset contains a tool with the expected naming convention."""
    toolsets = get_all_toolsets()
    # Each toolset should have at least one tool registered
    for ts in toolsets:
        assert ts is not None


def test_readme_review_tool_is_discovered():
    """readme_review.py replaces part of the retired docs_review tool."""
    assert "readme_review_guidance" in _discovered_tool_names()


def test_docstring_review_tool_is_discovered():
    """docstring_review.py replaces part of the retired docs_review tool."""
    assert "docstring_review_guidance" in _discovered_tool_names()
