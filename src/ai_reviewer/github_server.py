"""GitHub MCP Server configuration for the AI reviewer agent."""

from pydantic_ai.mcp import MCPToolset, StdioTransport


def get_github_server(github_token: str) -> MCPToolset:
    """
    Create and return a configured GitHub MCP server toolset.

    Uses the official GitHub MCP Server Docker image to provide
    GitHub API access via MCP tools (PRs, files, reviews, etc.).

    Args:
        github_token: GitHub token (PAT or GITHUB_TOKEN from Actions).

    Returns:
        Configured MCPToolset instance using the GitHub MCP server via stdio.
    """
    transport = StdioTransport(
        "docker",
        args=[
            "run",
            "-i",
            "--rm",
            "-e",
            "GITHUB_PERSONAL_ACCESS_TOKEN",
            "ghcr.io/github/github-mcp-server",
        ],
        env={"GITHUB_PERSONAL_ACCESS_TOKEN": github_token},
    )
    # pydantic-ai defaults MCPToolset's init handshake timeout to 5s, which is too
    # tight for a cold `docker pull` of the MCP server image
    return MCPToolset(transport, init_timeout=60)
