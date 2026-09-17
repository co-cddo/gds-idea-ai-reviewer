"""CDK app for deploying the AI Reviewer IAM infrastructure."""

import os

import aws_cdk as cdk
from stacks.iam_stack import AIReviewerIAMStack
from stacks.inference_profiles_stack import InferenceProfilesStack

app = cdk.App()

# Read configuration
phase = app.node.try_get_context("phase") or "dev"
account_number = app.node.try_get_context("account_number") or os.environ.get("CDK_DEFAULT_ACCOUNT")
region = app.node.try_get_context("region") or os.environ.get("CDK_DEFAULT_REGION", "eu-west-2")
bedrock_model_id = app.node.try_get_context("bedrock_model_id")

env = cdk.Environment(account=account_number, region=region)

# The shared source inference profile for every team.
cross_region_profile_arn = f"arn:aws:bedrock:{region}:{account_number}:inference-profile/eu.{bedrock_model_id}"

inference_profiles_stack = InferenceProfilesStack(
    app,
    f"ai-reviewer-inference-profiles-{phase}",
    env=env,
    cross_region_profile_arn=cross_region_profile_arn,
)

AIReviewerIAMStack(
    app,
    f"ai-reviewer-iam-{phase}",
    env=env,
    github_org=app.node.try_get_context("github_org"),
    role_name=app.node.try_get_context("role_name"),
    bedrock_model_id=bedrock_model_id,
    ai_reviewer_inference_profile_arn=inference_profiles_stack.profile_arns["ai-reviewer"],
)

cdk.Tags.of(app).add("Environment", phase)
cdk.Tags.of(app).add("ManagedBy", "cdk")
cdk.Tags.of(app).add("Repository", "co-cddo/gds-idea-ai-reviewer")
cdk.Tags.of(app).add("AppName", "ai-reviewer")

app.synth()
