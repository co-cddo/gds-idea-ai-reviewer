"""IAM stack for the AI Reviewer GitHub Action.

Creates an IAM role that GitHub Actions can assume via OIDC to call
AWS Bedrock for AI-powered code reviews.

The GitHub OIDC provider must already exist in the account.
"""

import aws_cdk as cdk
import config
from aws_cdk import aws_iam as iam
from aws_cdk import aws_ssm as ssm
from constructs import Construct

from stacks.inference_profiles_stack import profile_arn_parameter_name


class AIReviewerIAMStack(cdk.Stack):
    """Stack that creates the IAM role for the AI reviewer GitHub Action.

    Args:
        github_orgs: GitHub organisations to trust (e.g. ['co-cddo', 'gds-dtx']).
        role_name: Name for the IAM role.
        bedrock_model_id: Bedrock model ID to grant InvokeModel access for.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        github_orgs: list[str],
        role_name: str,
        bedrock_model_id: str,
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
                        # GitHub's ID-qualified subjects add "@<id>" after the org and repo names.
                        "token.actions.githubusercontent.com:sub": [
                            subject
                            for org in github_orgs
                            for subject in (f"repo:{org}/*:*", f"repo:{org}@*/*:*")
                        ],
                    },
                    "StringEquals": {
                        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
                    },
                },
            ),
            max_session_duration=cdk.Duration.hours(1),
        )

        # The ai-reviewer profile ARN changes whenever the profile is replaced (e.g. on a model bump).
        # It is read from SSM, not imported from the profiles stack, because a CloudFormation export
        # that is in use blocks that replacement.
        profile_arn = ssm.StringParameter.value_for_string_parameter(
            self, profile_arn_parameter_name(config.INVOKING_PROFILE_TEAM)
        )

        # Grant bedrock:InvokeModel on the specific model and the ai-reviewer inference profile only
        role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowBedrockInvokeModel",
                actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
                resources=[
                    # Foundation model ARN, one per region the eu.* profile can route to
                    *[f"arn:aws:bedrock:{r}::foundation-model/{bedrock_model_id}" for r in config.BEDROCK_FM_REGIONS],
                    profile_arn,
                ],
            )
        )

        # Outputs
        cdk.CfnOutput(self, "RoleArn", value=role.role_arn, description="ARN of the AI reviewer IAM role")
        cdk.CfnOutput(self, "RoleName", value=role.role_name, description="Name of the AI reviewer IAM role")
