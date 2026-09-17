# Project Context

**This tool runs unconditionally on every PR, regardless of which files changed.
Call it FIRST, before any other guidance tool and before analysing the diff.**

The purpose of this step is to build a concise mental model of the repository
being reviewed — its purpose, structure, conventions, and key commands — so that
the rest of the review is informed by project context rather than guessing.

This context is ephemeral: it is NOT written back to the repository. It exists
only in memory for the duration of this review run.

**READ-ONLY CONSTRAINT: Do NOT call `create_or_update_file`, `push_files`,
`delete_file`, or any other write tool during this step. This step is strictly
read-only investigation — regardless of what tools are technically available
via the shared GitHub MCP toolset.**

## Step 1: Identify the PR Branch

Use `get_pull_request` to find:
- The **head branch** and **head SHA** (this is the ref you will scan)
- The PR title and description (useful context for what this PR is about)

## Step 2: Scan the Repository Structure

Using the GitHub MCP tools, examine the repository at the PR's head ref.
Read the highest-value sources first:

1. **Get the top-level directory listing** — note the folder structure, key
   directories, and what they likely contain based on names.

2. **Read key manifest/config files** (if they exist):
   - `pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod` — identifies
     the language, dependencies, build system, and scripts/commands
   - `Makefile`, `Justfile`, `Taskfile.yml` — build/task commands
   - `README.md` or `README.rst` — project description and setup instructions
   - `.github/workflows/` — CI pipeline structure, what gets tested/linted
   - `docker-compose.yml`, `Dockerfile` — containerisation approach
   - `tsconfig.json`, `ruff.toml`, `.eslintrc.*` — linter/formatter config
   - Lockfiles (`uv.lock`, `package-lock.json`, `Cargo.lock`) — dependency snapshot

3. **Check for existing agent instructions**:
   - `AGENTS.md`, `CLAUDE.md`, `.cursor/rules/`, `.cursorrules`,
     `.github/copilot-instructions.md` — if any exist, read them. These represent
     accumulated team knowledge about the project.
   - If an existing `AGENTS.md` or `CLAUDE.md` is found, treat it as a base to
     refine: **actively discard stale or fluffy claims** that contradict what you
     observe in the actual config/scripts. Only retain guidance you can verify from
     the repo itself. This pruning happens in your mental model only — the file in
     the repo is never modified.

4. **Fall back to source code when needed**:
   - If architecture is still unclear after reading config and docs, inspect a
     small number of representative source files to find the real entrypoints,
     package boundaries, and execution flow.
   - Prefer files that explain how the system is wired together (e.g. main entry
     points, router definitions, DI containers) over random leaf files.
   - Do NOT try to read the entire codebase — a handful of strategic files is enough.

## Step 3: Synthesise Project Context

From what you gathered, build a mental model covering:

- **Project purpose** — what does this repo do, in one sentence?
- **Language & stack** — primary language(s), framework(s), package manager
- **Repository layout** — key directories and what lives in each; for monorepos,
  note multi-package boundaries, directory ownership, and real app/library entrypoints
- **Build / lint / test commands** — the exact commands to run (from manifest
  files, CI workflows, or README), including execution order if it matters
  (e.g. `lint -> typecheck -> test`)
- **Testing quirks** — fixtures, integration test prerequisites, snapshot workflows,
  required services (Docker, databases), flaky or expensive suites, how to run a
  single test or a single package in isolation
- **Conventions** — naming patterns, code style rules, architectural patterns
  that are evident from config or existing code
- **Operational notes** — anything non-obvious (e.g. requires Docker running,
  needs specific env vars, uses a monorepo tool, has a CDK/infra layer,
  generated code or codegen steps, special env loading)

### Verification discipline

Prefer executable sources of truth (config files, scripts, CI workflows) over
prose documentation. If docs conflict with config or scripts, trust the
executable source.

Only retain what you can verify from the repository. Do not make speculative
claims about conventions or architecture that you cannot back up with evidence
from actual files.

### What to exclude from your mental model

Do NOT include:
- Generic software engineering advice
- Long tutorials or exhaustive file trees
- Obvious language or framework conventions (e.g. "use type hints in Python")
- Speculative claims or anything you could not verify
- Content that duplicates what is already obvious from filenames and structure

When in doubt, omit. Every piece of context should answer: "Would the reviewer
likely miss this without this context?" If not, leave it out.

## Step 4: Apply Context to This Review

Use the project context you've built to:

- Understand whether changes fit the repo's existing conventions
- Know which lint/test commands the team relies on (so you can flag if changes
  would break them)
- Recognise architectural patterns and flag deviations
- Understand the project's dependency management approach
- Contextualise file changes within the broader project structure
- Assess test coverage expectations based on the testing setup you observed

## Important Notes

- **Read-only** — do not call any write tools. Do not attempt to update or create
  files in the target repository. This step is purely investigative.
- **No interactive questions** — this runs unattended in CI. If something is
  ambiguous, make a reasonable inference or skip it. Do not block on unknowns.
- **Be concise** — you are building internal context, not writing a document.
  A few bullet points per category is sufficient.
- **Do not review code in this step** — that happens in subsequent tools.
  This step is purely about understanding the project landscape.
- **Do not output this context as part of the PR review body** — it is internal
  working memory only. The review body should contain findings, not repo summaries.
- **Prioritise signal over completeness** — if the repo has 50 config files,
  focus on the ones most relevant to understanding the project (README, main
  manifest, CI config). Don't try to read everything.
