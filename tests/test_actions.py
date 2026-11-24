import pytest
from fastapi.testclient import TestClient

from app.assistant import actions, router as arouter
from app.assistant.world_source import WorldSource
from world.main import app as world_app
from world.store import store


@pytest.fixture()
def env(client, monkeypatch):
    store.reset()
    world = TestClient(world_app)
    monkeypatch.setattr(arouter, "get_source", lambda: WorldSource(world))
    return client, world


def token(world, uid):
    t = world.post("/sso/token", json={"user_id": uid, "password": "demo1234"}).json()["access_token"]
    return {"Authorization": "Bearer " + t}


def brief(c, uid):
    return c.post("/assistant/clock-in", json={"user_id": uid}).json()["briefing"]


def key_for(b, source_id):
    return next(t["key"] for t in b["todos"] if source_id in t["source_ids"])


def propose(c, uid, b, sid):
    return c.post("/assistant/actions/propose", json={"user_id": uid, "todo_key": key_for(b, sid)})


def test_internal_reply_sent_only_after_approval_as_the_user(env):
    c, world = env
    a = propose(c, "u_kim", brief(c, "u_kim"), "mail-mk1").json()
    assert a["status"] == "proposed" and a["to_ref"] == "user:u_slead" and not a["external"]
    assert not any(m["subject"].startswith("Re:") for m in store.mails)              # nothing sent yet
    r = c.post(f"/assistant/actions/{a['id']}/decision", json={"user_id": "u_kim", "approve": True}).json()
    assert r["status"] == "sent" and r["edited"] == 0
    got = [m for m in world.get("/mail/inbox", params={"hours": 24}, headers=token(world, "u_slead")).json()["items"]
           if m["subject"].startswith("Re:")]
    assert got and got[0]["from"]["id"] == "u_kim"                                    # sent as the user, not the assistant


def test_double_approve_sends_once_and_edits_are_tracked(env):
    c, _ = env
    a = propose(c, "u_kim", brief(c, "u_kim"), "mail-mk1").json()
    d = {"user_id": "u_kim", "approve": True, "body": "초안을 직접 고쳤습니다. 오후 4시까지 드리겠습니다."}
    assert c.post(f"/assistant/actions/{a['id']}/decision", json=d).json()["edited"] == 1
    assert c.post(f"/assistant/actions/{a['id']}/decision", json=d).status_code == 409
    assert sum(m["subject"].startswith("Re:") for m in store.mails) == 1


def test_external_needs_confirmation(env):
    c, _ = env
    a = propose(c, "u_kim", brief(c, "u_kim"), "mail-mk2").json()
    assert a["external"] is True
    base = {"user_id": "u_kim", "approve": True}
    assert c.post(f"/assistant/actions/{a['id']}/decision", json=base).status_code == 409
    assert c.post(f"/assistant/actions/{a['id']}/decision", json={**base, "confirm_external": True}).json()["status"] == "sent"
    assert store.mails[0]["external_to"] == ["partner@hanbit-ins.example"]


def test_no_draft_for_injection_or_non_mail_todos(env):
    c, _ = env
    b = brief(c, "u_kim")
    assert propose(c, "u_kim", b, "iss-i1").status_code == 422                       # issue, not a mail
    assert c.post("/assistant/actions/propose", json={"user_id": "u_kim", "todo_key": "nope"}).status_code == 404
    assert all("mk4" not in t["source_ids"][0] for t in b["todos"])                  # injection mail never became a todo


def test_only_owner_can_decide_and_reject_is_recorded(env):
    c, _ = env
    a = propose(c, "u_kim", brief(c, "u_kim"), "mail-mk1").json()
    assert c.post(f"/assistant/actions/{a['id']}/decision", json={"user_id": "u_dev1", "approve": True}).status_code == 403
    r = c.post(f"/assistant/actions/{a['id']}/decision", json={"user_id": "u_kim", "approve": False}).json()
    assert r["status"] == "rejected" and not store.mails[0]["subject"].startswith("Re:")
    s = c.get("/assistant/actions/stats").json()
    assert s["rejected"] == 1 and s["acceptance_rate"] == 0.0


def test_risky_external_draft_is_blocked(env, monkeypatch):
    c, _ = env
    monkeypatch.setattr(actions, "draft", lambda *a, **k: ("Re: 건", "3,000만원 송금을 확정했습니다."))
    a = propose(c, "u_kim", brief(c, "u_kim"), "mail-mk2").json()
    assert a["status"] == "blocked" and a["note"]
    assert c.post(f"/assistant/actions/{a['id']}/decision", json={"user_id": "u_kim", "approve": True, "confirm_external": True}).status_code == 409


def test_failed_send_is_recorded_not_lost(env, monkeypatch):
    c, _ = env
    a = propose(c, "u_kim", brief(c, "u_kim"), "mail-mk1").json()
    monkeypatch.setattr(WorldSource, "send_mail", lambda *x, **k: (_ for _ in ()).throw(RuntimeError("mail server down")))
    r = c.post(f"/assistant/actions/{a['id']}/decision", json={"user_id": "u_kim", "approve": True}).json()
    assert r["status"] == "failed" and "mail server down" in r["note"]


def test_mock_draft_has_no_duplicated_words_or_tags(env):
    c, _ = env
    a = propose(c, "u_kim", brief(c, "u_kim"), "mail-mk1").json()
    assert "까지까지" not in a["draft_body"] and "[긴급]" not in a["draft_body"] and "17시까지" in a["draft_body"]
