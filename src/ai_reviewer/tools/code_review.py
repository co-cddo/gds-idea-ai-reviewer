"""Code review guidance tool."""

from ai_reviewer.tools._tool_template import make_review_tool

toolset = make_review_tool(
    name="code_review_guidance",
    prompt_file="code_review.md",
    description="Get detailed instructions for performing an AI code review on a pull request.",
)
