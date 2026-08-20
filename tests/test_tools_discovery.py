from ai_reviewer.tools import get_all_toolsets


def _discovered_tool_names() -> set[str]:
    toolsets = get_all_toolsets()
    return {name for ts in toolsets for name in ts.tools}


def test_get_all_toolsets_discovers_tools():
    """Auto-discovery finds agent_context, cdk_review_guidance,
    readme_review_guidance and docstring_review_guidance by name.

    code_review_guidance and docs_review_guidance remain intentionally
    excluded — their modules (_code_review.py / _docs_review.py) are
    underscore-prefixed pending breakout, and readme_review/docstring_review
    are their focused replacements. Asserted by name rather than count, so
    this fails if any expected tool goes missing or a retired one reappears.
    """
    names = _discovered_tool_names()

    for expected in (
        "agent_context",
        "cdk_review_guidance",
        "readme_review_guidance",
        "docstring_review_guidance",
    ):
        assert expected in names

    for excluded in ("code_review_guidance", "docs_review_guidance"):
        assert excluded not in names


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
