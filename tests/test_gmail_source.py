import base64
import time

import httpx
import pytest

from app.assistant.gmail_source import GmailError, GmailSource


def b64(s):
    return base64.urlsafe_b64encode(s.encode()).decode().rstrip("=")


def msg(mid, subject, frm, text, age_h=2, html=None):
    parts = [{"mimeType": "text/plain", "body": {"data": b64(text)}}] if text else [{"mimeType": "text/html", "body": {"data": b64(html)}}]
    return {"id": mid, "internalDate": str(int((time.time() - age_h * 3600) * 1000)), "snippet": "snip",
            "payload": {"mimeType": "multipart/alternative", "headers": [{"name": "From", "value": frm}, {"name": "Subject", "value": subject}], "parts": parts}}


def make(handler):
    return GmailSource(httpx.Client(transport=httpx.MockTransport(handler)), "cid", "sec", "rt")


def ok_handler(msgs):
    calls = []

    def h(req):
        calls.append((req.method, str(req.url)))
        if req.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json={"access_token": "AT", "expires_in": 3600})
        assert req.headers["authorization"] == "Bearer AT"
        if req.url.path.endswith("/messages"):
            return httpx.Response(200, json={"messages": [{"id": m["id"]} for m in msgs]})
        return httpx.Response(200, json=next(m for m in msgs if req.url.path.endswith(m["id"])))
    h.calls = calls
    return h


def test_inbox_becomes_external_untrusted_items():
    h = ok_handler([msg("a1", "견적 확인 부탁", '"김 대리" <Kim@Corp.com>', "내일까지 회신 주세요."), msg("a2", "공지", "no-reply@x.com", None, html="<style>p{}</style><p>안녕 &amp; 반가워</p>")])
    s = make(h)
    items = s.fetch(s.users()[0], 24)
    assert [i.id for i in items] == ["mail-a1", "mail-a2"]
    a, b = items
    assert a.sender == "김 대리" and a.reply_to == "ext:kim@corp.com" and a.external and a.visible_to == ["me"]
    assert b.body == "안녕 & 반가워"
    assert all(m == "GET" or "oauth2" in u for m, u in h.calls)           # nothing but reads (token refresh is the only POST)


def test_it_cannot_send_anything():
    assert not hasattr(make(ok_handler([])), "send_mail")                   # read-only: the reply flow refuses, nothing can leave the mailbox


def test_old_mail_is_left_out_and_errors_are_readable():
    s = make(ok_handler([msg("o", "오래됨", "a@b.com", "x", age_h=200)]))
    assert s.fetch(s.users()[0], 24) == []
    bad = make(lambda r: httpx.Response(400, json={"error": "invalid_grant"}))
    with pytest.raises(GmailError) as e:
        bad.fetch(bad.users()[0], 24)
    assert "rt" not in str(e.value) and "인증" in str(e.value)
    nokey = GmailSource(httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200))), "", "", "")
    with pytest.raises(GmailError):
        nokey.fetch(nokey.users()[0], 24)


def test_rate_limit_is_explained():
    def h(req):
        if req.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json={"access_token": "AT", "expires_in": 3600})
        return httpx.Response(429)
    s = make(h)
    with pytest.raises(GmailError, match="한도"):
        s.fetch(s.users()[0], 24)


def test_gmail_failure_reaches_the_ui_as_a_readable_502(client, monkeypatch):
    from app.assistant import router
    src = GmailSource(httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(400))), "c", "s", "r")
    monkeypatch.setattr(router, "get_source", lambda: src)
    r = client.get("/assistant/users")
    assert r.status_code == 200
    r = client.post("/assistant/clock-in", json={"user_id": "me"})
    assert r.status_code == 502 and "인증" in r.json()["detail"]
