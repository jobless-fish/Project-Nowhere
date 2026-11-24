import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient

from app.assistant import router as arouter
from app.assistant.world_source import WorldSource
from world import services
from world.main import app as world_app
from world.store import GOLD, store


@pytest.fixture()
def world(client, monkeypatch):
    store.reset()
    http = TestClient(world_app)
    src = WorldSource(http)
    monkeypatch.setattr(arouter, "get_source", lambda: src)
    return http, src


def hdr(http, uid, pw="demo1234"):
    r = http.post("/sso/token", json={"user_id": uid, "password": pw})
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def test_sso_and_token_required(world):
    http, _ = world
    assert http.post("/sso/token", json={"user_id": "u_kim", "password": "x"}).status_code == 401
    assert http.get("/mail/inbox").status_code == 401
    assert http.get("/mail/inbox", headers={"Authorization": "Bearer a.b"}).status_code == 401


def test_services_enforce_permissions(world):
    http, _ = world
    kim, ceo = hdr(http, "u_kim"), hdr(http, "u_ceo")
    assert http.get("/mail/messages/mc1", headers=kim).status_code == 403          # someone else's mail
    assert http.get("/mail/messages/mc1", headers=ceo).status_code == 200
    names = {c["name"] for c in http.get("/chat/channels", headers=kim).json()}
    assert "임원회의" not in names and "컴플라이언스" not in names
    assert http.get("/chat/channels/c_exec/messages", headers=kim).status_code == 403
    assert http.get("/chat/channels/c_exec/messages", headers=ceo).status_code == 200


def test_pagination_covers_everything(world):
    http, _ = world
    h = hdr(http, "u_kim")
    full = http.get("/mail/inbox", params={"hours": 72, "limit": 100}, headers=h).json()["items"]
    got, off = [], 0
    while off is not None:
        j = http.get("/mail/inbox", params={"hours": 72, "limit": 2, "offset": off}, headers=h).json()
        got += j["items"]; off = j["next_offset"]
    assert [m["id"] for m in got] == [m["id"] for m in full] and len(full) > 2


def test_assistant_via_world_for_each_featured_user(world):
    http, src = world
    for uid, gold in GOLD.items():
        b = http_clock(uid, world)
        cited = {i for t in b["todos"] for i in t["source_ids"]}
        assert set(gold) <= cited, (uid, set(gold) - cited)


def http_clock(uid, world):
    from app.main import app
    with TestClient(app) as c:
        return c.post("/assistant/clock-in", json={"user_id": uid}).json()["briefing"]


def test_world_injection_and_exec_secrets(world):
    b = http_clock("u_kim", world)
    assert [f["id"] for f in b["flagged"]] == ["mail-mk4"]
    assert not any(i.startswith("msg-cm3") or i.startswith("msg-cm4") for i in b["sources"])  # exec-only chat
    assert "mail-mc1" not in b["sources"]


def test_signed_webhook(world):
    from app.main import app
    import time
    sign = lambda b: hmac.new(b"test-webhook-secret-0123456789", b, hashlib.sha256).hexdigest()
    body = json.dumps({"user_id": "u_dev1", "ts": time.time()}).encode()
    good = sign(body)
    with TestClient(app) as c:
        assert c.post("/assistant/webhook/clock-in", content=body, headers={"X-Signature": "00"}).status_code == 401
        assert c.post("/assistant/webhook/clock-in", content=body).status_code == 401
        r = c.post("/assistant/webhook/clock-in", content=body, headers={"X-Signature": good})
        assert r.status_code == 200 and r.json()["briefing"]["user"]["id"] == "u_dev1"
        old = json.dumps({"user_id": "u_dev1", "ts": time.time() - 3600}).encode()      # correctly signed but an hour old: a replay
        assert c.post("/assistant/webhook/clock-in", content=old, headers={"X-Signature": sign(old)}).status_code == 401
        nots = json.dumps({"user_id": "u_dev1"}).encode()                                # correctly signed, no timestamp
        assert c.post("/assistant/webhook/clock-in", content=nots, headers={"X-Signature": sign(nots)}).status_code == 400


def test_hr_clock_in_notifies_assistant(world, monkeypatch):
    http, _ = world
    seen = []
    monkeypatch.setattr(services, "notify_assistant", lambda uid: seen.append(uid))
    assert http.post("/hr/clock-in", headers=hdr(http, "u_kim")).status_code == 200
    assert seen == ["u_kim"]


def test_webhook_fails_closed_without_a_real_secret(world, monkeypatch):
    import time
    from app.main import app
    body = json.dumps({"user_id": "u_dev1", "ts": time.time()}).encode()
    for value in (None, "", "short", "dev-webhook"):          # missing, empty, too short, the old built-in default
        if value is None:
            monkeypatch.delenv("ASSISTANT_WEBHOOK_SECRET", raising=False)
        else:
            monkeypatch.setenv("ASSISTANT_WEBHOOK_SECRET", value)
        sig = hmac.new((value or "").encode(), body, hashlib.sha256).hexdigest()          # even a correctly computed signature is refused
        with TestClient(app) as c:
            r = c.post("/assistant/webhook/clock-in", content=body, headers={"X-Signature": sig})
            assert r.status_code == 503, value
            assert c.get("/health").json()["webhook_configured"] is False


def test_world_does_not_sign_with_a_guessable_key(monkeypatch, caplog):
    sent = []
    monkeypatch.setenv("ASSISTANT_URL", "http://assistant.invalid/api")
    monkeypatch.setenv("ASSISTANT_WEBHOOK_SECRET", "dev-webhook")
    monkeypatch.setattr(services.httpx, "post", lambda *a, **k: sent.append(a))
    services.notify_assistant("u_kim")
    assert sent == []
    monkeypatch.setenv("ASSISTANT_WEBHOOK_SECRET", "a-long-enough-secret-123")
    services.notify_assistant("u_kim")
    assert len(sent) == 1


def test_combined_server_generates_a_random_secret_per_process():
    import os, subprocess, sys
    code = "import os, server; print(os.environ['ASSISTANT_WEBHOOK_SECRET'])"
    a, b = (subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=".", env={**os.environ, "DOCFLOW_DB": ":memory:", "ASSISTANT_WEBHOOK_SECRET": ""}).stdout.strip() for _ in range(2))
    assert len(a) >= 32 and a != b
