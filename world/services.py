import hashlib
import hmac
import json
import logging
import os
from datetime import datetime, timedelta

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from .auth import current_user, sign
from .store import CHANNELS, PASSWORD, store

log = logging.getLogger("world")


def _since(hours: int) -> str:
    return (datetime.now() - timedelta(hours=hours)).isoformat(timespec="seconds")


def _page(rows, limit, offset):
    chunk = rows[offset: offset + limit]
    return {"items": chunk, "next_offset": offset + limit if offset + limit < len(rows) else None}


def _person(uid):
    u = store.users.get(uid)
    return {"id": uid, "name": u["name"], "email": u["email"]} if u else None


# ---- SSO ----
sso = APIRouter(prefix="/sso")


class Login(BaseModel):
    user_id: str
    password: str


@sso.post("/token")
def token(b: Login):
    if b.user_id not in store.users or b.password != os.getenv("WORLD_PASSWORD", PASSWORD):
        raise HTTPException(401, "bad credentials")
    return {"access_token": sign(b.user_id), "expires_in": 3600}


@sso.get("/users")  # company directory
def directory():
    return [{k: u[k] for k in ("id", "name", "title", "team", "role")} for u in store.users.values()]


# ---- Mail server ----
mail = APIRouter(prefix="/mail")


def _mail_out(m):
    sender = _person(m["sender"]) if m["sender"] else {"id": None, "name": m["external"], "email": m["external"]}
    return {"id": m["id"], "from": sender, "external": m["external"] is not None, "to": m["to"],
            "subject": m["subject"], "body": m["body"], "ts": m["ts"]}


@mail.get("/inbox")
def inbox(hours: int = 24, limit: int = 50, offset: int = 0, me=Depends(current_user)):
    rows = [_mail_out(m) for m in store.mails if me["id"] in m["to"] and m["ts"] >= _since(hours)]
    return _page(rows, min(limit, 100), offset)


@mail.get("/messages/{mid}")
def message(mid: str, me=Depends(current_user)):
    m = next((m for m in store.mails if m["id"] == mid), None)
    if not m:
        raise HTTPException(404, "not found")
    if me["id"] not in m["to"] and me["id"] != m["sender"]:
        raise HTTPException(403, "not a participant")
    return _mail_out(m)


class Send(BaseModel):
    to: list[str]
    subject: str
    body: str


@mail.post("/send", status_code=201)
def send(b: Send, me=Depends(current_user)):
    if any(t not in store.users for t in b.to):
        raise HTTPException(422, "unknown recipient")
    mid = f"s{len(store.mails) + 1}"
    store.mails.insert(0, dict(id=mid, sender=me["id"], external=None, to=b.to, subject=b.subject, body=b.body,
                               ts=datetime.now().isoformat(timespec="seconds")))
    return {"id": mid}


# ---- Messenger ----
chat = APIRouter(prefix="/chat")


@chat.get("/channels")
def channels(me=Depends(current_user)):
    return [{"id": c, "name": v[0], "private": v[1]} for c, v in CHANNELS.items() if me["id"] in store.members(c)]


@chat.get("/channels/{cid}/messages")
def messages(cid: str, hours: int = 24, limit: int = 50, offset: int = 0, me=Depends(current_user)):
    if cid not in CHANNELS:
        raise HTTPException(404, "no such channel")
    if me["id"] not in store.members(cid):
        raise HTTPException(403, "not a member")
    rows = [{**m, "author": _person(m["author"]), "channel_name": CHANNELS[cid][0]}
            for m in store.chat if m["channel"] == cid and m["ts"] >= _since(hours)]
    return _page(rows, min(limit, 100), offset)


# ---- Issue tracker ----
tracker = APIRouter(prefix="/tracker")


@tracker.get("/issues")
def issues(hours: int = 48, me=Depends(current_user)):
    def visible(i):  # assignee, same team, or executives for escalated items only
        return i["assignee"] == me["id"] or i["team"] == me["team"] or (me["role"] == "executive" and i["escalated"])
    return {"items": [i for i in store.issues if visible(i) and i["ts"] >= _since(hours)]}


# ---- Portal (notices / board) ----
portal = APIRouter(prefix="/portal")


@portal.get("/notices")
def notices(hours: int = 72, me=Depends(current_user)):
    return {"items": [n for n in store.notices if store.audience_ok(me, n["audience"]) and n["ts"] >= _since(hours)]}


@portal.get("/posts")
def posts(hours: int = 72, me=Depends(current_user)):
    return {"items": [p for p in store.posts if store.audience_ok(me, p["audience"]) and p["ts"] >= _since(hours)]}


# ---- HR / attendance: clocking in notifies the assistant by signed webhook ----
hr = APIRouter(prefix="/hr")


def notify_assistant(user_id: str):
    url = os.getenv("ASSISTANT_URL")
    if not url:
        return
    body = json.dumps({"user_id": user_id}).encode()
    sig = hmac.new(os.getenv("ASSISTANT_WEBHOOK_SECRET", "dev-webhook").encode(), body, hashlib.sha256).hexdigest()
    try:
        httpx.post(f"{url.rstrip('/')}/assistant/webhook/clock-in", content=body, timeout=15,
                   headers={"X-Signature": sig, "Content-Type": "application/json"})
    except Exception as e:  # attendance must never fail because the assistant is down
        log.warning("assistant webhook failed: %s", e)


@hr.post("/clock-in")
def clock_in(bg: BackgroundTasks, me=Depends(current_user)):
    at = datetime.now().isoformat(timespec="seconds")
    store.attendance.setdefault((me["id"], at[:10]), at)
    bg.add_task(notify_assistant, me["id"])
    return {"user_id": me["id"], "clock_in_at": store.attendance[(me["id"], at[:10])]}
