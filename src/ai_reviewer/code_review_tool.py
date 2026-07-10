"""Code review guidance tool for the AI reviewer agent.

Follows the same 'guidance tool' pattern as the readme_analysis_tool
in gds-idea-mcp - returns detailed step-by-step instructions that the
agent follows to perform the review using GitHub MCP tools.
"""

from pydantic_ai import RunContext

# File extensions to review for code quality
REVIEWABLE_EXTENSIONS = (
    ".py",
    ".sql",
    ".html",
    ".jinja2",
    ".j2",
    ".css",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".yaml",
    ".yml",
    ".json",
    ".toml",
)

# File extensions reviewed by the docs_review_tool instead
DOCS_EXTENSIONS = (
    ".md",
    ".rst",
)

# File patterns to always skip (auto-generated, binary, vendored)
SKIP_PATTERNS = (
    ".lock",
    ".txt",
    ".csv",
    ".png",
    ".jpg",
    ".svg",
    ".gif",
    ".ico",
    ".woff",
    ".woff2",
    ".eot",
    ".ttf",
    "_version.py",
    "__pycache__",
    ".venv",
    "node_modules",
    "migrations/",
)


def code_review_tool(agent_instance):
    """Register the code review guidance tool on the agent."""

    @agent_instance.tool
    def code_review_guidance(ctx: RunContext, repository: str, pr_number: int) -> str:
        """
        Get detailed instructions for performing an AI code review on a pull request.

        Args:
            repository: Repository in 'owner/repo' format.
            pr_number: Pull request number to review.
        """

        reviewable_exts = ", ".join(REVIEWABLE_EXTENSIONS)
        docs_exts = ", ".join(DOCS_EXTENSIONS)
        skip_patterns = ", ".join(SKIP_PATTERNS)

        return f"""# AI Code Review Instructions

## Target
- Repository: {repository}
- Pull Request: #{pr_number}

## Step 1: Get Pull Request Information

Use the GitHub MCP tools to:

1. **Get the pull request details** using `get_pull_request`:
   - owner: {repository.split("/")[0] if "/" in repository else "UNKNOWN"}
   - repo: {repository.split("/")[1] if "/" in repository else repository}
   - pullNumber: {pr_number}
   - Note the PR title, description, base branch, and head branch.

2. **Get the pull request diff** using `get_pull_request_diff`:
   - owner: {repository.split("/")[0] if "/" in repository else "UNKNOWN"}
   - repo: {repository.split("/")[1] if "/" in repository else repository}
   - pullNumber: {pr_number}
   - This returns the full diff of all changed files.

## Step 2: Filter Files for Review

From the diff, identify files to review:

**CODE REVIEW these file extensions:** {reviewable_exts}

**DELEGATE to docs_review_guidance tool:** {docs_exts}
(Call the `docs_review_guidance` tool for documentation files — do not review them here)

**SKIP these patterns entirely:** {skip_patterns}

For each reviewable file, note:
- The file path
- Lines added (prefixed with +)
- Lines removed (prefixed with -)
- Surrounding context lines

## Step 3: Analyse Changes

For each reviewable file, evaluate against these criteria:

### 3.1 Bugs and Logic Errors
- Off-by-one errors, incorrect conditions
- Unhandled edge cases (None, empty, boundary values)
- Race conditions or concurrency issues
- Resource leaks (unclosed files, connections)
- Incorrect exception handling (bare except, swallowed errors)

### 3.2 Security
- SQL injection (raw string formatting in queries)
- Hardcoded secrets, API keys, or credentials
- Insecure deserialization
- Path traversal vulnerabilities
- Missing input validation or sanitisation
- Overly permissive permissions or CORS settings
- Sensitive data in logs or error messages

### 3.3 Code Quality and Style
- Functions that are too long or do too many things
- Poor variable or function naming
- Code duplication that should be extracted
- Missing type hints on public functions (Python)
- Dead code or commented-out code blocks
- Overly complex conditionals that should be simplified

### 3.4 Architecture and Design
- Tight coupling between components
- Violations of separation of concerns
- Missing abstraction layers
- Inappropriate use of global state
- Breaking changes to public APIs without clear justification

### 3.5 Testing Considerations
- New logic without corresponding tests
- Test coverage gaps for edge cases
- Brittle tests that depend on implementation details

### 3.6 Python-Specific (for .py files)
- Mutable default arguments
- Use of deprecated stdlib functions
- Missing `__all__` for public module APIs
- Inappropriate use of `*args`/`**kwargs` hiding interface
- Context managers not used where appropriate

### 3.7 SQL-Specific (for .sql files)
- Missing WHERE clauses on UPDATE/DELETE
- N+1 query patterns
- Missing indexes for frequently queried columns
- Unsafe dynamic SQL construction

### 3.8 HTML/Template-Specific (for .html/.jinja2 files)
- Cross-site scripting (XSS) via unescaped variables
- Missing CSRF tokens on forms
- Accessibility issues (missing alt text, aria labels)
- Broken or hardcoded URLs

### 3.9 Configuration Files (for .yaml/.yml/.json/.toml files)
- Valid structure and well-formed syntax
- Consistent key naming conventions (kebab-case, snake_case, camelCase)
- Comments explaining non-obvious settings (where format supports it)

### 3.10 GitHub Actions Workflows (for .github/workflows/*.yml)
- Are job and step names descriptive?
- Are permissions minimally scoped (not overly broad)?
- Are action versions pinned to a tag/SHA (not @latest or @main for third-party)?
- Are secrets referenced correctly?
- Are inputs/outputs documented with descriptions?
- Are there workflow-level comments explaining purpose and usage?

### 3.11 Infrastructure Config (cdk.json, pyproject.toml, package.json)
- Are placeholder values filled in (not "TODO" or template defaults)?
- Are version constraints reasonable?
- Are required fields present?

## Step 4: Prepare Review Comments

For each issue found:
1. Determine the **severity**: critical (bug/security), suggestion (improvement), or nit (style)
2. Note the **file path** and **line number** (from the diff)
3. Write a **clear, constructive comment** explaining:
   - What the issue is
   - Why it matters
   - A suggested fix (if applicable)

### Comment Format Guidelines
- Be constructive and respectful - suggest improvements, don't criticise
- Prefix critical issues with "Bug:" or "Security:"
- Prefix suggestions with "Suggestion:"
- Prefix minor style issues with "Nit:"
- Include code snippets for suggested fixes where helpful
- If a pattern appears multiple times, comment on the first occurrence and note "this pattern appears X more times"

### What NOT to Comment On
- Formatting issues already handled by linters (ruff, prettier)
- Personal style preferences with no clear benefit
- Changes unrelated to the PR's purpose
- TODOs or future improvements unless they indicate incomplete work

## Step 5: Submit the Review

Use `create_pull_request_review` to submit the review:
- owner: {repository.split("/")[0] if "/" in repository else "UNKNOWN"}
- repo: {repository.split("/")[1] if "/" in repository else repository}
- pullNumber: {pr_number}
- event: "COMMENT"
  (IMPORTANT: Use "COMMENT" not "REQUEST_CHANGES" - this review is advisory/optional)
- body: A DETAILED summary of ALL findings (see template below). This is the main visible output on the PR.
- comments: Array of inline comments, each with:
  - path: file path relative to repo root
  - position: line position in the diff (not the file line number)
  - body: the review comment text

### Review Body Template

The review body is the primary summary visible on the PR. It MUST include a categorised
list of ALL findings so that the full picture is captured in one place (not just in
scattered inline comments). Use this structure:

```
## AI Code Review Summary

**Files reviewed:** [list each file]
**Issues found:** [Y critical, Z suggestions, W nits/docs]

### Critical (Bugs & Security)
1. **`filename.py`** — Brief description of the issue and suggested fix
2. **`filename.py`** — Next issue...

### Suggestions
3. **`filename.py`** — Description of improvement
4. **`config.yaml`** — Description...

### Documentation
5. **`README.md`** — Description of docs issue (e.g. wrong function names, missing sections)
6. **`filename.py`** — Missing docstrings on X public functions

### Nits
7. **`filename`** — Minor style issue (only if worth mentioning)

---

[1-2 sentence overall assessment: is this ready to merge, or are there blockers?]

---
*This is an automated review by the GDS IDEA AI Reviewer. Comments are advisory.*
```

**Important:** Include ALL findings in this body, even if they also have inline comments.
The body serves as the complete summary a reviewer can scan without expanding every inline
comment. Omit empty sections (e.g. if there are no nits, skip that heading).

## Step 6: Handle Edge Cases

- **If no reviewable files exist in the PR:** Submit a review with body only (no inline comments),
  noting that no reviewable source files were found in this PR.
- **If the diff is very large (>50 files):** Focus on the most significant changes.
  Prioritise new files and files with the most additions.
- **If you encounter errors:** Report what you could review and note any files that
  couldn't be analysed.

## Important Notes

- NEVER approve or request changes - always use event "COMMENT"
- Be concise - developers don't want to read essays
- Focus on genuine issues, not nitpicks
- If the code looks good, say so briefly - don't manufacture issues
- Remember this is running in CI on every labelled PR - keep it useful
"""
