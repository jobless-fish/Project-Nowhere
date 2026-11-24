import pytest
from fastapi.testclient import TestClient

from app import autonomy
from app.assistant import router as arouter
from app.assistant.world_source import WorldSource
from world.main import app as world_app
from world.store import store


@pytest.fixture()
def env(client, monkeypatch):
    store.reset()
    monkeypatch.setattr(arouter, "get_source", lambda: WorldSource(TestClient(world_app)))
    return client


def brief(c, uid="u_kim"):
    return c.post("/assistant/clock-in", json={"user_id": uid}).json()["briefing"]


def tkey(b, sid):
    return next(t["key"] for t in b["todos"] if sid in t["source_ids"])


def decide(c, aid, uid="u_kim", **kw):
    return c.post(f"/assistant/actions/{aid}/decision", json={"user_id": uid, "approve": True, **kw})


def row(c, key="reply_internal"):
    return next(x for x in c.get("/autonomy").json() if x["doc_type"] == key)


def test_default_is_assisted_and_outcomes_are_recorded(env):
    c = env
    assert autonomy.get_mode("reply_internal") == "assisted"
    b = brief(c)
    a = c.post("/assistant/actions/propose", json={"user_id": "u_kim", "todo_key": tkey(b, "mail-mk1")}).json()
    decide(c, a["id"])                                                    # as drafted -> agree
    s = row(c)
    assert (s["samples"], s["agree"]) == (1, 1)


def test_edits_and_rejections_count_against_the_assistant(env):
    c = env
    b = brief(c)
    a = c.post("/assistant/actions/propose", json={"user_id": "u_kim", "todo_key": tkey(b, "mail-mk1")}).json()
    decide(c, a["id"], body="다른 내용으로 고쳐서 보냅니다.")
    s = row(c)
    assert (s["samples"], s["agree"]) == (1, 0)
    store.reset()   # fresh mailbox; stats persist in DB


def test_external_replies_never_promote_or_change_mode(env):
    c = env
    for i in range(40):
        autonomy.record_outcome(i, "reply_external", "assisted", True)
    assert autonomy.status("reply_external")["recommended_mode"] == "assisted"
    assert c.post("/autonomy/reply_external/mode", json={"mode": "auto"}).status_code == 404   # not even exposed
    with pytest.raises(ValueError):
        autonomy.set_mode("reply_external", "auto")


def test_reply_has_no_shadow_mode(env):
    assert env.post("/autonomy/reply_internal/mode", json={"mode": "shadow"}).status_code == 422


def test_promotion_is_a_recommendation_then_drafts_are_prepared_but_never_sent(env):
    c = env
    for i in range(35):
        autonomy.record_outcome(i, "reply_internal", "assisted", True)
    s = row(c)
    assert s["mode"] == "assisted" and s["recommended_mode"] == "auto"                  # a person must confirm
    assert c.post("/autonomy/reply_internal/mode", json={"mode": "auto"}).json()["mode"] == "auto"
    b = brief(c)                                                                          # clock in after promotion
    drafts = c.get("/assistant/actions", params={"user_id": "u_kim"}).json()
    sources = {d["source_id"] for d in drafts}
    assert "mail-mk1" in sources                                                          # internal mail todo: pre-drafted
    assert "mail-mk2" not in sources and "mail-mk4" not in sources                        # external / injection: no draft
    assert all(d["status"] == "proposed" for d in drafts)                                 # nothing was sent
    assert not any(m["subject"].startswith("Re:") for m in store.mails)
    assert b["todos"]                                                                     # briefing itself unchanged
    again = c.post("/assistant/clock-in", json={"user_id": "u_kim"}).json()
    assert again["cached"] and len(c.get("/assistant/actions", params={"user_id": "u_kim"}).json()) == len(drafts)


def test_auto_is_demoted_when_quality_drops(env):
    c = env
    autonomy.set_mode("reply_internal", "auto")
    for i in range(12):
        autonomy.record_outcome(i, "reply_internal", "auto", i < 5)                       # ~42% as-is
    assert row(c)["applied"] == "demoted" and autonomy.get_mode("reply_internal") == "assisted"
