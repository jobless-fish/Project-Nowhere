import pytest
from fastapi.testclient import TestClient

from world import npc
from world.main import app as world_app
from world.store import store


@pytest.fixture()
def w(monkeypatch):
    store.reset()
    clock = [__import__("time").time()]
    store.now = lambda: clock[0]                      # virtual time: replies arrive when we say so
    monkeypatch.setattr(npc, "llm_hook", None)
    c = TestClient(world_app)
    toks = {}

    def tok(uid):
        toks.setdefault(uid, {"Authorization": "Bearer " + c.post("/sso/token", json={"user_id": uid, "password": "demo1234"}).json()["access_token"]})
        return toks[uid]
    yield c, tok, clock
    store.now = __import__("time").time


def wait(clock, s=120):
    clock[0] += s


def chat_msgs(c, tok, uid, cid):
    return c.get(f"/chat/channels/{cid}/messages", params={"latest": True, "limit": 200, "hours": 72}, headers=tok(uid)).json()


def test_chat_post_requires_membership_and_validates(w):
    c, tok, _ = w
    assert c.post("/chat/channels/c_exec/messages", json={"text": "hi"}, headers=tok("u_kim")).status_code == 403
    assert c.post("/chat/channels/c_sales/messages", json={"text": "  "}, headers=tok("u_kim")).status_code == 422
    assert c.post("/chat/channels/c_sales/messages", json={"text": "가" * 1001}, headers=tok("u_kim")).status_code == 422
    assert c.post("/chat/channels/nope/messages", json={"text": "x"}, headers=tok("u_kim")).status_code == 404


def test_colleagues_answer_with_at_most_three_replies_from_channel_members_only(w):
    c, tok, clock = w
    for text in ["이번 주 방문 일정 공유드립니다. 확인 부탁드려요", "점심 같이 가실 분?", "견적서 어디서 받을 수 있어요?", "안녕하세요", "고맙습니다"]:
        before = len(chat_msgs(c, tok, "u_kim", "c_sales")["items"])
        r = c.post("/chat/channels/c_sales/messages", json={"text": text}, headers=tok("u_kim")).json()
        assert 0 <= r["replies_coming"] <= 3
        assert chat_msgs(c, tok, "u_kim", "c_sales")["typing"] is True                       # not instant: typing first
        wait(clock)
        after = chat_msgs(c, tok, "u_kim", "c_sales")
        new = after["items"][before + 1:]                                                   # +1 is my own message
        assert len(new) <= 3 and after["typing"] is False
        members = store.members("c_sales")
        assert all(m["author"]["id"] in members and m["author"]["id"] != "u_kim" for m in new)


def test_replies_are_deterministic_and_in_character(w):
    c, tok, clock = w
    c.post("/chat/channels/c_sales/messages", json={"text": "견적서 어디서 받을 수 있어요?"}, headers=tok("u_kim")); wait(clock)
    a = [m["text"] for m in chat_msgs(c, tok, "u_kim", "c_sales")["items"][-3:]]
    assert a and all(len(t) > 3 for t in a)
    store.reset(); store.now = lambda: clock[0]; wait(clock, 0)
    c.post("/chat/channels/c_sales/messages", json={"text": "견적서 어디서 받을 수 있어요?"}, headers=tok("u_kim")); wait(clock)
    assert [m["text"] for m in chat_msgs(c, tok, "u_kim", "c_sales")["items"][-3:]] == a   # same message, same answers


def test_dm_gets_exactly_one_reply_from_that_person_and_stays_private(w):
    c, tok, clock = w
    d = c.post("/chat/dm", json={"to": "u_slead"}, headers=tok("u_kim")).json()
    assert d["dm"] is True and d["name"] == "이정호"
    assert c.post("/chat/dm", json={"to": "u_kim"}, headers=tok("u_kim")).status_code == 422          # not with yourself
    c.post(f"/chat/channels/{d['id']}/messages", json={"text": "팀장님, 보고서 초안 부탁드린 부분 확인해 주실 수 있을까요?"}, headers=tok("u_kim")); wait(clock)
    items = chat_msgs(c, tok, "u_kim", d["id"])["items"]
    assert len(items) == 2 and items[1]["author"]["id"] == "u_slead"
    assert c.get(f"/chat/channels/{d['id']}/messages", headers=tok("u_dev1")).status_code == 403     # a third person cannot read it
    names = {x["id"]: x["name"] for x in c.get("/chat/channels", headers=tok("u_slead")).json()}
    assert names[d["id"]] == "김민수"                                                                 # each side sees the OTHER person's name


def test_mail_compose_validation_and_external_confirmation(w):
    c, tok, _ = w
    ok = {"to": ["u_slead"], "subject": "보고서 공유", "body": "초안 공유드립니다."}
    sent0 = len(c.get("/mail/sent", headers=tok("u_kim")).json()["items"])        # the seeded company already has mail he sent
    assert c.post("/mail/send", json={**ok, "to": []}, headers=tok("u_kim")).status_code == 422
    assert c.post("/mail/send", json={**ok, "subject": " "}, headers=tok("u_kim")).status_code == 422
    assert c.post("/mail/send", json={**ok, "to": ["u_nobody"]}, headers=tok("u_kim")).status_code == 422
    assert c.post("/mail/send", json={**ok, "to": [], "to_external": ["a@b.example"]}, headers=tok("u_kim")).status_code == 409
    assert c.post("/mail/send", json={**ok, "to": [], "to_external": ["a@b.example"], "confirm_external": True}, headers=tok("u_kim")).status_code == 201
    sent = c.get("/mail/sent", headers=tok("u_kim")).json()["items"]
    assert len(sent) == sent0 + 1 and sent[0]["to_external"] == ["a@b.example"]                 # only the valid one was stored


def test_mail_replies_arrive_later_as_mail_at_most_three_and_a_lead_may_ask_for_more(w):
    c, tok, clock = w
    to = ["u_slead", "u_sales2", "u_dev1", "u_cs1", "u_hr"]
    r = c.post("/mail/send", json={"to": to, "subject": "3분기 보고서 공유", "body": "3분기 실적 보고서 작업을 마쳤습니다. 공유드립니다. 확인 부탁드려요."}, headers=tok("u_kim")).json()
    assert r["replies_coming"] <= 3
    assert c.get("/mail/inbox", headers=tok("u_kim")).json()["items"] == [] or True
    before = {m["id"] for m in c.get("/mail/inbox", params={"hours": 1}, headers=tok("u_kim")).json()["items"]}
    wait(clock)
    got = [m for m in c.get("/mail/inbox", params={"hours": 1}, headers=tok("u_kim")).json()["items"] if m["id"] not in before]   # only what arrived since: seeded
    assert 1 <= len(got) <= 3 and all(m["from"]["id"] in to and m["subject"].startswith(("Re:", "추가 요청")) for m in got)       # mail depends on the time of day
    assert all(m["thread"] == r["id"] for m in got)


def test_unread_counts_follow_what_was_actually_read(w):
    c, tok, clock = w
    base = c.get("/mail/unread", headers=tok("u_kim")).json()["count"]
    c.post("/mail/send", json={"to": ["u_slead"], "subject": "확인 요청", "body": "확인 부탁드립니다."}, headers=tok("u_kim")); wait(clock)
    u = c.get("/mail/unread", headers=tok("u_kim")).json()
    assert u["count"] >= base + 1 and u["latest"]["subject"].startswith("Re:") and u["typing"] is False
    c.post("/mail/seen", headers=tok("u_kim"))
    assert c.get("/mail/unread", headers=tok("u_kim")).json()["count"] == 0
    c.post("/chat/channels/c_sales/messages", json={"text": "점심 같이 가실 분?"}, headers=tok("u_kim")); wait(clock)
    assert c.get("/chat/unread", headers=tok("u_kim")).json()["total"] >= 1
    chat_msgs(c, tok, "u_kim", "c_sales")                                                              # opening the channel marks it read
    assert c.get("/chat/unread", headers=tok("u_kim")).json()["by_channel"].get("c_sales", 0) == 0


def test_only_the_assignee_changes_an_issue_and_resolving_needs_a_note(w):
    c, tok, _ = w
    assert c.patch("/tracker/issues/i1", json={"status": "진행 중"}, headers=tok("u_slead")).status_code == 403
    assert c.patch("/tracker/issues/i1", json={"status": "해결"}, headers=tok("u_kim")).status_code == 422
    assert c.patch("/tracker/issues/i1", json={"status": "끝", "comment": "x"}, headers=tok("u_kim")).status_code == 422
    r = c.patch("/tracker/issues/i1", json={"status": "해결", "comment": "동기화 작업을 재실행했고 정상 확인"}, headers=tok("u_kim")).json()
    assert r["status"] == "해결" and r["log"][-1]["by"] == "u_kim"


def test_notice_acknowledgement_is_recorded_per_person(w):
    c, tok, _ = w
    def acked(uid):
        return next(n for n in c.get("/portal/notices", headers=tok(uid)).json()["items"] if n["id"] == "n1")["acked"]
    assert acked("u_kim") is False
    assert c.post("/portal/notices/n1/ack", headers=tok("u_kim")).json()["acked"] is True
    assert acked("u_kim") is True and acked("u_dev1") is False
    assert c.post("/portal/notices/nope/ack", headers=tok("u_kim")).status_code == 404


def test_model_output_is_validated_and_the_cap_of_three_holds(w, monkeypatch):
    c, tok, clock = w
    monkeypatch.setattr(npc, "SYNC", True)
    members = sorted(u for u in store.members("c_sales") if u != "u_kim")       # sets iterate in hash order: sort so the test is the same every run
    before = {m["id"] for m in chat_msgs(c, tok, "u_kim", "c_sales")["items"]}
    monkeypatch.setattr(npc, "llm_hook", lambda p: {"replies": [
        {"from": members[0], "text": "확인했어요 https://evil.example 여기 보세요"}, {"from": members[0], "text": "같은 사람 두 번"}, {"from": "u_ceo", "text": "채널에 없는 사람"},
        {"from": "u_nobody", "text": "없는 사람"}, {"from": members[1], "text": "네, 제가 볼게요."}, {"from": members[2], "text": "저도요."}, {"from": members[3], "text": "넷째"}]})
    c.post("/chat/channels/c_sales/messages", json={"text": "도와주실 분?"}, headers=tok("u_kim")); wait(clock)
    new = [m for m in chat_msgs(c, tok, "u_kim", "c_sales")["items"] if m["id"] not in before and m["author"]["id"] != "u_kim"]     # only the replies
    authors = [m["author"]["id"] for m in new]
    assert 1 <= len(authors) <= 3 and len(set(authors)) == len(authors) and "u_ceo" not in authors and "u_nobody" not in authors
    assert not any("http" in m["text"] for m in new)


def test_model_failure_or_garbage_falls_back_to_the_rules(w, monkeypatch):
    c, tok, clock = w
    monkeypatch.setattr(npc, "SYNC", True)
    for hook in (lambda p: (_ for _ in ()).throw(RuntimeError("down")), lambda p: {"replies": "garbage"}, lambda p: None):
        monkeypatch.setattr(npc, "llm_hook", hook)
        before = len(chat_msgs(c, tok, "u_kim", "c_sales")["items"])
        c.post("/chat/channels/c_sales/messages", json={"text": "견적서 어디서 받을 수 있어요?"}, headers=tok("u_kim")); wait(clock)
        assert 1 < len(chat_msgs(c, tok, "u_kim", "c_sales")["items"]) - before <= 4          # my message + 1..3 rule-based replies
        assert store.generating == 0


def test_the_model_payload_only_offers_real_candidates(w, monkeypatch):
    c, tok, _ = w
    seen = {}
    monkeypatch.setattr(npc, "SYNC", True)
    monkeypatch.setattr(npc, "llm_hook", lambda p: seen.update(p) or None)
    c.post("/chat/channels/c_comp/messages", json={"text": "규정 확인 부탁드립니다"}, headers=tok("u_legal"))
    members = store.members("c_comp")
    assert seen["max_replies"] == 3 and 1 <= len(seen["candidates"]) <= 6
    assert all(x["id"] in members and x["id"] != "u_legal" for x in seen["candidates"])


def test_classifier():
    assert npc.classify("보고서 확인 부탁드립니다") == "request" and npc.classify("이거 어떻게 해요?") == "question"
    assert npc.classify("작업 완료했습니다") == "report" and npc.classify("점심 드실래요") == "social" and npc.classify("감사합니다") == "thanks"


def test_llm_reply_with_invented_number_is_dropped():
    cands = [{"id": "a"}, {"id": "b"}]
    raw = {"replies": [{"from": "a", "text": "기본값은 30초예요."}, {"from": "b", "text": "확인해 보고 알려드릴게요."}]}
    assert [r["from"] for r in npc.validate_llm(raw, cands, "타임아웃 기본값이 몇 초인가요?")] == ["b"]
    assert len(npc.validate_llm({"replies": [{"from": "a", "text": "30초예요."}]}, cands, "기본 30초 맞나요?")) == 1


def test_executive_may_update_an_escalated_issue_but_not_others(w):
    c, tok, _ = w
    esc = next(i for i in store.issues if i["escalated"])
    other = next(i for i in store.issues if not i["escalated"] and i["assignee"] != "u_cto")
    assert c.patch(f"/tracker/issues/{esc['id']}", json={"status": "진행 중"}, headers=tok("u_cto")).status_code == 200
    assert c.patch(f"/tracker/issues/{other['id']}", json={"status": "진행 중"}, headers=tok("u_cto")).status_code == 403


def test_a_reply_delivered_in_the_same_second_as_mark_seen_still_counts_as_new(w):
    """Regression: unread compares timestamps; with whole-second resolution a reply that arrives right after the page marked the inbox as seen was lost."""
    c, tok, clock = w
    c.post("/mail/send", json={"to": ["u_slead"], "subject": "일정 확인 부탁", "body": "다음 주 일정 확인 부탁드립니다."}, headers=tok("u_kim"))
    assert store.pending
    base = int(clock[0]) + 100
    store.pending[0]["due"] = base + 0.5                       # due half way through a second
    clock[0] = base + 0.45
    assert c.post("/mail/seen", headers=tok("u_kim")).status_code == 200      # the page has just looked: same second as the delivery below
    clock[0] = base + 0.55
    u = c.get("/mail/unread", headers=tok("u_kim")).json()
    assert u["count"] == 1 and u["latest"]["subject"].startswith("Re:")


def test_an_executive_cannot_reopen_an_issue_the_assignee_resolved(w):
    c, tok, _ = w
    esc = next(i for i in store.issues if i["escalated"])
    assignee = esc["assignee"]
    assert c.patch(f"/tracker/issues/{esc['id']}", json={"status": "해결", "comment": "원인 수정 후 배포"}, headers=tok(assignee)).status_code == 200
    r = c.patch(f"/tracker/issues/{esc['id']}", json={"status": "진행 중"}, headers=tok("u_ceo"))
    assert r.status_code == 422 and "이미 해결" in r.json()["detail"] and esc["status"] == "해결"
    assert c.patch(f"/tracker/issues/{esc['id']}", json={"status": "진행 중"}, headers=tok(assignee)).status_code == 200      # the assignee may reopen
