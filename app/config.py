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
# Autonomy ladder: shadow (AI only suggests) -> assisted (human approves every item) -> auto
DEFAULT_MODE = os.getenv("DEFAULT_MODE", "shadow")
SAMPLE_RATE = float(os.getenv("AUDIT_SAMPLE_RATE", "0.1"))  # share of auto items still sent to a human
PROMOTE_SHADOW_N, PROMOTE_SHADOW_LB = 20, 0.85      # shadow -> assisted
PROMOTE_ASSIST_N, PROMOTE_ASSIST_LB = 30, 0.95      # assisted -> auto
DEMOTE_LB = 0.90                                    # auto -> assisted when recent outcomes fall below
# Reply drafts: promotion only means "pre-drafted at clock-in" (sending always needs a human click), so the bar is lower
REPLY_PROMOTE_N, REPLY_PROMOTE_LB = 20, 0.80
REPLY_DEMOTE_LB = 0.60
