"""Inference profiles stack.

Creates one Bedrock Application Inference Profile per team, each copying
same eu-west-2 foundation model as its model source.
"""

import aws_cdk as cdk
from aws_cdk import aws_bedrock as bedrock
from constructs import Construct

# Teams to create an Application Inference Profile for.
TEAMS = ["ai-reviewer", "econ", "sds", "ds"]


class InferenceProfilesStack(cdk.Stack):
    """Stack that creates one Application Inference Profile per team.

    Args:
        foundation_model_arn: ARN of the foundation model to use as the
            model source for every team's application inference profile.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        foundation_model_arn: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.profile_arns: dict[str, str] = {}

        for team in TEAMS:
            profile = bedrock.CfnApplicationInferenceProfile(
                self,
                f"{team.title().replace('-', '')}InferenceProfile",
                inference_profile_name=team,
                description=f"Application inference profile for the {team} team, used for cost tracking.",
                model_source=bedrock.CfnApplicationInferenceProfile.InferenceProfileModelSourceProperty(
                    copy_from=foundation_model_arn,
                ),
                tags=[cdk.CfnTag(key="Team", value=team)],
            )

            self.profile_arns[team] = profile.attr_inference_profile_arn

            cdk.CfnOutput(
                self,
                f"{team.title().replace('-', '')}InferenceProfileArn",
                value=profile.attr_inference_profile_arn,
                description=f"ARN of the {team} application inference profile",
            )
