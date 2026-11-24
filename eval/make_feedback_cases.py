"""Reproducibly generates eval/feedback_cases.jsonl by simulating a few days of real use of the demo company
(people mark todos, edit/reject reply drafts) and harvesting the signals. Fictional data only."""
import json
import os
import tempfile
from pathlib import Path

os.environ["DOCFLOW_DB"] = str(Path(tempfile.mkdtemp()) / "fb.db")
os.environ["LLM_PROVIDER"] = "mock"
os.environ["SOURCE"] = "fixture"


def main():
    from fastapi.testclient import TestClient
    from app import config
    from app.assistant import router as arouter
    from app.assistant.world_source import WorldSource
    from app.main import app
    from world.main import app as world_app
    from world.store import store
    config.DEFAULT_MODE = "auto"
    store.reset()
    arouter.get_source = lambda: WorldSource(TestClient(world_app))
    with TestClient(app) as c:
        key = lambda b, sid: next(t["key"] for t in b["todos"] if sid in t["source_ids"])
        fb = lambda uid, k, v: c.post("/assistant/feedback", json={"user_id": uid, "todo_key": k, "value": v})
        for uid, done, wrong in (("u_kim", ["mail-mk1", "iss-i1"], ["ntc-n1"]), ("u_dev1", ["mail-md1", "iss-i2"], []),
                                 ("u_ceo", ["mail-mc1", "iss-i3"], ["ntc-n1"])):
            b = c.post("/assistant/clock-in", json={"user_id": uid}).json()["briefing"]
            for sid in done: fb(uid, key(b, sid), "done")
            for sid in wrong: fb(uid, key(b, sid), "wrong")
            for sid, mode in (("mail-mk1", "edit"), ("mail-md1", "asis"), ("mail-mc2", "reject"), ("mail-mc3", "edit")):
                if not any(sid in t["source_ids"] for t in b["todos"]):
                    continue
                a = c.post("/assistant/actions/propose", json={"user_id": uid, "todo_key": key(b, sid)}).json()
                body = {"user_id": uid, "approve": mode != "reject", "confirm_external": True}
                if mode == "edit":
                    body["body"] = "확인했습니다. 오늘 오후 중 먼저 요약본을 보내고, 세부 자료는 내일 오전까지 정리해 드리겠습니다."
                c.post(f"/assistant/actions/{a['id']}/decision", json=body)
        c.post("/assistant/eval/harvest")
        rows = c.get("/assistant/eval/export").json()
    out = Path(__file__).with_name("feedback_cases.jsonl")
    out.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    print(len(rows), "cases ->", out)


if __name__ == "__main__":
    main()
