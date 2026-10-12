"""Track PRs using the AI review label across a GitHub organisation, and scrape user feedback.

Lists every PR in the organisation that currently carries the review label, whether or not
anyone left feedback. For each PR it reads the conversation comments and keeps only human
comments whose body starts with the ``## AI REVIEW FEEDBACK`` h2 header that users were
asked to use.

Output has one row per feedback comment, plus one row (empty comment columns,
``has_feedback`` false) for each labelled PR with no feedback comment.

Limitations:
    - PRs that had the label removed after the review ran are not found, because the
      search only sees the current labels.
    - Only repositories readable with the authenticated ``gh`` login are scanned. PRs whose
      comments fail to load still get a no-feedback row, and are listed on stderr.
    - Only PR conversation comments are scanned, not review bodies or inline comments.

Usage:
    uv run python scripts/scrape_review_feedback.py --out feedback.csv
    uv run python scripts/scrape_review_feedback.py --format json --out feedback.json
"""

import argparse
import csv
import json
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_ORG = "co-cddo"
DEFAULT_LABEL = "ai-review"

# gh caps search results at 1000; hitting it means the scrape is probably incomplete.
SEARCH_LIMIT = 1000

# An h2 header (exactly two '#') reading "AI REVIEW FEEDBACK" at the very start of the comment.
FEEDBACK_HEADER_RE = re.compile(r"##[ \t]+AI REVIEW FEEDBACK\b", re.IGNORECASE)

CSV_COLUMNS = [
    "repo",
    "pr_number",
    "pr_url",
    "pr_title",
    "pr_state",
    "has_feedback",
    "comment_id",
    "comment_url",
    "author",
    "created_at",
    "body",
]


def run_gh(args: list[str]) -> str:
    """Run a ``gh`` command and return its stdout.

    Raises:
        subprocess.CalledProcessError: If ``gh`` exits non-zero.
    """
    result = subprocess.run(["gh", *args], capture_output=True, text=True, check=True)
    return result.stdout


def search_labelled_prs(org: str, label: str) -> list[dict]:
    """Return the PRs in ``org`` that currently carry ``label``, in any state."""
    output = run_gh(
        [
            "search",
            "prs",
            "--owner",
            org,
            "--label",
            label,
            "--limit",
            str(SEARCH_LIMIT),
            "--json",
            "number,repository,state,url,title",
        ]
    )
    return json.loads(output)


def fetch_issue_comments(repo: str, pr_number: int) -> list[dict]:
    """Return every conversation comment on a PR, following pagination."""
    output = run_gh(["api", "--paginate", "--slurp", f"repos/{repo}/issues/{pr_number}/comments"])
    pages = json.loads(output)
    return [comment for page in pages for comment in page]


def is_feedback_comment(comment: dict) -> bool:
    """Return True for a human comment that starts with the feedback header."""
    user = comment.get("user") or {}
    if user.get("type") == "Bot":
        return False
    body = (comment.get("body") or "").lstrip()
    return FEEDBACK_HEADER_RE.match(body) is not None


def to_row(pr: dict, comment: dict | None) -> dict:
    """Flatten a PR and one of its feedback comments into an output row.

    Pass ``comment=None`` for a labelled PR with no feedback: the comment columns are empty
    and ``has_feedback`` is false.
    """
    row = {
        "repo": pr["repository"]["nameWithOwner"],
        "pr_number": pr["number"],
        "pr_url": pr["url"],
        "pr_title": pr["title"],
        "pr_state": pr["state"],
        "has_feedback": comment is not None,
        "comment_id": "",
        "comment_url": "",
        "author": "",
        "created_at": "",
        "body": "",
    }
    if comment is not None:
        row.update(
            comment_id=comment["id"],
            comment_url=comment["html_url"],
            author=(comment.get("user") or {}).get("login", ""),
            created_at=comment["created_at"],
            body=comment["body"],
        )
    return row


def write_rows(rows: list[dict], fmt: str, out: Path | None) -> None:
    """Write rows as CSV or JSON to ``out``, or to stdout when ``out`` is None."""
    handle = out.open("w", newline="", encoding="utf-8") if out else sys.stdout
    try:
        if fmt == "json":
            json.dump(rows, handle, indent=2)
            handle.write("\n")
        else:
            writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
    finally:
        if out:
            handle.close()


def scrape(org: str, label: str) -> tuple[list[dict], int, list[str]]:
    """Collect output rows for every labelled PR.

    Each PR yields one row per feedback comment, or a single no-feedback row if it has none
    (including when its comments could not be loaded).

    Returns:
        Tuple of (rows, number of PRs scanned, descriptions of PRs whose comments failed to load).
    """
    prs = search_labelled_prs(org, label)
    if len(prs) >= SEARCH_LIMIT:
        print(f"Warning: search returned {SEARCH_LIMIT} PRs, the cap; results may be incomplete.", file=sys.stderr)

    rows: list[dict] = []
    failed: list[str] = []
    for pr in prs:
        repo = pr["repository"]["nameWithOwner"]
        try:
            comments = fetch_issue_comments(repo, pr["number"])
        except subprocess.CalledProcessError as exc:
            failed.append(f"{repo}#{pr['number']}: {exc.stderr.strip() or exc}")
            comments = []
        feedback = [comment for comment in comments if is_feedback_comment(comment)]
        rows.extend(to_row(pr, comment) for comment in feedback)
        if not feedback:
            rows.append(to_row(pr, None))
    return rows, len(prs), failed


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--org", default=DEFAULT_ORG, help="GitHub organisation to search (default: %(default)s)")
    parser.add_argument("--label", default=DEFAULT_LABEL, help="PR label to search for (default: %(default)s)")
    parser.add_argument("--format", choices=["csv", "json"], default="csv", help="Output format (default: csv)")
    parser.add_argument("--out", type=Path, help="Output file (default: stdout)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Track labelled PRs and their feedback comments, and write them out. Returns the process exit code."""
    args = parse_args(argv)
    try:
        rows, scanned, failed = scrape(args.org, args.label)
    except FileNotFoundError:
        print("Error: the gh CLI is not installed or not on PATH.", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        print(f"Error: gh failed (is it authenticated? try `gh auth status`): {exc.stderr.strip()}", file=sys.stderr)
        return 1

    write_rows(rows, args.format, args.out)

    feedback_rows = [row for row in rows if row["has_feedback"]]
    prs_with_feedback = len({(row["repo"], row["pr_number"]) for row in feedback_rows})
    print(
        f"Labelled PRs: {scanned} | with feedback: {prs_with_feedback} | "
        f"feedback comments: {len(feedback_rows)} | comments failed to load: {len(failed)}",
        file=sys.stderr,
    )
    if failed:
        print("PRs whose comments could not be read (listed as no feedback):", file=sys.stderr)
        for line in failed:
            print(f"  {line}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
