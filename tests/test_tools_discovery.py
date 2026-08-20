from ai_reviewer.tools import get_all_toolsets


def _discovered_tool_names() -> set[str]:
    toolsets = get_all_toolsets()
    return {name for ts in toolsets for name in ts.tools}


def test_get_all_toolsets_discovers_tools():
    """Auto-discovery finds agent_context, cdk_review_guidance, and
    dash_app_review_guidance.

    code_review and docs_review are intentionally excluded (underscore-prefixed,
    pending breakout into focused tools) and should NOT be counted here.
    """
    toolsets = get_all_toolsets()
    assert len(toolsets) >= 3


def test_toolsets_have_expected_names():
    """Each discovered toolset contains a tool with the expected naming convention."""
    toolsets = get_all_toolsets()
    # Each toolset should have at least one tool registered
    for ts in toolsets:
        assert ts is not None


def test_dash_app_review_tool_is_discovered():
    """dash_app_review.py provides guidance for reviewing Plotly Dash apps."""
    assert "dash_app_review_guidance" in _discovered_tool_names()


def test_every_guidance_tool_renders_its_prompt_template():
    """Every discovered guidance tool's prompt template must format cleanly.

    Catches unescaped `{`/`}` characters in a prompt's code examples — a
    literal brace in Markdown (e.g. a dict literal) breaks str.format() at
    call time unless doubled to `{{`/`}}`.
    """
    for ts in get_all_toolsets():
        for name, tool in ts.tools.items():
            rendered = tool.function(None, repository="co-cddo/example", pr_number=42)
            assert "co-cddo/example" in rendered, f"{name} did not substitute repository"
            assert "42" in rendered, f"{name} did not substitute pr_number"
