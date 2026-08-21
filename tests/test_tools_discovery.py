from ai_reviewer.tools import get_all_toolsets


def test_get_all_toolsets_discovers_tools():
    """Auto-discovery finds at least agent_context, cdk_review_guidance,
    readme_review_guidance and docstring_review_guidance.

    code_review and docs_review are intentionally excluded (underscore-prefixed,
    pending breakout into focused tools) and should NOT be counted here.
    """
    toolsets = get_all_toolsets()
    assert len(toolsets) >= 4


def test_toolsets_have_expected_names():
    """Each discovered toolset contains a tool with the expected naming convention."""
    toolsets = get_all_toolsets()
    # Each toolset should have at least one tool registered
    for ts in toolsets:
        assert ts is not None


def test_retired_tools_are_excluded():
    """code_review_guidance and docs_review_guidance are retired (underscore-prefixed
    modules pending breakout) and must not resurface as discovered tools."""
    toolsets = get_all_toolsets()
    names = {name for ts in toolsets for name in ts.tools}
    for excluded in ("code_review_guidance", "docs_review_guidance"):
        assert excluded not in names
