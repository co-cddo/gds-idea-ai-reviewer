"""Test posting comments on pull requests."""

import httpx
import pytest

from ai_reviewer.github_comments import post_pr_comment


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_post_pr_comment_sends_expected_request() -> None:
    """The comment goes to the issue comments endpoint with auth headers and the body."""
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["Authorization"]
        seen["body"] = request.read()
        return httpx.Response(201, json={"html_url": "https://github.com/o/r/pull/7#issuecomment-1"})

    url = post_pr_comment("o/r", 7, "hello", "tok", client=_client(handler))

    assert url == "https://github.com/o/r/pull/7#issuecomment-1"
    assert seen["method"] == "POST"
    assert seen["url"] == "https://api.github.com/repos/o/r/issues/7/comments"
    assert seen["auth"] == "Bearer tok"
    assert seen["body"] == b'{"body":"hello"}'


def test_post_pr_comment_raises_on_error_status() -> None:
    """A rejected request surfaces as an HTTPError for the caller to handle."""
    client = _client(lambda request: httpx.Response(403, json={"message": "forbidden"}))

    with pytest.raises(httpx.HTTPStatusError):
        post_pr_comment("o/r", 7, "hello", "tok", client=client)
