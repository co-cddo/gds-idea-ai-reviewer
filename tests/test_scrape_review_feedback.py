"""Test the review-feedback scraper's matching, row shaping and orchestration (offline)."""

import csv
import importlib.util
import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "scrape_review_feedback.py"
_spec = importlib.util.spec_from_file_location("scrape_review_feedback", _SCRIPT)
scraper = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(scraper)


def _comment(body: str | None, user_type: str = "User", login: str = "alice") -> dict:
    return {
        "id": 1,
        "html_url": "https://github.com/o/r/pull/7#issuecomment-1",
        "created_at": "2026-10-01T10:00:00Z",
        "user": {"login": login, "type": user_type},
        "body": body,
    }


def _pr(number: int = 7, repo: str = "o/r") -> dict:
    return {
        "number": number,
        "repository": {"nameWithOwner": repo},
        "state": "merged",
        "url": f"https://github.com/{repo}/pull/{number}",
        "title": "A PR",
    }


@pytest.mark.parametrize(
    ("comment", "expected"),
    [
        (_comment("## AI REVIEW FEEDBACK\nGood catch on the IAM policy"), True),
        (_comment("\n  ## AI REVIEW FEEDBACK\nleading whitespace"), True),
        (_comment("## ai review feedback\nlower case"), True),
        (_comment("##  AI REVIEW FEEDBACK"), True),
        (_comment("### AI REVIEW FEEDBACK\nh3 not h2"), False),
        (_comment("# AI REVIEW FEEDBACK\nh1 not h2"), False),
        (_comment("##AI REVIEW FEEDBACK\nno space"), False),
        (_comment("## AI Review Loop — Summary"), False),
        (_comment("Thanks!\n## AI REVIEW FEEDBACK\nheader not at start"), False),
        (_comment("## AI REVIEW FEEDBACK\nfrom a bot", user_type="Bot", login="github-actions[bot]"), False),
        (_comment(""), False),
        (_comment(None), False),
        ({"id": 2, "body": "## AI REVIEW FEEDBACK", "user": None}, True),
    ],
)
def test_is_feedback_comment(comment: dict, expected: bool) -> None:
    """Only human comments that begin with the h2 feedback header match."""
    assert scraper.is_feedback_comment(comment) is expected


def test_to_row_flattens_pr_and_comment() -> None:
    """A row carries every CSV column."""
    row = scraper.to_row(_pr(), _comment("## AI REVIEW FEEDBACK\nbody text"))

    assert list(row) == scraper.CSV_COLUMNS
    assert row["repo"] == "o/r"
    assert row["pr_number"] == 7
    assert row["author"] == "alice"
    assert row["has_feedback"] is True
    assert row["body"] == "## AI REVIEW FEEDBACK\nbody text"


def test_to_row_without_comment_keeps_pr_fields_and_blanks_comment_fields() -> None:
    """A labelled PR with no feedback still produces a row, flagged has_feedback false."""
    row = scraper.to_row(_pr(), None)

    assert list(row) == scraper.CSV_COLUMNS
    assert row["repo"] == "o/r"
    assert row["pr_number"] == 7
    assert row["has_feedback"] is False
    assert all(row[col] == "" for col in ("comment_id", "comment_url", "author", "created_at", "body"))


def test_fetch_issue_comments_flattens_pages() -> None:
    """Paginated --slurp output (list of pages) becomes one flat list."""
    with patch.object(scraper, "run_gh", return_value='[[{"id": 1}, {"id": 2}], [{"id": 3}]]') as run_gh:
        comments = scraper.fetch_issue_comments("o/r", 7)

    assert [c["id"] for c in comments] == [1, 2, 3]
    assert "repos/o/r/issues/7/comments" in run_gh.call_args.args[0]


def test_scrape_lists_every_labelled_pr_and_filters_comments_by_header() -> None:
    """Every PR appears; only header-matching comments count as feedback; failed fetches are reported."""
    prs = [_pr(1), _pr(2), _pr(3), _pr(4), _pr(5)]
    error = subprocess.CalledProcessError(1, "gh", stderr="HTTP 404")

    def fake_fetch(repo: str, number: int) -> list[dict]:
        if number == 1:  # feedback plus chatter
            return [_comment("## AI REVIEW FEEDBACK\nuseful"), _comment("unrelated chatter")]
        if number == 2:  # fetch fails
            raise error
        if number == 3:  # comments, none are feedback
            return [_comment("## AI Review Loop - Summary")]
        if number == 4:  # two feedback comments
            return [_comment("## AI REVIEW FEEDBACK\none"), _comment("## AI REVIEW FEEDBACK\ntwo")]
        return []  # no comments at all

    with (
        patch.object(scraper, "search_labelled_prs", return_value=prs),
        patch.object(scraper, "fetch_issue_comments", side_effect=fake_fetch),
    ):
        rows, scanned, failed = scraper.scrape("o", "ai-review")

    assert scanned == 5
    assert [(r["pr_number"], r["has_feedback"]) for r in rows] == [
        (1, True),
        (2, False),
        (3, False),
        (4, True),
        (4, True),
        (5, False),
    ]
    assert failed == ["o/r#2: HTTP 404"]


def test_write_rows_csv_quotes_multiline_bodies(tmp_path: Path) -> None:
    """Newlines and commas in a body survive a CSV round trip."""
    out = tmp_path / "out.csv"
    row = scraper.to_row(_pr(), _comment("## AI REVIEW FEEDBACK\nline, two"))

    scraper.write_rows([row], "csv", out)

    with out.open(newline="", encoding="utf-8") as handle:
        read_back = list(csv.DictReader(handle))
    assert read_back[0]["body"] == "## AI REVIEW FEEDBACK\nline, two"


def test_write_rows_json_includes_has_feedback(tmp_path: Path) -> None:
    """JSON output keeps has_feedback as a boolean for both row kinds."""
    out = tmp_path / "out.json"

    scraper.write_rows([scraper.to_row(_pr(), None)], "json", out)

    assert json.loads(out.read_text(encoding="utf-8"))[0]["has_feedback"] is False


def test_main_summary_distinguishes_unloaded_prs(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    """The stderr summary counts labelled PRs, feedback, and PRs whose comments failed to load."""
    rows = [scraper.to_row(_pr(1), _comment("## AI REVIEW FEEDBACK")), scraper.to_row(_pr(2), None)]
    with patch.object(scraper, "scrape", return_value=(rows, 2, ["o/r#2: HTTP 404"])):
        assert scraper.main(["--out", str(tmp_path / "o.csv")]) == 0

    err = capsys.readouterr().err
    assert "Labelled PRs: 2 | with feedback: 1 | feedback comments: 1 | comments failed to load: 1" in err
    assert "o/r#2: HTTP 404" in err


def test_main_reports_missing_gh(capsys: pytest.CaptureFixture[str]) -> None:
    """A missing gh binary gives a clear error and a non-zero exit code."""
    with patch.object(scraper, "scrape", side_effect=FileNotFoundError):
        assert scraper.main([]) == 1

    assert "gh CLI is not installed" in capsys.readouterr().err
