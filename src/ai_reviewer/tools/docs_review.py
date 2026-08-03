"""Docs review guidance tool."""

from ai_reviewer.tools._tool_template import make_review_tool

toolset = make_review_tool(
    name="docs_review_guidance",
    prompt_file="docs_review.md",
    description="Get detailed instructions for reviewing documentation in a pull request.",
)
