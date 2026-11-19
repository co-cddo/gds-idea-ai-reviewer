# Tech debt scan

Runs the AI reviewer's guidance over whole repositories (read-only, nothing is posted to GitHub) and summarises the concerns that recur across them. Results go to `scripts/techdebt/outputs/` (git-ignored): `repos/<owner>__<repo>.md`, `per_repo.jsonl` and `report.md`.

## Prerequisites

- Docker running (the GitHub MCP server runs as a container; the first run pulls the image).
- A GitHub token that can read every repo you list, in both `co-cddo` and `gds-dtx`. If the orgs enforce SSO, the token must be authorised for them.
- AWS credentials with Bedrock `InvokeModel`.
- A Bedrock inference profile ARN. The base model ID cannot be invoked on demand, so local runs need `BEDROCK_INFERENCE_PROFILE_ARN`.

## Setup

From the repo root:

```sh
uv sync

export GITHUB_TOKEN=$(gh auth token)        # or a PAT
export AWS_PROFILE=<your-bedrock-profile>
export AWS_REGION=eu-west-2                 # default
export BEDROCK_INFERENCE_PROFILE_ARN=<arn>
```

Profile ARNs are published to SSM at `/ai-reviewer/inference-profiles/<team>`. Look yours up with:

```sh
export BEDROCK_INFERENCE_PROFILE_ARN=$(aws ssm get-parameter \
  --name /ai-reviewer/inference-profiles/<team> \
  --query Parameter.Value --output text --profile <profile>)
```

## Run a trial first

```sh
uv run python scripts/techdebt/techdebt_scan.py co-cddo/<repo-a> gds-dtx/<repo-b> --limit 2
```

Then read `scripts/techdebt/outputs/repos/*.md` and `report.md`.

## Full run

Copy the example list and edit it. `repos.txt` is git-ignored, so your list stays local:

```sh
cp scripts/techdebt/repos.example.txt scripts/techdebt/repos.txt
```

Put one repo per line. Bare names mean `co-cddo`, other orgs are written in full (`gds-dtx/repo-c`), and `#` starts a comment.

```sh
uv run python scripts/techdebt/techdebt_scan.py --repos-file scripts/techdebt/repos.txt
```

## Options

| Flag | Default | Purpose |
|---|---|---|
| `--limit N` | none | Scan only the first N repos. |
| `--max-files N` | 25 | Files the agent may read per repo. |
| `--concurrency N` | 2 | Repos scanned in parallel. |
| `--ref REF` | each repo's default branch | Scan a specific branch, tag or SHA. |
| `--default-org` | `co-cddo` | Org for bare repo names. |
| `--out-dir` | `scripts/techdebt/outputs` | Where results go. |
| `--force` | off | Rescan repos already in `per_repo.jsonl`. |
| `--model-id` | `$MODEL_ID` or `anthropic.claude-sonnet-5-5` | Model to use. |

## Behaviour

- Progress and the estimated cost print to stderr.
- Reruns skip repos already in `per_repo.jsonl` (use `--force` to redo them). `report.md` is regenerated each run from the repos in that run's selection.
- If any repo fails, the exit code is 1 and the failures are listed at the end. The other repos' results are kept.
