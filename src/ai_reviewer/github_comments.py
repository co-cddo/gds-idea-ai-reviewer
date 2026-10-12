"""Post comments on GitHub pull requests."""

import httpx

GITHUB_API = "https://api.github.com"
TIMEOUT_SECONDS = 30


def post_pr_comment(
    repo: str,
    pr_number: int,
    body: str,
    token: str,
    client: httpx.Client | None = None,
) -> str:
    """Post a conversation comment on a pull request.

    Args:
        repo: Repository in 'owner/repo' format.
        pr_number: Pull request number.
        body: Markdown body of the comment.
        token: GitHub token allowed to write to the pull request.
        client: Optional HTTP client, used to override the transport in tests.

    Returns:
        The URL of the created comment.

    Raises:
        httpx.HTTPError: If the request fails or GitHub returns an error status.
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    url = f"{GITHUB_API}/repos/{repo}/issues/{pr_number}/comments"
    owns_client = client is None
    client = client or httpx.Client(timeout=TIMEOUT_SECONDS)
    try:
        response = client.post(url, headers=headers, json={"body": body})
        response.raise_for_status()
        return response.json()["html_url"]
    finally:
        if owns_client:
            client.close()
