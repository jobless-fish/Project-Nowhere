"""Run an evaluation several times against the real model and report mean / min / max, because one run of a language model proves little.

  python -m eval.repeat npc -n 5
  python -m eval.repeat briefing -n 3
  python -m eval.repeat docs -n 3
Needs LLM_PROVIDER=openai + LLM_BASE_URL/LLM_MODEL/LLM_API_KEY (see eval/RESULTS.md). Appends a record to eval/runs.jsonl.
"""
import argparse
import json
import os
import re
import statistics
import subprocess
import sys
import time
from pathlib import Path

CMD = {"npc": [sys.executable, "-m", "eval.npc_eval", "--llm"], "briefing": [sys.executable, "-m", "eval.briefing_eval", "--world"],
       "docs": [sys.executable, "-m", "eval.run_eval"]}


def parse(kind: str, out: str) -> dict:
    m = {}
    if kind == "npc":
        raw_part, _, served = out.partition("[사용자에게 가는 결과")
        for tag, part in (("raw_", raw_part), ("served_", served)):
            for k in ("valid", "grounded", "register", "clean", "relevant", "safe"):
                r = re.search(rf"^\s+{k}\s+(\d+)/(\d+)", part, re.M)
                if r and int(r.group(2)):
                    m[tag + k] = int(r.group(1)) / int(r.group(2))
        for key, pat in (("api_errors", r"API 오류로 제외 (\d+)개"), ("rejected", r"규칙으로 대체 (\d+)개"), ("answered", r"모델이 답한 (\d+)개")):
            r = re.search(pat, out)
            m[key] = int(r.group(1)) if r else 0
    elif kind == "briefing":
        r = re.search(r"recall=([\d.]+) precision=([\d.]+) injection_leaks=(\d+)", out)
        if r:
            m.update(recall=float(r.group(1)), precision=float(r.group(2)), leaks=int(r.group(3)))
        m["degraded_users"] = out.count("degraded=True")
    else:
        r = re.search(r"field_accuracy=([\d.]+)", out)
        if r:
            m["field_accuracy"] = float(r.group(1))
        m["failed_docs"] = len(re.findall(r"^\s+FAIL ", out, re.M))
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=CMD)
    ap.add_argument("-n", type=int, default=3)
    ap.add_argument("--timeout", type=int, default=420)
    a = ap.parse_args()
    runs, errs = [], 0
    for i in range(a.n):
        t = time.time()
        try:
            p = subprocess.run(CMD[a.kind], capture_output=True, text=True, timeout=a.timeout, env=os.environ)
            m = parse(a.kind, p.stdout)
            if not m:
                raise RuntimeError(p.stderr[-200:] or "no metrics")
            m["seconds"] = round(time.time() - t)
            runs.append(m)
            print(f"run {i + 1}/{a.n}: {m}", flush=True)
        except Exception as e:  # noqa: BLE001
            errs += 1
            print(f"run {i + 1}/{a.n}: FAILED {type(e).__name__}: {str(e)[:120]}", flush=True)
    summary = {}
    for k in sorted({k for r in runs for k in r}):
        v = [r[k] for r in runs if k in r]
        summary[k] = {"mean": round(statistics.mean(v), 3), "min": min(v), "max": max(v)}
    rec = {"kind": a.kind, "n": a.n, "ok_runs": len(runs), "errors": errs, "model": os.getenv("LLM_MODEL"), "at": time.strftime("%Y-%m-%d %H:%M"), "summary": summary}
    print(json.dumps(rec, ensure_ascii=False, indent=1))
    with open(Path(__file__).with_name("runs.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
