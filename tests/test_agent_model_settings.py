"""Test the Bedrock model settings that ReviewerAgent builds."""

import asyncio
from unittest.mock import patch

import pytest
from pydantic_ai.models.test import TestModel

from ai_reviewer.agent import ReviewerAgent
from ai_reviewer.tools import get_all_toolsets


@pytest.mark.parametrize(
    ("enable_thinking", "expected_extra_fields"),
    [
        (False, {"thinking": {"type": "between_tools"}}),
        (True, None),
    ],
)
def test_thinking_setting_sent_to_bedrock(enable_thinking: bool, expected_extra_fields: dict | None) -> None:
    """The thinking flag decides which extra request fields reach Bedrock."""
    with patch("ai_reviewer.agent.get_github_server"):
        reviewer = ReviewerAgent(github_token="unused", enable_thinking=enable_thinking)

    assert reviewer.agent.model.settings.get("bedrock_additional_model_requests_fields") == expected_extra_fields


def test_review_returns_output_and_run_report() -> None:
    """review() hands back the model output plus a report of the tools actually called."""
    with patch("ai_reviewer.agent.get_github_server"):
        reviewer = ReviewerAgent(github_token="unused")

    with reviewer.agent.override(model=TestModel(call_tools=["agent_context"]), toolsets=get_all_toolsets()):
        result = asyncio.run(reviewer.review(repo="co-cddo/example", pr_number=42))

    assert result.output
    assert "Review tools called (in order):\n  agent_context" in result.report
    assert "Estimated cost:" in result.report
    assert result.cost_comment.startswith("<!-- ai-reviewer:run-cost -->")
