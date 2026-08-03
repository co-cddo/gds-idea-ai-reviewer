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
    ├── GitHub App Token (gds-idea-ai-reviewer)
    │       └── Authenticates access to repos
    ▼
This Repo (checked out by workflow)
    ├── GitHub MCP Server (Docker container)
    │       └── Fetches PR diff, posts review comments
    └── Pydantic AI Agent (Bedrock Claude)
            └── Analyses code, generates review feedback
```

1. A developer adds the `ai-review` label to a PR
2. The reusable workflow in the catalogue generates a GitHub App installation token
3. The workflow checks out this repo and starts the Pydantic AI agent
4. The agent uses the GitHub MCP Server to fetch the PR diff, reviews it against
   quality criteria, and submits a PR review as **gds-idea-ai-reviewer[bot]**
   with `COMMENT` event (advisory, non-blocking)

## Usage (Consuming Repos)

Add this to your repo's CI workflow:

```yaml
# .github/workflows/ci.yml
on:
  pull_request:
    types: [opened, synchronize, labeled]

permissions:
  id-token: write
  contents: read
  pull-requests: write

jobs:
  ai-review:
    uses: co-cddo/gds-idea-workflows-catalogue/.github/workflows/ci_ai_review.yml@main
    secrets: inherit
```

Then add the `ai-review` label to any PR to trigger a review.

> **Note:** The `gds-idea-ai-reviewer` GitHub App must be installed on your repo
> for this to work. See [GitHub App Setup](#github-app-setup) below.

The `ai-review` label needs to exist in your repository. Create it once via the
GitHub UI (Issues > Labels > New label) or via the CLI:

```bash
gh label create "ai-review" --description "Trigger AI code review" --color "7057ff"
```

Alternatively, GitHub auto-creates labels when you apply them to a PR for the
first time — so you can skip this step and just type `ai-review` in the label
field on the PR page.

For early testing (before merge to main in the catalogue):

```yaml
    uses: co-cddo/gds-idea-workflows-catalogue/.github/workflows/ci_ai_review.yml@ai_reviewer
```

## GitHub App Setup

The reviewer authenticates via the
[gds-idea-ai-reviewer](https://github.com/organizations/co-cddo/settings/apps/gds-idea-ai-reviewer)
GitHub App. The app controls which repos the reviewer can access — installing or
uninstalling it on a repo grants or revokes access.

### App Permissions

| Permission | Access |
|------------|--------|
| Contents | Read & Write |
| Pull requests | Read & Write |

### Installation

The app must be installed on:

- **This repo** (`co-cddo/gds-idea-ai-reviewer`) — so the workflow can check out
  the reviewer code
- **Each consuming repo** — so the reviewer can read PR diffs and post reviews

To manage installations:
https://github.com/organizations/co-cddo/settings/installations

### Org Secrets

> **Note:** Org admin access is required to create org-level secrets and manage
> app installations across repos.

The following secrets must be set at the org level
(`https://github.com/organizations/co-cddo/settings/secrets/actions`):

| Secret | Value |
|--------|-------|
| `GDS_IDEA_AI_REVIEWER_APP_ID` | The App's **Client ID** (e.g. `Iv23...`) |
| `GDS_IDEA_AI_REVIEWER_APP_PRIVATE_KEY` | Private key in **PKCS#8** format |

Repository access on the secrets must include all repos that use the reviewer.

### Private Key Format

GitHub generates private keys in PKCS#1 format (`-----BEGIN RSA PRIVATE KEY-----`).
The `actions/create-github-app-token@v3` action requires PKCS#8 format. Convert with:

```bash
openssl pkcs8 -topk8 -inform PEM -outform PEM -nocrypt \
  -in your-key.pem \
  -out your-key-pkcs8.pem
```

The converted key starts with `-----BEGIN PRIVATE KEY-----`. Use the full
contents of the PKCS#8 file (including header and footer lines) as the secret value.

To set the secret via CLI (avoids copy-paste issues):

```bash
gh secret set GDS_IDEA_AI_REVIEWER_APP_PRIVATE_KEY \
  --org co-cddo \
  --visibility all \
  < your-key-pkcs8.pem
```

### Reviewer Identity

Reviews appear as **gds-idea-ai-reviewer[bot]** with the app's avatar, giving
a distinct branded identity separate from `github-actions[bot]`.

## Cost Control

The review **only runs when the PR has the `ai-review` label**. No label = no
run = no cost. This is enforced in the reusable workflow's `if:` condition.

Additionally, the GitHub App must be installed on the repo — repos without the
app installed cannot trigger the reviewer even if the workflow and label are
present.

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

### Workflow Inputs (catalogue)

| Input | Default | Description |
|-------|---------|-------------|
| `aws_account_id` | `992382722318` | AWS account with Bedrock access |
| `aws_role_name` | `ai-reviewer-role` | IAM role name for OIDC |
| `model_id` | `anthropic.claude-sonnet-4-6` | Bedrock model ID |
| `aws_region` | `eu-west-2` | AWS region |

## Future Enhancements

### Cost Tracking & Attribution

- CloudWatch dashboard for Bedrock token usage and invocation counts
- Per-repo cost attribution using custom CloudWatch metrics (track which repos
  generate the most review cost)
- AWS Budget alerts when spend exceeds thresholds

### Specialised Review Tools

The current reviewer uses general-purpose code and documentation review tools.
Future work will introduce **specialised tools for different PR types**:

- **CDK apps** — CloudFormation best practices, IAM least-privilege, resource
  tagging, construct patterns
- **Python packages** — packaging standards, dependency hygiene, type hints,
  test coverage patterns
- **Documentation** — structure, accuracy against code, completeness, style
- **Web apps using gds-idea-app-kit** — component usage, accessibility,
  GDS design system compliance

### Crowdsourced Review Criteria

Each specialised tool will reference a dedicated README containing its review
criteria. These READMEs serve as the single source of truth for what the agent
checks, and can be synced to Confluence for easier reading and contribution
across teams.

This allows the wider team to contribute review rules without modifying the
agent code — update the relevant README and the agent picks up the new criteria
on its next run.

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
