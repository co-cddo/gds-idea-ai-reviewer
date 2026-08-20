# README Review Standards

Target: {repository} / PR #{pr_number}

This document defines README standards for gds-idea projects. It serves as both
a human-readable reference and the automated reviewer's criteria. It is scoped
to `README` files only — Python docstrings, MkDocs/website documentation, and
other doc types are handled by their own dedicated reviewers.

**Scope:** `README.md`, `README.rst`, and any nested `README.*` at the root of a
package or subdirectory (e.g. `lambda/webhook_receiver/README.md`,
`app_src/README.md`).

**Out of scope:** Python docstrings, `docs/**` and MkDocs sites (`mkdocs.yml`),
`CONTRIBUTING.md`/`CODE_OF_CONDUCT.md`/`SECURITY.md` (review only if changed in
the PR, and only against the Structure and Clarity sections — they are not
READMEs), `CHANGELOG.md`, auto-generated docs, `LICENCE`/`LICENSE` files
themselves.

**How to review:** Work from the PR diff you already have from the code review.
Only review a README if it was added or modified in this PR, **or** if the PR
changes behaviour that an existing README documents (see Section 6). Judge each
file against its purpose — a subfolder README for a single Lambda does not need
the full top-level structure. Never invent gaps to fill a quota; flag only what
would genuinely confuse or slow down a developer.

## 1. Structure and Completeness

### Cover the sections a reader needs to get started

- A top-level `README.md` should give a reader enough to understand the project
  and run it. Expect most of the following, judged against the project's
  purpose:
  - **Project title and one-line description** — what this is and what problem
    it solves, in plain English.
  - **Prerequisites** — runtime versions, AWS access, accounts, tools required
    before starting.
  - **Installation / setup** — how to install dependencies and get to a working
    state.
  - **Usage** — how to actually run the thing, with working commands.
  - **Configuration** — environment variables, config files, and their defaults.
  - **External dependencies** — third-party APIs, other internal systems, or
    downstream services the app depends on, and what each is used for
    (see below).
  - **Architecture / workflow overview** — for repos with more than one
    component or service, how the pieces fit together (see below).
  - **Repository structure** — for non-trivial repos, a short overview of the
    key top-level directories (see below).
  - **Development setup** — how a contributor gets a local dev environment
    working (env vars, linting, pre-commit hooks).
  - **Testing** — how to run the test suite, and what's expected to pass
    before opening a PR.
  - **Troubleshooting** — known setup/runtime gotchas (see Section 4).
  - **Licence** — stated or linked.
- Not every README needs every section. A single-Lambda subfolder README may
  only need a description, its inputs/outputs, the AWS resources it reads from
  or writes to, and how to build it. Judge by the file's role, not a checklist.
- The rationale: a README is the first thing a new joiner or external team
  reads. Missing setup or usage information is the most common reason someone
  cannot run a repo they have just cloned.

**Flag when:** a top-level README for a runnable project has no way to install,
run, or configure it — a reader would be stuck after cloning.

**Do not flag when:** a purpose-specific file (e.g. a Lambda subfolder README)
legitimately omits sections that do not apply to it.

### Order sections so a first-time reader can follow them top to bottom

- Sections should flow in the order a reader needs them: what it is →
  prerequisites → install → usage → configuration → development → licence.
- A reader should not have to scroll to the bottom for prerequisites they needed
  before the install step at the top.

### Document architecture, external dependencies, and repository structure for non-trivial repos

- **Architecture/workflow overview** — if the repo has more than one
  component or service (e.g. a web app plus a scheduled Lambda plus
  infrastructure, or multiple stacks that call each other), the README should
  show how they relate. Prefer a **Mermaid diagram** in a fenced ` ```mermaid `
  code block over a linked image or an external doc — it renders natively on
  GitHub, stays in the repo as reviewable text, and shows up in diffs when the
  architecture changes. A clear prose description of the relationships is an
  acceptable alternative for simpler cases.
- **External dependencies** — a reader auditing or extending the app needs to
  know what it talks to beyond its own code (third-party APIs, other internal
  systems, downstream services), and briefly what each is for.
- **Repository structure** — for a repo with more than a handful of
  top-level directories, a short fenced tree of the key folders (what lives
  where) saves a reader from having to explore blindly.
- Scale the expectation to the repo: a single-purpose repo or a small
  subfolder README does not need any of these — the existing description
  already conveys the same information.

**Bad — architecture diagram lives only in an external Confluence page:**
```markdown
## Architecture
See our Confluence page for the architecture diagram.
```

**Good — a Mermaid diagram kept in the repo, reviewable in the diff:**
`````markdown
## Architecture

```mermaid
graph LR
    Browser --> ALB[ALB with Cognito auth]
    ALB --> App[Dash/Flask app]
    App --> S3[S3 - source data]
    App --> Athena[Athena - queries]
```
`````

**Good — a repository structure overview:**
`````markdown
## Repository Structure

```text
app_src/
  dash_app.py       # Entry point, routing, auth
  callbacks/        # Callback wiring per page
  dashboards/       # Page layouts
  utils/            # Pure helper functions
lambda/
  data_refresh/     # Scheduled data-refresh function
```
`````

**Bad — the app clearly calls an external API but the README never says so:**
```python
# The code calls out to a third-party service...
response = requests.get(f"https://api.example-provider.com/v1/lookup/{{ref}}")
```
```markdown
<!-- ...but the README has no mention of example-provider.com anywhere -->
```

**Good — the dependency is named and its purpose is explained:**
```markdown
## External Dependencies
- **Example Provider API** — used to validate case references before
  submission. Requires an API key set via `EXAMPLE_PROVIDER_API_KEY`.
```

**Flag when:** a repo with multiple components/services has no architecture
overview at all and a reader cannot tell how the pieces relate from the README,
**or** the code clearly calls an external API/service that the README never
mentions.

**Do not flag when:** a single-service or single-purpose repo has no diagram
or folder tree — the existing prose already covers the same ground; or every
external call the code makes is already named in the README, even briefly.

## 2. Accuracy Against Code

**This is the most important check.** A README that is confidently wrong is worse
than one that is missing — it sends readers down the wrong path.

Verify every factual claim against the actual repo and this PR's diff:

- Do code snippets match real function signatures, class names, and imports in
  the repo?
- Are package and dependency versions consistent with `pyproject.toml` /
  `requirements.txt`?
- Are CLI commands, subcommands, and flags accurate and currently supported?
- Are environment variable names spelled exactly as the code reads them?
- Are file paths, directory names, and module paths correct?
- Are API endpoints, routes, and URLs correct?
- Are AWS resource references (bucket names, function names, account/region
  conventions) consistent with the CDK config?

**Bad — example drifts from the code it documents:**
```python
# README says:
from mypackage import run_review

# But the code was renamed in this PR to:
from mypackage import run_readme_review
```

**Good — snippet matches the current public API and is runnable as written:**
```python
from mypackage import run_readme_review

run_readme_review(repository="co-cddo/my-project", pr_number=42)
```

### Check env var and command names character-for-character

- Environment variable names and CLI flags must match the code exactly,
  including case and separators (`GITHUB_TOKEN` vs `GITHUB_API_TOKEN`,
  `--dry-run` vs `--dryrun`).
- A near-miss is harder to debug than an obvious omission, because the reader
  assumes the docs are right and looks everywhere else first.

## 3. Installation, Prerequisites and Getting Started

### Give a clean, copy-pasteable setup path

- Setup steps should be runnable commands, not prose descriptions of what to do.
- State prerequisites (Python version, `uv`/`pip`, Node, Docker, AWS profile)
  before the first install command that assumes them.
- If the repo uses `gds-idea-app-kit` or a shared template, point to the shared
  setup rather than duplicating and letting it drift.

**Bad — vague, non-runnable, hidden assumptions:**
```markdown
Install the dependencies and set up your environment, then run the app.
```

**Good — explicit prerequisites and copy-pasteable commands:**
```markdown
## Prerequisites
- Python 3.12+
- `uv` installed
- AWS SSO profile `gds-idea-dev` configured

## Setup
```bash
uv sync
uv run pytest        # verify the environment
```
```

### Document the devcontainer launch steps in full, if the repo uses one

- If the repo contains a `.devcontainer/` folder (or otherwise expects
  development inside a devcontainer), the README **must** spell out the exact
  ordered steps required to get the container running — not just "open in a
  devcontainer".
- This is the single most common gap across gds-idea repos: the container
  configuration exists, but the surrounding host-side prerequisites (Docker
  runtime, AWS profile, role assumption, MFA) are assumed knowledge. A new
  joiner cannot infer these, and they fail silently with unhelpful errors
  (missing Docker socket, expired credentials, `NoCredentialProviders`).
- The steps must be runnable commands in the order a reader executes them, and
  must cover, where relevant:
  - **Starting the container runtime** (e.g. `colima start`) before opening the
    container.
  - **Exporting the AWS profile** the container will use.
  - **Assuming the role and completing MFA** so AWS credentials are live inside
    the container.
  - **Launching the devcontainer** itself (VS Code "Reopen in Container", or the
    CLI equivalent).
- If any step is environment-specific (profile name, role, region), state it
  explicitly as an example the reader substitutes, rather than omitting it.

**Bad — assumes all the host-side setup:**
```markdown
## Development
Open the project in VS Code and reopen in the devcontainer.
```

**Good — the full, ordered, copy-pasteable sequence:**
```markdown
## Running in a devcontainer

1. Start the container runtime:
   ```bash
   colima start
   ```
2. Export the AWS profile the container should use:
   ```bash
   export AWS_PROFILE=aws-prototype
   ```
3. Assume the role and complete MFA when prompted:
   ```bash
   idea-app provide-role
   ```
4. Launch the devcontainer: in VS Code, run
   **Dev Containers: Reopen in Container** (or `devcontainer up` from the CLI).
```

## 4. Troubleshooting

### Capture known, recurring gotchas — don't just document the happy path

- If the repo has a known, recurring setup or runtime issue (devcontainer
  credential/socket errors, a flaky external dependency, a common
  misconfiguration), a Troubleshooting section should capture it as a
  symptom → fix pair, not just leave it to be rediscovered by every new joiner.
  This is the natural home for the devcontainer failure modes named in
  Section 3 (missing Docker socket, expired credentials,
  `NoCredentialProviders`) when they recur often enough to be "known".
- **Never invent a Troubleshooting section from nothing.** Only flag a gap here
  when a known recurring issue is actually evident — from the PR description,
  linked issues, comments, or an existing-but-incomplete Troubleshooting
  section — not by default the way Installation/Usage are checked. An absent
  Troubleshooting section is not itself a defect; a *known* gotcha that stays
  undocumented is.
- If an existing Troubleshooting section documents an issue this PR fixes, it
  should be removed or updated in the same PR — a stale troubleshooting entry
  for a bug that no longer exists is as misleading as a stale code example.

**Bad — a known recurring issue is referenced in the PR but never written down:**
```markdown
<!-- PR description mentions: "Fixes the third report of devcontainer builds
     failing with 'no such file' on first run — needs a rebuild without cache" -->
<!-- README has no Troubleshooting section at all -->
```

**Good — the known gotcha is captured as symptom → fix:**
`````markdown
## Troubleshooting

**Devcontainer fails on first build with "no such file":**
Rebuild without the Docker layer cache:
```bash
devcontainer build --no-cache
```
`````

**Flag when:** a known, recurring issue is evident from the PR/repo context but
not captured anywhere in the README.

**Do not flag when:** the repo has no known recurring issues yet — do not
invent a Troubleshooting section just to fill the checklist.

## 5. Usage Examples

### Show at least one complete, working example

- Include a minimal example that a reader can run end to end, not a fragment
  that assumes undocumented setup.
- Prefer showing expected output (or its shape) so a reader knows what success
  looks like.
- Keep examples current with the PR — if this PR adds or changes a command,
  the example must reflect it.

**Bad — fragment that will not run on its own:**
```python
result = reviewer.run()   # what is `reviewer`? where did it come from?
```

**Good — self-contained and shows the shape of the result:**
```python
from mypackage import ReadmeReviewer

reviewer = ReadmeReviewer(repository="co-cddo/my-project", pr_number=42)
comments = reviewer.run()
# comments -> list[ReviewComment], each with prefix, file, line, message
```

## 6. Keeping Documentation in Step with the Code

### Update the README when this PR changes behaviour it documents

- If the PR adds or changes a CLI command, flag, environment variable, API
  endpoint, config option, or public function that the README documents, the
  README must be updated in the same PR.
- Documentation that lags behind code is the most common source of stale,
  misleading READMEs. Catching it at PR time is the only cheap moment.
- Treat "is this README maintained?" as an **accuracy** question, not a
  metadata question: judge freshness by whether the content still matches the
  current codebase (see Section 2), not by whether it carries a manually
  maintained "Last updated"/version date. A hand-written date goes stale the
  moment it is merged and becomes noise for a reviewer to police. If a README
  does carry such a field and this PR's changes contradict it, flag it the
  same as any other stale claim — but do not require the field to exist in
  the first place.

**Flag when:** the diff adds a new `--dry-run` flag (or new env var, endpoint,
etc.) but the Usage/Configuration section is untouched.

### Flag placeholder and unresolved content

- Placeholder text (`TBA`, `TODO`, `FIXME`, `changeme`, `Lorem ipsum`,
  `<your-value-here>`, "coming soon") must be resolved before merging, or
  explicitly marked as a tracked follow-up.
- Empty or stub sections with a heading and no content should either be filled
  or removed.

## 7. Clarity, Formatting and Style

### Keep the writing clear, and the formatting consistent

- Writing should be concise and in plain English; explain or link acronyms and
  project-specific terms on first use (GATS, GAS, CDK, MCP, etc.).
- Heading levels should nest properly (no jumping `#` → `###`), and there should
  be a single top-level `#` title.
- Lists, tables, and emphasis should be used consistently, not mixed ad hoc.
- Use UK English spelling (licence, behaviour, organisation) to match the rest
  of the estate.

### Fence code blocks and tag them with a language

- Every code block must be fenced (triple backticks), never indented-only, and
  must carry a language identifier (` ```bash `, ` ```python `, ` ```json `).
- The language tag drives syntax highlighting and signals to the reader what
  they are looking at.

**Bad — no language tag, so no highlighting and ambiguous intent:**
````markdown
```
uv sync
uv run pytest
```
````

**Good — tagged as shell:**
````markdown
```bash
uv sync
uv run pytest
```
````

### Format links correctly and keep them alive

- Links must use proper Markdown syntax `[text](url)`, not bare or broken
  references, and relative links to repo files must resolve.
- Anchor links (`#section-name`) must match a real heading.

## 8. Comment Prefixes

Use a single prefix per comment so the author can triage quickly:

- **Docs:** — Missing or incorrect information that would confuse or mislead a
  reader (wrong example, undocumented new flag, broken setup step, an
  undocumented external dependency a reader would need to know about).
- **Suggestion:** — A change that would improve readability or completeness but
  is not strictly wrong (e.g. adding an architecture diagram or folder-structure
  overview to an already-usable README).
- **Nit:** — Minor formatting or style issue (missing language tag, heading
  jump, inconsistent list style).

## 9. Example Comments

For a README not updated after a behaviour change:

    Docs: This PR adds the `--dry-run` flag to the CLI, but the Usage section
    of the README hasn't been updated to mention it.

For an inaccurate code example:

    Docs: The example imports `run_review`, but this was renamed to
    `run_readme_review` in this PR. The snippet will fail as written.

For a missing setup path:

    Docs: The README describes what the tool does but has no installation or
    run instructions. A reader who clones this repo has no way to start it.

For a mismatched environment variable:

    Docs: The README references `GITHUB_API_TOKEN`, but the code reads
    `GITHUB_TOKEN` (see `config.py`). The names need to match.

For an unfenced or untagged code block:

    Nit: This code block should be fenced with a language identifier
    (```bash) so it gets syntax highlighting.

For a devcontainer with undocumented launch steps:

    Docs: This repo has a `.devcontainer/` but the README only says "reopen in
    container". Please document the host-side steps first — starting the
    container runtime (`colima start`), exporting the AWS profile, and assuming
    the role with MFA — otherwise a new joiner hits credential errors with no
    way to diagnose them.

For a placeholder shipped in the diff:

    Docs: This section still contains `TBA`. Please resolve it before merging
    or link a tracked follow-up issue.

For a new external dependency that isn't documented:

    Docs: This PR adds a call to the [ExampleAPI] service, but the README's
    external dependencies aren't updated to mention it. A reader trying to run
    this locally won't know they need access to it.

For a non-trivial repo with no architecture overview:

    Suggestion: This repo now has three separate components (the app, the
    scheduled Lambda, and the infra stack). A short architecture diagram (a
    Mermaid block would work well) would help a new joiner see how they relate.

For a known gotcha left undocumented:

    Docs: The PR description mentions this fixes a recurring devcontainer build
    failure — worth adding a Troubleshooting entry so future contributors who
    hit the same symptom before pulling this fix can find it.

## 10. Anti-Patterns to Flag

- **Code examples that do not match the current code** (renamed functions,
  changed signatures, removed flags)
- **Environment variable or CLI flag names that differ from the code**
- **New behaviour in the PR with no corresponding README update** (new flag,
  env var, endpoint, or config option)
- **Placeholder content shipped to main** (`TBA`, `TODO`, `changeme`,
  `<your-value-here>`, "coming soon")
- **Unfenced code blocks, or fenced blocks with no language identifier**
- **Broken links or anchors** (dead relative paths, `#section` with no matching
  heading)
- **Non-runnable setup instructions** (prose where commands are needed, or
  hidden prerequisites)
- **A `.devcontainer/` in the repo but no documented launch steps** — or steps
  that skip host-side prerequisites (container runtime, AWS profile export, role
  assumption/MFA) and jump straight to "reopen in container"
- **A multi-component/multi-service repo with no architecture overview at all**
  — a reader cannot tell how the pieces relate
- **A clear external dependency/integration used by the code with no mention
  in the README**
- **A known, recurring issue evident from the PR/repo context left out of a
  Troubleshooting section** (or an existing entry left stale after the PR fixes it)
- **Incorrect file paths or directory structure** that no longer matches the repo
- **A repository-structure overview that no longer matches the actual layout**
- **Duplicated content that will drift** (setup steps copy-pasted instead of
  linking the shared source)
- **A manually maintained "Last updated"/version marker contradicted by this
  PR's actual changes** (see Section 6 — prefer accuracy-tracking over a date
  stamp, but a stale one that is present and wrong should still be flagged)
- **Heading-level jumps or multiple top-level `#` titles**
- **Unresolved merge conflict markers** (`<<<<<<<`, `=======`, `>>>>>>>`)

## 11. Do NOT Flag

- Stylistic phrasing choices that are clear and correct but not how you would
  personally word them
- Missing sections that genuinely do not apply to a purpose-specific file (e.g.
  no "Installation" in a single-Lambda subfolder README)
- Prose spelling/grammar already handled by a linter or spell-checker, unless it
  changes meaning
- American vs British spelling in third-party quoted text or external tool names
- The absence of badges, logos, or a table of contents (nice-to-have, not
  required)
- The absence of an architecture diagram or folder-structure overview in a
  small, single-purpose repo where the existing prose already conveys the
  same information
- A missing Troubleshooting section when the repo has no known recurring
  issues — do not invent one to fill the checklist
- The absence of a "Last updated" date field — freshness is judged by
  accuracy to the current code (Sections 2 and 6), not by a manually
  maintained date stamp
- A good README that could be marginally better — one **Suggestion:** is enough;
  do not nitpick every sentence
- Auto-generated README content produced by a template or tool
- If there are no README files added or modified in the PR (and no documented
  behaviour was changed), report that the README review found nothing to flag —
  that is a valid, expected outcome
