"""Test the run entrypoint's environment handling and run report comment handling."""

import asyncio

import httpx
import pytest

from ai_reviewer import run


@pytest.fixture
def required_env(monkeypatch) -> None:
    """Set the env vars run.main() requires, and clear the optional inference profile one."""
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setenv("PR_NUMBER", "7")
    monkeypatch.setenv("REPO", "o/r")
    monkeypatch.delenv("BEDROCK_INFERENCE_PROFILE_ARN", raising=False)


@pytest.mark.parametrize("value", ["", "   "])
def test_main_rejects_empty_inference_profile_arn(monkeypatch, capsys, required_env, value) -> None:
    """An empty ARN (e.g. a failed lookup) must fail fast, not fall back to the base model ID."""
    monkeypatch.setenv("BEDROCK_INFERENCE_PROFILE_ARN", value)

    with pytest.raises(SystemExit) as exc_info:
        asyncio.run(run.main())

    assert exc_info.value.code == 1
    assert "BEDROCK_INFERENCE_PROFILE_ARN" in capsys.readouterr().out


def test_main_passes_inference_profile_arn_to_agent(monkeypatch, required_env) -> None:
    """A non-empty ARN is handed to ReviewerAgent unchanged."""
    arn = "arn:aws:bedrock:eu-west-2:123456789012:application-inference-profile/abc"
    monkeypatch.setenv("BEDROCK_INFERENCE_PROFILE_ARN", arn)
    captured: dict = {}

    class StubResult:
        output = "output"
        report = "report"
        report_comment = "comment"

    class StubAgent:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

        async def review(self, repo: str, pr_number: int) -> StubResult:
            return StubResult()

    monkeypatch.setattr(run, "ReviewerAgent", StubAgent)
    monkeypatch.setattr(run, "post_report_comment", lambda *args: None)

    asyncio.run(run.main())

    assert captured["inference_profile_arn"] == arn


def test_post_report_comment_prints_url_on_success(monkeypatch, capsys) -> None:
    """A posted comment is reported on stdout."""
    monkeypatch.setattr(run, "post_pr_comment", lambda repo, pr, body, token: "https://example/c/1")

    run.post_report_comment("o/r", 7, "body", "tok")

    assert "Posted run report comment: https://example/c/1" in capsys.readouterr().out


def test_post_report_comment_warns_instead_of_raising(monkeypatch, capsys) -> None:
    """A GitHub failure must not fail a review that already completed."""

    def boom(repo, pr, body, token):
        raise httpx.ConnectError("no network")

    monkeypatch.setattr(run, "post_pr_comment", boom)

    run.post_report_comment("o/r", 7, "body", "tok")

    assert "Warning: could not post run report comment: no network" in capsys.readouterr().err
