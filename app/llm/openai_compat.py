"""Any OpenAI-compatible chat endpoint: Ollama, Groq, OpenRouter, Gemini (OpenAI-compat), vLLM..."""
import os
import time

import httpx

from .base import LLMClient, LLMResult


class OpenAICompatClient(LLMClient):
    provider = "openai_compat"

    def __init__(self, base_url: str, model: str, api_key: str = ""):
        self.base_url, self.model = base_url.rstrip("/"), model
        self.api_key = api_key

    def complete(self, system: str, user: str) -> LLMResult:
        t0 = time.perf_counter()
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        r = httpx.post(
            f"{self.base_url}/chat/completions", headers=headers, timeout=120,
            json={"model": self.model, "temperature": 0, "max_tokens": 600,
                  "messages": [{"role": "system", "content": system},
                               {"role": "user", "content": f"<document>\n{user}\n</document>"}]},
        )
        r.raise_for_status()
        j = r.json()
        u = j.get("usage") or {}
        return LLMResult(j["choices"][0]["message"]["content"] or "",
                         u.get("prompt_tokens", 0), u.get("completion_tokens", 0),
                         int((time.perf_counter() - t0) * 1000), self.provider, self.model)
