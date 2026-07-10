"""CDK app for deploying the AI Reviewer IAM infrastructure."""

import os

import aws_cdk as cdk

from stacks.iam_stack import AIReviewerIAMStack

app = cdk.App()

# Read configuration from context (set in cdk.json or via --context)
phase = app.node.try_get_context("phase") or "dev"
account_number = app.node.try_get_context("account_number") or os.environ.get("CDK_DEFAULT_ACCOUNT")
region = app.node.try_get_context("region") or os.environ.get("CDK_DEFAULT_REGION", "eu-west-2")

env = cdk.Environment(account=account_number, region=region)

AIReviewerIAMStack(
    app,
    f"ai-reviewer-iam-{phase}",
    env=env,
    github_org=app.node.try_get_context("github_org"),
    role_name=app.node.try_get_context("role_name"),
    bedrock_model_id=app.node.try_get_context("bedrock_model_id"),
)

cdk.Tags.of(app).add("Environment", phase)
cdk.Tags.of(app).add("ManagedBy", "cdk")
cdk.Tags.of(app).add("Repository", "co-cddo/gds-idea-ai-reviewer")
cdk.Tags.of(app).add("AppName", "ai-reviewer")

app.synth()
