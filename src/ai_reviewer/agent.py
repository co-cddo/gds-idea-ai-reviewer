"""AI Reviewer Agent - orchestrates code review using Bedrock and GitHub MCP."""

from pydantic_ai import Agent
from pydantic_ai.models.bedrock import BedrockConverseModel
from pydantic_ai.providers.bedrock import BedrockProvider

from ai_reviewer.code_review_tool import code_review_tool
from ai_reviewer.docs_review_tool import docs_review_tool
from ai_reviewer.github_server import get_github_server


class ReviewerAgent:
    """
    AI code review agent using AWS Bedrock Claude and GitHub MCP Server.

    Connects to GitHub via the official MCP Server (Docker) and uses
    Bedrock for inference. Designed to run in GitHub Actions with OIDC
    authentication (default credential chain) or locally with an AWS profile.

    Registers two guidance tools:
    - code_review_guidance: Reviews source code, config files, workflows
    - docs_review_guidance: Reviews README/markdown files and Python docstrings

    Args:
        github_token: GitHub token for MCP server and PR access.
        model_id: AWS Bedrock model ID.
        aws_region: AWS region for Bedrock API calls.
        aws_profile: Optional AWS profile name (for local testing only).
    """

    def __init__(
        self,
        github_token: str,
        model_id: str = "anthropic.claude-sonnet-4-6",
        aws_region: str = "eu-west-2",
        aws_profile: str | None = None,
    ):
        # Setup Bedrock provider
        # In GitHub Actions: uses OIDC (default credential chain)
        # Locally: uses named profile (e.g. bedrock-user-jose)
        provider_kwargs: dict = {"region_name": aws_region}
        if aws_profile:
            provider_kwargs["profile_name"] = aws_profile
        self.bedrock_provider = BedrockProvider(**provider_kwargs)

        # Setup GitHub MCP server (Docker-based)
        self.github_server = get_github_server(github_token)

        # Create agent with GitHub toolset
        self.agent = Agent(
            BedrockConverseModel(model_id, provider=self.bedrock_provider),
            toolsets=[self.github_server],
        )

        # Register guidance tools
        code_review_tool(self.agent)
        docs_review_tool(self.agent)

    async def review(self, repo: str, pr_number: int) -> str:
        """
        Run an AI code review on a pull request.

        Fetches the PR diff via GitHub MCP, analyses code changes and
        documentation, then submits a review with inline comments.

        Args:
            repo: Repository in 'owner/repo' format.
            pr_number: Pull request number to review.

        Returns:
            Summary of the review that was submitted.
        """
        query = (
            f"Review pull request #{pr_number} in repository {repo}. "
            f"Use the code_review_guidance tool with repository='{repo}' "
            f"and pr_number={pr_number} to get review instructions for source code and config files. "
            f"Also use the docs_review_guidance tool with the same arguments to get instructions "
            f"for reviewing documentation (markdown files and Python docstrings). "
            f"Follow both sets of instructions and submit a single combined PR review."
        )

        async with self.agent:
            result = await self.agent.run(query)
            return result.output
