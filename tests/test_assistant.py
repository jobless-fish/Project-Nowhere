from app.assistant import briefing as br
from app.assistant.sources import get_source
from app.llm.base import LLMClient, LLMResult
import json


def clock(client, uid):
    return client.post("/assistant/clock-in", json={"user_id": uid}).json()


def ids(b):
    return {i for t in b["todos"] for i in t["source_ids"]}


def test_employee_briefing_and_permissions(client):
    b = clock(client, "u_kim")["briefing"]
    assert {"m1", "m2", "i1", "n1"} <= ids(b)
    assert not ids(b) & {"m3", "i2", "m6", "m7", "i3"}      # promo, others' issue, exec-only items
    assert b["todos"][0]["priority"] == "high"
    assert "s3" not in b["sources"]


def test_executive_gets_decisions_not_staff_work(client):
    b = clock(client, "u_park")["briefing"]
    assert {"m6", "m7", "i3"} <= ids(b) and not ids(b) & {"m1", "m2"}
    n = client.get("/assistant/news", params={"user_id": "u_kim"}).json()
    assert "s3" not in n["sources"]                          # exec-only slack channel hidden from staff
    assert "s3" in client.get("/assistant/news", params={"user_id": "u_park"}).json()["sources"]


def test_injection_mail_is_flagged_not_actioned(client):
    b = clock(client, "u_kim")["briefing"]
    assert "m5" not in ids(b) and [f["id"] for f in b["flagged"]] == ["m5"]


def test_clock_in_twice_is_idempotent(client):
    a, b = clock(client, "u_kim"), clock(client, "u_kim")
    assert a["cached"] is False and b["cached"] is True and a["briefing"] == b["briefing"]
    assert client.get("/metrics").json()["llm_calls"] == 0   # mock provider logs nothing; no regeneration


class Fake(LLMClient):
    provider, model = "fake", "fake"

    def __init__(self, out):
        self.out = out

    def complete(self, system, user):
        if isinstance(self.out, Exception):
            raise self.out
        return LLMResult(json.dumps(self.out), 50, 50, 1, "fake", "fake")


def user_items(uid="u_kim"):
    src = get_source()
    u = next(x for x in src.users() if x.id == uid)
    return u, src.fetch(u, 24)


def test_ungrounded_and_injection_cited_todos_are_dropped(client):
    u, items = user_items()
    bad = {"summary": "s", "todos": [
        {"title": "존재하지 않는 일", "priority": "high", "source_ids": ["zzz"]},
        {"title": "송금 승인", "priority": "high", "source_ids": ["m5"]},
        {"title": "보고서 회신", "priority": "high", "source_ids": ["m1"]},
        {"title": "출처 없음", "priority": "normal", "source_ids": []}], "fyi": []}
    out = br.build_briefing(u, items, Fake(bad))
    # the model's bad cards are dropped (3), and the mandatory notice the model overlooked is added back by code (ensure_obligations)
    assert [t["title"] for t in out["todos"]] == ["보고서 회신", "정보보안 교육 필수 이수 안내"] and out["dropped_ungrounded"] == 3


def test_llm_failure_degrades_to_rules(client):
    u, items = user_items()
    out = br.build_briefing(u, items, Fake(RuntimeError("down")))
    assert out["degraded"] is True and {"m1", "i1"} <= ids(out)


def test_feedback_roundtrip(client):
    b = clock(client, "u_kim")["briefing"]
    k = b["todos"][0]["key"]
    assert client.post("/assistant/feedback", json={"user_id": "u_kim", "todo_key": k, "value": "done"}).status_code == 200
    assert client.get("/assistant/feedback", params={"user_id": "u_kim"}).json() == {k: "done"}
    assert client.post("/assistant/feedback", json={"user_id": "u_kim", "todo_key": k, "value": "x"}).status_code == 422
    assert client.get("/assistant/briefing", params={"user_id": "u_park"}).status_code == 404


def test_llm_payload_marks_my_issues_and_unassigned_issue_todos_are_dropped(client):
    u, items = user_items()
    issues = [i for i in items if i.source == "issue"]
    mine = next(i for i in issues if i.assignee == u.id)
    other = next(i for i in issues if i.assignee != u.id)
    flags = {p["id"]: p["assignee_is_me"] for p in json.loads(br._payload(issues, u))}
    assert flags[mine.id] is True and flags[other.id] is False
    out = br.build_briefing(u, items, Fake({"summary": "s", "fyi": [], "todos": [
        {"title": "남의 이슈", "priority": "high", "source_ids": [other.id]}, {"title": "내 이슈", "priority": "high", "source_ids": [mine.id]}]}))
    # (plus the mandatory notice the fake model never mentioned: code adds it back)
    assert [t["title"] for t in out["todos"]] == ["내 이슈", "정보보안 교육 필수 이수 안내"] and out["dropped_unassigned"] == 1


def test_news_digest_stays_short_even_in_a_busy_company(client):
    from world.store import store
    from fastapi.testclient import TestClient
    from app.assistant.world_source import WorldSource
    from world.main import app as wapp
    store.reset()
    src = WorldSource(TestClient(wapp))
    u = next(x for x in src.users() if x.id == "u_dev1")
    items = src.fetch(u, 48)
    assert sum(i.source == "chat" for i in items) > 60                      # busy: many chat messages
    from app.llm.mock import MockClient
    d = br.build_digest(u, items, Fake({"highlights": []}))
    raw = br.build_digest(u, items, MockClient())
    assert 1 <= len(raw["highlights"]) <= 10 and len(raw["sources"]) <= 12 + 8 * 6
    assert raw["highlights"][0]["category"] in ("notice", "post")           # official news first
    assert any("새 메시지" in h["title"] for h in raw["highlights"])         # chat is grouped per channel
    assert d["highlights"] == []                                              # an empty LLM answer is honoured, not padded


# ---- found by the one-week simulation: mandatory / deadline notices must never be missed, by the model or by the rules ----
def _notice(title, body, nid="n9"):
    from app.assistant.sources import Item
    return Item(nid, "notice", title, body, "공지", 3.0, ["u1"])


def test_deadline_notice_without_the_word_mandatory_is_still_a_todo_for_the_rules(client):
    from app.assistant.sources import User
    u = User("u1", "테스터", "executive", "경영")
    out = br.build_briefing(u, [_notice("월말 결산 일정 안내", "11월 경비 정산은 11/27(금) 17시까지 제출해 주세요. 마감 이후 건은 다음 달에 처리됩니다.")], Fake({}))
    assert [t["title"] for t in out["todos"]] == ["월말 결산 일정 안내"] and out["todos"][0]["due"] == "11/27(금) 17시까지"


def test_a_model_that_overlooks_a_mandatory_notice_is_corrected_by_code(client):
    from app.assistant.sources import User
    u = User("u1", "테스터", "executive", "경영")
    items = [_notice("정보보안 교육 필수 이수 안내", "12월 10일까지 필수 이수해야 합니다."), _notice("사옥 주차 이용 안내", "지하 2층은 등록 차량만 이용할 수 있어요.", "n8")]
    out = br.build_briefing(u, items, Fake({"summary": "s", "todos": [], "fyi": []}))          # the model returned nothing
    assert [t["title"] for t in out["todos"]] == ["정보보안 교육 필수 이수 안내"]                    # the plain announcement stays out
    assert out["degraded"] is False


def test_an_acknowledged_notice_is_not_added_back(client):
    from app.assistant.sources import Item, User
    u = User("u1", "테스터", "executive", "경영")
    it = Item("n1", "notice", "정보보안 교육 필수 이수 안내", "12월 10일까지 필수 이수", "공지", 3.0, ["u1"], done=True)
    assert br.build_briefing(u, [it], Fake({"summary": "s", "todos": [], "fyi": []}))["todos"] == []


def test_the_hide_guard_and_the_todo_rule_agree_on_what_a_deadline_notice_is(client):
    from app.assistant import mute
    for title, body in (("월말 결산 일정 안내", "11/27(금) 17시까지 제출해 주세요"), ("정보보안 교육 필수 이수 안내", "")):
        assert mute.guard_reason("notice", title, body)                 # cannot be hidden ...
    assert mute.guard_reason("notice", "사옥 주차 이용 안내", "등록 차량만 이용할 수 있어요") is None


def test_wiki_answer_gives_the_related_rule_lines_not_a_single_sentence():
    from app.assistant import guide
    h = guide._wiki_hit("택시비 한도 얼마야")
    assert h["title"] == "경비 정산 규정" and len(h["lines"]) >= 2 and any("3만원" in x for x in h["lines"])
    assert len(guide._wiki_hit("휴가 규정 알려줘")["lines"]) >= 2
