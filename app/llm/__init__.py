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
    if p == "openai":
        from .openai_compat import OpenAICompatClient
        return OpenAICompatClient(
            os.getenv("LLM_BASE_URL", "http://localhost:11434/v1"),  # Ollama default
            os.getenv("LLM_MODEL", "qwen2.5:7b"), os.getenv("LLM_API_KEY", ""))
    from .mock import MockClient
    return MockClient()
