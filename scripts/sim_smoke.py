"""Smoke test of the one-week simulation: run all five days with a simple, rule-driven operator and verify the machinery (not the AI's judgement).

    python scripts/sim_smoke.py http://127.0.0.1:8890        (server started with scripts/sim_server.py)

Checks: the week starts on a business morning, time only moves forward, every scripted event arrives, the operator never hits an unexpected error
(todos that nobody can act on, reopening a resolved issue, ...), briefings are rebuilt each day, and the answer key can be read at the end.
Exit code 1 on any failure. The real, judgement-based run is docs/WEEK_SIMULATION_PROMPT.md.
"""
import collections
import sys

import httpx

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8890").rstrip("/")
c = httpx.Client(base_url=BASE, timeout=60)
problems, bad = [], []
ROLES = ["u_dev1", "u_cfo", "u_slead"]


def tok(u):
    return {"Authorization": "Bearer " + c.post("/world/sso/token", json={"user_id": u, "password": "demo1234"}).json()["access_token"]}


def call(method, url, expect_ok=True, **kw):
    r = c.request(method, url, **kw)
    if expect_ok and r.status_code >= 400:
        bad.append((method, url.split("?")[0][:50], r.status_code, r.text[:80]))
    return r


def check(cond, msg):
    if not cond:
        problems.append(msg)


def work(u, limit=6):
    call("POST", "/api/assistant/clock-in", json={"user_id": u})
    b = call("POST", "/api/assistant/briefing/refresh", json={"user_id": u}).json().get("briefing", {"todos": []})
    n = 0
    for t in b["todos"]:
        if n >= limit or (t.get("flow") or {}).get("status") == "done":
            continue
        key, kind = t["key"], t["kind"]
        if kind == "notice":
            call("POST", f"/api/assistant/todos/{key}/complete", json={"user_id": u})
        elif kind == "issue":
            call("POST", f"/api/assistant/todos/{key}/start", json={"user_id": u})
            call("POST", f"/api/assistant/todos/{key}/complete", json={"user_id": u, "note": "원인 확인 후 조치했습니다", "how": "done"})
        elif kind == "mail":
            r = call("POST", "/api/assistant/actions/propose", json={"user_id": u, "todo_key": key}, expect_ok=False)
            if r.status_code in (200, 201):
                a = r.json()
                call("POST", f"/api/assistant/actions/{a['id']}/decision", json={"user_id": u, "approve": not a.get("external"), "confirm_external": False})
        n += 1
    return b


s = call("POST", "/world/sim/start").json()
check(s.get("running") and len(s.get("days", [])) == 5, f"start failed: {s}")
check(s["now"].endswith("08:30"), "the week must start at 08:30")
last = s["now"]
briefs_per_day = {}
for day in range(5):
    for hh in (None, "11:00", "14:00", "17:30"):
        if hh:
            r = call("POST", "/world/sim/advance", json={"to": hh})
            check(r.status_code == 200 and r.json()["now"] > last, f"time did not move forward at {hh}")
            last = r.json()["now"]
        for u in ROLES:
            b = work(u)
            if hh is None and u == "u_dev1":
                briefs_per_day[day] = {t["title"] for t in b["todos"]}
    st = c.get("/world/sim/state").json()
    check(st["day"] == day + 1, f"day counter {st['day']} != {day + 1}")
    r = call("POST", "/world/sim/advance", json={"next_day": True} if day < 4 else {"to": "18:30"})
    last = r.json()["now"]
st = c.get("/world/sim/state").json()
check(st["finished"] and st["scenario_pending"] == 0, f"week did not finish cleanly: {st}")
check(call("POST", "/world/sim/advance", expect_ok=False, json={"hours": 1}).status_code == 422, "advancing after the end must be refused")
led = c.get("/world/sim/ledger").json()["items"]
check(len(led) == 25 and all(i["arrived"] for i in led), "answer key incomplete")
check(len({frozenset(v) for v in briefs_per_day.values()}) >= 3, "morning briefings barely changed from day to day: the assistant is not seeing new work")
check(not bad, f"unexpected errors: {collections.Counter((m, u, s_) for m, u, s_, _ in bad).most_common(6)}")
print(f"simulated week: {st['days'][0]} .. {st['days'][-1]}, background items released {st['background_released']}, scripted events {st['scenario_released']}/{st['scenario_total']}")
if problems:
    print("PROBLEMS:\n- " + "\n- ".join(problems))
    sys.exit(1)
print("week simulation machinery OK")
