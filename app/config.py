import os

DB_PATH = os.getenv("DOCFLOW_DB", "docflow.db")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "auto")  # auto | claude | mock
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5")
# USD per 1M tokens. Set to your contract prices; used only for cost tracking.
PRICE_IN = float(os.getenv("PRICE_IN_PER_MTOK", "3"))
PRICE_OUT = float(os.getenv("PRICE_OUT_PER_MTOK", "15"))
# Below this confidence a document goes to human review instead of auto-processing.
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.75"))
PROMPT_VERSION = os.getenv("PROMPT_VERSION", "v2")
