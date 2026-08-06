"""Project context guidance tool — called unconditionally on every PR."""

from ai_reviewer.tools._tool_template import make_review_tool

toolset = make_review_tool(
    name="agent_guidance",
    prompt_file="agent_guidance.md",
    description=(
        "Get instructions for building a concise understanding of this "
        "repository's structure, conventions, and build/test commands. "
        "ALWAYS call this tool FIRST, before any other guidance tool and "
        "before analysing the diff — regardless of which files changed."
    ),
)
