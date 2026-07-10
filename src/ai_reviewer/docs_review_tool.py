"""Documentation review guidance tool for the AI reviewer agent.

Reviews README/markdown files and docstrings in Python code. Focuses on
documentation quality, completeness, and accuracy against the actual codebase.

Inspired by the readme_analysis_tool pattern in gds-idea-mcp, adapted to
work as a PR review tool that posts inline comments.
"""

from pydantic_ai import RunContext


def docs_review_tool(agent_instance):
    """Register the documentation review guidance tool on the agent."""

    @agent_instance.tool
    def docs_review_guidance(ctx: RunContext, repository: str, pr_number: int) -> str:
        """
        Get detailed instructions for reviewing documentation in a pull request.

        Reviews README/markdown files for quality and completeness, and checks
        that Python docstrings are present and accurate.

        Args:
            repository: Repository in 'owner/repo' format.
            pr_number: Pull request number to review.
        """

        return f"""# Documentation Review Instructions

## Target
- Repository: {repository}
- Pull Request: #{pr_number}

## Scope

This review covers:
1. **Markdown files** (`.md`, `.rst`) — README quality, structure, accuracy
2. **Python docstrings** — presence and quality on public functions/classes

## Step 1: Identify Documentation in the PR

From the PR diff (which you should already have from the code review):
- Find any `.md` or `.rst` files that were added or modified
- Find any `.py` files with new or modified public functions/classes

## Step 2: Review Markdown / README Files

For each markdown file changed in the PR, evaluate against these criteria:

### 2.1 Structure and Completeness

A good README should have:
- [ ] **Project title and description** — clear, concise, explains what this is
- [ ] **Installation / Getting started** — how to set up and run
- [ ] **Usage examples** — working code snippets or commands
- [ ] **Configuration** — environment variables, config files, options
- [ ] **Prerequisites** — what you need before starting
- [ ] **Development setup** — how contributors get started
- [ ] **Licence** — clearly stated

Not all sections are needed for every file (e.g. a `CONTRIBUTING.md` won't
have installation instructions). Judge based on the file's purpose.

### 2.2 Accuracy Against Code

This is the most important check. Verify:
- Do code examples match actual function signatures in the repo?
- Are dependency versions consistent with pyproject.toml/requirements?
- Are CLI commands and flags accurate?
- Are environment variable names consistent with the code?
- Are file paths and directory structures accurate?
- Are API endpoints or URLs correct?

If the PR changes code behaviour, check whether the README was updated to match.

### 2.3 Clarity and Quality
- Is the writing clear and concise?
- Are technical terms explained where needed?
- Is formatting consistent (heading levels, code blocks, lists)?
- Are code blocks properly fenced with language identifiers (```python, ```bash)?
- Is there unnecessary duplication?
- Are links formatted correctly?

### 2.4 New Features Without Documentation

If the PR adds new functionality (new CLI commands, new env vars, new API
endpoints, new configuration options) — check whether the README or relevant
docs have been updated to cover it. Flag if not.

## Step 3: Review Python Docstrings

For `.py` files in the PR that have new or modified public functions/classes:

### 3.1 Presence

Check that these have docstrings:
- Public functions (no underscore prefix)
- Public classes
- Module-level docstrings (for new modules)
- Complex `__init__` methods (or class docstring covers it)

**DO NOT require docstrings on:**
- Private functions (`_helper_func`)
- Test functions (`test_something`)
- Simple one-line functions where the name is self-documenting
- Dunder methods other than `__init__` (unless complex)
- Property getters/setters with obvious names

### 3.2 Quality

For docstrings that exist, check:
- Do they follow a consistent format (Google style preferred)?
- Are parameters documented with descriptions?
- Are return values documented?
- Are raised exceptions documented (if non-obvious)?

### 3.3 Accuracy

- Do documented parameters match actual function signatures?
- Are types in docstrings consistent with type annotations?
- If a function signature changed in this PR, was the docstring updated?

## Step 4: Prepare Review Comments

### Comment Prefixes
- **Docs:** — Missing or incorrect documentation that could confuse users
- **Suggestion:** — Improvement that would help readability or completeness
- **Nit:** — Minor formatting or style issue

### Example Comments

For a function missing a docstring:
```
Docs: This public function is missing a docstring. Consider:

    \"\"\"Fetch and validate the user configuration.

    Args:
        config_path: Path to the configuration file.
        strict: If True, raise on unknown keys.

    Returns:
        Validated configuration dictionary.

    Raises:
        FileNotFoundError: If config_path does not exist.
    \"\"\"
```

For a README not updated after a code change:
```
Docs: This PR adds the `--dry-run` flag to the CLI but the Usage section
of the README hasn't been updated to mention it.
```

For a README with incorrect code example:
```
Docs: The example shows `from package import old_function` but this was
renamed to `new_function` in this PR.
```

For markdown formatting:
```
Nit: This code block should specify the language for syntax highlighting:
    ```python
    instead of just ```
```

## Step 5: Include in PR Review

Add documentation comments to the SAME PR review as the code review — do NOT
submit a separate review. Include docs inline comments in the `comments` array
alongside code review comments.

In the review summary body, include ALL documentation findings under the
"### Documentation" heading. List each finding with the file and a brief description,
for example:

```
### Documentation
5. **`README.md`** — Code examples reference wrong function names
6. **`README.md`** — Filler text should be removed
7. **`utils.py`** — 4 public functions missing docstrings
```

This ensures the full review body (from the code_review_guidance template) contains
a complete picture of ALL findings — code, config, AND documentation — in one place.

## Important Notes

- Be pragmatic — not every internal helper needs a full docstring
- Focus on what a new developer joining the team would need to understand
- If the README is good but could be slightly better, a single "Suggestion:"
  is fine — don't nitpick every sentence
- If no .md files or new public functions are in the PR, report that documentation
  review found nothing to flag — that's fine
- NEVER suggest adding documentation for its own sake — only flag genuine gaps
  that would cause confusion or friction
"""
