"""Test the run entrypoint's run report comment handling."""

import httpx

from ai_reviewer import run


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
