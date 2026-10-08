"""Configuration for the review agent's model settings."""

# Maximum output tokens for requests.
MAX_TOKENS = 16000

# False limits thinking to short updates, so it cannot use up MAX_TOKENS.
ENABLE_THINKING = False
