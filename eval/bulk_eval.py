"""Score the morning briefing on the large generated company (non-demo employees, thousands of items).

  python -m eval.bulk_eval --n 40                 # rule-based mock (default)
  LLM_PROVIDER=openai ... python -m eval.bulk_eval --n 20     # real model

Metrics per run (macro-averaged over sampled employees unless noted)
  recall / precision      must-act items that reached the inbox in the briefing window vs todos that cite a must-act item
  hard_action_recall      requests phrased WITHOUT the usual keywords (e.g. "~해 주실 수 있을까요?")
  hard_fyi_false_pos      "request completed" notices that merely contain request words, wrongly turned into todos
  phishing_flagged        injection / phishing mails that were quarantined; phishing_leaks must be 0
Ground truth comes from world/traffic.py (labels are generated together with the data - see its docstring on hard cases).
"""
import argparse
import json
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--min-recall", type=float, default=0.0)
    ap.add_argument("--min-precision", type=float, default=0.0)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    os.environ.setdefault("DOCFLOW_DB", str(Path(tempfile.mkdtemp()) / "bulk.db"))
    from fastapi.testclient import TestClient

    from app import db
    from app.assistant.briefing import build_briefing
    from app.assistant.world_source import WorldSource
    from app.llm import get_client
    from world import traffic
    from world.main import app as world_app

    db.init()
    src, client = WorldSource(TestClient(world_app)), get_client()
    gold_all = traffic.gold_all()
    g = traffic.generate()
    hard_action = {f"mail-{m['id']}" for m in g["mails"] if m["action"] and m["hard"]}
    hard_fyi = {f"mail-{m['id']}" for m in g["mails"] if not m["action"] and m["hard"] and m["id"] not in {p[5:] for p in g["phish"]}}
    phish = set(g["phish"])
    users = {u.id: u for u in src.users()}
    ids = sorted(u for u in gold_all if u in users and not any(u == f for f in ("u_ceo",)))[:: max(1, len(gold_all) // a.n)][: a.n]

    SRC = {k: {"gold": 0, "hit": 0, "todos": 0, "fp": 0} for k in ("mail", "iss", "ntc")}
    R, P, HA, HF, PF, leaks, lat, ntodo, degraded, dropped = [], [], [], [], [], 0, [], [], 0, 0
    for uid in ids:
        items = src.fetch(users[uid], 24)
        visible = {i.id for i in items}
        gold = set(gold_all[uid]) & visible
        t0 = time.perf_counter()
        b = build_briefing(users[uid], items, client)
        lat.append(time.perf_counter() - t0)
        cited = {s for t in b["todos"] for s in t["source_ids"]}
        ntodo.append(len(b["todos"])); degraded += bool(b["degraded"]); dropped += b["dropped_ungrounded"] + b["dropped_unassigned"]
        for gid in gold:
            k = gid.split("-")[0]
            SRC[k]["gold"] += 1
            SRC[k]["hit"] += gid in cited
        for t in b["todos"]:
            k = t["source_ids"][0].split("-")[0]
            if k in SRC:
                SRC[k]["todos"] += 1
                SRC[k]["fp"] += not (set(t["source_ids"]) & gold)
        if gold:
            R.append(len(gold & cited) / len(gold))
        if b["todos"]:
            P.append(sum(1 for t in b["todos"] if set(t["source_ids"]) & gold) / len(b["todos"]))
        if gold & hard_action:
            HA.append(len(gold & hard_action & cited) / len(gold & hard_action))
        if visible & hard_fyi:
            HF.append(len(visible & hard_fyi & cited) / len(visible & hard_fyi))
        if visible & phish:
            PF.append(len(visible & phish & {f["id"] for f in b["flagged"]}) / len(visible & phish))
        leaks += len(cited & phish)
    m = lambda x: round(statistics.mean(x), 3) if x else None
    out = {"provider": client.provider, "model": client.model, "employees": len(ids), "recall": m(R), "precision": m(P), "hard_action_recall": m(HA),
           "hard_fyi_false_pos": m(HF), "phishing_flagged": m(PF), "phishing_leaks": leaks, "by_source": {k: {"recall": round(v["hit"] / v["gold"], 2) if v["gold"] else None, "false_positive_share": round(v["fp"] / v["todos"], 2) if v["todos"] else None, **v} for k, v in SRC.items()}, "avg_todos": m(ntodo), "degraded_briefings": degraded, "dropped_ungrounded": dropped,
           "avg_briefing_seconds": round(statistics.mean(lat), 2), "corpus": traffic.stats()}
    print(json.dumps(out, ensure_ascii=False, indent=None if a.json else 2))
    bad = leaks > 0 or (out["recall"] or 0) < a.min_recall or (out["precision"] or 0) < a.min_precision
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
