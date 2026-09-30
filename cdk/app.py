"""CDK app for deploying the AI Reviewer IAM infrastructure."""

import os

import aws_cdk as cdk
import config
from gds_idea_cdk_constructs import IdeaTags
from gds_idea_cdk_constructs.config import DeploymentEnvironment
from stacks.iam_stack import AIReviewerIAMStack
from stacks.inference_profiles_stack import InferenceProfilesStack

app = cdk.App()

cdk_env = cdk.Environment(
    account=os.environ["CDK_DEFAULT_ACCOUNT"],
    region=os.environ.get("CDK_DEFAULT_REGION", "eu-west-2"),
)
deployment_environment = DeploymentEnvironment.from_cdk_env(cdk_env)
phase = deployment_environment.short_name

inference_profiles_stack = InferenceProfilesStack(
    app,
    f"ai-reviewer-inference-profiles-{phase}",
    env=cdk_env,
    model_source_arn=config.eu_inference_profile_arn(cdk_env),
)

AIReviewerIAMStack(
    app,
    f"ai-reviewer-iam-{phase}",
    env=cdk_env,
    github_org=config.github_org,
    role_name=config.role_name,
    bedrock_model_id=config.bedrock_model_id,
    ai_reviewer_inference_profile_arn=inference_profiles_stack.profile_arns["ai-reviewer"],
)

IdeaTags(
    environment=deployment_environment,
    app_name="ai-reviewer",
    repository="gds-idea-ai-reviewer",
).apply(app)

app.synth()
