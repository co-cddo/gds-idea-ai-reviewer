"""Generic Python cleanliness review guidance tool."""

from ai_reviewer.tools._tool_template import make_review_tool

toolset = make_review_tool(
    name="python_cleanliness_guidance",
    prompt_file="python-cleanliness/SKILL.md",
    description=(
        "Get instructions for reviewing general Python code cleanliness: function "
        "design, naming/constants, layering, error handling, and code structure. "
        "Call this tool whenever the PR contains any added or modified .py files."
    ),
)
