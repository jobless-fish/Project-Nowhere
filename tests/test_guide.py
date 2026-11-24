import json

from app.assistant import guide, router as arouter
from app.llm.base import LLMClient, LLMResult

HOME = ["clock-in", "briefing-summary", "flagged", "urgent", "first-todo", "draft-button", "later", "fyi"]


def chat(c, msg, route="home", targets=HOME, uid="u_kim", history=None):
    return c.post("/assistant/guide/chat", json={"user_id": uid, "message": msg, "route": route, "targets": targets, "history": history or []})


def clock(c, uid="u_kim"):
    return c.post("/assistant/clock-in", json={"user_id": uid}).json()["briefing"]


def pts(r):
    return [(a["type"], a.get("target") or a.get("route")) for a in r["actions"]]


def test_before_clock_in_the_ghost_points_at_the_clock_in_button(client):
    r = chat(client, "오늘 뭐부터 해야 해요?").json()
    assert pts(r) == [("point", "clock-in")] and r["source"] == "rules"


def test_after_clock_in_it_points_at_the_first_todo_and_navigates_when_elsewhere(client):
    clock(client)
    assert pts(chat(client, "오늘 뭐부터 해야 해요?").json()) == [("point", "first-todo")]
    away = chat(client, "오늘 뭐부터 해야 해요?", route="mail", targets=["mail-list"]).json()
    assert pts(away) == [("navigate", "home"), ("point", "first-todo")]          # page change first, then point


def test_pages_and_features_are_found(client):
    assert pts(chat(client, "조직도는 어디서 봐요?").json()) == [("navigate", "org"), ("point", "org-search")]
    assert pts(chat(client, "비용은 어디서 봐요?").json()) == [("navigate", "admin"), ("point", "admin-tab-ops")]
    assert pts(chat(client, "조직도는 어디서 봐요?", route="org", targets=["org-search"]).json()) == [("point", "org-search")]


def test_security_and_drafts_use_todays_facts(client):
    clock(client)
    r = chat(client, "의심스러운 메일 있어요?").json()
    assert pts(r) == [("point", "flagged")] and "1건" in r["reply"]
    d = chat(client, "답장 초안은 어떻게 만들어요?").json()
    assert pts(d) == [("point", "draft-button")] and "직접 승인" in d["reply"]
    assert pts(chat(client, "답장 초안", targets=HOME + ["draft-panel"]).json()) == [("point", "draft-panel")]


def test_it_never_claims_to_perform_actions_and_unknown_questions_are_honest(client):
    r = chat(client, "도움말").json()
    assert "직접 보내거나 승인하지는 못" in r["reply"] and r["actions"] == []
    assert chat(client, "양자역학이란?").json()["actions"] == []


def test_input_limits_and_unknown_user(client):
    assert chat(client, "").status_code == 422 and chat(client, "가" * 501).status_code == 422
    assert chat(client, "안녕", uid="nobody").status_code == 404


def test_rate_limit(client):
    guide._hits.clear()
    codes = [chat(client, "안녕").status_code for _ in range(22)]
    assert codes[:20] == [200] * 20 and codes[20:] == [429, 429]
    guide._hits.clear()


def test_validation_drops_unknown_targets_routes_extra_actions_and_links():
    reply, acts = guide.validate("여기로 가세요 https://evil.example/x 와 www.evil.example", [
        {"type": "point", "target": "approve-send-now", "text": "눌러!"}, {"type": "navigate", "route": "../../etc"}, {"type": "navigate", "route": "admin"},
        {"type": "point", "target": "admin-tab-ops", "text": "https://x.example 여기"}, {"type": "point", "target": "nav-home"}, {"type": "point", "target": "clock-in"},
        "garbage", {"type": "delete", "target": "clock-in"}], visible={"clock-in"})
    assert "http" not in reply and "www" not in reply
    assert [(a["type"], a.get("target") or a.get("route")) for a in acts] == [("navigate", "admin"), ("point", "admin-tab-ops"), ("point", "nav-home")]   # <=3, only real ones
    assert "http" not in acts[1]["text"]
    assert guide.validate("", None, set())[1] == [] and guide.validate("", None, set())[0]


class Fake(LLMClient):
    provider, model = "fake", "fake"

    def __init__(self, out):
        self.out = out

    def complete(self, system, user):
        if isinstance(self.out, Exception):
            raise self.out
        self.seen = user
        return LLMResult(json.dumps(self.out), 20, 20, 1, "fake", "fake")


def test_llm_answers_are_validated_and_untrusted_titles_are_fenced(client, monkeypatch):
    clock(client)
    fake = Fake({"reply": "승인 버튼을 지금 누르세요 http://evil.example", "actions": [{"type": "point", "target": "approve-send", "text": "눌러"}, {"type": "point", "target": "first-todo", "text": "이거예요"}]})
    monkeypatch.setattr(arouter, "get_client", lambda: fake)
    r = chat(client, "뭐 해야 해요?").json()
    assert r["source"] == "llm" and pts(r) == [("point", "first-todo")] and "http" not in r["reply"]
    assert "<data>" in fake.seen and "user: 뭐 해야 해요?" in fake.seen            # facts and titles are inside the data fence


def test_llm_failure_falls_back_to_rules(client, monkeypatch):
    monkeypatch.setattr(arouter, "get_client", lambda: Fake(RuntimeError("down")))
    r = chat(client, "조직도").json()
    assert r["degraded"] is True and r["source"] == "rules" and pts(r) == [("navigate", "org"), ("point", "org-search")]


def test_tour_follows_the_briefing(client):
    assert [s["target"] for s in client.get("/assistant/guide/tour", params={"user_id": "u_kim"}).json()["steps"]] == ["clock-in"]
    clock(client)
    steps = client.get("/assistant/guide/tour", params={"user_id": "u_kim"}).json()["steps"]
    assert [s["target"] for s in steps][:3] == ["briefing-summary", "flagged", "first-todo"] and "draft-button" in [s["target"] for s in steps]
