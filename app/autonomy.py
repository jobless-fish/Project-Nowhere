"""Autonomy ladder per document type: shadow -> assisted -> auto.

AI earns more autonomy only from measured agreement with humans. Promotion is a *recommendation*
a person confirms; demotion is applied automatically when quality drops.
"""
import math
import random

from . import config, db

MODES = ["shadow", "assisted", "auto"]
COMPARE_FIELDS = ("doc_type", "amount", "date_from", "date_to")


def wilson_lower(agree: int, n: int, z: float = 1.96) -> float:
    """95% lower confidence bound of the agreement rate: small samples cannot look 'perfect'."""
    if n == 0:
        return 0.0
    p = agree / n
    d = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n)
    return max(0.0, (centre - margin) / d)


def default_mode(doc_type: str) -> str:
    # reply drafts never start in "shadow": the human always sees and approves the draft
    return "assisted" if doc_type.startswith("reply_") else config.DEFAULT_MODE


def get_mode(doc_type: str) -> str:
    with db.conn() as c:
        r = c.execute("SELECT mode FROM modes WHERE doc_type=?", (doc_type,)).fetchone()
    return r["mode"] if r else default_mode(doc_type)


def set_mode(doc_type: str, mode: str):
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    if doc_type == "reply_external":
        raise ValueError("external replies always need a human approval")
    if doc_type.startswith("reply_") and mode == "shadow":
        raise ValueError("reply drafts have no shadow mode")
    with db.conn() as c:
        c.execute("INSERT INTO modes VALUES(?,?) ON CONFLICT(doc_type) DO UPDATE SET mode=excluded.mode",
                  (doc_type, mode))


def agrees(proposed: dict, actual: dict) -> bool:
    """Human result is the ground truth; only fields the human specified are compared."""
    return all(proposed.get(k) == v for k, v in actual.items() if k in COMPARE_FIELDS and v is not None)


def record_outcome(doc_id: int, doc_type: str, mode: str, agree: bool):
    with db.conn() as c:
        c.execute("INSERT INTO outcomes(document_id,doc_type,mode,agree) VALUES(?,?,?,?)",
                  (doc_id, doc_type, mode, int(agree)))


def should_sample() -> bool:
    return random.random() < config.SAMPLE_RATE


def status(doc_type: str) -> dict:
    mode = get_mode(doc_type)
    with db.conn() as c:
        # only outcomes measured in the current mode count toward the next decision
        rows = c.execute("SELECT agree FROM outcomes WHERE doc_type=? AND mode=? ORDER BY id DESC LIMIT 200",
                         (doc_type, mode)).fetchall()
    n, a = len(rows), sum(r["agree"] for r in rows)
    lb = wilson_lower(a, n)
    rec, why = mode, "collecting data"
    is_reply = doc_type.startswith("reply_")
    need_n, need_lb = (config.REPLY_PROMOTE_N, config.REPLY_PROMOTE_LB) if is_reply else (config.PROMOTE_ASSIST_N, config.PROMOTE_ASSIST_LB)
    demote_lb = config.REPLY_DEMOTE_LB if is_reply else config.DEMOTE_LB
    if doc_type == "reply_external":
        return {"doc_type": doc_type, "mode": mode, "samples": n, "agree": a, "agreement_rate": round(a / n, 3) if n else None,
                "lower_bound": round(lb, 3), "recommended_mode": mode, "reason": "external recipients: a human always approves"}
    if mode == "shadow" and n >= config.PROMOTE_SHADOW_N and lb >= config.PROMOTE_SHADOW_LB:
        rec, why = "assisted", f"agreement lower bound {lb:.2f} >= {config.PROMOTE_SHADOW_LB}"
    elif mode == "assisted" and n >= need_n and lb >= need_lb:
        rec, why = "auto", f"agreement lower bound {lb:.2f} >= {need_lb}"
    elif mode == "auto":
        recent = rows[:20]
        rn, ra = len(recent), sum(r["agree"] for r in recent)
        if rn >= 10 and wilson_lower(ra, rn) < demote_lb:
            rec, why = "assisted", f"recent agreement {ra}/{rn} too low"
    return {"doc_type": doc_type, "mode": mode, "samples": n, "agree": a,
            "agreement_rate": round(a / n, 3) if n else None, "lower_bound": round(lb, 3),
            "recommended_mode": rec, "reason": why}


def evaluate(doc_types: list[str]) -> list[dict]:
    """Apply automatic demotions; promotions stay recommendations until a person confirms."""
    out = []
    for t in doc_types:
        s = status(t)
        if s["mode"] == "auto" and s["recommended_mode"] == "assisted":
            set_mode(t, "assisted")
            s["applied"] = "demoted"
        out.append(s)
    return out
