"""Inference profiles stack.

Creates one Bedrock Application Inference Profile per team, each copying
the same eu.anthropic.claude-sonnet-5-5 inference profile as source. Each profile's
ARN is published to the SSM parameter `/ai-reviewer/inference-profiles/<team>`.
"""

import aws_cdk as cdk
from aws_cdk import aws_bedrock as bedrock
from aws_cdk import aws_ssm as ssm
from constructs import Construct

# Teams to create an Application Inference Profile for.
TEAMS = ["ai-reviewer", "econ", "sds", "ds"]


def profile_arn_parameter_name(team: str) -> str:
    """Name of the SSM parameter holding a team's application inference profile ARN."""
    return f"/ai-reviewer/inference-profiles/{team}"


class InferenceProfilesStack(cdk.Stack):
    """Stack that creates one Application Inference Profile per team.

    Args:
        model_source_arn: ARN of the inference profile to use as the
            model source for every team's application inference profile.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        model_source_arn: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.profile_arns: dict[str, str] = {}

        for team in TEAMS:
            profile = bedrock.CfnApplicationInferenceProfile(
                self,
                f"{team.title().replace('-', '')}InferenceProfile",
                inference_profile_name=team,
                description=f"Application inference profile for the {team} team used for cost tracking.",
                model_source=bedrock.CfnApplicationInferenceProfile.InferenceProfileModelSourceProperty(
                    copy_from=model_source_arn,
                ),
                tags=[cdk.CfnTag(key="Team", value=team)],
            )

            self.profile_arns[team] = profile.attr_inference_profile_arn

            # Publish the ARN via SSM rather than a CloudFormation export. Profiles are replaced
            # (new generated ARN) on a model bump.
            ssm.StringParameter(
                self,
                f"{team.title().replace('-', '')}InferenceProfileArnParameter",
                parameter_name=profile_arn_parameter_name(team),
                string_value=profile.attr_inference_profile_arn,
                description=f"ARN of the {team} application inference profile",
            )

            cdk.CfnOutput(
                self,
                f"{team.title().replace('-', '')}InferenceProfileArn",
                value=profile.attr_inference_profile_arn,
                description=f"ARN of the {team} application inference profile",
            )
