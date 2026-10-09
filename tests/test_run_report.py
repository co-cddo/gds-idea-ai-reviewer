"""Test the end-of-run report built from message history and usage."""

from decimal import Decimal

from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, ToolCallPart, UserPromptPart
from pydantic_ai.usage import RequestUsage, RunUsage

from ai_reviewer.run_report import collect_tool_calls, estimate_cost, format_run_report

GUIDANCE = {"agent_context", "cdk_review_guidance"}
MODEL = "anthropic.claude-sonnet-5-5"


def _response(*tool_names: str, model_name: str = MODEL, provider: str = "aws") -> ModelResponse:
    parts = [ToolCallPart(tool_name=n, args={}) for n in tool_names] or [TextPart(content="done")]
    return ModelResponse(
        parts=parts,
        usage=RequestUsage(input_tokens=1000, output_tokens=100),
        model_name=model_name,
        provider_name=provider,
    )


def _history() -> list:
    return [
        ModelRequest(parts=[UserPromptPart(content="review")]),
        _response("agent_context"),
        _response("get_pull_request_diff"),
        _response("cdk_review_guidance", "get_pull_request_files"),
        _response("pull_request_review_write"),
        _response(),
    ]


def test_collect_tool_calls_returns_names_in_call_order() -> None:
    """Calls are flattened across responses, preserving order; requests are ignored."""
    assert collect_tool_calls(_history()) == [
        "agent_context",
        "get_pull_request_diff",
        "cdk_review_guidance",
        "get_pull_request_files",
        "pull_request_review_write",
    ]


def test_estimate_cost_sums_priced_responses() -> None:
    """A known model gets a positive cost summed over every response."""
    cost = estimate_cost(_history())

    assert cost is not None
    assert cost > Decimal(0)


def test_estimate_cost_is_none_for_unknown_model() -> None:
    """An unpriced model yields None rather than raising."""
    assert estimate_cost([_response(model_name="not-a-real-model")]) is None


def test_report_separates_review_tools_from_other_calls() -> None:
    """Guidance tools are listed in order; everything else is counted."""
    usage = RunUsage(requests=5, tool_calls=5, input_tokens=5000, output_tokens=500)

    report = format_run_report(_history(), usage, GUIDANCE, MODEL)

    assert "  agent_context\n  cdk_review_guidance" in report
    assert "get_pull_request_diff x1" in report
    assert "pull_request_review_write x1" in report
    assert "Requests: 5 | Tool calls: 5" in report
    assert "Tokens: 5,000 in | 500 out" in report
    assert "Estimated cost: $" in report


def test_report_says_cost_unavailable_for_unknown_model() -> None:
    """The report still renders when no price exists."""
    report = format_run_report([_response(model_name="not-a-real-model")], RunUsage(), GUIDANCE, "not-a-real-model")

    assert "Estimated cost: unavailable" in report
    assert "  (none)" in report
