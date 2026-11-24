"""Feedback closes the loop: "관련 없음" hides that kind of item for that person, never for everyone, and never what must not be hidden."""
import pytest
from fastapi.testclient import TestClient

from app.assistant import mute


@pytest.fixture()
def w(monkeypatch, tmp_path):
    monkeypatch.setenv("SOURCE", "world")
    from app import config, db
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "m.db"))
    from world.main import app as world_app
    from world.store import store
    store.reset()
    from app.assistant import sources, world_source
    http = TestClient(world_app)
    monkeypatch.setattr(sources, "_source", world_source.WorldSource(http), raising=False)
    monkeypatch.setattr(sources, "get_source", lambda: world_source.WorldSource(http))
    import app.assistant.router as r
    monkeypatch.setattr(r, "get_source", lambda: world_source.WorldSource(http))
    from app.main import app
    with TestClient(app) as c:
        yield c, store


def briefing(c, uid):
    return c.post("/assistant/clock-in", json={"user_id": uid}).json()["briefing"]


def test_signature_ignores_numbers_prefixes_and_punctuation():
    a = mute.signature("mail", "Re: 캠페인 시안 승인 요청 (3차)")
    assert a == mute.signature("mail", "캠페인 시안 승인 요청 (4차)") == mute.signature("mail", "FWD: 캠페인  시안 승인 요청 (12차)")
    assert mute.signature("mail", "캠페인 시안 승인 요청!!") == mute.signature("mail", "캠페인 시안 승인 요청")
    assert a != mute.signature("notice", "캠페인 시안 승인 요청 (3차)")           # same words from another system are another kind


def test_guard_blocks_mandatory_notices_signals_and_my_p1(w):
    assert mute.guard_reason("notice", "정보보안 교육 필수 이수 안내", "12월 10일까지")
    assert mute.guard_reason("notice", "[예산] 개발본부 지출 페이스 108%", "")
    assert mute.guard_reason("issue", "결제 장애", "", "P1", True)
    assert mute.guard_reason("issue", "결제 장애", "", "P1", False) is None          # someone else's issue is not mine to protect
    assert mute.guard_reason("mail", "점심 모임 안내", "") is None


def test_wrong_hides_that_kind_for_that_person_only_and_it_stays_hidden(w):
    c, store = w
    b = briefing(c, "e266")                                                        # 류지우 (marketing) gets several campaign-approval mails
    camp = [t for t in b["todos"] if "캠페인 시안 승인 요청" in t["title"]]
    assert len(camp) >= 2
    r = c.post("/assistant/feedback", json={"user_id": "e266", "todo_key": camp[0]["key"], "value": "wrong"})
    assert r.status_code == 200 and r.json()["muted"]
    after = c.post("/assistant/briefing/refresh", json={"user_id": "e266"}).json()["briefing"]
    assert not [t for t in after["todos"] if "캠페인 시안 승인 요청" in t["title"]]    # the whole kind is gone, not just one mail
    assert {r["sig"] for r in c.get("/assistant/mutes", params={"user_id": "e266"}).json()["items"]} == mute.muted("e266")
    assert mute.muted("u_dev1") == set()                                            # nobody else was affected


def test_mandatory_notice_cannot_be_hidden_and_explains_why(w):
    c, _ = w
    b = briefing(c, "u_dev1")
    n = next(t for t in b["todos"] if t["kind"] == "notice" and "필수" in t["title"] + t["reason"])
    r = c.post("/assistant/feedback", json={"user_id": "u_dev1", "todo_key": n["key"], "value": "wrong"})
    assert r.status_code == 409 and "확인했어요" in r.json()["detail"]
    assert mute.muted("u_dev1") == set()
    assert c.get("/assistant/feedback", params={"user_id": "u_dev1"}).json().get(n["key"]) is None       # nothing recorded


def test_money_signals_cannot_be_hidden(w):
    c, _ = w
    b = briefing(c, "u_cfo")
    sig = next(t for t in b["todos"] if t["title"].startswith("[예산]"))
    assert c.post("/assistant/feedback", json={"user_id": "u_cfo", "todo_key": sig["key"], "value": "wrong"}).status_code == 409


def test_unmute_brings_it_back(w):
    c, _ = w
    b = briefing(c, "e266")
    t = next(t for t in b["todos"] if "캠페인 시안 승인 요청" in t["title"])
    c.post("/assistant/feedback", json={"user_id": "e266", "todo_key": t["key"], "value": "wrong"})
    rules = c.get("/assistant/mutes", params={"user_id": "e266"}).json()["items"]
    assert rules and c.post("/assistant/mutes/remove", json={"user_id": "e266", "sig": rules[0]["sig"]}).status_code == 200
    back = c.post("/assistant/briefing/refresh", json={"user_id": "e266"}).json()["briefing"]
    assert any("캠페인 시안 승인 요청" in x["title"] for x in back["todos"])
    assert c.post("/assistant/mutes/remove", json={"user_id": "e266", "sig": "nope"}).status_code == 404


def test_candidates_need_several_different_people(w):
    c, _ = w
    mute.add("a", "mail|점심 모임", "점심 모임", "mail")
    mute.add("a", "mail|점심 모임", "점심 모임", "mail")
    assert mute.candidates(2) == []                                                 # one person is not a pattern
    mute.add("b", "mail|점심 모임", "점심 모임", "mail")
    assert [x["users"] for x in mute.candidates(2)] == [2]
    assert c.get("/assistant/mutes/candidates").json()["items"][0]["title"] == "점심 모임"
