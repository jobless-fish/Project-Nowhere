import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.assistant import briefing, router as arouter
from app.assistant.world_source import WorldSource
from app.llm.mock import MockClient
from eval import feedback_eval
from world.main import app as world_app
from world.store import store

CASES = [json.loads(l) for l in (Path(feedback_eval.HERE) / "feedback_cases.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]


@pytest.fixture()
def env(client, monkeypatch):
    store.reset()
    monkeypatch.setattr(arouter, "get_source", lambda: WorldSource(TestClient(world_app)))
    return client


def use(c, uid="u_kim"):
    b = c.post("/assistant/clock-in", json={"user_id": uid}).json()["briefing"]
    k = lambda sid: next(t["key"] for t in b["todos"] if sid in t["source_ids"])
    return b, k


def test_harvest_labels_and_is_idempotent(env):
    c = env
    b, k = use(c)
    c.post("/assistant/feedback", json={"user_id": "u_kim", "todo_key": k("ntc-n1"), "value": "wrong"})
    c.post("/assistant/feedback", json={"user_id": "u_kim", "todo_key": k("iss-i1"), "value": "done"})
    c.post("/assistant/feedback", json={"user_id": "u_kim", "todo_key": k("mail-mk2"), "value": "dismissed"})   # not a clear signal
    a = c.post("/assistant/actions/propose", json={"user_id": "u_kim", "todo_key": k("mail-mk1")}).json()
    c.post(f"/assistant/actions/{a['id']}/decision", json={"user_id": "u_kim", "approve": True, "body": "고친 본문입니다."})
    first = c.post("/assistant/eval/harvest").json()
    assert first["new"] == {"todo": 3, "reply": 1}          # the done/wrong feedback, plus the todo that finished by SENDING a reply
    assert first["by"] == {"todo:negative": 1, "todo:positive": 2, "reply:edited": 1}
    assert c.post("/assistant/eval/harvest").json()["new"] == {"todo": 0, "reply": 0}      # re-harvest adds nothing
    rows = c.get("/assistant/eval/export").json()
    todo = next(r for r in rows if r["label"] == "negative")
    assert all("mk4" not in i["id"] for i in todo["payload"]["items"])                      # injection mail never enters the set
    assert next(r for r in rows if r["kind"] == "reply")["payload"]["final"] == "고친 본문입니다."


def test_committed_cases_replay_and_match_baseline():
    cur = feedback_eval.score(CASES, MockClient())
    base = json.loads((Path(feedback_eval.HERE) / "baseline.json").read_text())
    assert feedback_eval.compare(cur, base, 0.02) == []


def test_gate_catches_a_broken_change(monkeypatch):
    # a bad "improvement": the assistant stops proposing any todo -> confirmed todos are missed
    monkeypatch.setattr(briefing, "rule_based", lambda user, items: {"summary": "", "todos": [], "fyi": []})
    cur = feedback_eval.score(CASES, MockClient())
    base = json.loads((Path(feedback_eval.HERE) / "baseline.json").read_text())
    assert any("todo_pass_rate" in m for m in feedback_eval.compare(cur, base, 0.02))


def test_gate_catches_worse_drafts(monkeypatch):
    from app.assistant import actions
    monkeypatch.setattr(actions, "draft", lambda *a, **k: ("Re: x", "무관한 문장입니다."))
    cur = feedback_eval.score(CASES, MockClient())
    base = json.loads((Path(feedback_eval.HERE) / "baseline.json").read_text())
    assert any("reply_similarity" in m for m in feedback_eval.compare(cur, base, 0.02))


def test_compare_respects_tolerance():
    assert feedback_eval.compare({"todo_pass_rate": 0.74}, {"todo_pass_rate": 0.75}, 0.02) == []
    assert feedback_eval.compare({"todo_pass_rate": 0.70}, {"todo_pass_rate": 0.75}, 0.02)
