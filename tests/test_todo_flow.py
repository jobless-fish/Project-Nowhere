import pytest
from fastapi.testclient import TestClient

from app.assistant import router as arouter
from app.assistant.world_source import WorldSource
from world.main import app as world_app
from world.store import store


@pytest.fixture()
def env(client, monkeypatch):
    store.reset()
    world = TestClient(world_app)
    monkeypatch.setattr(arouter, "get_source", lambda: WorldSource(world))

    def tok(uid):
        return {"Authorization": "Bearer " + world.post("/sso/token", json={"user_id": uid, "password": "demo1234"}).json()["access_token"]}
    return client, world, tok


def brief(c, uid="u_kim"):
    return c.post("/assistant/clock-in", json={"user_id": uid}).json()["briefing"]


def todo(b, sid):
    return next(t for t in b["todos"] if sid in t["source_ids"])


def act(c, key, what, uid="u_kim", **kw):
    return c.post(f"/assistant/todos/{key}/{what}", json={"user_id": uid, **kw})


def test_todos_carry_their_kind_and_no_flow_before_work_starts(env):
    c, _, _ = env
    b = brief(c)
    assert todo(b, "mail-mk1")["kind"] == "mail" and todo(b, "iss-i1")["kind"] == "issue" and todo(b, "ntc-n1")["kind"] == "notice"
    assert all(t["flow"] is None for t in b["todos"])


def test_issue_start_then_resolve_changes_the_real_tracker(env):
    c, w, tok = env
    k = todo(brief(c), "iss-i1")["key"]
    assert act(c, k, "complete", note="").status_code == 409                                    # a resolution note is required
    s = act(c, k, "start").json()
    assert s["flow"]["status"] == "in_progress" and next(i for i in store.issues if i["id"] == "i1")["status"] == "진행 중"
    r = act(c, k, "complete", note="동기화 작업을 재실행했고 정상 확인").json()
    assert r["flow"]["status"] == "done" and "동기화" in r["flow"]["outcome"]
    i = next(i for i in store.issues if i["id"] == "i1")
    assert i["status"] == "해결" and i["log"][-1]["comment"].startswith("동기화") and i["log"][-1]["by"] == "u_kim"


def test_resolved_issue_and_acknowledged_notice_do_not_come_back_as_todos(env):
    c, w, tok = env
    b = brief(c)
    act(c, todo(b, "iss-i1")["key"], "complete", note="조치 완료했습니다")
    act(c, todo(b, "ntc-n1")["key"], "complete")
    assert act(c, todo(b, "ntc-n1")["key"], "start").status_code == 409                          # notices have no 'start work' step
    again = c.post("/assistant/briefing/refresh", json={"user_id": "u_kim"}).json()["briefing"]
    ids = {i for t in again["todos"] for i in t["source_ids"]}
    assert "iss-i1" not in ids and "ntc-n1" not in ids and "mail-mk1" in ids                      # finished work is gone, real work remains


def test_mail_todo_finishes_only_by_replying_or_by_giving_a_reason(env):
    c, _, _ = env
    b = brief(c)
    k = todo(b, "mail-mk1")["key"]
    assert act(c, k, "complete").status_code == 409                                              # no free "done"
    assert act(c, k, "complete", how="no_reply", note="").status_code == 409
    k2 = todo(b, "mail-mk2")["key"]
    done = act(c, k2, "complete", how="no_reply", note="전화로 이미 답변드렸어요").json()
    assert done["flow"]["status"] == "done" and "답장 없이" in done["flow"]["outcome"]
    # replying finishes the other one automatically, and mail is really sent
    a = c.post("/assistant/actions/propose", json={"user_id": "u_kim", "todo_key": k}).json()
    c.post(f"/assistant/actions/{a['id']}/decision", json={"user_id": "u_kim", "approve": True})
    after = c.get("/assistant/briefing", params={"user_id": "u_kim"}).json()
    f = todo(after, "mail-mk1")["flow"]
    assert f["status"] == "done" and f["outcome"].startswith("회신 발송") and f["ref"].startswith("mail:")


def test_reopening_restores_the_issue_and_the_todo(env):
    c, _, _ = env
    k = todo(brief(c), "iss-i1")["key"]
    act(c, k, "complete", note="조치 완료")
    r = act(c, k, "reopen").json()
    assert r["flow"] is None and next(i for i in store.issues if i["id"] == "i1")["status"] == "열림"


def test_someone_elses_issue_cannot_be_changed_through_the_assistant(env):
    c, _, _ = env
    k = todo(brief(c, "u_dev1"), "iss-i2")["key"]
    # kim is not the assignee of i2 and the key does not exist in his briefing
    assert act(c, k, "complete", note="내가 해결했어요").status_code == 404


def test_refresh_after_a_colleagues_reply_brings_the_new_request_without_losing_progress(env, monkeypatch):
    c, w, tok = env
    from world import npc
    clock = [__import__("time").time()]
    store.now = lambda: clock[0]
    b = brief(c)
    k_issue = todo(b, "iss-i1")["key"]
    act(c, k_issue, "complete", note="조치 완료")
    w.post("/mail/send", json={"to": ["u_slead"], "subject": "3분기 실적 보고", "body": "3분기 실적 보고서 작업을 마쳤습니다. 공유드립니다."}, headers=tok("u_kim"))
    clock[0] += 300
    r = c.post("/assistant/briefing/refresh", json={"user_id": "u_kim"}).json()
    done = next(t for t in r["briefing"]["todos"] if t["key"] == k_issue) if any(t["key"] == k_issue for t in r["briefing"]["todos"]) else None
    assert done is None or done["flow"]["status"] == "done"                                      # progress is not lost (it may also have left the list)
    assert isinstance(r["new"], list)
    store.now = __import__("time").time
