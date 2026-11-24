from app import autonomy, config

LEAVE = "이준호입니다. 2026-12-24 연차 사용하고 싶습니다."


def test_wilson_penalises_small_samples():
    assert autonomy.wilson_lower(5, 5) < 0.6        # 5/5 is not trustworthy yet
    assert autonomy.wilson_lower(100, 100) > 0.96
    assert autonomy.wilson_lower(0, 0) == 0.0


def test_shadow_does_not_touch_erp_and_label_compares(client, monkeypatch):
    monkeypatch.setattr(config, "DEFAULT_MODE", "shadow")
    d = client.post("/documents", json={"text": LEAVE}).json()
    assert d["status"] == "shadow" and d["erp_ref"] is None
    assert client.get("/erp/records").json() == []
    r = client.post(f"/documents/{d['id']}/label",
                    json={"actual": {"doc_type": "leave_request", "date_from": "2026-12-24"}})
    assert r.json()["agree"] is True
    bad = client.post("/documents", json={"text": LEAVE}).json()
    r = client.post(f"/documents/{bad['id']}/label", json={"actual": {"doc_type": "inquiry"}})
    assert r.json()["agree"] is False


def test_promotion_is_recommended_not_applied(client, monkeypatch):
    monkeypatch.setattr(config, "DEFAULT_MODE", "shadow")
    for _ in range(25):
        d = client.post("/documents", json={"text": LEAVE}).json()
        client.post(f"/documents/{d['id']}/label", json={"actual": {"doc_type": "leave_request"}})
    s = next(x for x in client.get("/autonomy").json() if x["doc_type"] == "leave_request")
    assert s["mode"] == "shadow" and s["recommended_mode"] == "assisted"   # a person must confirm
    assert client.post("/autonomy/leave_request/mode", json={"mode": "assisted"}).json()["mode"] == "assisted"
    d = client.post("/documents", json={"text": LEAVE}).json()
    assert d["status"] == "needs_review"                                  # assisted: human approves
    assert client.post("/autonomy/leave_request/mode", json={"mode": "bogus"}).status_code == 422


def test_auto_demotes_when_quality_drops(client):
    autonomy.set_mode("leave_request", "auto")
    for i in range(12):
        autonomy.record_outcome(i, "leave_request", "auto", i < 6)   # only 50% agreement
    s = next(x for x in client.get("/autonomy").json() if x["doc_type"] == "leave_request")
    assert s["applied"] == "demoted"
    assert autonomy.get_mode("leave_request") == "assisted"


def test_only_current_mode_outcomes_count(client):
    autonomy.set_mode("inquiry", "assisted")
    for i in range(40):
        autonomy.record_outcome(i, "inquiry", "shadow", True)       # earned in shadow, not in assisted
    s = autonomy.status("inquiry")
    assert s["samples"] == 0 and s["recommended_mode"] == "assisted"
