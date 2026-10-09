"""AI Reviewer Agent - orchestrates code review using Bedrock and GitHub MCP."""

from dataclasses import dataclass
from importlib.resources import files

from pydantic_ai import Agent
from pydantic_ai.models.bedrock import BedrockConverseModel, BedrockModelSettings
from pydantic_ai.providers.bedrock import BedrockProvider

from ai_reviewer import config
from ai_reviewer.github_server import get_github_server
from ai_reviewer.run_report import format_run_report
from ai_reviewer.tools import get_all_toolsets


@dataclass(frozen=True)
class ReviewResult:
    """Outcome of a review run.

    Attributes:
        output: The model's final message summarising the review it submitted.
        report: Plain-text run report listing tools called, token usage and estimated cost.
    """

    output: str
    report: str


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
        max_tokens: Maximum output tokens for Bedrock requests. Defaults
            to ai_reviewer.config.MAX_TOKENS.
        enable_thinking: Whether the model thinks before replying. When
            False, it only writes short updates between tool calls.
            Defaults to ai_reviewer.config.ENABLE_THINKING.
    """

    def __init__(
        self,
        github_token: str,
        model_id: str = "anthropic.claude-sonnet-5-5",
        aws_region: str = "eu-west-2",
        aws_profile: str | None = None,
        inference_profile_arn: str | None = None,
        max_tokens: int = config.MAX_TOKENS,
        enable_thinking: bool = config.ENABLE_THINKING,
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

        model_settings = BedrockModelSettings(max_tokens=max_tokens)
        if not enable_thinking:
            # Sonnet 5.5 turns thinking off with "between_tools".
            model_settings["bedrock_additional_model_requests_fields"] = {"thinking": {"type": "between_tools"}}
        if inference_profile_arn:
            model_settings["bedrock_inference_profile"] = inference_profile_arn

        # Create agent with GitHub MCP + all discovered review toolsets
        self.model_id = model_id
        review_toolsets = get_all_toolsets()
        self.guidance_tool_names = {name for toolset in review_toolsets for name in toolset.tools}
        self.agent = Agent(
            BedrockConverseModel(model_id, provider=self.bedrock_provider, settings=model_settings),
            instructions=agent_instructions,
            toolsets=[self.github_server, *review_toolsets],
        )

    async def review(self, repo: str, pr_number: int) -> ReviewResult:
        """
        Run an AI code review on a pull request.

        Fetches the PR diff via GitHub MCP, analyses code changes and
        documentation, then submits a review with inline comments.

        Args:
            repo: Repository in 'owner/repo' format.
            pr_number: Pull request number to review.

        Returns:
            The model's summary of the review it submitted, plus a run report
            built from the run's actual tool calls and usage.
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
            report = format_run_report(result.all_messages(), result.usage, self.guidance_tool_names, self.model_id)
            return ReviewResult(output=result.output, report=report)
