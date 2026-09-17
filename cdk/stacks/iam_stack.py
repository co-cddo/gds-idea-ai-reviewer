"""IAM stack for the AI Reviewer GitHub Action.

Creates an IAM role that GitHub Actions can assume via OIDC to call
AWS Bedrock for AI-powered code reviews.

The GitHub OIDC provider must already exist in the account.
"""

import aws_cdk as cdk
import config
from aws_cdk import aws_iam as iam
from constructs import Construct


class AIReviewerIAMStack(cdk.Stack):
    """Stack that creates the IAM role for the AI reviewer GitHub Action.

    Args:
        github_org: GitHub organisation to trust (e.g. 'co-cddo').
        role_name: Name for the IAM role.
        bedrock_model_id: Bedrock model ID to grant InvokeModel access for.
        ai_reviewer_inference_profile_arn: inference profile of the ai-reviewer-specific ARN
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        github_org: str,
        role_name: str,
        bedrock_model_id: str,
        ai_reviewer_inference_profile_arn: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Import the existing GitHub OIDC provider.
        # This provider is created once per account and is shared across all
        # workflows that use OIDC auth (CDK deploy, Terraform, etc.).
        # ARN format is deterministic: arn:aws:iam::<account>:oidc-provider/<issuer>
        oidc_provider_arn = f"arn:aws:iam::{self.account}:oidc-provider/token.actions.githubusercontent.com"

        oidc_provider = iam.OpenIdConnectProvider.from_open_id_connect_provider_arn(
            self,
            "GitHubOIDCProvider",
            open_id_connect_provider_arn=oidc_provider_arn,
        )

        # Create the AI reviewer role, trusted by the GitHub org via OIDC
        role = iam.Role(
            self,
            "AIReviewerRole",
            role_name=role_name,
            description="IAM role for the GDS IDEA AI code reviewer GitHub Action. Grants bedrock:InvokeModel only.",
            assumed_by=iam.WebIdentityPrincipal(
                oidc_provider.open_id_connect_provider_arn,
                conditions={
                    "StringLike": {
                        "token.actions.githubusercontent.com:sub": f"repo:{github_org}/*:*",
                    },
                    "StringEquals": {
                        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
                    },
                },
            ),
            max_session_duration=cdk.Duration.hours(1),
        )

        # Grant bedrock:InvokeModel on the specific model and application inference profile only
        role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowBedrockInvokeModel",
                actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
                resources=[
                    # Foundation model ARN
                    *[f"arn:aws:bedrock:{r}::foundation-model/{bedrock_model_id}" for r in config.BEDROCK_FM_REGIONS],
                    ai_reviewer_inference_profile_arn,
                ],
            )
        )

        # Outputs
        cdk.CfnOutput(self, "RoleArn", value=role.role_arn, description="ARN of the AI reviewer IAM role")
        cdk.CfnOutput(self, "RoleName", value=role.role_name, description="Name of the AI reviewer IAM role")
