"""README review guidance tool."""

from ai_reviewer.tools._tool_template import make_review_tool

toolset = make_review_tool(
    name="readme_review_guidance",
    prompt_file="readme-review/SKILL.md",
    description=(
        "Get instructions for reviewing README files. "
        "Call this tool when the PR adds or modifies a README.md, README.rst, "
        "or any nested README.* file, OR when the PR changes behaviour "
        "(CLI flags, env vars, endpoints, config options) that an existing "
        "README documents."
    ),
)
