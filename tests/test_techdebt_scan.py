"""Test the tech-debt scan script's repo parsing, aggregation and orchestration (offline, stub models)."""

import asyncio
import importlib.util
import json
from pathlib import Path

import httpx
import pytest
from pydantic_ai.models.test import TestModel

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "techdebt" / "techdebt_scan.py"
_spec = importlib.util.spec_from_file_location("techdebt_scan", _SCRIPT)
scan = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(scan)


# Set up finding in shape of scripts finding model
def _finding(pattern: str = "No Type Hints", severity: str = "suggestion", path: str | None = "a.py", **extra) -> dict:
    return {
        "category": "python_cleanliness",
        "severity": severity,
        "path": path,
        "summary": "Public functions lack type hints.",
        "recurring_pattern": pattern,
        "raised_by": "python_cleanliness_guidance",
        **extra,
    }


# What LLM would return for a repo
def _scan_output(findings: list[dict] | None = None) -> dict:
    return {
        "stack": "Python / uv",
        "files_examined": ["a.py"],
        "overall": "Reasonable shape.",
        "findings": [_finding()] if findings is None else findings,
    }


# What a per-repo record looks like
def _record(repo: str = "co-cddo/a", findings: list[dict] | None = None) -> dict:
    return {
        "key": repo,
        "repo": repo,
        "org": repo.split("/")[0],
        "ref": "main",
        "stack": "Python",
        "overall": "ok",
        "files_examined": ["a.py"],
        "file_reads": 1,
        "tool_calls": {"get_file_contents": 1},
        "findings": [_finding()] if findings is None else findings,
    }


# Test the pydantic-AI Agent
def _scanner(output: dict):
    return scan.Agent(TestModel(custom_output_args=output), output_type=scan.RepoScan)


#
def _client(inaccessible: set[str] = frozenset()) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        repo = request.url.path.removeprefix("/repos/")
        if repo in inaccessible:
            return httpx.Response(404, json={"message": "Not Found"})
        return httpx.Response(200, json={"default_branch": "trunk"})

    return httpx.AsyncClient(base_url="https://api.github.com", transport=httpx.MockTransport(handler))


# Test the LLM reporting i.e. summarisation after all repos are scanned
def _reporter():
    return scan.Agent(TestModel(custom_output_args=None), output_type=str)


def test_parse_repos_expands_bare_names_dedupes_and_reads_file(tmp_path: Path) -> None:
    """Bare names use the default org, comments and blanks are ignored, duplicates drop case-insensitively."""
    repos_file = tmp_path / "repos.txt"
    repos_file.write_text("# teams\n\nfoo  # trailing\ngds-dtx/Bar\nCO-CDDO/FOO\n", encoding="utf-8")

    repos = scan.parse_repos(["gds-dtx/bar", "baz.git"], repos_file, "co-cddo")

    assert repos == ["gds-dtx/bar", "co-cddo/baz", "co-cddo/foo"]
    with pytest.raises(ValueError, match="Invalid repository name"):
        scan.parse_repos(["a/b/c"], None, "co-cddo")


def test_group_patterns_ranks_by_distinct_repos_and_normalises_labels() -> None:
    """Labels differing in case/whitespace merge; patterns are ranked by distinct repos, then count."""
    records = [
        _record("co-cddo/a", [_finding("No  Type hints"), _finding("No type hints", path="b.py"), _finding("rare")]),
        _record("gds-dtx/b", [_finding("no type hints")]),
    ]

    patterns = scan.group_patterns(records)

    assert [p["pattern"] for p in patterns] == ["no type hints", "rare"]
    assert patterns[0]["repos"] == ["co-cddo/a", "gds-dtx/b"]
    assert patterns[0]["finding_count"] == 3
    assert patterns[0]["findings"][0]["url"] == "https://github.com/co-cddo/a/blob/main/a.py"


def test_run_writes_outputs_then_resumes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A run stores one record and one markdown file per repo plus a report; reruns skip; --force redoes."""
    out_dir = tmp_path / "out"
    scanner, reporter, client = _scanner(_scan_output()), _reporter(), _client()

    def go(*extra: str) -> int:
        args = scan.parse_args(["co-cddo/a", "gds-dtx/b", "--out-dir", str(out_dir), *extra])
        return asyncio.run(scan.run(args, scanner, reporter, client))

    assert go() == 0
    lines = (out_dir / "per_repo.jsonl").read_text(encoding="utf-8").splitlines()
    records = [json.loads(line) for line in lines]
    assert sorted(r["key"] for r in records) == ["co-cddo/a", "gds-dtx/b"]
    assert {r["ref"] for r in records} == {"trunk"}  # defaults to the repo's default branch
    assert (out_dir / "repos" / "co-cddo__a.md").exists()
    assert (out_dir / "repos" / "gds-dtx__b.md").exists()
    report = (out_dir / "report.md").read_text(encoding="utf-8")
    assert "# Tech debt report" in report
    assert "| gds-dtx | 1 | 1 |" in report
    assert "Done." in capsys.readouterr().err

    go()
    assert len((out_dir / "per_repo.jsonl").read_text(encoding="utf-8").splitlines()) == 2
    assert "Skipping 2 repos already in per_repo.jsonl" in capsys.readouterr().err

    go("--force")
    assert len((out_dir / "per_repo.jsonl").read_text(encoding="utf-8").splitlines()) == 2


def test_run_limit_and_failures_do_not_stop_the_run(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """--limit caps repos scanned; an inaccessible repo is reported, others are kept, exit code is 1."""
    out_dir = tmp_path / "out"
    args = scan.parse_args(["o/missing", "o/good", "o/ignored", "--out-dir", str(out_dir), "--limit", "2"])

    code = asyncio.run(scan.run(args, _scanner(_scan_output()), _reporter(), _client({"o/missing"})))

    assert code == 1
    stored = [json.loads(line)["key"] for line in (out_dir / "per_repo.jsonl").read_text(encoding="utf-8").splitlines()]
    assert stored == ["o/good"]
    err = capsys.readouterr().err
    assert "o/missing FAILED: RepoAccessError" in err
    assert "repos failed: 1" in err
    assert "o/ignored" not in err


def test_scan_toolset_is_read_only() -> None:
    assert set(scan.SCAN_GITHUB_TOOLS) == {"get_file_contents", "get_repository_tree"}
    assert "pull_request_review_write" not in scan.SCAN_GITHUB_TOOLS
