"""AI Reviewer Agent - orchestrates code review using Bedrock and GitHub MCP."""

from importlib.resources import files

from pydantic_ai import Agent
from pydantic_ai.models.bedrock import BedrockConverseModel, BedrockModelSettings
from pydantic_ai.providers.bedrock import BedrockProvider

from ai_reviewer.github_server import get_github_server
from ai_reviewer.tools import get_all_toolsets


class ReviewerAgent:
    """
    AI code review agent using AWS Bedrock Claude and GitHub MCP Server.

    Connects to GitHub via the official MCP Server (Docker) and uses
    Bedrock for inference. Designed to run in GitHub Actions with OIDC
    authentication (default credential chain) or locally with an AWS profile.

    Review tools are auto-discovered from the ai_reviewer.tools package.
    To add a new tool, create a prompt in prompts/ and a module in tools/.

    Args:
        github_token: GitHub token for MCP server and PR access.
        model_id: AWS Bedrock model ID.
        aws_region: AWS region for Bedrock API calls.
        aws_profile: Optional AWS profile name (for local testing only).
        inference_profile_arn: Bedrock inference profile ARN. When
            set, requests are routed through this inference profile (for
            cost tracking).
    """

    def __init__(
        self,
        github_token: str,
        model_id: str = "anthropic.claude-sonnet-5",
        aws_region: str = "eu-west-2",
        aws_profile: str | None = None,
        inference_profile_arn: str | None = None,
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

        # Load agent-level instructions (submission template, combination logic)
        agent_instructions = files("ai_reviewer.prompts").joinpath("agent_prompt.md").read_text()

        model_settings = (
            BedrockModelSettings(bedrock_inference_profile=inference_profile_arn) if inference_profile_arn else None
        )

        # Create agent with GitHub MCP + all discovered review toolsets
        self.agent = Agent(
            BedrockConverseModel(model_id, provider=self.bedrock_provider, settings=model_settings),
            instructions=agent_instructions,
            toolsets=[self.github_server, *get_all_toolsets()],
        )

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
            f"Fetch the diff, examine the changed files, and select which "
            f"guidance tools are relevant based on what you observe. "
            f"Call only the relevant tools, follow their instructions, "
            f"and submit a single combined PR review."
        )

        async with self.agent:
            result = await self.agent.run(query)
            return result.output
