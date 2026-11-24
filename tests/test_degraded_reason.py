"""When the model fails the briefing falls back to rules AND says why, so "degraded" is never a mystery."""
import pytest

from app.assistant import briefing
from app.assistant.sources import Item, User


class Failing:
    provider, model = "openai_compat", "m"

    def __init__(self, msg):
        self.msg = msg

    def complete(self, system, user):
        raise RuntimeError(self.msg)


@pytest.mark.parametrize("err,needle", [
    ("HTTPStatusError: Client error '429 Too Many Requests' for url 'https://x/chat/completions'", "429"),
    ("HTTPStatusError: Client error '401 Unauthorized' for url 'https://x'", "401"),
    ("HTTPStatusError: Client error '404 Not Found' for url 'https://x'", "404"),
    ("ReadTimeout: The read operation timed out", "시간이 초과"),
    ("ValueError: no JSON object in LLM output", "JSON"),
    ("HTTPStatusError: Server error '503 Service Unavailable'", "5xx"),
])
def test_reason_is_explained_in_words(client, err, needle):
    u = User("u1", "테스터", "employee", "개발")
    items = [Item("mail-1", "mail", "확인 요청", "내일까지 확인 부탁드립니다.", "김", 2.0, ["u1"])]
    b = briefing.build_briefing(u, items, Failing(err))
    assert b["degraded"] is True and needle in b["degraded_reason"]["why"]
    assert b["todos"]                                              # the rule-based fallback still produced the work list


def test_healthy_briefing_has_no_reason(client):
    from app.llm.mock import MockClient
    u = User("u1", "테스터", "employee", "개발")
    b = briefing.build_briefing(u, [Item("mail-1", "mail", "요청", "확인 부탁드립니다.", "김", 2.0, ["u1"])], MockClient())
    assert b["degraded"] is False and b["degraded_reason"] is None


def test_keys_never_reach_the_reason():
    r = briefing.explain_llm_failure("HTTPStatusError: 401 for url https://x?key=AIzaSyA1234567890abcdefghijk Bearer abc.def.ghi sk-abcdefghijklmnop12345")
    assert "AIza" not in r["raw"] and "sk-abc" not in r["raw"] and "abc.def" not in r["raw"]
