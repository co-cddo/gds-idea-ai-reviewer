# Code Review Instructions

## Target
- Repository: {repository}
- Pull Request: #{pr_number}

## File Scope

**Review these extensions:** .py, .sql, .html, .jinja2, .j2, .css, .js, .ts, .tsx, .jsx, .yaml, .yml, .json, .toml

**Delegate to docs_review_guidance:** .md, .rst

**Skip entirely:** .lock, .txt, .csv, .png, .jpg, .svg, .gif, .ico, .woff, .woff2, .eot, .ttf, _version.py, __pycache__, .venv, node_modules, migrations/

## Step 1: Get Pull Request Information

Use the GitHub MCP tools to:

1. **Get the pull request details** using `get_pull_request`:
   - owner: the owner part of {repository} (before the "/")
   - repo: the repo part of {repository} (after the "/")
   - pullNumber: {pr_number}
   - Note the PR title, description, base branch, and head branch.

2. **Get the pull request diff** using `get_pull_request_diff`:
   - owner: the owner part of {repository} (before the "/")
   - repo: the repo part of {repository} (after the "/")
   - pullNumber: {pr_number}
   - This returns the full diff of all changed files.

## Step 2: Filter Files for Review

From the diff, apply the file scope above. For each reviewable file, note:
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
- Be constructive and respectful — suggest improvements, don't criticise
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
