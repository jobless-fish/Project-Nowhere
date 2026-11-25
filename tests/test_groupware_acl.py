"""Groupware access control: search must not leak, and the department walls must hold."""
import pytest
from fastapi.testclient import TestClient

from world import acl
from world.main import app
from world.store import store


@pytest.fixture()
def w():
    store.reset()
    c = TestClient(app)

    def tok(uid):
        return {"Authorization": "Bearer " + c.post("/sso/token", json={"user_id": uid, "password": "demo1234"}).json()["access_token"]}

    def search(uid, q, **kw):
        r = c.get("/groupware/search", params={"q": q, **kw}, headers=tok(uid))
        assert r.status_code == 200, r.text
        return r.json()

    def ids(uid, q, **kw):
        return [i["id"] for i in search(uid, q, **kw)["items"]]
    c.tok, c.search, c.ids = tok, search, ids
    return c


def doc(title_part):
    return next(d for d in store.docs if title_part in d["title"])


def user_in(dept, exclude=()):
    return next(u["id"] for u in store.users.values() if u["dept_key"] == dept and u["role"] == "employee" and u["id"] not in exclude)


def test_the_owner_department_finds_its_own_documents(w):
    d = doc("인수합병 후보")
    assert d["id"] in w.ids(user_in("strategy"), "인수합병")


def test_search_for_a_hidden_document_looks_exactly_like_a_search_for_nothing(w):
    """A marketing person (behind the strategy wall) searches the exact title of the M&A document and a word that exists nowhere: same answer."""
    mk = user_in("marketing")
    hit = w.search(mk, "인수합병 후보 검토")
    nothing = w.search(mk, "존재하지않는단어qzx")
    assert hit == nothing == {"items": [], "next_offset": None}


def test_a_denied_document_leaves_no_trace_in_snippets_counts_or_paging(w):
    mk = user_in("marketing")
    r = w.search(mk, "예산")                               # the budget doc of strategy is behind the wall, the campaign budget is not
    titles = " ".join(i["title"] + i["snippet"] for i in r["items"])
    assert "예산 배분" not in titles and "겨울 캠페인" in titles
    assert set(r) == {"items", "next_offset"}              # no total / hidden count


def test_department_barrier_beats_an_explicit_grant(w):
    d = doc("한빛손해보험 제휴 제안서")
    d["audience"].append("dept:insurance")                 # someone shares the sales document with underwriting...
    ins = user_in("insurance")
    assert d["id"] not in w.ids(ins, "한빛손해보험")         # ...the wall still holds: a deny cannot be granted away
    assert w.get(f"/groupware/docs/{d['id']}", headers=w.tok(ins)).status_code == 404


def test_barrier_is_symmetric_and_only_between_the_listed_pairs(w):
    assert acl.blocked_pair("sales", "insurance") and acl.blocked_pair("insurance", "sales")
    uw, sales = doc("언더라이팅 심사 기준"), doc("한빛손해보험 제휴 제안서")
    assert uw["id"] not in w.ids(user_in("sales"), "언더라이팅")
    assert sales["id"] not in w.ids(user_in("insurance"), "한빛손해보험")
    assert not acl.blocked_pair("eng", "sales")             # no wall between development and sales
    shared = doc("결제 연동 장애 사후 분석")
    assert shared["id"] in w.ids(user_in("sales"), "결제 연동") and shared["id"] in w.ids(user_in("insurance"), "결제 연동")


def test_opening_a_hidden_document_is_a_404_like_a_missing_one(w):
    mk = w.tok(user_in("marketing"))
    assert w.get(f"/groupware/docs/{doc('인수합병 후보')['id']}", headers=mk).status_code == 404
    assert w.get("/groupware/docs/does-not-exist", headers=mk).status_code == 404


def test_explicit_deny_beats_everything_even_the_owner_department(w):
    d = doc("급여 인상률")
    assert d["id"] in w.ids("u_hr", "급여 인상률")           # HR (인사팀) may read it
    mk_support = next((u["id"] for u in store.users.values() if u["dept_key"] == "marketing"), None)
    assert d["id"] not in w.ids(mk_support, "급여 인상률")    # marketing is denied explicitly
    d["deny"].append("user:u_hr")
    assert d["id"] not in w.ids("u_hr", "급여 인상률")        # a deny on the person wins over owner department and grants


def test_permission_changes_take_effect_on_the_next_search(w):
    d = doc("겨울 캠페인 매체 예산")
    sales = user_in("sales")
    assert d["id"] in w.ids(sales, "캠페인")
    d["audience"].remove("dept:sales")
    assert d["id"] not in w.ids(sales, "캠페인")


def test_oversight_may_cross_a_wall_and_every_use_is_written_down(w):
    d = doc("인수합병 후보")
    comp = next(u["id"] for u in store.users.values() if u["unit"] == "컴플라이언스팀")
    ordinary_legal = next(u["id"] for u in store.users.values() if u["dept_key"] == "legal" and u["unit"] != "컴플라이언스팀")
    assert w.get(f"/groupware/docs/{d['id']}", headers=w.tok(comp)).status_code == 200          # audit access
    assert w.get(f"/groupware/docs/{d['id']}", headers=w.tok("u_ceo")).status_code == 200
    assert w.get(f"/groupware/docs/{d['id']}", headers=w.tok(ordinary_legal)).status_code == 404   # the rest of legal is not oversight
    log = w.get("/groupware/acl/audit", headers=w.tok("u_ceo")).json()["items"]
    assert {a["user"] for a in log if a["action"] == "barrier_exempt_view"} >= {comp, "u_ceo"}


def test_blocked_attempts_are_audited_for_oversight_only(w):
    mk = user_in("marketing")
    w.search(mk, "인수합병")
    w.get(f"/groupware/docs/{doc('인수합병 후보')['id']}", headers=w.tok(mk))
    assert w.get("/groupware/acl/audit", headers=w.tok(mk)).status_code == 403          # the refused person cannot read the log
    log = w.get("/groupware/acl/audit", headers=w.tok("u_ceo")).json()
    acts = {a["action"] for a in log["items"] if a["user"] == mk}
    assert {"search_blocked_match", "open_denied"} <= acts
    assert w.get("/groupware/acl/explain", params={"user_id": mk, "doc_id": doc("인수합병 후보")["id"]}, headers=w.tok(mk)).status_code == 403
    ex = w.get("/groupware/acl/explain", params={"user_id": mk, "doc_id": doc("인수합병 후보")["id"]}, headers=w.tok("u_ceo")).json()
    assert ex["allowed"] is False and "barrier" in ex["reason"]


def test_every_search_result_is_one_the_person_may_open(w):
    """Property: across all people and several queries, whatever search returns can be opened, and nothing else leaks into the pages."""
    uids = [u["id"] for u in list(store.users.values())[:80:4]] + ["u_ceo", "u_cfo", "u_legal"]
    for uid in uids:
        for q in ("예산", "조사", "개인정보", "주간", "협상"):
            for it in w.search(uid, q, limit=50)["items"]:
                assert w.get(f"/groupware/docs/{it['id']}", headers=w.tok(uid)).status_code == 200, (uid, q, it["id"])
                d = next(x for x in store.docs if x["id"] == it["id"]) if it["kind"] == "doc" else None
                if d and d["owner"]:
                    assert not acl.blocked_pair(store.users[uid]["dept_key"], d["owner"]) or acl.exempt(store.users[uid])
