"""Turns real user signals into regression cases.

  "관련 없음" / 완료 on a todo  -> todo case   (negative / positive)
  reply sent as-is / edited / rejected -> reply case (accepted / edited / rejected)

Cases carry a snapshot of the inputs so they can be replayed later against a new prompt, model or rule set
(`python -m eval.feedback_eval`). PRODUCTION NOTE: snapshots contain business text. A real deployment needs
employee consent, PII masking and a retention limit before harvesting; this demo data is fictional.
"""
import json
from dataclasses import asdict

from .. import db
from .guard import is_suspicious

BODY_MAX = 600


def _snap(item) -> dict:
    d = asdict(item)
    d["body"] = d["body"][:BODY_MAX]
    d.pop("visible_to", None)
    return d


def harvest(source) -> dict:
    users = {u.id: u for u in source.users()}
    cache: dict[str, list] = {}

    def items(uid):
        if uid not in cache:
            cache[uid] = source.fetch(users[uid], hours=72)
        return cache[uid]

    with db.conn() as c:
        fbs = [dict(r) for r in c.execute("SELECT * FROM todo_feedback WHERE value IN ('done','wrong')")]
        briefs = {(r["user_id"], r["day"]): json.loads(r["payload"]) for r in c.execute("SELECT * FROM briefings")}
        acts = [dict(r) for r in c.execute("SELECT * FROM actions WHERE status IN ('sent','rejected')")]
    new = {"todo": 0, "reply": 0}

    def add(key, kind, label, payload):
        with db.conn() as c:
            n = c.execute("INSERT OR IGNORE INTO eval_cases(key,kind,label,payload) VALUES(?,?,?,?)",
                          (key, kind, label, json.dumps(payload, ensure_ascii=False))).rowcount
        new[kind] += n

    for f in fbs:
        uid = f["user_id"]
        todo = next((t for t in briefs.get((uid, f["day"]), {}).get("todos", []) if t["key"] == f["todo_key"]), None)
        if not todo or uid not in users:
            continue
        pool = [_snap(i) for i in items(uid) if i.source in ("mail", "issue", "notice") and not is_suspicious(i)]
        add(f"todo:{uid}:{f['day']}:{f['todo_key']}", "todo", "positive" if f["value"] == "done" else "negative",
            {"user": asdict(users[uid]), "items": pool, "source_ids": todo["source_ids"], "title": todo["title"]})
    for a in acts:
        uid = a["user_id"]
        item = next((i for i in items(uid) if i.id == a["source_id"]), None) if uid in users else None
        if not item:
            continue
        todo = next((t for t in briefs.get((uid, a["day"]), {}).get("todos", []) if t["key"] == a["todo_key"]), {})
        label = "rejected" if a["status"] == "rejected" else ("edited" if a["edited"] else "accepted")
        add(f"reply:{a['id']}", "reply", label,
            {"user": asdict(users[uid]), "item": _snap(item), "todo": {"due": todo.get("due")},
             "draft": a["draft_body"], "final": a["final_body"]})
    return new


def summary() -> dict:
    with db.conn() as c:
        rows = c.execute("SELECT kind, label, COUNT(*) n FROM eval_cases GROUP BY kind, label").fetchall()
    return {"total": sum(r["n"] for r in rows), "by": {f"{r['kind']}:{r['label']}": r["n"] for r in rows}}


def export() -> list[dict]:
    with db.conn() as c:
        return [{"key": r["key"], "kind": r["kind"], "label": r["label"], "payload": json.loads(r["payload"])}
                for r in c.execute("SELECT * FROM eval_cases ORDER BY key")]
