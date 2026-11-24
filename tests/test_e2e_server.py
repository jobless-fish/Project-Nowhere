"""Real end-to-end: start the single-process server and drive it over HTTP only (no TestClient, no mocks of our own code).
Catches what unit tests cannot: loopback calls, the signed clock-in webhook, event-loop blocking, mount prefixes."""
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).parent.parent


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def srv(tmp_path_factory):
    port = free_port()
    env = {**os.environ, "PORT": str(port), "DOCFLOW_DB": str(tmp_path_factory.mktemp("e2e") / "e2e.db"), "LLM_PROVIDER": "mock",
           "DEFAULT_MODE": "auto", "PYTHONPATH": str(ROOT)}
    for k in ("SOURCE", "WORLD_URL", "ASSISTANT_URL", "DOCFLOW_API_KEY", "ANTHROPIC_API_KEY"):
        env.pop(k, None)
    p = subprocess.Popen([sys.executable, "-m", "uvicorn", "server:combined", "--port", str(port), "--log-level", "warning"],
                         cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{port}"
    for _ in range(60):
        try:
            if httpx.get(base + "/api/health", timeout=1).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.25)
    else:
        p.kill()
        pytest.fail("server did not start: " + p.stdout.read().decode()[-500:])
    yield httpx.Client(base_url=base, timeout=20)
    p.terminate()
    p.wait(timeout=10)


def login(c, uid):
    r = c.post("/world/sso/token", json={"user_id": uid, "password": "demo1234"})
    assert r.status_code == 200
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def test_clock_in_webhook_builds_the_briefing(srv):
    h = login(srv, "u_kim")
    assert srv.post("/world/hr/clock-in", headers=h).status_code == 200      # HR system -> signed webhook -> assistant
    for _ in range(40):                                                       # asynchronous: poll like the UI does
        r = srv.get("/api/assistant/briefing", params={"user_id": "u_kim"})
        if r.status_code == 200:
            break
        time.sleep(0.25)
    assert r.status_code == 200, "webhook never produced a briefing (event loop blocked?)"
    b = r.json()
    cited = {i for t in b["todos"] for i in t["source_ids"]}
    assert {"mail-mk1", "iss-i1"} <= cited and [f["id"] for f in b["flagged"]] == ["mail-mk4"]


def test_reply_is_sent_as_the_user_and_arrives(srv):
    b = srv.get("/api/assistant/briefing", params={"user_id": "u_kim"}).json()
    key = next(t["key"] for t in b["todos"] if "mail-mk1" in t["source_ids"])
    a = srv.post("/api/assistant/actions/propose", json={"user_id": "u_kim", "todo_key": key}).json()
    assert a["status"] == "proposed"
    sent = srv.post(f"/api/assistant/actions/{a['id']}/decision", json={"user_id": "u_kim", "approve": True, "body": "확인했습니다. 오늘 16시까지 보내겠습니다."})
    assert sent.json()["status"] == "sent"
    inbox = srv.get("/world/mail/inbox", params={"hours": 24}, headers=login(srv, "u_slead")).json()["items"]
    reply = next(m for m in inbox if m["subject"].startswith("Re:"))
    assert reply["from"]["id"] == "u_kim" and "16시" in reply["body"]


def test_permissions_hold_over_the_wire(srv):
    kim = login(srv, "u_kim")
    assert srv.get("/world/chat/channels/c_exec/messages", headers=kim).status_code == 403
    assert srv.get("/world/mail/messages/mc1", headers=kim).status_code == 403
    assert srv.get("/world/mail/inbox").status_code == 401


def test_feedback_flows_into_eval_cases(srv):
    b = srv.get("/api/assistant/briefing", params={"user_id": "u_kim"}).json()
    key = next(t["key"] for t in b["todos"] if "iss-i1" in t["source_ids"])
    assert srv.post("/api/assistant/feedback", json={"user_id": "u_kim", "todo_key": key, "value": "done"}).status_code == 200
    h = srv.post("/api/assistant/eval/harvest").json()
    assert h["total"] >= 2 and h["by"].get("todo:positive", 0) >= 1 and h["by"].get("reply:edited", 0) >= 1


def test_web_app_is_served_when_built(srv):
    r = srv.get("/")
    if not (ROOT / "web" / "dist").exists():
        pytest.skip("web/dist not built")
    assert r.status_code == 200 and "<div id=\"root\">" in r.text


def test_demo_starts_with_an_empty_portable_database(tmp_path):
    """No /tmp assumption (Windows) and no leftovers from a previous run; a user-supplied DOCFLOW_DB is never deleted."""
    keep = tmp_path / "keep.db"
    keep.write_text("precious")
    env = {k: v for k, v in os.environ.items() if k != "DOCFLOW_DB"} | {"PYTHONPATH": str(ROOT), "TMPDIR": str(tmp_path), "TEMP": str(tmp_path), "TMP": str(tmp_path)}
    (tmp_path / "nowhere-demo.db").write_text("stale data from an earlier run")
    out = subprocess.run([sys.executable, "-c", "import server, os; print(os.environ['DOCFLOW_DB'])"], cwd=ROOT, env=env, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr[-300:]
    db = Path(out.stdout.strip().splitlines()[-1])
    assert db.parent == tmp_path and db.name == "nowhere-demo.db" and not db.exists()          # portable temp dir, stale file removed
    env2 = {**env, "DOCFLOW_DB": str(keep)}
    subprocess.run([sys.executable, "-c", "import server"], cwd=ROOT, env=env2, capture_output=True, text=True)
    assert keep.read_text() == "precious"                                                      # explicit path is never touched
