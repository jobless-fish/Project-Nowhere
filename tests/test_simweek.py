"""A simulated working week: work arrives on a schedule as the shared clock is advanced, nothing is visible early, and every scripted event has an answer key."""
from datetime import datetime

import pytest
import simclock
from fastapi.testclient import TestClient

from world import simweek
from world.main import app
from world.store import store


@pytest.fixture()
def sim(monkeypatch):
    monkeypatch.setenv("NOWHERE_SIM", "1")
    simclock.reset()
    store.reset()
    c = TestClient(app)
    yield c
    simclock.reset()


def tok(c, uid):
    return {"Authorization": "Bearer " + c.post("/sso/token", json={"user_id": uid, "password": "demo1234"}).json()["access_token"]}


def test_disabled_by_default(monkeypatch):
    monkeypatch.delenv("NOWHERE_SIM", raising=False)
    c = TestClient(app)
    assert c.get("/sim/state").json() == {"enabled": False}
    assert c.post("/sim/start").status_code == 404 and c.post("/sim/advance", json={"hours": 1}).status_code == 404


def test_start_picks_the_next_business_morning_and_five_business_days(sim):
    s = sim.post("/sim/start").json()
    assert s["running"] and len(s["days"]) == 5
    assert all(datetime.fromisoformat(d).weekday() < 5 for d in s["days"])
    assert s["now"].endswith("08:30") and s["day"] == 1 and s["scenario_total"] == len(simweek.SCENARIO)
    assert datetime.fromisoformat(s["start"]) > datetime.now()                     # never starts in the past


def test_first_start_skips_weekends():
    assert simweek.first_start(datetime(2026, 11, 28, 10, 0)).strftime("%a %H:%M") == "Mon 08:30"     # Saturday -> Monday
    assert simweek.first_start(datetime(2026, 11, 27, 7, 0)).strftime("%d %H:%M") == "27 08:30"       # Friday before 08:30 -> same day
    assert simweek.first_start(datetime(2026, 11, 27, 9, 0)).strftime("%a") == "Mon"                   # Friday after 08:30 -> Monday
    assert [d.weekday() for d in simweek.business_days(datetime(2026, 11, 27).date())] == [4, 0, 1, 2, 3]


def test_nothing_is_visible_before_its_time_and_arrives_when_the_clock_passes(sim):
    sim.post("/sim/start")
    h = tok(sim, "u_dev1")
    ids = lambda: {i["key"] for i in sim.get("/tracker/issues", params={"hours": 24 * 10}, headers=h).json()["items"]}
    assert "ENG-901" not in ids()                                                   # the P1 comes on day 2 at 10:20
    sim.post("/sim/advance", json={"next_day": True})
    sim.post("/sim/advance", json={"to": "10:00"})
    assert "ENG-901" not in ids()
    sim.post("/sim/advance", json={"to": "10:30"})
    assert "ENG-901" in ids()
    p1 = next(i for i in sim.get("/tracker/issues", params={"hours": 240}, headers=h).json()["items"] if i["key"] == "ENG-901")
    assert p1["severity"] == "P1" and p1["assignee"] == "u_dev1" and p1["status"] == "열림"


def test_time_only_moves_forward_and_stops_at_the_end_of_the_week(sim):
    sim.post("/sim/start")
    assert sim.post("/sim/advance", json={"to": "08:00"}).status_code == 422          # earlier than now
    assert sim.post("/sim/advance", json={}).status_code == 422
    assert sim.post("/sim/advance", json={"hours": 99}).status_code == 422
    for _ in range(10):
        r = sim.post("/sim/advance", json={"next_day": True})
        if r.status_code != 200:
            break
    s = sim.get("/sim/state").json()
    assert s["finished"] and s["scenario_pending"] == 0 and s["scenario_released"] == s["scenario_total"]
    assert sim.post("/sim/advance", json={"hours": 1}).status_code == 422             # the week is over


def test_ledger_is_an_answer_key_for_every_scripted_event(sim):
    sim.post("/sim/start")
    items = sim.get("/sim/ledger").json()["items"]
    assert len(items) == len(simweek.SCENARIO) and all(i["action"] in ("reply", "resolve", "ack", "quarantine", "doc", "ignore") for i in items)
    assert [i["at"] for i in items] == sorted(i["at"] for i in items)
    assert any(i["action"] == "quarantine" for i in items) and any(i["action"] == "resolve" and i["sla"] <= 60 for i in items)
    assert not all(i["arrived"] for i in items)
    for _ in range(6):
        sim.post("/sim/advance", json={"next_day": True})
    assert all(i["arrived"] for i in sim.get("/sim/ledger").json()["items"])


def test_the_assistant_sees_a_new_day_and_the_new_work(sim, monkeypatch, tmp_path):
    from app import config
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "s.db"))
    from app import db
    db.init()
    import app.assistant.router as r
    from app.assistant.world_source import WorldSource
    monkeypatch.setattr(r, "get_source", lambda: WorldSource(sim))
    from app.main import app as assistant
    a = TestClient(assistant)
    sim.post("/sim/start")
    d1 = a.post("/assistant/clock-in", json={"user_id": "u_dev1"}).json()
    sim.post("/sim/advance", json={"next_day": True}); sim.post("/sim/advance", json={"to": "10:40"})
    d2 = a.post("/assistant/clock-in", json={"user_id": "u_dev1"}).json()
    assert d1["clock_in_at"][:10] != d2["clock_in_at"][:10]                             # a different business day, not a cached briefing
    assert any("결제 응답 지연" in t["title"] for t in d2["briefing"]["todos"])           # the P1 raised at 10:20 is today's first todo for its owner
    assert not any("결제 응답 지연" in t["title"] for t in d1["briefing"]["todos"])
    phish = [f for f in d2["briefing"]["flagged"]]
    sim.post("/sim/advance", json={"to": "15:30"})
    ref = a.post("/assistant/briefing/refresh", json={"user_id": "u_dev1"}).json()["briefing"]
    assert any("계정 정지" in f["title"] for f in ref["flagged"]) and not any("계정 정지" in t["title"] for t in ref["todos"])    # phishing is quarantined, never a todo


def test_deterministic(monkeypatch):
    monkeypatch.setenv("NOWHERE_SIM", "1")
    out = []
    for _ in range(2):
        simclock.reset(); store.reset()
        out.append(TestClient(app).post("/sim/start").json())
        TestClient(app).post("/sim/advance", json={"next_day": True})
        out.append(TestClient(app).get("/sim/state").json()["background_released"])
    simclock.reset()
    assert out[0]["background_pending"] == out[2]["background_pending"] and out[1] == out[3]
