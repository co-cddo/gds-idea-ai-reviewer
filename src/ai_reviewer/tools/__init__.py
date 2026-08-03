"""Auto-discovery of review tool modules.

Any module in this package that exports a `toolset` attribute (a FunctionToolset)
will be automatically picked up by get_all_toolsets(). Modules prefixed with '_'
are ignored (e.g. _tool_template.py). Means we can just add tools
going forward and it'll work.
"""

import importlib
import pkgutil

from pydantic_ai import FunctionToolset


def get_all_toolsets() -> list[FunctionToolset]:
    """Discover and return all FunctionToolsets from this package."""
    toolsets: list[FunctionToolset] = []

    # Import the whole folder so pkgutils knows where to look for relevant modules
    package = importlib.import_module("ai_reviewer.tools")

    for _, module_name, _ in pkgutil.iter_modules(package.__path__):
        if module_name.startswith("_"):
            continue
        module = importlib.import_module(f"ai_reviewer.tools.{module_name}")
        if hasattr(module, "toolset"):
            toolsets.append(module.toolset)
    return toolsets
