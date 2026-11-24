import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .. import db
from ..llm import get_client
from .briefing import build_briefing, build_digest
from .sources import get_source

# NOTE: the demo trusts the user_id in the request. In production derive it from SSO/OIDC claims
# and from the attendance system's webhook, never from client input.
router = APIRouter(prefix="/assistant")


def _user(user_id: str):
    u = next((u for u in get_source().users() if u.id == user_id), None)
    if not u:
        raise HTTPException(404, "unknown user")
    return u


def _today():
    return datetime.now().strftime("%Y-%m-%d")


class ClockIn(BaseModel):
    user_id: str


@router.get("/users")
def users():
    return [u.__dict__ for u in get_source().users()]


@router.post("/clock-in")
def clock_in(body: ClockIn):
    user, day = _user(body.user_id), _today()
    with db.conn() as c:
        c.execute("INSERT OR IGNORE INTO attendance VALUES(?,?,?)",
                  (user.id, day, datetime.now().isoformat(timespec="seconds")))
        at = c.execute("SELECT clock_in_at FROM attendance WHERE user_id=? AND day=?", (user.id, day)).fetchone()[0]
        row = c.execute("SELECT payload FROM briefings WHERE user_id=? AND day=?", (user.id, day)).fetchone()
    if row:  # clocking in twice must not regenerate (cost) or change the list the user is working from
        return {"clock_in_at": at, "briefing": json.loads(row[0]), "cached": True}
    items = get_source().fetch(user, hours=24)
    brief = build_briefing(user, items, get_client())
    brief["user"] = user.__dict__
    with db.conn() as c:
        c.execute("INSERT INTO briefings(user_id,day,payload) VALUES(?,?,?)",
                  (user.id, day, json.dumps(brief, ensure_ascii=False)))
    return {"clock_in_at": at, "briefing": brief, "cached": False}


@router.get("/briefing")
def briefing(user_id: str):
    _user(user_id)
    with db.conn() as c:
        row = c.execute("SELECT payload FROM briefings WHERE user_id=? AND day=?", (user_id, _today())).fetchone()
    if not row:
        raise HTTPException(404, "not clocked in yet")
    return json.loads(row[0])


@router.get("/news")
def news(user_id: str):
    user = _user(user_id)
    return build_digest(user, get_source().fetch(user, hours=48), get_client())


class Feedback(BaseModel):
    user_id: str
    todo_key: str
    value: str  # done | dismissed | wrong


@router.post("/feedback")
def feedback(body: Feedback):
    _user(body.user_id)
    if body.value not in ("done", "dismissed", "wrong"):
        raise HTTPException(422, "value must be done|dismissed|wrong")
    with db.conn() as c:
        c.execute("INSERT OR REPLACE INTO todo_feedback(user_id,day,todo_key,value) VALUES(?,?,?,?)",
                  (body.user_id, _today(), body.todo_key, body.value))
    return {"ok": True}


@router.get("/feedback")
def feedback_list(user_id: str):
    with db.conn() as c:
        return {r["todo_key"]: r["value"] for r in c.execute(
            "SELECT todo_key, value FROM todo_feedback WHERE user_id=? AND day=?", (user_id, _today()))}
