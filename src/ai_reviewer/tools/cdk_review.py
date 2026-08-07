"""CDK infrastructure review guidance tool."""

from ai_reviewer.tools._tool_template import make_review_tool

toolset = make_review_tool(
    name="cdk_review_guidance",
    prompt_file="cdk_review.md",
    description=(
        "Get instructions for reviewing AWS CDK infrastructure code. "
        "Call this tool when the PR contains: cdk.json, app.py alongside "
        "a stacks/ directory, files importing aws_cdk or aws_cdk_lib, "
        "OR when aws-cdk-lib is listed as a dependency in pyproject.toml."
    ),
)
