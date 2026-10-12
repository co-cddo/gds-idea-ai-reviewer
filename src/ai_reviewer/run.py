"""Entry point for the AI reviewer agent when run from GitHub Actions or locally."""

import asyncio
import os
import sys

import httpx

from ai_reviewer.agent import ReviewerAgent
from ai_reviewer.github_comments import post_pr_comment


async def main() -> None:
    """Run the AI code review agent using environment variables for configuration."""
    # Required environment variables (set by action.yml or manually for local testing)
    github_token = os.environ.get("GITHUB_TOKEN")
    pr_number_str = os.environ.get("PR_NUMBER")
    repo = os.environ.get("REPO")

    if not github_token:
        print("Error: GITHUB_TOKEN environment variable is required")
        sys.exit(1)
    if not pr_number_str:
        print("Error: PR_NUMBER environment variable is required")
        sys.exit(1)
    if not repo:
        print("Error: REPO environment variable is required")
        sys.exit(1)

    pr_number = int(pr_number_str)

    # Optional configuration
    model_id = os.environ.get("MODEL_ID", "anthropic.claude-sonnet-5-5")
    aws_region = os.environ.get("AWS_REGION", "eu-west-2")
    aws_profile = os.environ.get("AWS_PROFILE")  # For local testing only (not used in Actions)
    inference_profile_arn = os.environ.get("BEDROCK_INFERENCE_PROFILE_ARN")

    print(f"Starting AI review for {repo}#{pr_number}")
    print(f"Model: {model_id} | Region: {aws_region}")
    if aws_profile:
        print(f"AWS Profile: {aws_profile} (local mode)")
    if inference_profile_arn:
        print(f"Inference profile: {inference_profile_arn}")

    agent = ReviewerAgent(
        github_token=github_token,
        model_id=model_id,
        aws_region=aws_region,
        aws_profile=aws_profile,
        inference_profile_arn=inference_profile_arn,
    )

    result = await agent.review(repo=repo, pr_number=pr_number)

    print("Review complete.")
    print(result.output)
    print()
    print(result.report)

    post_report_comment(repo, pr_number, result.report_comment, github_token)


def post_report_comment(repo: str, pr_number: int, body: str, token: str) -> None:
    """Post the run report on the PR, warning instead of failing if GitHub rejects it."""
    try:
        url = post_pr_comment(repo, pr_number, body, token)
    except httpx.HTTPError as exc:
        print(f"Warning: could not post run report comment: {exc}", file=sys.stderr)
    else:
        print(f"Posted run report comment: {url}")


if __name__ == "__main__":
    asyncio.run(main())
