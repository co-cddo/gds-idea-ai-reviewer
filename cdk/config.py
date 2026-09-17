"""Constants for the ai-reviewer CDK app."""

import aws_cdk as cdk

github_org = "co-cddo"
role_name = "ai-reviewer-role"
bedrock_model_id = "anthropic.claude-sonnet-5"

# Claude Sonnet 5 doesn't support on-demand inference,
# only geo or global cross-Region inference profiles work.
# eu.anthropic.claude-sonnet-5 profile can route to any of these regions,
# so bedrock:InvokeModel on the foundation model must be granted
# in all of them otherwise can cause a failure.
BEDROCK_FM_REGIONS = [
    "eu-central-1",
    "eu-central-2",
    "eu-north-1",
    "eu-south-1",
    "eu-south-2",
    "eu-west-1",
    "eu-west-2",
    "eu-west-3",
]


def eu_inference_profile_arn(cdk_env: cdk.Environment) -> str:
    """ARN of the eu inference profile, used as
    the model source for every team's application inference profile."""
    return f"arn:aws:bedrock:{cdk_env.region}:{cdk_env.account}:inference-profile/eu.{bedrock_model_id}"
