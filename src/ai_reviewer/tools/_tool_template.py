"""A generic template for creating review guidance toolsets from prompts and minimal structure.

Each tool module gets its own FunctionToolset rather than sharing one.
This avoids circular imports between __init__.py and the template and keeps
each tool independently composable.
The agent will discover them all anyway with get_all_toolsets() export.
"""

from importlib.resources import files

from pydantic_ai import FunctionToolset, RunContext


def make_review_tool(name: str, prompt_file: str, description: str) -> FunctionToolset:
    """
    Create a FunctionToolset with a single guidance tool that returns
    an referenced prompt template.

    Args:
        name: Tool function name the LLM will see (e.g. "cdk_review_guidance").
        prompt_file: Filename in the ai_reviewer.prompts package (e.g. "cdk_review.md").
        description: Docstring/description the LLM sees for this tool.
    """
    ts = FunctionToolset()

    def guidance(ctx: RunContext, repository: str, pr_number: int) -> str:
        template = files("ai_reviewer.prompts").joinpath(prompt_file).read_text()
        return template.format(repository=repository, pr_number=pr_number)

    # # Set the function's identity so Pydantic AI uses the correct tool name
    # and description in the schema it sends to the LLM based on defined values. Otherwise every function
    # would be called "guidance".
    guidance.__name__ = name
    guidance.__doc__ = description
    ts.add_function(guidance, name=name)
    return ts
