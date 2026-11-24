"""From checkbox to workflow: what "done" means depends on the kind of work, and finishing really changes something.

  mail    -> done when a reply was SENT (automatic), or explicitly closed "without reply" with a reason
  issue   -> start (tracker status "진행 중"), resolve (status "해결" + the note is written to the tracker's log)
  notice  -> acknowledged (recorded in the portal; it no longer comes back as a todo)
Finished work stays visible with its outcome instead of vanishing.
"""
from datetime import datetime

import simclock

from .. import db


def today() -> str:
    return simclock.now().strftime("%Y-%m-%d")


def kind_of(todo: dict) -> str:
    return {"mail": "mail", "iss": "issue", "ntc": "notice"}.get(todo["source_ids"][0].split("-")[0], "other")


def flows(user_id: str, day: str | None = None) -> dict:
    with db.conn() as c:
        rows = c.execute("SELECT todo_key, status, outcome, ref, updated_at FROM todo_flow WHERE user_id=? AND day=?", (user_id, day or today())).fetchall()
    return {r["todo_key"]: {"status": r["status"], "outcome": r["outcome"], "ref": r["ref"], "at": r["updated_at"]} for r in rows}


def put(user_id: str, key: str, status: str, outcome: str, ref: str = ""):
    with db.conn() as c:
        c.execute("INSERT INTO todo_flow(user_id,day,todo_key,status,outcome,ref,updated_at) VALUES(?,?,?,?,?,?,?) "
                  "ON CONFLICT(user_id,day,todo_key) DO UPDATE SET status=excluded.status, outcome=excluded.outcome, ref=excluded.ref, updated_at=excluded.updated_at",
                  (user_id, today(), key, status, outcome, ref, simclock.now().isoformat(timespec="seconds")))


def drop(user_id: str, key: str):
    with db.conn() as c:
        c.execute("DELETE FROM todo_flow WHERE user_id=? AND day=? AND todo_key=?", (user_id, today(), key))


def attach(user_id: str, brief: dict) -> dict:
    f = flows(user_id)
    for t in brief["todos"]:
        t["flow"] = f.get(t["key"])
        t["kind"] = kind_of(t)
    return brief


def raw_id(todo: dict) -> str:
    return todo["source_ids"][0].split("-", 1)[1]


def start(user, todo: dict, source):
    if kind_of(todo) != "issue":
        raise ValueError("only issues have a 'start work' step")
    if hasattr(source, "update_issue"):
        source.update_issue(user, raw_id(todo), "진행 중", "작업을 시작했어요")
    put(user.id, todo["key"], "in_progress", "작업 중", f"issue:{raw_id(todo)}")


def complete(user, todo: dict, source, note: str, how: str):
    kind, note = kind_of(todo), note.strip()
    if kind == "issue":
        if len(note) < 2:
            raise ValueError("해결한 내용을 짧게 적어 주세요")
        if hasattr(source, "update_issue"):
            source.update_issue(user, raw_id(todo), "해결", note)
        put(user.id, todo["key"], "done", f"해결 처리: {note[:120]}", f"issue:{raw_id(todo)}")
    elif kind == "notice":
        if hasattr(source, "ack_notice"):
            source.ack_notice(user, raw_id(todo))
        put(user.id, todo["key"], "done", "확인 완료", f"notice:{raw_id(todo)}")
    elif kind == "mail":
        if (flows(user.id).get(todo["key"]) or {}).get("status") == "done":
            return
        if how != "no_reply" or len(note) < 2:
            raise ValueError("회신을 보내거나, 회신하지 않는 사유를 적어 주세요")
        put(user.id, todo["key"], "done", f"답장 없이 처리: {note[:120]}", "")
    else:
        raise ValueError("unsupported todo")


def reply_sent(user, todo_key: str, to_name: str, mail_ref: str):
    """Called when a drafted reply was actually sent: the request has been answered."""
    put(user.id, todo_key, "done", f"회신 발송 → {to_name}", f"mail:{mail_ref}")
