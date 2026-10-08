"""Test the Bedrock model settings that ReviewerAgent builds."""

from unittest.mock import patch

import pytest

from ai_reviewer.agent import ReviewerAgent


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
