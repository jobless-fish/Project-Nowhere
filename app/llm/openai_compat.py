"""Any OpenAI-compatible chat endpoint: Ollama, Groq, OpenRouter, Gemini (OpenAI-compat), vLLM...

Hosted free tiers are rate limited and spiky (429/503/timeouts), so transient failures are retried with
exponential backoff + jitter and the server's Retry-After is respected. Client errors (400/401/404) fail fast.
"""
import random
import time

import httpx

from .base import LLMClient, LLMResult

RETRYABLE = {429, 500, 502, 503, 504}


class OpenAICompatClient(LLMClient):
    provider = "openai_compat"

    def __init__(self, base_url: str, model: str, api_key: str = "", max_retries: int = 4, timeout: float = 60,
                 http: httpx.Client | None = None, sleep=time.sleep):
        self.base_url, self.model, self.api_key = base_url.rstrip("/"), model, api_key
        self.max_retries, self.http, self._sleep = max_retries, http or httpx.Client(timeout=timeout), sleep

    def _delay(self, attempt: int, r: httpx.Response | None) -> float:
        ra = r.headers.get("retry-after") if r is not None else None
        if ra and ra.replace(".", "", 1).isdigit():
            return min(float(ra), 60)
        return min(2 ** attempt, 30) + random.uniform(0, 0.5)

    def complete(self, system: str, user: str) -> LLMResult:
        t0 = time.perf_counter()
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        body = {"model": self.model, "temperature": 0, "max_tokens": 600,
                "messages": [{"role": "system", "content": system},
                             {"role": "user", "content": f"<document>\n{user}\n</document>"}]}
        for attempt in range(self.max_retries + 1):
            try:
                r = self.http.post(f"{self.base_url}/chat/completions", headers=headers, json=body)
            except (httpx.TimeoutException, httpx.TransportError):
                if attempt >= self.max_retries:
                    raise
                self._sleep(self._delay(attempt, None))
                continue
            if r.status_code in RETRYABLE and attempt < self.max_retries:
                self._sleep(self._delay(attempt, r))
                continue
            r.raise_for_status()
            j = r.json()
            u = j.get("usage") or {}
            return LLMResult(j["choices"][0]["message"]["content"] or "",
                             u.get("prompt_tokens", 0), u.get("completion_tokens", 0),
                             int((time.perf_counter() - t0) * 1000), self.provider, self.model)
        raise RuntimeError("unreachable")  # pragma: no cover
