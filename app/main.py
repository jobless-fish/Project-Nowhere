import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import autonomy, config, db, pipeline
from .schemas import SubmitIn


@asynccontextmanager
async def lifespan(_):
    db.init()
    yield


app = FastAPI(title="DocFlow", version="0.1.0", lifespan=lifespan)


def auth(x_api_key: str | None = Header(default=None)):
    key = os.getenv("DOCFLOW_API_KEY")  # unset = open (local demo only)
    if key and x_api_key != key:
        raise HTTPException(401, "invalid API key")


def _row(r):
    d = dict(r)
    d["extraction"] = json.loads(d["extraction"]) if d["extraction"] else None
    d["audit"] = json.loads(d["audit"])
    return d


@app.get("/health")
def health():
    return {"ok": True, "prompt_version": config.PROMPT_VERSION}


@app.post("/documents", dependencies=[Depends(auth)], status_code=201)
def submit(body: SubmitIn):
    doc_id = pipeline.process(body.text, body.source)
    return get_document(doc_id)


@app.get("/documents", dependencies=[Depends(auth)])
def list_documents(status: str | None = None, limit: int = 50):
    q, args = "SELECT * FROM documents", []
    if status:
        q += " WHERE status=?"; args.append(status)
    q += " ORDER BY id DESC LIMIT ?"; args.append(min(limit, 200))
    with db.conn() as c:
        return [_row(r) for r in c.execute(q, args)]


@app.get("/documents/{doc_id}", dependencies=[Depends(auth)])
def get_document(doc_id: int):
    with db.conn() as c:
        r = c.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
    if not r:
        raise HTTPException(404, "not found")
    return _row(r)


class ReviewIn(BaseModel):
    approve: bool
    reviewer: str = "reviewer"
    corrected: dict | None = None


@app.post("/documents/{doc_id}/review", dependencies=[Depends(auth)])
def review(doc_id: int, body: ReviewIn):
    try:
        result = pipeline.review(doc_id, body.approve, body.reviewer, body.corrected)
    except LookupError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(409, str(e))
    return {"result": result, "document": get_document(doc_id)}


class LabelIn(BaseModel):
    actual: dict
    reviewer: str = "reviewer"


@app.post("/documents/{doc_id}/label", dependencies=[Depends(auth)])
def label(doc_id: int, body: LabelIn):
    try:
        return {"agree": pipeline.label(doc_id, body.actual, body.reviewer)}
    except LookupError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(409, str(e))


DOC_TYPES = ["expense_claim", "leave_request", "purchase_request", "inquiry"]


@app.get("/autonomy", dependencies=[Depends(auth)])
def autonomy_status():
    return autonomy.evaluate(DOC_TYPES)


class ModeIn(BaseModel):
    mode: str


@app.post("/autonomy/{doc_type}/mode", dependencies=[Depends(auth)])
def set_mode(doc_type: str, body: ModeIn):
    if doc_type not in DOC_TYPES:
        raise HTTPException(404, "unknown doc_type")
    try:
        autonomy.set_mode(doc_type, body.mode)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return autonomy.status(doc_type)


@app.get("/metrics", dependencies=[Depends(auth)])
def metrics():
    with db.conn() as c:
        calls = c.execute(
            "SELECT COUNT(*) n, COALESCE(SUM(ok),0) ok, COALESCE(SUM(cost_usd),0) cost, "
            "COALESCE(AVG(latency_ms),0) avg_ms, COALESCE(SUM(input_tokens),0) tin, "
            "COALESCE(SUM(output_tokens),0) tout FROM llm_calls").fetchone()
        by_status = {r["status"]: r["n"] for r in c.execute(
            "SELECT status, COUNT(*) n FROM documents GROUP BY status")}
        p95 = [r["latency_ms"] for r in c.execute(
            "SELECT latency_ms FROM llm_calls ORDER BY latency_ms")]
    total = sum(by_status.values())
    return {
        "documents": by_status,
        "auto_processed_rate": round(by_status.get("processed", 0) / total, 3) if total else 0,
        "llm_calls": calls["n"], "llm_success_rate": round(calls["ok"] / calls["n"], 3) if calls["n"] else 0,
        "avg_latency_ms": round(calls["avg_ms"]), "p95_latency_ms": p95[int(len(p95) * .95) - 1] if p95 else 0,
        "tokens_in": calls["tin"], "tokens_out": calls["tout"],
        "total_cost_usd": round(calls["cost"], 4),
        "prompt_version": config.PROMPT_VERSION,
    }


@app.get("/erp/records", dependencies=[Depends(auth)])
def erp_records():
    with db.conn() as c:
        return [dict(r) | {"payload": json.loads(r["payload"])}
                for r in c.execute("SELECT * FROM erp_records ORDER BY id DESC LIMIT 100")]


@app.get("/")
def index():
    return FileResponse(Path(__file__).parent / "static" / "index.html")
