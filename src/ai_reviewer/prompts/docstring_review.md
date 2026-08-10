# Documentation Review Instructions

## Target
- Repository: {repository}
- Pull Request: #{pr_number}

## Scope

This review covers **Python docstrings** — presence and quality on public
functions, classes, and modules.

**Out of scope:** README and other Markdown files (`.md`, `.rst`) are handled by
the dedicated README reviewer — do not review or comment on them here. MkDocs /
website documentation and auto-generated docs are also out of scope.

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

**DO NOT require docstrings on:**
- Private functions (`_helper_func`)
- Test functions (`test_something`)
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

## Important Notes

- Be pragmatic — not every internal helper needs a full docstring
- Focus on what a new developer joining the team would need to understand
- Do not review README or other Markdown files here — that is the README
  reviewer's job; flagging them would produce duplicate comments
- If no new or modified public Python definitions are in the PR, report that the
  docstring review found nothing to flag — that's fine
- NEVER suggest adding documentation for its own sake — only flag genuine gaps
  that would cause confusion or friction
