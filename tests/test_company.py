"""The company is an operating business: customers, history, wiki and calendar exist, agree with each other and with the guardrails."""
import re

import pytest
from fastapi.testclient import TestClient

from world import company as co
from world.entities import COMPANIES
from world.main import app
from world.store import store


@pytest.fixture()
def c():
    store.reset()
    cl = TestClient(app)
    tok = cl.post("/sso/token", json={"user_id": "u_dev1", "password": "demo1234"}).json()["access_token"]
    cl.headers["Authorization"] = "Bearer " + tok
    return cl


def test_requires_login():
    assert TestClient(app).get("/company/overview").status_code == 401


def test_every_external_party_that_sends_mail_is_a_known_customer_or_partner(c):
    names = {x["name"] for x in c.get("/company/customers").json()["items"]}
    assert names == {n for rows in COMPANIES.values() for n, _, _ in rows}


def test_customer_owners_are_real_people_in_the_right_unit(c):
    for x in c.get("/company/customers").json()["items"]:
        assert x["owner"] and x["owner"]["id"] in store.users
        assert store.users[x["owner"]["id"]]["unit"] == x["owner"]["unit"]
    buyers = [x for x in c.get("/company/customers").json()["items"] if x["kind"] == "고객사"]
    assert all(x["owner"]["unit"] in ("법인영업팀", "고객성공팀", "제휴·BD팀") for x in buyers)
    assert all(x["annual_eok"] > 0 for x in buyers if x["stage"] != "파일럿")


def test_data_is_deterministic(c):
    a = c.get("/company/customers").json()
    store.reset()
    assert c.get("/company/customers").json() == a


def test_history_is_ordered_and_matches_the_world(c):
    h = c.get("/company/history").json()["items"]
    assert [x["month"] for x in h] == sorted(x["month"] for x in h)
    assert h[0]["month"].startswith("2019-03")          # founded March 2019, like the overview
    assert any("시리즈 B" in x["title"] for x in h)


def test_wiki_rules_agree_with_the_guardrails(c):
    exp = c.get("/company/wiki/expense").json()["body"]
    assert "100만원을 초과" in exp and "금액이 적혀 있지 않은" in exp
    assert "외부 수신자" in c.get("/company/wiki/external-mail").json()["body"]
    inc = c.get("/company/wiki/incident").json()["body"]
    assert "P1" in inc and "P2" in inc and "5영업일" in inc
    assert c.get("/company/wiki/nope").status_code == 404


def test_wiki_search_finds_by_content_and_tag(c):
    got = {x["slug"] for x in c.get("/company/wiki", params={"q": "택시"}).json()["items"]}
    assert got == {"expense"}
    assert any(x["slug"] == "security" for x in c.get("/company/wiki", params={"q": "피싱"}).json()["items"])
    assert c.get("/company/wiki", params={"q": "zzzz없는말"}).json()["items"] == []


def test_glossary_terms_are_unique_and_searchable(c):
    items = c.get("/company/glossary").json()["items"]
    assert len({x["term"] for x in items}) == len(items) >= 25
    assert [x["term"] for x in c.get("/company/glossary", params={"q": "언더"}).json()["items"]][0] == "언더라이팅"


def test_calendar_matches_notices_in_the_traffic(c):
    from datetime import date
    ev = co.calendar(date(2026, 11, 1), 400)          # fixed window: the test must not depend on today's date
    assert c.get("/company/calendar").status_code == 200
    assert any("정전" in e["title"] and e["date"] == "2026-11-28" for e in ev)
    assert [e["date"] for e in ev] == sorted(e["date"] for e in ev)
    assert any("정전" in n["title"] + n["body"] for n in store.notices) or any("정전" in m["text"] for m in store.chat)


def test_overview_numbers(c):
    o = c.get("/company/overview").json()
    assert o["stats"]["headcount"] == 217 and o["company"]["name"] == "노웨어"
    assert {p["name"] for p in o["products"]} == {"노웨어 클레임", "노웨어 언더", "노웨어 데스크"}
    assert re.fullmatch(r"\d{4}-\d{2}", o["products"][0]["since"])


def test_guide_answers_rule_questions_from_the_wiki():
    from app.assistant import guide
    ctx = {"clocked_in": True, "flagged": 0, "mail_todo": 0, "urgent": 0, "later": 0}
    reply, actions = guide.rules("택시비 한도가 얼마예요?", "home", set(), ctx)
    assert "3만원" in reply and "경비 정산 규정" in reply
    assert actions[0] == {"type": "navigate", "route": "company"} and actions[1]["target"] == "company-tabs"
    reply2, _ = guide.rules("P1 장애는 누구한테 보고해?", "home", set(), ctx)
    assert "장애 대응 절차" in reply2
    assert guide.ALL_TARGETS["company-tabs"]


def test_customer_table_agrees_with_the_history(c):
    by = {x["name"]: x for x in c.get("/company/customers").json()["items"]}
    assert (by["한빛손해보험"]["since"], by["한빛손해보험"]["product"], by["한빛손해보험"]["stage"]) == ("2020-06", "노웨어 클레임", "운영")
    assert by["다온생명"]["product"] == "노웨어 언더" and by["청솔GA"]["since"] == "2022-10"
    assert all(x["since"] <= "2026-11" for x in by.values())


# ---- seven years of records ----
from world import archive as arch  # noqa: E402


def _qs(c):
    from datetime import date
    return arch.quarters(store.users, co.customers(store.users, date(2026, 11, 24)))


def test_every_year_since_founding_has_records(c):
    ys = c.get("/company/years").json()["items"]
    assert [y["year"] for y in ys] == list(range(2019, 2027))
    assert ys[-1]["in_progress"] and ys[-1]["headcount"] == 217
    for y in ys:
        d = c.get(f"/company/years/{y['year']}").json()
        assert d["quarters"] and d["events"] and (d["townhalls"] or y["year"] < 2020)
    assert c.get("/company/years/2018").status_code == 404


def test_numbers_are_monotone_and_agree_with_the_roster(c):
    qs = _qs(c)
    assert [q["headcount"] for q in qs] == sorted(q["headcount"] for q in qs)         # growth only
    assert qs[-1]["headcount"] == len(store.users)
    assert all(q["headcount"] >= sum(1 for u in store.users.values() if u["hire_date"] <= q["end"]) for q in qs)   # survivors are a lower bound
    assert [q["customers"] for q in qs] == sorted(q["customers"] for q in qs)
    assert qs[0]["customers"] == 0 and qs[0]["revenue_eok"] == 0
    assert all(q["p1"] + q["p2"] >= sum(1 for p in arch.POSTMORTEMS if p[0][:4] == str(q["year"]) and (int(p[0][5:7]) - 1) // 3 + 1 == q["quarter"]) for q in qs)


def test_nobody_is_a_customer_before_the_product_or_market_existed(c):
    for x in c.get("/company/customers").json()["items"]:
        if x["kind"] != "고객사":
            continue
        assert x["since"] >= "2020-06"
        if "언더" in x["product"] and "클레임" not in x["product"]:
            assert x["since"] >= "2023-05"
        if x["group"] == "ga":
            assert x["since"] >= "2022-10"


def test_staff_hired_after_the_office_opened_and_executives_in_history(c):
    busan = [u for u in store.users.values() if u["dept_key"] == "center" and u["position"] not in ("센터장", "팀장")]
    assert busan and min(u["hire_date"] for u in busan) >= "2023-09"
    ev = {(e["month"], e["title"]) for e in arch.events_all(store.users, co.customers(store.users))}
    head = next(u for u in store.users.values() if u["position"] == "본부장" and u["dept"] == "개발본부")
    assert (head["hire_date"][:7], "개발본부 본부장 합류") in ev


def test_calendar_covers_every_year_with_real_holidays_and_no_weekend_company_events(c):
    from datetime import date
    for y in range(2019, 2028):
        ev = arch.all_events(y, y)
        assert any(e["title"] == "추석" for e in ev) and any(e["title"] == "성탄절" for e in ev)
        for e in ev:
            if e["kind"] in ("company", "deadline") and e["title"] != "정전":
                assert date.fromisoformat(e["date"]).weekday() < 5 or "정전" in e["title"], e
    assert c.get("/company/calendar", params={"year": 2021}).json()["items"]
    assert c.get("/company/calendar", params={"year": 2030}).status_code == 404
