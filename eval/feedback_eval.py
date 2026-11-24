"""Replay harvested user feedback against the CURRENT prompts/rules/model and gate regressions.

  python -m eval.feedback_eval                      # score + compare with eval/baseline.json
  python -m eval.feedback_eval --update-baseline    # accept the current scores as the new baseline
  python -m eval.feedback_eval --data my_cases.jsonl --tolerance 0.05

todo cases : negative ("관련 없음") must NOT be cited by a todo; positive (done) must be cited.
reply cases: similarity of a fresh draft to what the human finally sent (or kept). Higher = closer to what people want.
Exit code 1 if a score drops below the baseline by more than the tolerance (CI gate).
"""
import argparse
import difflib
import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent


def score(cases: list[dict], client) -> dict:
    from app.assistant import actions
    from app.assistant.briefing import build_briefing
    from app.assistant.sources import Item, User

    mk = lambda d: Item(**{**d, "visible_to": []})  # snapshots drop ACL info on purpose
    todo_total = todo_pass = 0
    sims, rejected_total, rejected_changed = [], 0, 0
    failures = []
    for c in cases:
        p, user = c["payload"], None
        user = User(**p["user"])
        if c["kind"] == "todo":
            items = [mk(i) for i in p["items"]]
            b = build_briefing(user, items, client)
            cited = {i for t in b["todos"] for i in t["source_ids"]}
            hit = bool(cited & set(p["source_ids"]))
            ok = hit if c["label"] == "positive" else not hit
            todo_total += 1; todo_pass += ok
            if not ok:
                failures.append(f"{c['label']} todo still wrong: {p['title']}")
        else:
            subject, body = actions.draft(user, mk(p["item"]), p["todo"], client)
            if c["label"] == "rejected":
                rejected_total += 1; rejected_changed += body != p["draft"]
            else:
                sims.append(difflib.SequenceMatcher(None, body, p["final"] or p["draft"]).ratio())
    return {"todo_cases": todo_total, "todo_pass_rate": round(todo_pass / todo_total, 3) if todo_total else None,
            "reply_cases": len(sims), "reply_similarity": round(sum(sims) / len(sims), 3) if sims else None,
            "rejected_cases": rejected_total, "rejected_changed": rejected_changed, "failures": failures}


def compare(current: dict, baseline: dict, tol: float) -> list[str]:
    bad = []
    for k in ("todo_pass_rate", "reply_similarity"):
        if baseline.get(k) is not None and current.get(k) is not None and current[k] < baseline[k] - tol:
            bad.append(f"{k} regressed {baseline[k]} -> {current[k]}")
    return bad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(HERE / "feedback_cases.jsonl"))
    ap.add_argument("--baseline", default=str(HERE / "baseline.json"))
    ap.add_argument("--tolerance", type=float, default=0.02)
    ap.add_argument("--update-baseline", action="store_true")
    a = ap.parse_args()
    os.environ.setdefault("DOCFLOW_DB", str(Path(tempfile.mkdtemp()) / "fb.db"))
    from app import db
    from app.llm import get_client
    db.init()
    cases = [json.loads(l) for l in open(a.data, encoding="utf-8") if l.strip()]
    client = get_client()
    cur = score(cases, client)
    print(json.dumps({"provider": client.provider, **cur}, ensure_ascii=False, indent=2))
    if a.update_baseline:
        Path(a.baseline).write_text(json.dumps({k: cur[k] for k in ("todo_pass_rate", "reply_similarity")}, indent=2))
        print("baseline updated"); return 0
    if Path(a.baseline).exists():
        bad = compare(cur, json.loads(Path(a.baseline).read_text()), a.tolerance)
        for b in bad:
            print("REGRESSION:", b)
        return 1 if bad else 0
    print("no baseline yet (run with --update-baseline)"); return 0


if __name__ == "__main__":
    sys.exit(main())
