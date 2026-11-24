import hashlib
import hmac
import json
import os
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel

from .. import db
from ..llm import get_client
from .. import autonomy
from . import actions, flow, flywheel, guide
from .briefing import build_briefing, build_digest
from .sources import get_source

# NOTE: the demo trusts the user_id in the request. In production derive it from SSO/OIDC claims
# and from the attendance system's webhook, never from client input.
router = APIRouter(prefix="/assistant")
public = APIRouter(prefix="/assistant")  # authenticated by HMAC signature instead of API key


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
    return _clock_in(body.user_id)


@public.post("/webhook/clock-in")
async def clock_in_webhook(request: Request, x_signature: str | None = Header(default=None)):
    """Called by the attendance system. Authenticated by HMAC over the raw body (no user session here)."""
    raw = await request.body()
    secret = os.getenv("ASSISTANT_WEBHOOK_SECRET", "dev-webhook").encode()
    good = hmac.new(secret, raw, hashlib.sha256).hexdigest()
    if not x_signature or not hmac.compare_digest(x_signature, good):
        raise HTTPException(401, "bad signature")
    # _clock_in does blocking HTTP (it may call back into this very server): never run it on the event loop
    return await run_in_threadpool(_clock_in, json.loads(raw)["user_id"])


def _clock_in(user_id: str):
    user, day = _user(user_id), _today()
    with db.conn() as c:
        c.execute("INSERT OR IGNORE INTO attendance VALUES(?,?,?)",
                  (user.id, day, datetime.now().isoformat(timespec="seconds")))
        at = c.execute("SELECT clock_in_at FROM attendance WHERE user_id=? AND day=?", (user.id, day)).fetchone()[0]
        row = c.execute("SELECT payload FROM briefings WHERE user_id=? AND day=?", (user.id, day)).fetchone()
    if row:  # clocking in twice must not regenerate (cost) or change the list the user is working from
        return {"clock_in_at": at, "briefing": flow.attach(user.id, json.loads(row[0])), "cached": True}
    items = get_source().fetch(user, hours=24)
    brief = build_briefing(user, items, get_client())
    brief["user"] = user.__dict__
    with db.conn() as c:
        c.execute("INSERT INTO briefings(user_id,day,payload) VALUES(?,?,?)",
                  (user.id, day, json.dumps(brief, ensure_ascii=False)))
    autonomy.evaluate(["reply_internal"])                       # demote first if quality dropped
    if autonomy.get_mode("reply_internal") == "auto":           # earned trust: drafts are prepared, never sent
        _prepare_drafts(user, brief)
    return {"clock_in_at": at, "briefing": flow.attach(user.id, brief), "cached": False}


def _prepare_drafts(user, brief):
    source, client = get_source(), get_client()
    for t in brief["todos"]:
        try:
            actions.propose(user, brief, t["key"], source, client, internal_only=True)
        except (LookupError, ValueError):
            continue          # not a mail todo / external / flagged: simply no pre-draft


@router.get("/briefing")
def briefing(user_id: str):
    _user(user_id)
    with db.conn() as c:
        row = c.execute("SELECT payload FROM briefings WHERE user_id=? AND day=?", (user_id, _today())).fetchone()
    if not row:
        raise HTTPException(404, "not clocked in yet")
    return flow.attach(user_id, json.loads(row[0]))


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


class Propose(BaseModel):
    user_id: str
    todo_key: str


class Decision(BaseModel):
    user_id: str
    approve: bool
    subject: str | None = None
    body: str | None = None
    confirm_external: bool = False


@router.post("/actions/propose", status_code=201)
def propose_action(b: Propose):
    user = _user(b.user_id)
    with db.conn() as c:
        row = c.execute("SELECT payload FROM briefings WHERE user_id=? AND day=?", (user.id, _today())).fetchone()
    if not row:
        raise HTTPException(404, "not clocked in yet")
    try:
        return actions.propose(user, json.loads(row[0]), b.todo_key, get_source(), get_client())
    except LookupError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.get("/actions")
def list_actions(user_id: str):
    _user(user_id)
    return actions.list_today(user_id)


@router.get("/actions/stats")
def action_stats():
    return actions.stats()


@router.post("/actions/{aid}/decision")
def decide_action(aid: int, b: Decision):
    user = _user(b.user_id)
    try:
        return actions.decide(user, aid, b.approve, b.subject, b.body, b.confirm_external, get_source())
    except LookupError as e:
        raise HTTPException(404, str(e))
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(409, str(e))


@router.post("/eval/harvest")
def eval_harvest():
    return {"new": flywheel.harvest(get_source()), **flywheel.summary()}


@router.get("/eval/summary")
def eval_summary():
    return flywheel.summary()


@router.get("/eval/export")
def eval_export():
    return flywheel.export()


class ChatIn(BaseModel):
    user_id: str
    message: str
    route: str = "home"
    targets: list[str] = []
    history: list[dict] = []


@router.post("/guide/chat")
def guide_chat(b: ChatIn):
    _user(b.user_id)
    if not b.message.strip() or len(b.message) > 500:
        raise HTTPException(422, "message must be 1-500 characters")
    if not guide.rate_ok(b.user_id):
        raise HTTPException(429, "잠깐만요, 너무 빨라요. 조금 뒤에 다시 물어봐 주세요.")
    hist = [{"role": "user" if h.get("role") == "user" else "bot", "text": str(h.get("text", ""))} for h in b.history[-6:] if isinstance(h, dict)]
    return guide.answer(b.message.strip(), b.route, {t for t in b.targets if t in guide.ALL_TARGETS}, hist, b.user_id, get_client())


@router.get("/guide/tour")
def guide_tour(user_id: str):
    _user(user_id)
    return {"steps": guide.tour(user_id)}


@router.get("/diag")
def diag():
    """What a user can look at when something says 'connection problem': can this server reach the company systems?"""
    out = {"llm": get_client().provider, "source": os.getenv("SOURCE", "fixture"), "world_url": os.getenv("WORLD_URL") if os.getenv("SOURCE") == "world" else None}
    try:
        out["employees"] = len(get_source().users())
        out["ok"], out["error"] = True, None
    except Exception as e:
        out["ok"], out["error"] = False, f"{type(e).__name__}: {str(e)[:160]}"
    return out


def _todo(user_id: str, key: str) -> dict:
    with db.conn() as c:
        row = c.execute("SELECT payload FROM briefings WHERE user_id=? AND day=?", (user_id, _today())).fetchone()
    t = next((t for t in (json.loads(row[0])["todos"] if row else []) if t["key"] == key), None)
    if not t:
        raise HTTPException(404, "todo not found")
    return t


class TodoAct(BaseModel):
    user_id: str
    note: str = ""
    how: str = ""          # mail: "no_reply"


def _run(user_id: str, key: str, fn):
    user, t = _user(user_id), _todo(user_id, key)
    try:
        fn(user, t, get_source())
    except ValueError as e:
        raise HTTPException(409, str(e))
    except Exception as e:                      # the company system refused (permissions, rules) or is unreachable
        status = getattr(getattr(e, "response", None), "status_code", None)
        raise HTTPException(409 if status in (403, 422) else 502, f"사내 시스템이 요청을 처리하지 못했어요 ({status or type(e).__name__})")
    return flow.attach(user_id, {"todos": [t]})["todos"][0]


@router.post("/todos/{key}/start")
def todo_start(key: str, b: TodoAct):
    return _run(b.user_id, key, lambda u, t, s: flow.start(u, t, s))


@router.post("/todos/{key}/complete")
def todo_complete(key: str, b: TodoAct):
    return _run(b.user_id, key, lambda u, t, s: flow.complete(u, t, s, b.note, b.how))


@router.post("/todos/{key}/reopen")
def todo_reopen(key: str, b: TodoAct):
    def go(u, t, s):
        if flow.kind_of(t) == "issue" and hasattr(s, "update_issue") and (flow.flows(u.id).get(key) or {}).get("status") in ("in_progress", "done"):
            s.update_issue(u, flow.raw_id(t), "열림", "다시 열었어요")
        flow.drop(u.id, key)
    return _run(b.user_id, key, go)


@router.post("/briefing/refresh")
def briefing_refresh(b: ClockIn):
    """New mail may have arrived since this morning: rebuild today's briefing. Finished work keeps its state (keys are stable)."""
    user = _user(b.user_id)
    with db.conn() as c:
        old = c.execute("SELECT payload FROM briefings WHERE user_id=? AND day=?", (user.id, _today())).fetchone()
    if not old:
        raise HTTPException(404, "not clocked in yet")
    before = {t["key"] for t in json.loads(old[0])["todos"]}
    brief = build_briefing(user, get_source().fetch(user, hours=24), get_client())
    brief["user"] = user.__dict__
    with db.conn() as c:
        c.execute("UPDATE briefings SET payload=? WHERE user_id=? AND day=?", (json.dumps(brief, ensure_ascii=False), user.id, _today()))
    out = flow.attach(user.id, brief)
    return {"briefing": out, "new": [t["key"] for t in out["todos"] if t["key"] not in before]}
