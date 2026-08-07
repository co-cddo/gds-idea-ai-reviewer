# Code Review Instructions

## Target
- Repository: {repository}
- Pull Request: #{pr_number}

## File Scope

**Review these extensions:** .py, .sql, .html, .jinja2, .j2, .css, .js, .ts, .tsx, .jsx, .yaml, .yml, .json, .toml

**Delegate to the README reviewer:** `README.*` files (`README.md`, `README.rst`,
and nested package/subfolder READMEs) — do not comment on them here.

**Delegate to the docstring reviewer:** docstring **content, quality, and
accuracy** (Google-style formatting, Args/Returns/Raises completeness, drift from
signatures) in `.py` files, and all other Markdown/`.rst` documentation. This
reviewer may still note the **absence** of a docstring on new public code as part
of code quality (3.3), but must not critique the wording of docstrings that exist.

**Delegate to the CDK reviewer:** CDK infrastructure specifics — typed config
objects, IAM `.grant_*()` patterns, removal policies, stack structure, resource
naming/tagging (see 3.11). Do not raise competing comments on `app.py`,
`stacks/**`, or `cdk.json` where the CDK reviewer owns the standard.

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
- Incorrect exception handling: bare `except:` clauses, overly broad
  `except Exception`, or swallowed errors
- Failure to raise a **specific or custom** exception where an input is invalid
  or an operation fails (a generic `Exception`/`ValueError` where a domain-
  specific exception would be clearer)

### 3.2 Security
- SQL injection (raw string formatting in queries)
- Hardcoded secrets, API keys, or credentials (these must be loaded via
  environment variables, e.g. `os.getenv`)
- Insecure deserialization
- Path traversal vulnerabilities
- Missing input validation or sanitisation on external inputs
- Overly permissive permissions or CORS settings
- Sensitive data in logs or error messages

### 3.3 Code Quality and Style
- Functions that are too long or do too many things (SRP violations)
- Duplication that should be extracted into a shared helper (DRY)
- **Naming:** vague or cryptic names — flag generic `df`, single-letter names,
  and abbreviations that obscure meaning; names should be descriptive and
  self-explanatory
- **Type hints:** flag missing or incomplete static type hints on **function
  arguments, return types, and class variables** — not just public functions
- **Comments:** flag comments that describe *what* the code does rather than
  *why*; complex logic should carry a concise "why" comment
- Dead code or commented-out code blocks — including functions, wrappers, or
  methods that are **defined but never referenced** anywhere in the codebase
  (check call sites, not just the definition)
- **Repeated boilerplate:** several near-identical functions/wrappers that differ
  only in which method or constant they call. Flag ~3+ occurrences of the same
  shape as a candidate for parametrisation, a factory, or a loop over a mapping,
  rather than N hand-written copies
- Overly complex conditionals that should be simplified

### 3.4 Architecture and Design
- Tight coupling between components
- Violations of separation of concerns (SRP/SOLID)
- Missing abstraction layers
- Inappropriate use of global state
- Breaking changes to public APIs without clear justification

### 3.5 Testing Considerations
- New logic without corresponding tests
- Test coverage gaps for edge cases
- Brittle tests that depend on implementation details
- **Style:** prefer pytest **functional style** — flag new test classes used
  where module-level functions would do (classes only where genuinely necessary)
- **Duplication:** flag repeated near-identical test bodies that should use
  `@pytest.mark.parametrize`

### 3.6 Python-Specific (for .py files)
- Mutable default arguments
- Use of deprecated stdlib functions
- Missing `__all__` for public module APIs
- Inappropriate use of `*args`/`**kwargs` hiding interface
- Context managers not used where appropriate
- **`print()` used for telemetry/logging** — production code must use the
  standard `logging` module with an appropriate level (DEBUG/INFO/WARNING/
  ERROR/CRITICAL). (Exception: `print()` is acceptable in CDK stack/synth code
  and in genuine CLI user-output — do not flag those.)
- Missing docstring on a **new public** function, class, or module (note its
  absence only — defer wording/quality to the docstring reviewer)
- **UK English:** flag US spellings in new identifiers, user-facing strings, and
  comments (e.g. `color` → `colour`, `initialize` → `initialise`) — raise as a
  Nit, and ignore where the token is a third-party API name that must match

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
- **Pydantic:** CDK context/configuration should be modelled with strongly
  typed Pydantic (not raw dict/context lookups). Note: deeper CDK config
  standards belong to the CDK reviewer — defer to it rather than duplicating.

### 3.12 Caching and Performance Abstractions (any language)
- **Justify the cache:** when a PR adds a caching layer (`@cache.memoize`,
  `functools.lru_cache`, a Redis/SimpleCache wrapper, memoisation helpers), check
  there is evidence the cached operation is actually expensive. Flag caching
  added to cheap operations (small datasets, sub-millisecond/low-millisecond
  work) where the serialisation cost of storing and reconstructing the result
  (e.g. DataFrame `.to_dict()` round-trips) may exceed the cost of recomputing.
- **Cache invalidation:** prefer invalidation that happens naturally (e.g.
  per-instance `lru_cache` that resets when a new model instance is built) over
  caches that require manual `cache.clear()` calls scattered through the code.
  Flag manual-clear patterns as a correctness risk (stale data if a clear is
  missed).
- **Cache placement:** flag caching bolted onto the presentation/wiring layer
  (e.g. wrapper functions in `app.py`) when it would sit more cohesively next to
  the data model or the expensive call it protects.
- **Pull-its-weight test:** an abstraction added "for performance" should have a
  plausible reason to exist. If a simpler direct call would be imperceptibly
  slower to a user, note it as a **Suggestion** to simplify — do not block.

**Do not flag:** caches on genuinely expensive work (large datasets, network/DB
round-trips, heavy computation), or existing caching untouched by the PR.

### 3.13 App Patterns (for callbacks/apps)
- **Callback fan-out:** flag several callbacks that each independently fetch or
  compute the **same** filtered data from the same inputs on one interaction.
  Suggest sharing the result once via `dcc.Store` (a single callback populates
  the store; chart callbacks read from it) rather than relying on a cache to mask
  redundant calls.
- **Near-identical data-access methods:** flag several filter/aggregation methods
  that differ only trivially (e.g. `get_overview_filtered_data`,
  `get_case_filtered_data`, `get_assurer_filtered_data`) as candidates for a
  single parametrised method.

**Do not flag:** distinct callbacks that legitimately need different data, or a
single shared call per interaction.

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
- Formatting issues already handled by linters (ruff, prettier) — including line
  length, import ordering, and whitespace
- Personal style preferences with no clear benefit
- Changes unrelated to the PR's purpose
- TODOs or future improvements unless they indicate incomplete work
- Docstring wording/quality, README content, or CDK infrastructure standards —
  these are owned by their dedicated reviewers (see delegation notes above);
  commenting here would produce duplicate feedback
