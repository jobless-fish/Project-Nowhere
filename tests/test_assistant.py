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
    assert [t["title"] for t in out["todos"]] == ["보고서 회신"] and out["dropped_ungrounded"] == 3


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
