"""Offline checks on the synthesized CDK stacks (no AWS access).

Guards against the cross-stack coupling that deadlocked model bumps (#35): an IAM stack
importing a profile ARN from the profiles stack creates a CloudFormation export, and
CloudFormation refuses to change an export while it is imported.

Skipped unless the `cdk` dependency group is installed (`uv sync --group cdk`).
"""

import json
import runpy
import sys
from pathlib import Path

import pytest

pytest.importorskip("aws_cdk")
pytest.importorskip("gds_idea_cdk_constructs")

from aws_cdk.assertions import Template  # noqa: E402
from gds_idea_cdk_constructs.config import DeploymentEnvironment  # noqa: E402

CDK_DIR = Path(__file__).resolve().parent.parent / "cdk"
# app.py rejects account IDs unknown to DeploymentEnvironment. Synthesis is offline, so nothing is deployed.
ACCOUNT = DeploymentEnvironment.DEVELOPMENT.value
REGION = "eu-west-2"
PARAMETER_PREFIX = "/ai-reviewer/inference-profiles/"


@pytest.fixture(scope="module")
def cdk_app(tmp_path_factory):
    """Run cdk/app.py (flat imports, so cdk/ must be on sys.path) and return its module globals."""
    mp = pytest.MonkeyPatch()
    mp.setenv("CDK_DEFAULT_ACCOUNT", ACCOUNT)
    mp.setenv("CDK_DEFAULT_REGION", REGION)
    mp.setenv("CDK_OUTDIR", str(tmp_path_factory.mktemp("cdk-out")))
    mp.syspath_prepend(str(CDK_DIR))
    try:
        yield runpy.run_path(str(CDK_DIR / "app.py"))
    finally:
        mp.undo()
        for name in ("config", "stacks", "stacks.iam_stack", "stacks.inference_profiles_stack"):
            sys.modules.pop(name, None)


@pytest.fixture(scope="module")
def profiles(cdk_app):
    stack = cdk_app["inference_profiles_stack"]
    return stack, Template.from_stack(stack).to_json()


@pytest.fixture(scope="module")
def iam(cdk_app):
    stack = cdk_app["iam_stack"]
    return stack, Template.from_stack(stack).to_json()


def test_every_team_profile_arn_is_published_to_ssm(profiles):
    _, template = profiles
    teams = {
        r["Properties"]["Name"].removeprefix(PARAMETER_PREFIX)
        for r in template["Resources"].values()
        if r["Type"] == "AWS::SSM::Parameter"
    }
    assert teams == {"ai-reviewer", "econ", "sds", "ds"}


def test_iam_policy_has_no_application_profile_wildcard(iam):
    _, template = iam
    assert "application-inference-profile/*" not in json.dumps(template)


def test_iam_stack_reads_only_the_ai_reviewer_profile_arn_from_ssm(iam):
    _, template = iam
    ssm_params = {
        p["Default"]
        for p in template["Parameters"].values()
        if p["Type"] == "AWS::SSM::Parameter::Value<String>" and not p["Default"].startswith("/cdk-bootstrap/")
    }
    assert ssm_params == {f"{PARAMETER_PREFIX}ai-reviewer"}


def test_iam_policy_references_the_ssm_parameter_for_the_profile(iam):
    _, template = iam
    policies = [r for r in template["Resources"].values() if r["Type"] == "AWS::IAM::Policy"]
    statements = [s for p in policies for s in p["Properties"]["PolicyDocument"]["Statement"]]
    (invoke,) = [s for s in statements if s["Sid"] == "AllowBedrockInvokeModel"]
    refs = [r["Ref"] for r in invoke["Resource"] if isinstance(r, dict)]
    assert len(refs) == 1 and refs[0] in template["Parameters"]


def test_iam_stack_depends_on_profiles_stack(cdk_app):
    assert cdk_app["inference_profiles_stack"] in cdk_app["iam_stack"].dependencies


def test_role_trusts_exactly_the_configured_github_orgs(iam):
    _, template = iam
    (role,) = [r for r in template["Resources"].values() if r["Type"] == "AWS::IAM::Role"]
    (statement,) = role["Properties"]["AssumeRolePolicyDocument"]["Statement"]
    subjects = statement["Condition"]["StringLike"]["token.actions.githubusercontent.com:sub"]
    assert sorted(subjects) == [
        "repo:co-cddo/*:*",
        "repo:co-cddo@*/*:*",
        "repo:gds-dtx/*:*",
        "repo:gds-dtx@*/*:*",
    ]
