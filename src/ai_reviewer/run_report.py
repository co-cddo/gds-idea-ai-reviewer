"""Build the end-of-run report: which tools were called, token usage and estimated cost.

Everything here is derived from the finished run's message history and usage, so unlike the
model's own "Reviewed by" section it cannot be wrong about what actually happened.
"""

from collections import Counter
from collections.abc import Iterable
from decimal import Decimal

from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.usage import RunUsage


def collect_tool_calls(messages: Iterable[ModelMessage]) -> list[str]:
    """Return the name of every tool the model called, in call order."""
    return [
        part.tool_name
        for message in messages
        if isinstance(message, ModelResponse)
        for part in message.parts
        if isinstance(part, ToolCallPart)
    ]


def estimate_cost(messages: Iterable[ModelMessage]) -> Decimal | None:
    """Sum the estimated USD price of every model response, or None if any cannot be priced.

    Prices come from the public price table bundled with pydantic-ai, so this is an estimate
    and will not exactly match the AWS bill.
    """
    total = Decimal(0)
    for message in messages:
        if not isinstance(message, ModelResponse):
            continue
        try:
            total += message.cost().total_price
        except (LookupError, AssertionError):
            return None
    return total


RUN_REPORT_MARKER = "<!-- ai-reviewer:run-cost -->"


def format_run_report(
    messages: list[ModelMessage],
    usage: RunUsage,
    guidance_tool_names: set[str],
    model_id: str,
) -> str:
    """Format the run report printed after a review.

    Args:
        messages: The full message history of the run.
        usage: Token and request totals for the run.
        guidance_tool_names: Names of the review guidance tools, used to separate them from
            GitHub MCP calls.
        model_id: Model the cost was estimated for.
    """
    calls = collect_tool_calls(messages)
    guidance_calls = [name for name in calls if name in guidance_tool_names]
    other_calls = Counter(name for name in calls if name not in guidance_tool_names)
    cost = estimate_cost(messages)

    lines = ["--- Run report ---", "Review tools called (in order):"]
    lines += [f"  {name}" for name in guidance_calls] or ["  (none)"]
    lines.append("Other tool calls: " + (", ".join(f"{n} x{c}" for n, c in sorted(other_calls.items())) or "(none)"))
    lines.append(f"Model requests: {usage.requests} | Tool calls: {usage.tool_calls}")
    lines.append(
        f"Tokens: {usage.input_tokens:,} in | {usage.output_tokens:,} out | "
        f"{usage.cache_read_tokens:,} cache-read | {usage.cache_write_tokens:,} cache-write"
    )
    if cost is None:
        lines.append(f"Estimated cost: unavailable (no price found for {model_id})")
    else:
        lines.append(f"Estimated cost: ${cost:.2f} ({model_id}, USD, from public list prices)")
    return "\n".join(lines)


def format_report_comment(
    messages: list[ModelMessage],
    usage: RunUsage,
    guidance_tool_names: set[str],
    model_id: str,
) -> str:
    """Format the run report as a collapsed PR comment.

    The summary line shows the estimated cost; expanding it reveals the same report the CLI prints.
    The leading hidden marker lets tooling find these comments later.

    Args:
        messages: The full message history of the run.
        usage: Token and request totals for the run.
        guidance_tool_names: Names of the review guidance tools.
        model_id: Model the cost was estimated for.
    """
    cost = estimate_cost(messages)
    cost_text = "cost unavailable" if cost is None else f"est. ${cost:.2f}"
    summary = f"Run report: {cost_text} ({usage.requests} model requests, {usage.tool_calls} tool calls)"
    report = format_run_report(messages, usage, guidance_tool_names, model_id)
    return f"{RUN_REPORT_MARKER}\n<details>\n<summary>{summary}</summary>\n\n```text\n{report}\n```\n\n</details>"
