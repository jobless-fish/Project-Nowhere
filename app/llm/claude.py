import time

from .base import LLMClient, LLMResult


class ClaudeClient(LLMClient):
    provider = "claude"

    def __init__(self, model: str):
        import anthropic  # imported lazily so mock mode needs no key

        self.model = model
        self._c = anthropic.Anthropic(max_retries=2, timeout=30)

    def complete(self, system: str, user: str) -> LLMResult:
        t0 = time.perf_counter()
        r = self._c.messages.create(
            model=self.model,
            max_tokens=600,
            system=system,
            messages=[{"role": "user", "content": f"<document>\n{user}\n</document>"}],
        )
        text = "".join(b.text for b in r.content if b.type == "text")
        return LLMResult(
            text, r.usage.input_tokens, r.usage.output_tokens,
            int((time.perf_counter() - t0) * 1000), self.provider, self.model,
        )
