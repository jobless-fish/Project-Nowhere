"""Score the extraction pipeline against a labelled dataset.

    python -m eval.run_eval                  # uses configured provider
    python -m eval.run_eval --min-acc 0.9    # exit 1 if below (used in CI)
"""
import argparse
import json
import os
import sys
import tempfile
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-acc", type=float, default=0.0)
    ap.add_argument("--prompt", default=None, help="prompt version to evaluate (v1|v2)")
    ap.add_argument("--data", default=str(Path(__file__).with_name("dataset.jsonl")))
    args = ap.parse_args()

    os.environ.setdefault("DOCFLOW_DB", str(Path(tempfile.mkdtemp()) / "eval.db"))
    os.environ.setdefault("DEFAULT_MODE", "auto")
    os.environ.setdefault("AUDIT_SAMPLE_RATE", "0")
    if args.prompt:
        os.environ["PROMPT_VERSION"] = args.prompt
    from app import config, db, pipeline  # imported after env is set

    db.init()
    rows = [json.loads(l) for l in open(args.data, encoding="utf-8") if l.strip()]
    fails, field_ok, field_n, cost, api_failed = [], 0, 0, 0.0, 0
    for r in rows:
        doc_id = pipeline.process(r["text"], "eval")
        with db.conn() as c:
            d = c.execute("SELECT status, extraction FROM documents WHERE id=?", (doc_id,)).fetchone()
        if d["status"] == "failed" or not d["extraction"]:
            api_failed += 1          # the call itself failed (rate limit, timeout): a fact about the network, not about the model, so it is not scored
            continue
        got = json.loads(d["extraction"])
        got["needs_review"] = d["status"] == "needs_review"
        bad = {k: (v, got.get(k)) for k, v in r["expect"].items()
               if k != "needs_review" and got.get(k) != v}
        if r["expect"].get("needs_review") is not None and r["expect"]["needs_review"] != got["needs_review"]:
            bad["needs_review"] = (r["expect"]["needs_review"], got["needs_review"])
        field_n += len(r["expect"]); field_ok += len(r["expect"]) - len(bad)
        if bad:
            fails.append((r["text"][:40], bad))
    with db.conn() as c:
        cost = c.execute("SELECT COALESCE(SUM(cost_usd),0) c FROM llm_calls").fetchone()["c"]
    acc = field_ok / field_n
    print(f"prompt={config.PROMPT_VERSION} provider={config.LLM_PROVIDER} "
          f"docs={len(rows)} scored={len(rows) - api_failed} api_failed={api_failed} field_accuracy={acc:.3f} cost_usd={cost:.4f}")
    for t, b in fails:
        print(f"  FAIL {t!r}: {b}")
    return 1 if acc < args.min_acc else 0


if __name__ == "__main__":
    sys.exit(main())
