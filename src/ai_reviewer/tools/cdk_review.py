"""CDK infrastructure review guidance tool."""

from ai_reviewer.tools._tool_template import make_review_tool

toolset = make_review_tool(
    name="cdk_review_guidance",
    prompt_file="cdk-review/SKILL.md",
    description=(
        "Get instructions for reviewing AWS CDK infrastructure code, "
        "including Lambda/app deployment conventions (folder layout, "
        "logging). Call this tool when the PR touches ANY of: cdk.json, "
        "cdk.context.json, app.py, config.py, any file under stacks/, "
        "any file under lambda/, app_src/Dockerfile, "
        "tests/unit/test_*_stack.py, or any file importing aws_cdk / "
        "aws_cdk_lib. Also call it when aws-cdk-lib is listed as a "
        "dependency in pyproject.toml, even if no CDK files changed in "
        "this specific diff (repo-level fallback signal, e.g. first PR "
        "against a new CDK repo)."
    ),
)
