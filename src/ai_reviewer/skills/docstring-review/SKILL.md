---
name: docstring-review
description: Review Python docstrings for presence, quality, and accuracy, and catch docstrings that narrate edit history or cite ticket/PR numbers instead of describing current behaviour. Use when writing or reviewing docstrings on public Python functions, classes, or modules.
metadata:
  ai_reviewer_tool: docstring_review_guidance
---

# Documentation Review Instructions


## Scope

This review covers **Python docstrings** — presence and quality on public
functions, classes, and modules.

**Out of scope:** README and other Markdown files (`.md`, `.rst`) are handled by
the dedicated README reviewer — do not review or comment on them here. MkDocs /
website documentation and auto-generated docs are also out of scope. Line
comments that narrate history (e.g. `# Renamed from get_data() in this PR`) are
also out of scope — this reviewer judges docstring content only, not code
comments.

## Step 1: Identify Documentation in the PR

From the PR diff (which you should already have from the code review):
- Find any `.py` files with new or modified public functions, classes, or
  modules.

If the PR contains no new or modified public Python definitions, report that the
docstring review found nothing to flag — that is a valid outcome.

## Step 2: Review Python Docstrings

For `.py` files in the PR that have new or modified public functions/classes:

### 2.1 Presence

Check that these have docstrings:
- Public functions (no underscore prefix)
- Public classes
- Module-level docstrings (for new modules)
- Complex `__init__` methods (or class docstring covers it)
- Test functions (`test_something`), unless the name alone fully describes
  the scenario — non-obvious parametrized cases, fixtures, or setup still
  need a short docstring explaining what's being tested

**DO NOT require docstrings on:**
- Private functions (`_helper_func`)
- Simple one-line functions where the name is self-documenting
- Dunder methods other than `__init__` (unless complex)
- Property getters/setters with obvious names

### 2.2 Quality

For docstrings that exist, check:
- Do they follow a consistent format (Google style preferred)?
- Are parameters documented with descriptions?
- Are return values documented?
- Are raised exceptions documented (if non-obvious)?

### 2.3 Accuracy

- Do documented parameters match actual function signatures?
- Are types in docstrings consistent with type annotations?
- If a function signature changed in this PR, was the docstring updated?

### 2.4 Historical Narration and Ticket References

Docstrings describe **what the code does now** — never how it got there.
Flag any docstring added or modified in this PR that:

- **Narrates an edit**: describes itself as added, removed, renamed, fixed,
  refactored, or updated, rather than simply stating current behaviour.
  Give-away phrasing: "renamed from...", "previously accepted...", "no longer
  requires...", "now uses...", "updated to...".
- **Cites a ticket, issue, or PR** — internal or external, in any form
  (`#123`, `GH-123`, `JIRA-456`, "see PR #42", "Fixes #99", a bare
  `github.com/.../issues/NN` link). That context belongs in the commit
  message or PR description, not the docstring.

**Bad — narrates the edit instead of describing current behaviour:**
```python
def fetch_data(source: str) -> dict[str, Any]:
    """Fetch data from the given source.

    Renamed from `get_data` and updated to accept a `source` argument
    instead of the removed `path` parameter. See PR #482 for context.
    """
```

**Good — states only what the function does now:**
```python
def fetch_data(source: str) -> dict[str, Any]:
    """Fetch data from the given source.

    Args:
        source: Identifier for the data source to query.

    Returns:
        The retrieved data as a dictionary.
    """
```

**Flag when:** a docstring added or modified in this PR narrates an edit or
cites an issue/PR/ticket number, however phrased.

**Do not flag when:** the docstring states current behaviour, arguments,
returns, and exceptions — even for new, deprecated, or superseding
behaviour — as long as the wording describes the current contract rather
than the edit history.

**Boundary with line comments (out of scope here):**
```python
def fetch_data(source: str) -> dict[str, Any]:  # Renamed from get_data() in this PR
    """Fetch data from the given source.

    Renamed from `get_data` — see PR #482 for details.
    """
```
- The docstring text → **flag** as `Docs:` (this is a 2.4 violation).
- The line comment → **not flagged here** — this reviewer judges docstring
  content only, not code comments.

## Step 3: Prepare Review Comments

### Comment Prefixes
- **Docs:** — Missing or incorrect documentation that could confuse users
- **Suggestion:** — Improvement that would help readability or completeness
- **Nit:** — Minor formatting or style issue

### Example Comments

For a function missing a docstring:

    Docs: This public function is missing a docstring. Consider adding one
    documenting its purpose, arguments, return value, and any exceptions.

For a docstring that has drifted from the signature:

    Docs: The docstring lists a `timeout` parameter, but the function signature
    no longer accepts it. Please update the docstring to match.

For a docstring missing return documentation:

    Suggestion: This docstring documents the arguments but not the return
    value. Consider adding a `Returns:` section describing what it yields.

For an inconsistent docstring style:

    Nit: This docstring mixes reStructuredText (`:param:`) with Google style.
    Consider standardising on Google style to match the rest of the module.

For a docstring that narrates a change or cites a ticket:

    Docs: This docstring narrates the change ("renamed from `get_data`...
    see PR #482") rather than describing current behaviour. Docstrings
    should state only what the function does now — move the history to
    the commit message or PR description.

## Important Notes

- Be pragmatic — not every internal helper needs a full docstring
- Focus on what a new developer joining the team would need to understand
- Do not review README or other Markdown files here — that is the README
  reviewer's job; flagging them would produce duplicate comments
- If no new or modified public Python definitions are in the PR, report that the
  docstring review found nothing to flag — that's fine
- NEVER suggest adding documentation for its own sake — only flag genuine gaps
  that would cause confusion or friction
- NEVER let a docstring narrate history or cite an issue/PR/ticket — flag
  as `Docs:` any docstring describing an edit (added/renamed/fixed/etc.)
  or referencing a ticket number instead of stating current behaviour
