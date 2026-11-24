import json
import re
from dataclasses import dataclass


@dataclass
class LLMResult:
    text: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    provider: str
    model: str


class LLMClient:
    provider = "base"
    model = "base"

    def complete(self, system: str, user: str) -> LLMResult:  # pragma: no cover
        raise NotImplementedError


def parse_json(text: str) -> dict:
    """Tolerate code fences / stray prose around the JSON object."""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no JSON object in LLM output")
    return json.loads(m.group(0))
