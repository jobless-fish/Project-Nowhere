import os

from .. import config
from .base import LLMClient


def get_client() -> LLMClient:
    p = config.LLM_PROVIDER
    if p == "auto":
        p = "claude" if os.getenv("ANTHROPIC_API_KEY") else "mock"
    if p == "claude":
        from .claude import ClaudeClient
        return ClaudeClient(config.CLAUDE_MODEL)
    from .mock import MockClient
    return MockClient()
