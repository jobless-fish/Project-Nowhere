import httpx
import pytest

from app.llm.openai_compat import OpenAICompatClient

OK = {"choices": [{"message": {"content": '{"doc_type":"inquiry","confidence":0.9}'}}], "usage": {"prompt_tokens": 3, "completion_tokens": 4}}


def client(handler, retries=4):
    sleeps = []
    c = OpenAICompatClient("http://llm/v1", "m", "k", max_retries=retries, http=httpx.Client(transport=httpx.MockTransport(handler)),
                           sleep=sleeps.append)
    return c, sleeps


def test_retries_503_then_429_with_retry_after_then_succeeds():
    seq = iter([httpx.Response(503), httpx.Response(429, headers={"retry-after": "7"}), httpx.Response(200, json=OK)])
    c, sleeps = client(lambda req: next(seq))
    r = c.complete("s", "u")
    assert r.output_tokens == 4 and len(sleeps) == 2 and sleeps[1] == 7        # server's Retry-After wins


def test_timeout_is_retried():
    calls = []

    def handler(req):
        calls.append(1)
        if len(calls) == 1:
            raise httpx.ReadTimeout("slow", request=req)
        return httpx.Response(200, json=OK)
    c, sleeps = client(handler)
    assert c.complete("s", "u").text and len(calls) == 2 and len(sleeps) == 1


def test_client_errors_fail_fast_without_retry():
    c, sleeps = client(lambda req: httpx.Response(404, json={"error": "model gone"}))
    with pytest.raises(httpx.HTTPStatusError):
        c.complete("s", "u")
    assert sleeps == []


def test_gives_up_after_max_retries():
    n = []
    c, sleeps = client(lambda req: (n.append(1), httpx.Response(503))[1], retries=2)
    with pytest.raises(httpx.HTTPStatusError):
        c.complete("s", "u")
    assert len(n) == 3 and len(sleeps) == 2


def test_backoff_grows_and_is_capped():
    c, _ = client(lambda req: httpx.Response(200, json=OK))
    d = [c._delay(a, None) for a in (0, 1, 2, 3, 9)]
    assert d[0] < d[1] < d[2] < d[3] and d[4] <= 30.5
