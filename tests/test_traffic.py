import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.assistant.guard import is_suspicious
from world import traffic
from world.main import app as world_app
from world.people import FEATURED
from world.store import store

G = traffic.generate()
W = traffic.generate_world()
ROOT = Path(__file__).parent.parent


class Obj:  # minimal Item-like for the injection guard
    def __init__(self, m):
        self.title, self.body = m["subject"], m["body"]


def test_scale_and_determinism():
    assert traffic.generate() is G and len(G["mails"]) > 2000 and len(W["messages"]) > 1000 and len(W["issues"]) > 150 and len(W["channels"]) > 40
    assert 0.15 < sum(m["action"] for m in G["mails"]) / len(G["mails"]) < 0.35          # most mail is informational, like real life
    assert sum(m["hard"] for m in G["mails"]) > 100 and len(G["phish"]) == 40


def test_activity_follows_working_hours():
    h = Counter(m["slot"]["hour"] for m in G["mails"])
    assert sum(v for k, v in h.items() if 9 <= k <= 18) / sum(h.values()) > 0.85


def test_demo_accounts_only_get_light_noise():
    recv = Counter(r for m in G["mails"] for r in m["to"] if r in FEATURED)
    assert set(recv.values()) == {6}
    assert not any(f in G["gold"] for f in FEATURED) and not any(f in W["gold_issues"] for f in FEATURED)
    assert all(not m["action"] for m in G["mails"] if set(m["to"]) & set(FEATURED))


def test_every_gold_label_points_at_something_the_person_really_gets():
    mails = {m["id"]: m for m in G["mails"]}
    issues = {i["id"]: i for i in W["issues"]}
    for uid, ids in traffic.gold_all().items():
        for gid in ids:
            kind, _, rid = gid.partition("-")
            if kind == "mail":
                assert uid in mails[rid]["to"] and mails[rid]["action"]
            elif kind == "iss":
                assert issues[rid]["assignee"] == uid and issues[rid]["severity"] in ("P1", "P2")
            else:
                assert gid == "ntc-n1"


def test_injection_guard_flags_exactly_the_phishing_mails():
    flagged = {f"mail-{m['id']}" for m in G["mails"] if is_suspicious(Obj(m))}
    assert flagged == set(G["phish"])                      # no false alarms on ordinary mail, no phishing missed
    featured_phish = [m for m in G["mails"] if f"mail-{m['id']}" in G["phish"] and set(m["to"]) & set(FEATURED)]
    assert featured_phish == []


def test_channel_authors_are_members_and_nothing_is_dated_in_the_future():
    store.reset()
    for m in store.chat:
        assert m["author"] in store.members(m["channel"]), m["id"]
    now = store.t0.isoformat(timespec="seconds")
    assert all(m["ts"] <= now for m in store.mails) and all(c["ts"] <= now for c in store.chat)
    assert min(m["ts"] for m in store.mails) >= (store.t0 - timedelta(days=3, hours=1)).isoformat(timespec="seconds")


@pytest.fixture()
def http():
    store.reset()
    c = TestClient(world_app)
    def tok(uid):
        return {"Authorization": "Bearer " + c.post("/sso/token", json={"user_id": uid, "password": "demo1234"}).json()["access_token"]}
    return c, tok


def test_big_inbox_paginates_completely_and_unit_channels_are_private_to_members(http):
    c, tok = http
    heavy = max(Counter(r for m in G["mails"] for r in m["to"] if r not in FEATURED).items(), key=lambda kv: kv[1])[0]
    h = tok(heavy)
    got, off = [], 0
    while off is not None:
        j = c.get("/mail/inbox", params={"hours": 72, "limit": 20, "offset": off}, headers=h).json()
        got += j["items"]; off = j["next_offset"]
    assert len(got) > 60 and len({m["id"] for m in got}) == len(got)
    unit_ch = next(cid for cid, (_n, _p, sel) in store.channels.items() if sel == "unit:백엔드1팀")
    assert c.get(f"/chat/channels/{unit_ch}/messages", headers=tok("u_kim")).status_code == 403          # sales rep, not in that team
    assert c.get(f"/chat/channels/{unit_ch}/messages", headers=tok("u_dev1")).status_code == 200         # backend1 member


def test_bulk_eval_runs_and_reports_no_phishing_leaks():
    r = subprocess.run([sys.executable, "-m", "eval.bulk_eval", "--n", "12", "--json"], cwd=ROOT, capture_output=True, text=True,
                       env={**__import__("os").environ, "LLM_PROVIDER": "mock", "PYTHONPATH": str(ROOT)})
    assert r.returncode == 0, r.stderr[-400:]
    out = json.loads(r.stdout)
    assert out["employees"] == 12 and out["phishing_leaks"] == 0 and out["recall"] > 0.5 and "by_source" in out
