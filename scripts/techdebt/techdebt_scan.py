"""Scan whole repositories with the AI reviewer's guidance and summarise recurring tech debt.

For each repository an agent reads a bounded sample of files from the default branch (read-only:
nothing is posted to GitHub), applies the reviewer's guidance tools and returns structured findings.
Counts are then computed in Python, and one more LLM call clusters the findings into themes that
recur across repositories.

Outputs, in ``--out-dir`` (default ``scripts/techdebt/outputs``, git-ignored):
    repos/<owner>__<repo>.md  readable findings for one repository
    per_repo.jsonl            one validated record per scanned repository (a rerun skips these)
    report.md                 counts plus LLM-written recurring themes, each claim linked to a file

Needs ``GITHUB_TOKEN`` (read access to every repo, including SSO authorisation), AWS credentials for
Bedrock and Docker (the GitHub MCP server). Uses the reviewer's Bedrock environment variables
(``MODEL_ID``, ``AWS_REGION``, ``AWS_PROFILE``, ``BEDROCK_INFERENCE_PROFILE_ARN``).

Usage:
    uv run python scripts/techdebt/techdebt_scan.py co-cddo/repo-a gds-dtx/repo-b --limit 2
    uv run python scripts/techdebt/techdebt_scan.py --repos-file repos.txt
"""

import argparse
import asyncio
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Literal

import httpx
from pydantic import BaseModel
from pydantic_ai import Agent, PromptedOutput
from pydantic_ai.models import Model
from pydantic_ai.models.bedrock import BedrockConverseModel, BedrockModelSettings
from pydantic_ai.providers.bedrock import BedrockProvider
from pydantic_ai.usage import UsageLimits

from ai_reviewer import config
from ai_reviewer.github_comments import GITHUB_API, TIMEOUT_SECONDS
from ai_reviewer.github_server import get_github_server
from ai_reviewer.run_report import collect_tool_calls, estimate_cost
from ai_reviewer.tools import get_all_toolsets

HERE = Path(__file__).resolve().parent
PROMPT_FILE = HERE / "techdebt_prompt.md"
DEFAULT_OUT_DIR = HERE / "outputs"
DEFAULT_MODEL_ID = "anthropic.claude-sonnet-5-5"
DEFAULT_REGION = "eu-west-2"
DEFAULT_ORG = "co-cddo"
DEFAULT_CONCURRENCY = 2
DEFAULT_MAX_FILES = 25

# Read-only subset of the GitHub MCP tools: a scan must never be able to post a review.
SCAN_GITHUB_TOOLS = ("get_file_contents", "get_repository_tree")

# A scan reads many files, so allow more model requests than pydantic-ai's default cap.
MAX_REQUESTS_PER_REPO = 150

# Limits on what the report writer is sent, so a large run does not overflow one request.
MAX_PATTERNS_IN_REPORT = 60
MAX_EXAMPLES_PER_PATTERN = 5

REPO_RE = re.compile(r"^[\w.-]+/[\w.-]+$")

Category = Literal[
    "bug_security",
    "overengineering",
    "python_cleanliness",
    "docstrings",
    "docs_readme",
    "cdk",
    "dash",
    "testing",
    "dependencies",
    "other",
]
Severity = Literal["critical", "suggestion", "nit"]


class Finding(BaseModel):
    """One tech-debt finding in a repository."""

    category: Category
    severity: Severity
    path: str | None = None
    summary: str
    recurring_pattern: str
    raised_by: str


class RepoScan(BaseModel):
    """The model's scan of one repository."""

    stack: str
    files_examined: list[str]
    overall: str
    findings: list[Finding]


REPORT_INSTRUCTIONS = """\
You write the findings section of a tech-debt report that summarises what an automated AI code
reviewer flagged across many repositories.

You are given overall counts and a list of `patterns`. Each pattern has a normalised `pattern`
label, a `category`, the `repos` it appears in, and up to a few example `findings` (each with a
`repo`, `severity`, `summary` and a `url`).

Write Markdown with these sections, omitting any with nothing to say:
## Most common concerns
## Concerns that are critical or security related
## Concerns specific to one organisation
## Other observations

Rules:
- Merge patterns that describe the same underlying problem, and say how many repositories each
  merged theme covers. Rank themes by the number of distinct repositories affected.
- Every claim must link to at least one example as [owner/repo path](url). Do not state anything
  you cannot link.
- Never invent counts, repositories, paths, quotes or URLs. Only use what is given.
- The scan sampled a limited number of files per repository, so do not claim a problem is absent
  anywhere. Describe only what was flagged.
- Be concise. Do not repeat the counts table. Do not propose fixes unless the finding itself does.
"""


# --- Repository list -------------------------------------------------------------------------


def normalise_repo(raw: str, default_org: str) -> str:
    """Return ``owner/repo`` for a CLI or file entry, expanding a bare name into ``default_org``.

    Raises:
        ValueError: If the entry is not a valid repository name.
    """
    name = raw.strip().removesuffix(".git")
    if "/" not in name:
        name = f"{default_org}/{name}"
    if not REPO_RE.match(name):
        raise ValueError(f"Invalid repository name: {raw!r} (expected owner/repo)")
    return name


def parse_repos(cli_repos: list[str], repos_file: Path | None, default_org: str) -> list[str]:
    """Combine CLI repos and a repos file (one per line, ``#`` comments) into a de-duplicated list.

    Duplicates are matched case-insensitively and the first spelling is kept.
    """
    entries = list(cli_repos)
    if repos_file is not None:
        for line in repos_file.read_text(encoding="utf-8").splitlines():
            line = line.split("#", 1)[0].strip()
            if line:
                entries.append(line)
    seen: set[str] = set()
    repos = []
    for entry in entries:
        repo = normalise_repo(entry, default_org)
        if repo.lower() not in seen:
            seen.add(repo.lower())
            repos.append(repo)
    return repos


def repo_filename(repo: str) -> str:
    """Return a file name for a repo that cannot collide across organisations."""
    return repo.replace("/", "__") + ".md"


# --- Models and GitHub access ----------------------------------------------------------------


def build_model(model_id: str, region: str, profile: str | None, inference_profile_arn: str | None) -> Model:
    """Build the Bedrock model with the same settings the reviewer uses (thinking off)."""
    provider_kwargs: dict = {"region_name": region}
    if profile:
        provider_kwargs["profile_name"] = profile
    settings = BedrockModelSettings(
        max_tokens=config.MAX_TOKENS,
        bedrock_additional_model_requests_fields={"thinking": {"type": "between_tools"}},
    )
    if inference_profile_arn:
        settings["bedrock_inference_profile"] = inference_profile_arn
    return BedrockConverseModel(model_id, provider=BedrockProvider(**provider_kwargs), settings=settings)


def make_scanner(model: Model, toolsets: list) -> Agent:
    """Create the per-repo scan agent.

    Uses prompted output (the model writes JSON as text) because Sonnet 5.5 with thinking set to
    "between_tools" rejects the forced ``tool_choice`` that pydantic-ai's default tool output sends.
    """
    return Agent(
        model,
        instructions=PROMPT_FILE.read_text(encoding="utf-8"),
        toolsets=toolsets,
        output_type=PromptedOutput(RepoScan),
    )


def make_reporter(model: Model) -> Agent:
    """Create the agent that writes the cross-repo themes."""
    return Agent(model, instructions=REPORT_INSTRUCTIONS, output_type=str)


def make_github_client(token: str) -> httpx.AsyncClient:
    """Create the HTTP client used to check repository access and find default branches."""
    return httpx.AsyncClient(
        base_url=GITHUB_API,
        timeout=TIMEOUT_SECONDS,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )


class RepoAccessError(Exception):
    """The token cannot read the repository (missing, no permission, or SSO not authorised)."""


async def fetch_default_branch(client: httpx.AsyncClient, repo: str) -> str:
    """Return the repo's default branch, failing early and clearly if the token cannot read it."""
    response = await client.get(f"/repos/{repo}")
    if response.status_code in (401, 403, 404):
        raise RepoAccessError(
            f"{repo} is not accessible with this token (HTTP {response.status_code}); "
            "check the name, the token's access and SSO authorisation"
        )
    response.raise_for_status()
    return response.json()["default_branch"]


# --- Scanning --------------------------------------------------------------------------------


def build_query(repo: str, ref: str, max_files: int) -> str:
    """Build the per-repo user prompt."""
    return (
        f"Scan repository {repo} at ref {ref} for tech debt. Read at most {max_files} files from "
        f"that ref, prioritising entrypoints, the largest modules and tests. Use the guidance tools "
        f"that match what the repository contains (omit pr_number when calling them) and return the "
        f"structured result."
    )


async def scan_repo(
    scanner: Agent, client: httpx.AsyncClient, repo: str, ref: str | None, max_files: int
) -> tuple[dict, Decimal | None]:
    """Scan one repository.

    Returns:
        Tuple of (record to store, estimated cost in USD or None if it could not be priced). Tool call
        counts come from the run's message history, not from the model's own account.

    Raises:
        RepoAccessError: If the token cannot read the repository.
    """
    default_branch = await fetch_default_branch(client, repo)
    ref = ref or default_branch
    result = await scanner.run(
        build_query(repo, ref, max_files), usage_limits=UsageLimits(request_limit=MAX_REQUESTS_PER_REPO)
    )
    messages = result.all_messages()
    tool_calls = Counter(collect_tool_calls(messages))
    record = {
        "key": repo,
        "repo": repo,
        "org": repo.split("/", 1)[0],
        "ref": ref,
        "stack": result.output.stack,
        "overall": result.output.overall,
        "files_examined": result.output.files_examined,
        "file_reads": tool_calls.get("get_file_contents", 0),
        "tool_calls": dict(tool_calls),
        "findings": [finding.model_dump() for finding in result.output.findings],
    }
    return record, estimate_cost(messages)


def load_records(path: Path) -> dict[str, dict]:
    """Read previously scanned repos from a JSONL file, keyed by ``owner/repo``."""
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as handle:
        records = (json.loads(line) for line in handle if line.strip())
        return {record["key"]: record for record in records}


def finding_url(record: dict, finding: dict) -> str:
    """Link to the file a finding is about, or to the repository when it has no path."""
    base = f"https://github.com/{record['repo']}"
    return f"{base}/blob/{record['ref']}/{finding['path']}" if finding.get("path") else base


# --- Aggregation and report ------------------------------------------------------------------


def normalise_pattern(pattern: str) -> str:
    """Lower-case and collapse whitespace so trivially different labels group together."""
    return " ".join(pattern.lower().split())


def compute_counts(records: list[dict]) -> dict:
    """Count findings by category, severity and organisation, plus the repos each org contributed."""
    findings = [f for record in records for f in record["findings"]]
    return {
        "repos_scanned": len(records),
        "repos_by_org": dict(Counter(r["org"] for r in records)),
        "repos_with_findings": sum(1 for r in records if r["findings"]),
        "findings_total": len(findings),
        "by_severity": dict(Counter(f["severity"] for f in findings)),
        "by_category": dict(Counter(f["category"] for f in findings)),
        "findings_by_org": dict(Counter(r["org"] for r in records for _ in r["findings"])),
    }


def group_patterns(records: list[dict]) -> list[dict]:
    """Group findings by normalised pattern, ranked by distinct repos affected, then finding count."""
    grouped: dict[str, dict] = defaultdict(lambda: {"repos": set(), "categories": Counter(), "findings": []})
    for record in records:
        for finding in record["findings"]:
            group = grouped[normalise_pattern(finding["recurring_pattern"])]
            group["repos"].add(record["repo"])
            group["categories"][finding["category"]] += 1
            group["findings"].append(
                {
                    "repo": record["repo"],
                    "path": finding.get("path"),
                    "severity": finding["severity"],
                    "summary": finding["summary"],
                    "url": finding_url(record, finding),
                }
            )
    patterns = [
        {
            "pattern": pattern,
            "category": group["categories"].most_common(1)[0][0],
            "repos": sorted(group["repos"]),
            "finding_count": len(group["findings"]),
            "findings": group["findings"][:MAX_EXAMPLES_PER_PATTERN],
        }
        for pattern, group in grouped.items()
    ]
    return sorted(patterns, key=lambda p: (-len(p["repos"]), -p["finding_count"], p["pattern"]))


def format_counts(counts: dict) -> str:
    """Render the counts as a Markdown section."""
    lines = [
        "## Counts",
        "",
        f"- Repositories scanned: {counts['repos_scanned']} (with findings: {counts['repos_with_findings']})",
        f"- Findings: {counts['findings_total']}",
        "",
        "| Organisation | Repos | Findings |",
        "|---|---|---|",
    ]
    lines += [
        f"| {org} | {repos} | {counts['findings_by_org'].get(org, 0)} |"
        for org, repos in sorted(counts["repos_by_org"].items())
    ]
    lines += ["", "| Severity | Count |", "|---|---|"]
    lines += [f"| {key} | {value} |" for key, value in sorted(counts["by_severity"].items())]
    lines += ["", "| Category | Count |", "|---|---|"]
    lines += [f"| {key} | {value} |" for key, value in sorted(counts["by_category"].items())]
    return "\n".join(lines)


def format_repo_markdown(record: dict) -> str:
    """Render one repository's scan as Markdown."""
    lines = [
        f"# {record['repo']}",
        "",
        f"- Ref: `{record['ref']}`",
        f"- Stack: {record['stack']}",
        f"- Files examined ({record['file_reads']} file reads): "
        + (", ".join(f"`{p}`" for p in record["files_examined"]) or "none reported"),
        "",
        record["overall"],
    ]
    for severity, heading in (("critical", "Critical"), ("suggestion", "Suggestions"), ("nit", "Nits")):
        group = [f for f in record["findings"] if f["severity"] == severity]
        if not group:
            continue
        lines += ["", f"## {heading}", ""]
        for number, finding in enumerate(group, start=1):
            where = f"[`{finding['path']}`]({finding_url(record, finding)})" if finding.get("path") else "repo-wide"
            lines.append(
                f"{number}. **{where}** ({finding['category']}, via `{finding['raised_by']}`): {finding['summary']}"
            )
    if not record["findings"]:
        lines += ["", "No findings."]
    return "\n".join(lines) + "\n"


async def write_report(reporter: Agent, records: list[dict]) -> tuple[str, Decimal | None]:
    """Build report.md text: Python-computed counts followed by LLM-written themes.

    Returns:
        Tuple of (Markdown text, estimated cost of the theme call in USD or None).
    """
    counts = compute_counts(records)
    patterns = group_patterns(records)[:MAX_PATTERNS_IN_REPORT]
    header = "# Tech debt report\n\n" + format_counts(counts)
    if not patterns:
        return header + "\n\nNo findings were reported.\n", Decimal(0)
    result = await reporter.run(json.dumps({"counts": counts, "patterns": patterns}, indent=2))
    cost = estimate_cost(result.all_messages())
    return f"{header}\n\n# Recurring themes\n\n{result.output.strip()}\n", cost


# --- Orchestration ---------------------------------------------------------------------------


async def scan_all(
    scanner: Agent,
    client: httpx.AsyncClient,
    repos: list[str],
    existing: dict[str, dict],
    out_dir: Path,
    ref: str | None,
    max_files: int,
    concurrency: int,
) -> tuple[Decimal | None, list[str]]:
    """Scan every repo not already stored, appending each result to ``per_repo.jsonl`` as it finishes.

    Returns:
        Tuple of (total estimated cost or None if any call could not be priced, failure descriptions).
    """
    semaphore = asyncio.Semaphore(concurrency)
    total_cost: Decimal | None = Decimal(0)
    failed: list[str] = []
    jsonl_path = out_dir / "per_repo.jsonl"
    (out_dir / "repos").mkdir(parents=True, exist_ok=True)

    async def worker(index: int, repo: str, handle) -> None:
        nonlocal total_cost
        async with semaphore:
            started = time.monotonic()
            try:
                record, cost = await scan_repo(scanner, client, repo, ref, max_files)
            except Exception as exc:  # one bad repo must not stop the run
                failed.append(f"{repo}: {type(exc).__name__}: {exc}")
                print(f"[{index}/{len(repos)}] {repo} FAILED: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
                return
        existing[repo] = record
        handle.write(json.dumps(record) + "\n")
        handle.flush()
        (out_dir / "repos" / repo_filename(repo)).write_text(format_repo_markdown(record), encoding="utf-8")
        total_cost = None if cost is None or total_cost is None else total_cost + cost
        print(
            f"[{index}/{len(repos)}] {repo} scanned: {len(record['findings'])} findings, "
            f"{record['file_reads']} file reads ({time.monotonic() - started:.1f}s)",
            file=sys.stderr,
            flush=True,
        )

    todo = [(i, r) for i, r in enumerate(repos, start=1) if r not in existing]
    skipped = len(repos) - len(todo)
    if skipped:
        print(
            f"Skipping {skipped} repos already in {jsonl_path.name} (use --force to redo).", file=sys.stderr, flush=True
        )
    with jsonl_path.open("a", encoding="utf-8") as handle:
        await asyncio.gather(*(worker(i, r, handle) for i, r in todo))
    return total_cost, failed


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("repos", nargs="*", help="owner/repo (a bare name uses --default-org)")
    parser.add_argument("--repos-file", type=Path, help="File with one repo per line; '#' starts a comment")
    parser.add_argument("--default-org", default=DEFAULT_ORG, help="Organisation for bare repo names")
    parser.add_argument("--ref", help="Branch, tag or SHA to scan (default: each repo's default branch)")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR, help="Output directory")
    parser.add_argument("--limit", type=int, help="Scan only the first N repos (try 2 first)")
    parser.add_argument("--max-files", type=int, default=DEFAULT_MAX_FILES, help="Files the agent may read per repo")
    parser.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY, help="Repos scanned in parallel")
    parser.add_argument("--force", action="store_true", help="Rescan repos already in per_repo.jsonl")
    parser.add_argument("--model-id", default=os.environ.get("MODEL_ID", DEFAULT_MODEL_ID))
    args = parser.parse_args(argv)
    if not args.repos and args.repos_file is None:
        parser.error("give at least one repo or --repos-file")
    return args


async def run(args: argparse.Namespace, scanner: Agent, reporter: Agent, client: httpx.AsyncClient) -> int:
    """Scan the repos, then write the report. Returns the process exit code."""
    repos = parse_repos(args.repos, args.repos_file, args.default_org)
    if args.limit is not None:
        repos = repos[: args.limit]
    print(f"Repos to scan: {len(repos)}", file=sys.stderr, flush=True)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = args.out_dir / "per_repo.jsonl"
    if args.force:
        jsonl_path.unlink(missing_ok=True)
    existing = load_records(jsonl_path)

    async with scanner:  # starts the GitHub MCP server once, shared by every scan
        cost, failed = await scan_all(
            scanner, client, repos, existing, args.out_dir, args.ref, args.max_files, args.concurrency
        )

    # Report only on this run's selection, so --limit gives a report for those repos.
    records = [existing[r] for r in repos if r in existing]
    print(f"Writing report from {len(records)} repos...", file=sys.stderr, flush=True)
    text, report_cost = await write_report(reporter, records)
    (args.out_dir / "report.md").write_text(text, encoding="utf-8")

    total = None if cost is None or report_cost is None else cost + report_cost
    cost_text = "unavailable" if total is None else f"~${total:.2f}"
    print(
        f"Done. Report: {args.out_dir / 'report.md'} | repos failed: {len(failed)} "
        f"| estimated cost this run: {cost_text}",
        file=sys.stderr,
    )
    for line in failed:
        print(f"  {line}", file=sys.stderr)
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    """Build the models and GitHub clients from the environment and run the scan."""
    args = parse_args(argv)
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("Error: GITHUB_TOKEN environment variable is required", file=sys.stderr)
        return 1
    model = build_model(
        args.model_id,
        os.environ.get("AWS_REGION", DEFAULT_REGION),
        os.environ.get("AWS_PROFILE"),
        os.environ.get("BEDROCK_INFERENCE_PROFILE_ARN"),
    )
    scanner = make_scanner(model, [get_github_server(token, tools=SCAN_GITHUB_TOOLS), *get_all_toolsets()])

    async def go() -> int:
        async with make_github_client(token) as client:
            return await run(args, scanner, make_reporter(model), client)

    return asyncio.run(go())


if __name__ == "__main__":
    sys.exit(main())
