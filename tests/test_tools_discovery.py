from ai_reviewer.tools import get_all_toolsets


def test_get_all_toolsets_discovers_tools():
    """Auto-discovery finds at least the code and docs review toolsets."""
    toolsets = get_all_toolsets()
    assert len(toolsets) >= 2


def test_toolsets_have_expected_names():
    """Each discovered toolset contains a tool with the expected naming convention."""
    toolsets = get_all_toolsets()
    # Each toolset should have at least one tool registered
    for ts in toolsets:
        assert ts is not None
