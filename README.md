# GDS IDEA AI Code Reviewer

AI-powered code review agent that runs as a GitHub Action. Uses AWS Bedrock
(Claude Sonnet 4.6) via the GitHub MCP Server to analyse pull request diffs
and post advisory review comments.

## How It Works

```
Consuming Repo (PR with 'ai-review' label)
    │
    ▼
Workflows Catalogue (ci_ai_review.yml)
    │
    ▼
This Action (action.yml)
    ├── GitHub MCP Server (Docker container)
    │       └── Fetches PR diff, posts review comments
    └── Pydantic AI Agent (Bedrock Claude)
            └── Analyses code, generates review feedback
```

1. A developer adds the `ai-review` label to a PR
2. The reusable workflow in the catalogue triggers this action
3. The action starts the GitHub MCP Server (Docker) and the Pydantic AI agent
4. The agent fetches the PR diff, reviews it against quality criteria, and
   submits a PR review with `COMMENT` event (advisory, non-blocking)

## Usage (Consuming Repos)

Add this to your repo's CI workflow:

```yaml
# .github/workflows/ci.yml
on:
  pull_request:
    types: [opened, synchronize, labeled]

jobs:
  ai-review:
    uses: co-cddo/gds-idea-workflows-catalogue/.github/workflows/ci_ai_review.yml@main
    secrets: inherit
```

Then add the `ai-review` label to any PR to trigger a review.

The `ai-review` label needs to exist in your repository. Create it once via the
GitHub UI (Issues > Labels > New label) or via the API:

```bash
curl -X POST -H "Authorization: token $GITHUB_TOKEN" \
  "https://api.github.com/repos/YOUR_ORG/YOUR_REPO/labels" \
  -d '{"name":"ai-review","color":"7057ff","description":"Trigger AI code review"}'
```

Alternatively, GitHub auto-creates labels when you apply them to a PR for the
first time — so you can skip this step and just type `ai-review` in the label
field on the PR page.

For early testing (before merge to main in the catalogue):

```yaml
    uses: co-cddo/gds-idea-workflows-catalogue/.github/workflows/ci_ai_review.yml@ai_reviewer
```

## Cost Control

The review **only runs when the PR has the `ai-review` label**. No label = no
run = no cost. This is enforced in the reusable workflow's `if:` condition.

## What Gets Reviewed

The agent uses two review tools:

### Code Review (`code_review_guidance`)

Reviews source code and configuration files:
- **Source code:** `.py`, `.sql`, `.html`, `.jinja2`, `.j2`, `.css`, `.js`, `.ts`, `.tsx`, `.jsx`
- **Config files:** `.yaml`, `.yml`, `.json`, `.toml`

Criteria: bugs, security, code quality, architecture, testing, and
language/format-specific checks (including GitHub Actions workflow best practices).

### Documentation Review (`docs_review_guidance`)

Reviews documentation quality and completeness:
- **Markdown files:** `.md`, `.rst` — structure, accuracy against code, completeness
- **Python docstrings:** checks public functions/classes have accurate docstrings

Criteria: README structure, accuracy vs actual code, missing docs for new features,
docstring presence and quality on public APIs.

### Skipped Files

The following are always skipped: `.lock`, `.csv`, images, fonts,
`_version.py`, `__pycache__`, `.venv`, `node_modules`, `migrations/`

## Configuration

### Action Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `github-token` | Yes | - | GitHub token for PR access and MCP server |
| `aws-role-arn` | Yes | - | IAM role ARN for Bedrock (assumed via OIDC) |
| `aws-region` | No | `eu-west-2` | AWS region for Bedrock API |
| `model-id` | No | `anthropic.claude-sonnet-4-6` | Bedrock model ID |

### Workflow Inputs (catalogue)

| Input | Default | Description |
|-------|---------|-------------|
| `aws_account_id` | `992382722318` | AWS account with Bedrock access |
| `aws_role_name` | `ai-reviewer-role` | IAM role name for OIDC |
| `model_id` | `anthropic.claude-sonnet-4-6` | Bedrock model ID |
| `aws_region` | `eu-west-2` | AWS region |

## Local Testing

### Prerequisites

- [Docker](https://www.docker.com/) running (for the GitHub MCP Server)
- [uv](https://docs.astral.sh/uv/) for Python package management
- AWS profile with Bedrock access (`bedrock-user-jose` or similar)
- A GitHub PAT with repo read access

### Running Locally

```bash
cd /path/to/gds-idea-ai-reviewer

export GITHUB_TOKEN="ghp_your_pat_here"
export PR_NUMBER=1
export REPO="co-cddo/your-test-repo"
export AWS_PROFILE="bedrock-user-jose"
export AWS_REGION="eu-west-2"
export MODEL_ID="anthropic.claude-sonnet-4-6"

uv run python -m ai_reviewer.run
```

The agent will:
1. Start the GitHub MCP Server Docker container
2. Fetch the PR diff from GitHub
3. Send it to Bedrock Claude for analysis
4. Post a review comment on the PR

## AWS Setup

### IAM Role

The action needs an IAM role (`ai-reviewer-role`) that:
- Is trusted by GitHub Actions OIDC (`token.actions.githubusercontent.com`)
- Has `bedrock:InvokeModel` permission on the configured model
- Is scoped to `repo:co-cddo/*:*` (any repo in the org)

### Deploying with CDK

The IAM role infrastructure is defined in `cdk/`. To deploy:

```bash
cd cdk/
uv sync --group cdk
uv run cdk deploy --profile aws-prototype
# Enter MFA code when prompted
```

This creates:
- IAM role `ai-reviewer-role` in the DEV account (`992382722318`)
- Trust policy for GitHub OIDC (scoped to `co-cddo` org)
- Bedrock InvokeModel permission (scoped to Claude Sonnet 4.6)

The CDK stack imports the existing GitHub OIDC provider (which already
exists if CDK/Terraform workflows use OIDC in the same account).

## Prerequisites

- [uv](https://docs.astral.sh/uv/) for Python package management
- [git](https://git-scm.com/)
- [gitleaks](https://github.com/gitleaks/gitleaks) for pre-commit secret scanning (`brew install gitleaks`)
- [Docker](https://www.docker.com/) for the GitHub MCP Server

## Getting Started (Development)

1. Clone the repository:

   ```bash
   git clone git@github.com:co-cddo/gds-idea-ai-reviewer.git
   cd gds-idea-ai-reviewer
   ```

2. Install dependencies:

   ```bash
   uv sync
   ```

3. Set up pre-commit hooks:

   ```bash
   uv run pre-commit install
   ```

## Development

### Running Tests

```bash
uv run pytest
```

### Running Linting

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
```

### Pre-commit Hooks

Pre-commit hooks run automatically on `git commit`. They will:

- **Auto-fix** lint issues detected by `ruff check --fix`
- **Auto-format** code with `ruff format`
- **Check** YAML/TOML syntax, trailing whitespace, merge conflicts
- **Scan** for leaked secrets with gitleaks
- **Prevent** direct commits to `main`

If files are modified by the hooks, the commit will be aborted.
Review the changes, `git add` them, and commit again.

To run hooks against all files manually:

```bash
uv run pre-commit run --all-files
```

## Versioning

This project uses [hatch-vcs](https://github.com/ofek/hatch-vcs) for
automatic versioning from git tags. Versions are never set manually.

On merge to `main`, the auto-release workflow creates a new tag based on
PR labels:

- `bump:major` — major version bump
- `bump:minor` — minor version bump
- (default) — patch version bump

## Licence

[MIT License](LICENCE)
