"""Is the real model reachable and configured? Run this BEFORE a long simulation.   python scripts/llm_check.py

Reads the same environment variables the server reads (never a file). Prints which provider/model will be used, makes one tiny call, and tells you what to fix.
Exit code 0 only if the model answered.
"""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> int:
    from app import config
    from app.llm import get_client
    prov = os.getenv("LLM_PROVIDER", "mock")
    if prov in ("mock", "") or (prov == "auto" and not os.getenv("ANTHROPIC_API_KEY")):
        print("LLM_PROVIDER is not set (or 'mock'): the built-in mock model would be used, not a real one.\n"
              "  Gemini (cheap, free tier):  LLM_PROVIDER=openai  LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai  LLM_MODEL=gemini-3.5-flash-lite  LLM_API_KEY=<your key>\n"
              "  Claude:                     LLM_PROVIDER=claude  ANTHROPIC_API_KEY=<your key>")
        return 2
    if prov == "openai" and not os.getenv("LLM_API_KEY"):
        print("LLM_API_KEY is missing (set it as an environment variable, never in a file).")
        return 2
    if prov in ("claude", "auto") and not os.getenv("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is missing.")
        return 2
    c = get_client()
    print(f"provider={c.provider} model={c.model}")
    t = time.time()
    try:
        r = c.complete('Reply with the JSON {"ok": true} and nothing else.', "ping")
    except Exception as e:  # noqa: BLE001
        status = getattr(getattr(e, "response", None), "status_code", None)
        hint = {401: "the key is wrong or expired", 403: "the key has no access to this model/endpoint", 404: "the model name or base URL is wrong", 429: "rate limit / quota reached: wait a minute (free tiers are small) or use another key"}.get(status, "check network/proxy and the variables above")
        print(f"FAILED ({type(e).__name__} {status or ''}): {hint}")
        return 1
    print(f"OK in {time.time() - t:.1f}s -> {r.text.strip()[:60]}   tokens in/out: {r.input_tokens}/{r.output_tokens}")
    print("Tip: for correct cost numbers set PRICE_IN_PER_MTOK / PRICE_OUT_PER_MTOK to your model's price (USD per million tokens), e.g. 0.10 and 0.40 for gemini flash-lite.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
