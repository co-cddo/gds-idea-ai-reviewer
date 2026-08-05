"""Docs review guidance tool."""

from ai_reviewer.tools._tool_template import make_review_tool

toolset = make_review_tool(
    name="docs_review_guidance",
    prompt_file="docs_review.md",
    description=(
        "Get instructions for reviewing documentation changes. "
        "Call this tool when the PR contains .md or .rst files, "
        "OR when new/modified public Python functions may need docstrings."
    ),
)
