"""The admin console of an operating company is never empty, and the ladder numbers it shows are real consequences of the seeded history."""
from app import autonomy, db
from app.seed_history import seed


def test_seed_fills_every_admin_tab(client):
    assert seed() is True
    assert seed() is False                                   # never twice, never into a database that already has data
    tabs = {r["doc_type"]: r for r in client.get("/autonomy").json()}
    assert tabs["expense_claim"]["mode"] == "auto" and tabs["expense_claim"]["recommended_mode"] == "auto"       # earned auto and kept it
    assert tabs["inquiry"]["recommended_mode"] == "assisted"                                                      # a promotion waits for a person
    assert tabs["reply_internal"]["recommended_mode"] == "auto"
    assert tabs["purchase_request"]["recommended_mode"] == "shadow" and tabs["purchase_request"]["samples"] < 20   # still collecting
    m = client.get("/metrics").json()
    assert m["llm_calls"] > 100 and 0 < m["auto_processed_rate"] < 1 and m["p95_latency_ms"] > m["avg_latency_ms"] > 0
    assert len(client.get("/documents").json()) >= 20
    st = client.get("/assistant/actions/stats").json()
    assert st["sent_as_is"] > 20 and st["blocked"] == 1
    assert client.get("/assistant/eval/summary").json()["total"] >= 4


def test_seed_does_not_touch_a_database_that_already_has_documents(client):
    client.post("/documents", json={"text": "박서연입니다. 출장비 정산 요청합니다. 총 85만원", "source": "console"})
    assert seed() is False


def test_auto_mode_survives_a_good_recent_window_and_is_demoted_only_below_the_bar(client):
    autonomy.set_mode("expense_claim", "auto")
    for i in range(20):
        autonomy.record_outcome(i, "expense_claim", "auto", True)                       # a perfect window must NOT demote (its lower bound is only 0.84)
    assert autonomy.evaluate(["expense_claim"])[0]["mode"] == "auto"
    for i in range(20, 26):
        autonomy.record_outcome(i, "expense_claim", "auto", False)                      # recent hit rate drops under 0.90
    assert autonomy.evaluate(["expense_claim"])[0].get("applied") == "demoted"
