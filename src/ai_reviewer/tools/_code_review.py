"""Code review guidance tool."""

from ai_reviewer.tools._tool_template import make_review_tool

toolset = make_review_tool(
    name="code_review_guidance",
    prompt_file="code_review.md",
    description=(
        "Get instructions for reviewing general source code changes. "
        "Call this tool when the PR contains changes to application source files "
        "(.py, .sql, .html, .css, .js, .ts, .yaml, .json, .toml) or GitHub Actions "
        "workflows. If a more specialised tool exists for specific files (e.g. CDK "
        "infrastructure, documentation), prefer that tool — but still call this one "
        "for any remaining general source code."
    ),
)
