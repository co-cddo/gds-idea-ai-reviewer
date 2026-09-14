"""A generic template for creating review guidance toolsets from prompts and minimal structure.

Each tool module gets its own FunctionToolset rather than sharing one.
The agent will discover them all anyway with get_all_toolsets() export.

Guidance documents live in one of two packages:
    - ai_reviewer.skills: documents that double as OpenCode skills. metadata section is
      for OpenCode only — the agent never sees it, it is stripped via code before the
      guidance is returned to the LLM.
    - ai_reviewer.prompts: bot-orchestration-only documents (e.g. agent_context.md,
      agent_prompt.md) that are not necessary for OpenCode standards and run every time.
"""

import re
from importlib.resources import files

from pydantic_ai import FunctionToolset, RunContext

_FRONTMATTER_RE = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)


def _strip_frontmatter(text: str) -> str:
    """Remove a leading YAML frontmatter block (used by OpenCode skills), if present."""
    return _FRONTMATTER_RE.sub("", text, count=1)


def make_review_tool(
    name: str,
    prompt_file: str,
    description: str,
    package: str = "ai_reviewer.skills",
) -> FunctionToolset:
    """
    Create a FunctionToolset with a single guidance tool that returns
    a prompt template.

    Args:
        name: Tool function name the LLM will see (e.g. "cdk_review_guidance").
        prompt_file: Path to the file
        description: Docstring/description the LLM sees for this tool.
        package: The package the prompt_file lives in. Defaults to
            "ai_reviewer.skills" for documents that double as OpenCode skills.
            Use "ai_reviewer.prompts" for bot-orchestration-only guidance.
    """
    ts = FunctionToolset()

    def guidance(ctx: RunContext, repository: str, pr_number: int) -> str:
        resource = files(package).joinpath(*prompt_file.split("/"))
        body = _strip_frontmatter(resource.read_text())
        return f"Target: {repository} / PR #{pr_number}\n\n{body}"

    # # Set the function's identity so Pydantic AI uses the correct tool name
    # and description in the schema it sends to the LLM based on defined values. Otherwise every function
    # would be called "guidance".
    guidance.__name__ = name
    guidance.__doc__ = description
    ts.add_function(guidance, name=name)
    return ts
