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
from . import npc
from .store import COMPANY, PASSWORD, store

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


@sso.get("/users")  # login screen: the demo accounts by default, everyone with ?all=true
def login_users(all: bool = False):
    return [{k: u[k] for k in ("id", "name", "title", "team", "role")} for u in store.users.values() if all or u["featured"]]


# ---- Company directory (org chart + people search; any signed-in employee may read) ----
directory = APIRouter(prefix="/directory")
PUBLIC = ("id", "name", "grade", "position", "job_title", "dept", "unit", "team", "location", "email", "ext", "manager_id", "employment", "status", "hire_date")


def _public(p):
    return {k: p[k] for k in PUBLIC}


@directory.get("/org")
def org(me=Depends(current_user)):
    o = store.org
    return {"company": COMPANY, "headcount": o["headcount"], "ceo": _public(store.users[o["ceo_id"]]),
            "departments": [{**d, "head": _public(store.users[d["head_id"]]),
                             "units": [{**u, "lead": _public(store.users[u["lead_id"]]) if u["lead_id"] else None} for u in d["units"]]}
                            for d in o["departments"]]}


@directory.get("/people")
def people(q: str = "", dept: str = "", unit: str = "", limit: int = 30, offset: int = 0, me=Depends(current_user)):
    rows = [p for p in store.users.values()
            if (not q or q.lower() in f"{p['name']} {p['job_title']} {p['email']} {p['unit']}".lower())
            and (not dept or p["dept"] == dept) and (not unit or p["unit"] == unit)]
    rows.sort(key=lambda p: (p["dept_key"], p["unit"], p["position"] != "팀장", p["name"]))
    return _page([_public(p) for p in rows], min(limit, 100), offset) | {"total": len(rows)}


@directory.get("/people/{pid}")
def person(pid: str, me=Depends(current_user)):
    p = store.users.get(pid)
    if not p:
        raise HTTPException(404, "no such employee")
    chain, cur = [], p
    while cur["manager_id"]:
        cur = store.users[cur["manager_id"]]
        chain.append(_public(cur))
    reports = [_public(x) for x in store.users.values() if x["manager_id"] == pid]
    return {**_public(p), "chain_of_command": chain, "direct_reports": reports}


# ---- Mail server ----
mail = APIRouter(prefix="/mail")


def _mail_out(m):
    sender = _person(m["sender"]) if m["sender"] else {"id": None, "name": m.get("external_name") or m["external"], "email": m["external"]}
    is_ext = m["external"] is not None and not m["external"].endswith("@nowhere.example")
    return {"id": m["id"], "from": sender, "external": is_ext, "to": m["to"], "to_people": [_person(t) for t in m["to"] if t in store.users],
            "to_external": m.get("external_to", []), "subject": m["subject"], "body": m["body"], "ts": m["ts"], "thread": m.get("thread")}


@mail.get("/inbox")
def inbox(hours: int = 24, limit: int = 50, offset: int = 0, me=Depends(current_user)):
    store.deliver_due()
    rows = [_mail_out(m) for m in store.mails if me["id"] in m["to"] and m["ts"] >= _since(hours)]
    return _page(rows, min(limit, 100), offset)


@mail.get("/sent")
def sent(hours: int = 72, limit: int = 50, offset: int = 0, me=Depends(current_user)):
    rows = [_mail_out(m) for m in store.mails if m["sender"] == me["id"] and m["ts"] >= _since(hours)]
    return _page(rows, min(limit, 100), offset)


@mail.get("/unread")
def unread(me=Depends(current_user)):
    store.deliver_due()
    seen = store.mail_seen.get(me["id"], store.t0.isoformat(timespec="seconds"))
    new = [m for m in store.mails if me["id"] in m["to"] and m["sender"] != me["id"] and m["ts"] > seen]
    last = max(new, key=lambda m: m["ts"], default=None)
    return {"count": len(new), "latest": _mail_out(last) if last else None, "typing": store.generating > 0 or any(p["kind"] == "mail" and me["id"] in p["to"] for p in store.pending)}


@mail.post("/seen")
def mail_seen(me=Depends(current_user)):
    store.mail_seen[me["id"]] = store.now_iso()
    return {"ok": True}


@mail.get("/messages/{mid}")
def message(mid: str, me=Depends(current_user)):
    m = next((m for m in store.mails if m["id"] == mid), None)
    if not m:
        raise HTTPException(404, "not found")
    if me["id"] not in m["to"] and me["id"] != m["sender"]:
        raise HTTPException(403, "not a participant")
    return _mail_out(m)


class Send(BaseModel):
    to: list[str] = []
    to_external: list[str] = []
    subject: str
    body: str
    in_reply_to: str | None = None
    confirm_external: bool = False


@mail.post("/send", status_code=201)
def send(b: Send, me=Depends(current_user)):
    to = list(dict.fromkeys(b.to))
    if not (to or b.to_external) or any(t not in store.users for t in to):
        raise HTTPException(422, "unknown or missing recipient")
    if len(to) > 10 or len(b.to_external) > 3:
        raise HTTPException(422, "too many recipients")
    if not b.subject.strip() or not b.body.strip() or len(b.subject) > 200 or len(b.body) > 5000:
        raise HTTPException(422, "subject and body are required (subject <= 200, body <= 5000 characters)")
    if b.to_external and not b.confirm_external:
        raise HTTPException(409, "external recipients need confirm_external")
    mid = store.next_id("s")
    store.mails.insert(0, dict(id=mid, sender=me["id"], external=None, to=to, external_to=b.to_external, subject=b.subject.strip(), body=b.body.strip(),
                               ts=store.now_iso(), thread=b.in_reply_to))
    pool = [store.users[t] for t in to]
    ext = (b.to_external[0].split("@")[0].replace(".", " ").title() + " (외부)", b.to_external[0]) if b.to_external and not pool else None
    n = npc.respond(store, "mail", me, pool, b.body, subject=b.subject, mail_id=mid, external=ext)
    return {"id": mid, "replies_coming": n}


# ---- Messenger ----
chat = APIRouter(prefix="/chat")


def _chat_unread(uid: str, cid: str) -> int:
    seen = store.chat_seen.get((uid, cid), store.t0.isoformat(timespec="seconds"))
    return sum(1 for m in store.chat if m["channel"] == cid and m["ts"] > seen and m["author"] != uid)


def _chan(cid, v, me):
    if cid.startswith("dm_"):
        other = next(u for u in store.members(cid) if u != me["id"]) if len(store.members(cid)) > 1 else me["id"]
        return {"id": cid, "name": store.users[other]["name"], "private": True, "dm": True, "other": _person(other), "unread": _chat_unread(me["id"], cid)}
    return {"id": cid, "name": v[0], "private": v[1], "dm": False, "unread": _chat_unread(me["id"], cid)}


@chat.get("/channels")
def channels(me=Depends(current_user)):
    store.deliver_due()
    return [_chan(c, v, me) for c, v in store.channels.items() if me["id"] in store.members(c)]


@chat.get("/unread")
def chat_unread(me=Depends(current_user)):
    store.deliver_due()
    by = {c: _chat_unread(me["id"], c) for c in store.channels if me["id"] in store.members(c)}
    by = {c: n for c, n in by.items() if n}
    return {"total": sum(by.values()), "by_channel": by, "typing": store.generating > 0 or bool(store.pending)}


@chat.get("/channels/{cid}/messages")
def messages(cid: str, hours: int = 24, limit: int = 50, offset: int = 0, latest: bool = False, me=Depends(current_user)):
    if cid not in store.channels:
        raise HTTPException(404, "no such channel")
    if me["id"] not in store.members(cid):
        raise HTTPException(403, "not a member")
    store.deliver_due()
    rows = sorted(({**m, "author": _person(m["author"]), "channel_name": store.channels[cid][0]} for m in store.chat if m["channel"] == cid and m["ts"] >= _since(hours)),
                  key=lambda m: m["ts"])
    if latest:   # the chat window: the newest `limit` messages, oldest first
        store.chat_seen[(me["id"], cid)] = store.now_iso()
        typing = store.generating > 0 or any(p["kind"] == "chat" and p["channel"] == cid for p in store.pending)
        return {"items": rows[-min(limit, 200):], "next_offset": None, "typing": typing}
    return _page(rows, min(limit, 100), offset)


class Post(BaseModel):
    text: str


class DM(BaseModel):
    to: str


@chat.post("/dm")
def open_dm(b: DM, me=Depends(current_user)):
    if b.to not in store.users or b.to == me["id"]:
        raise HTTPException(422, "choose a colleague")
    cid = store.dm(me["id"], b.to)
    return _chan(cid, store.channels[cid], me)


@chat.post("/channels/{cid}/messages", status_code=201)
def post_message(cid: str, b: Post, me=Depends(current_user)):
    if cid not in store.channels:
        raise HTTPException(404, "no such channel")
    if me["id"] not in store.members(cid):
        raise HTTPException(403, "not a member")
    text = b.text.strip()
    if not text or len(text) > 1000:
        raise HTTPException(422, "message must be 1-1000 characters")
    store.deliver_due()
    ts = store.now_iso()
    mid = store.next_id("cu")
    store.chat.append(dict(id=mid, channel=cid, author=me["id"], text=text, ts=ts))
    store.chat_seen[(me["id"], cid)] = ts
    members = [store.users[u] for u in store.members(cid)]
    hist = [{"from": store.users[m["author"]]["name"], "text": m["text"]} for m in [m for m in store.chat if m["channel"] == cid][-7:-1]]
    n = npc.respond(store, "dm" if cid.startswith("dm_") else "chat", me, members, text, channel=cid, history=hist)
    return {"id": mid, "ts": ts, "replies_coming": n}


# ---- Issue tracker ----
tracker = APIRouter(prefix="/tracker")


@tracker.get("/issues")
def issues(hours: int = 48, me=Depends(current_user)):
    def visible(i):  # assignee, same team, or executives for escalated items only
        return i["assignee"] == me["id"] or i["team"] == me["team"] or (me["role"] == "executive" and i["escalated"])
    return {"items": [i for i in store.issues if visible(i) and i["ts"] >= _since(hours)]}


class IssueUpdate(BaseModel):
    status: str
    comment: str = ""


@tracker.patch("/issues/{iid}")
def update_issue(iid: str, b: IssueUpdate, me=Depends(current_user)):
    i = next((i for i in store.issues if i["id"] == iid), None)
    if not i:
        raise HTTPException(404, "no such issue")
    if i["assignee"] != me["id"] and not (me["role"] == "executive" and i["escalated"]):   # the assignee, or an executive for an escalated item
        raise HTTPException(403, "only the assignee can change an issue")
    if b.status not in ("열림", "진행 중", "해결"):
        raise HTTPException(422, "status must be 열림, 진행 중 or 해결")
    if b.status == "해결" and len(b.comment.strip()) < 2:
        raise HTTPException(422, "resolving needs a short note on what was done")
    i["status"] = b.status
    i["log"].append({"by": me["id"], "status": b.status, "comment": b.comment.strip()[:500], "ts": store.now_iso()})
    return i


# ---- Portal (notices / board) ----
portal = APIRouter(prefix="/portal")


@portal.get("/notices")
def notices(hours: int = 72, me=Depends(current_user)):
    return {"items": [{**n, "acked": (me["id"], n["id"]) in store.acks} for n in store.notices if store.audience_ok(me, n["audience"]) and n["ts"] >= _since(hours)]}


@portal.post("/notices/{nid}/ack")
def ack_notice(nid: str, me=Depends(current_user)):
    n = next((n for n in store.notices if n["id"] == nid), None)
    if not n or not store.audience_ok(me, n["audience"]):
        raise HTTPException(404, "no such notice")
    store.acks.add((me["id"], nid))
    return {"acked": True, "at": store.now_iso()}


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


# ---- Company knowledge: products, customers & partners, history, glossary, wiki, calendar ----
from datetime import date as _date  # noqa: E402

from . import archive as arch  # noqa: E402
from . import company as co  # noqa: E402
from .store import COMPANY  # noqa: E402

company = APIRouter(prefix="/company")


def _today():
    return store.t0.date() if hasattr(store, "t0") else _date.today()


@company.get("/overview")
def company_overview(me=Depends(current_user)):
    return {**co.overview(store.users, _today()), "company": COMPANY}


@company.get("/customers")
def company_customers(q: str = "", kind: str = "", stage: str = "", me=Depends(current_user)):
    rows = co.customers(store.users, _today())
    ql = q.strip().lower()
    return {"items": [c for c in rows if (not kind or c["kind"] == kind) and (not stage or c["stage"] == stage)
                      and (not ql or ql in (c["name"] + c["what"] + c.get("product", "") + (c["owner"] or {}).get("name", "")).lower())]}


@company.get("/customers/{cid}")
def company_customer(cid: str, me=Depends(current_user)):
    c = next((c for c in co.customers(store.users, _today()) if c["id"] == cid), None)
    if not c:
        raise HTTPException(404, "no such party")
    return c


@company.get("/history")
def company_history(me=Depends(current_user)):
    return {"items": co.history()}


@company.get("/glossary")
def company_glossary(q: str = "", me=Depends(current_user)):
    return {"items": co.glossary(q)}


@company.get("/wiki")
def company_wiki(q: str = "", me=Depends(current_user)):
    return {"items": co.wiki_list(q)}


@company.get("/wiki/{slug}")
def company_wiki_doc(slug: str, me=Depends(current_user)):
    d = co.wiki_get(slug)
    if not d:
        raise HTTPException(404, "no such document")
    return d


@company.get("/years")
def company_years(me=Depends(current_user)):
    ys = arch.years(store.users, co.customers(store.users, _today()))
    return {"items": [{k: y[k] for k in ("year", "headcount", "customers", "revenue_eok", "p1", "p2", "hired", "in_progress")} for y in ys]}


@company.get("/years/{year}")
def company_year(year: int, me=Depends(current_user)):
    if not arch.FIRST_YEAR <= year <= arch.NOW.year:
        raise HTTPException(404, "no records for that year")
    return arch.year_summary(store.users, co.customers(store.users, _today()), year)


@company.get("/calendar")
def company_calendar(days: int = 90, back: int = 7, year: int = 0, me=Depends(current_user)):
    if year:
        if not arch.FIRST_YEAR <= year <= arch.NOW.year + 1:
            raise HTTPException(404, "no calendar for that year")
        return {"today": _today().isoformat(), "items": arch.all_events(year, year)}
    start = _today() - __import__("datetime").timedelta(days=min(back, 60))
    return {"today": _today().isoformat(), "items": co.calendar(start, min(days, 400) + min(back, 60))}
