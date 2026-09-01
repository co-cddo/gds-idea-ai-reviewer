"""Docstring review guidance tool."""

from ai_reviewer.tools._tool_template import make_review_tool

toolset = make_review_tool(
    name="docstring_review_guidance",
    prompt_file="docstring_review.md",
    description=(
        "Get instructions for reviewing Python docstrings. "
        "Call this tool when the PR adds or modifies public functions, "
        "classes, or modules in .py files. README and other Markdown files "
        "are handled by the README reviewer, not this tool."
    ),
)
