from collections import Counter

import pytest
from fastapi.testclient import TestClient

from world.main import app as world_app
from world.people import DEPTS, FEATURED, build, org_summary
from world.store import store

P = build()
BY = {p["id"]: p for p in P}


def test_headcount_and_uniqueness():
    assert len(P) == 217
    assert len({p["id"] for p in P}) == len({p["email"] for p in P}) == len({p["name"] for p in P}) == len(P)


def test_deterministic():
    assert build() == build()


def test_single_ceo_and_every_chain_reaches_the_ceo_without_cycles():
    assert [p["id"] for p in P if p["manager_id"] is None] == ["u_ceo"]
    for p in P:
        seen, cur = set(), p
        while cur["manager_id"]:
            assert cur["id"] not in seen, f"cycle at {p['id']}"
            seen.add(cur["id"])
            cur = BY[cur["manager_id"]]
        assert cur["id"] == "u_ceo"


def test_each_unit_has_exactly_one_lead_and_the_right_size():
    for d in DEPTS:
        for (uname, n, *_r) in d["units"]:
            ms = [p for p in P if p["dept_key"] == d["key"] and p["unit"] == uname]
            assert len(ms) == n and sum(p["position"] == "팀장" for p in ms) == 1, (d["name"], uname)
            lead = next(p for p in ms if p["position"] == "팀장")
            assert all(m["manager_id"] == lead["id"] for m in ms if m is not lead)
            assert BY[lead["manager_id"]]["unit"] == d["name"]            # lead reports to the department head


def test_demo_accounts_are_placed_in_the_org():
    assert {p["id"] for p in P if p["featured"]} == set(FEATURED)
    kim = BY["u_kim"]
    assert (kim["dept"], kim["unit"], BY[kim["manager_id"]]["id"]) == ("사업본부", "법인영업팀", "u_slead")
    assert BY["u_cto"]["position"] == "본부장" and BY["u_cto"]["role"] == "executive"
    assert Counter(p["role"] for p in P)["executive"] == 4                    # CEO, CFO, CTO, CPO only


def test_realistic_mix():
    c = Counter(p["employment"] for p in P)
    assert c["정규직"] > 190 and c["계약직"] > 0 and c["인턴"] > 0
    assert {p["location"] for p in P} == {"서울 성수 본사", "판교 R&D센터", "부산 고객지원센터"}
    assert all(p["hire_date"] >= "2019-03-01" for p in P)


@pytest.fixture()
def http():
    store.reset()
    c = TestClient(world_app)
    t = c.post("/sso/token", json={"user_id": "u_kim", "password": "demo1234"}).json()["access_token"]
    return c, {"Authorization": "Bearer " + t}


def test_login_list_is_the_demo_accounts_but_all_can_be_requested(http):
    c, _ = http
    assert len(c.get("/sso/users").json()) == 13 and len(c.get("/sso/users", params={"all": True}).json()) == 217


def test_directory_requires_a_token_and_exposes_only_public_fields(http):
    c, h = http
    assert c.get("/directory/org").status_code == 401
    org = c.get("/directory/org", headers=h).json()
    assert len(org["departments"]) == 9 and sum(d["headcount"] for d in org["departments"]) + 1 == org["headcount"] == 217
    assert "featured" not in org["ceo"] and "role" not in org["ceo"]


def test_people_search_and_chain_of_command(http):
    c, h = http
    r = c.get("/directory/people", params={"q": "백엔드", "limit": 5}, headers=h).json()
    assert r["total"] >= 10 and len(r["items"]) == 5
    me = c.get("/directory/people/u_kim", headers=h).json()
    assert [x["id"] for x in me["chain_of_command"]][0] == "u_slead" and me["chain_of_command"][-1]["id"] == "u_ceo"
    lead = c.get("/directory/people/u_slead", headers=h).json()
    assert any(x["id"] == "u_kim" for x in lead["direct_reports"])
    assert c.get("/directory/people/nope", headers=h).status_code == 404
