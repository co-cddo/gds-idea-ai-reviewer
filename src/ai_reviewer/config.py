"""Configurationfor the review agent's model settings."""

# Maximum output tokens for requests.
MAX_TOKENS = 16000

# Whether adaptive thinking is enabled. Models like Claude
# Sonnet 5 allow this by default even with no `thinking`
# setting, which can use up MAX_TOKENS before any response is
# produced.
# Flip to True (and consider raising
# MAX_TOKENS) if thinking-driven review quality is considered
# worth the extra cost.
ENABLE_THINKING = False
