"""Constants for the ai-reviewer CDK app."""

import aws_cdk as cdk

github_org = "co-cddo"
role_name = "ai-reviewer-role"
bedrock_model_id = "anthropic.claude-sonnet-5"

# Regions to grant bedrock:InvokeModel for the underlying foundation model.
# Kept to eu-west-2 only so it's not going all across Europe
BEDROCK_FM_REGIONS = ["eu-west-2"]


def foundation_model_arn(cdk_env: cdk.Environment) -> str:
    """ARN of the foundation model in cdk_env's region, used as the model
    source for every team's application inference profile."""
    return f"arn:aws:bedrock:{cdk_env.region}::foundation-model/{bedrock_model_id}"
