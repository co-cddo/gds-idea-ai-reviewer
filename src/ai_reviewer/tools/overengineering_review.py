"""Overengineering review guidance tool."""

from ai_reviewer.tools._tool_template import make_review_tool

toolset = make_review_tool(
    name="overengineering_review_guidance",
    prompt_file="overengineering-review/SKILL.md",
    description=(
        "Get instructions for spotting overengineered or AI-bloated Python: speculative "
        "abstraction, scope creep, defensive code that cannot trigger, reinvented standard "
        "library features, and unnecessary complexity. "
        "Call this tool whenever the PR contains any added or modified .py files."
    ),
)
