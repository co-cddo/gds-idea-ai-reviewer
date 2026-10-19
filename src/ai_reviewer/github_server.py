"""GitHub MCP Server configuration for the AI reviewer agent."""

from pydantic_ai.mcp import MCPToolset, StdioTransport

# The only upstream tools exposed to the agent. The server fails at startup on an unknown
# name.
GITHUB_TOOLS = (
    "pull_request_read",  # PR metadata and diff (methods: get, get_diff, ...)
    "pull_request_review_write",  # post the review
    "get_file_contents",  # read files and list directories
    "get_repository_tree",  # repository tree for the project-context step
)


def get_github_server(github_token: str) -> MCPToolset:
    """
    Create and return a configured GitHub MCP server toolset.

    Uses the official GitHub MCP Server Docker image to provide
    GitHub API access via MCP tools. Only the tools in ``GITHUB_TOOLS``
    (read PRs and files, post a review) are exposed; write tools such as
    ``create_or_update_file`` or ``merge_pull_request`` are not registered.

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
            "-e",
            "GITHUB_TOOLS",
            "ghcr.io/github/github-mcp-server",
        ],
        env={
            "GITHUB_PERSONAL_ACCESS_TOKEN": github_token,
            "GITHUB_TOOLS": ",".join(GITHUB_TOOLS),
        },
    )
    # pydantic-ai defaults MCPToolset's init handshake timeout to 5s, which is too
    # tight for a cold `docker pull` of the MCP server image
    return MCPToolset(transport, init_timeout=60)
