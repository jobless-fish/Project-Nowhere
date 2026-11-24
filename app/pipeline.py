import json

from pydantic import ValidationError

from . import autonomy, config, db
from .integrations import erp
from .llm import get_client
from .llm.base import parse_json
from .llm.prompts import system_prompt
from .schemas import Extraction

EXPENSE_APPROVAL_LIMIT = 1_000_000  # KRW; above this a human must approve


def review_reason(e: Extraction) -> str | None:
    """Business guardrails applied on top of model confidence."""
    if e.doc_type == "other":
        return "unclassified document"
    if e.confidence < config.CONFIDENCE_THRESHOLD:
        return f"low confidence ({e.confidence:.2f})"
    if e.amount is not None and e.amount < 0:
        return "negative amount"
    if e.doc_type == "expense_claim" and (e.amount or 0) > EXPENSE_APPROVAL_LIMIT:
        return "amount over approval limit"
    if e.doc_type == "leave_request" and not e.date_from:
        return "leave request without dates"
    return None


def extract(text: str, doc_id: int | None = None, client=None) -> Extraction:
    """Run the LLM, validate output against the schema, log cost/latency. Retries once on bad output."""
    client = client or get_client()
    last_err = ""
    for attempt in range(2):
        res, ok, err, ext = None, 0, None, None
        try:
            res = client.complete(system_prompt(config.PROMPT_VERSION), text)
            ext = Extraction(**parse_json(res.text))
            ok = 1
        except (ValueError, ValidationError, json.JSONDecodeError) as ex:
            err = f"invalid output: {ex}"[:300]
        except Exception as ex:  # network / API errors
            err = f"{type(ex).__name__}: {ex}"[:300]
        _log_call(doc_id, client, res, ok, err)
        if ok:
            return ext
        last_err = err
        if err.startswith(("APIError", "APIStatus", "APIConnection")):
            break
    raise RuntimeError(last_err)


def _log_call(doc_id, client, res, ok, err, prompt_version=None):
    cost = 0.0
    if res:
        cost = (res.input_tokens * config.PRICE_IN + res.output_tokens * config.PRICE_OUT) / 1e6
        if res.provider == "mock":
            cost = 0.0
    with db.conn() as c:
        c.execute(
            "INSERT INTO llm_calls(document_id,provider,model,prompt_version,input_tokens,"
            "output_tokens,latency_ms,cost_usd,ok,error) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (doc_id, client.provider, client.model, prompt_version or config.PROMPT_VERSION,
             res.input_tokens if res else 0, res.output_tokens if res else 0,
             res.latency_ms if res else 0, cost, ok, err),
        )


def process(text: str, source: str = "api", client=None) -> int:
    with db.conn() as c:
        doc_id = c.execute("INSERT INTO documents(source,text,status) VALUES(?,?, 'new')",
                           (source, text)).lastrowid
        db.add_audit(c, doc_id, "received", source=source)
    try:
        e = extract(text, doc_id, client)
    except Exception as ex:
        with db.conn() as c:
            c.execute("UPDATE documents SET status='failed' WHERE id=?", (doc_id,))
            db.add_audit(c, doc_id, "extraction_failed", error=str(ex))
        return doc_id

    reason = review_reason(e)
    mode = autonomy.get_mode(e.doc_type)
    if not reason and mode == "assisted":
        reason = "assisted mode: human approves every item"
    elif not reason and mode == "auto" and autonomy.should_sample():
        reason = "audit sample"
    with db.conn() as c:
        c.execute("UPDATE documents SET extraction=? WHERE id=?",
                  (e.model_dump_json(), doc_id))
        db.add_audit(c, doc_id, "extracted", doc_type=e.doc_type, confidence=e.confidence)
        if mode == "shadow" and e.doc_type != "other":
            c.execute("UPDATE documents SET status='shadow' WHERE id=?", (doc_id,))
            db.add_audit(c, doc_id, "shadow_proposal", note="AI suggestion only; nothing sent to ERP")
            return doc_id
        if reason:
            c.execute("UPDATE documents SET status='needs_review' WHERE id=?", (doc_id,))
            db.add_audit(c, doc_id, "sent_to_review", reason=reason)
            return doc_id
    _dispatch(doc_id, e, actor="system")
    return doc_id


def _dispatch(doc_id: int, e: Extraction, actor: str):
    try:
        ref = erp.push(e.doc_type, e.model_dump(exclude={"confidence"}) | {"document_id": doc_id})
    except Exception as ex:
        with db.conn() as c:
            c.execute("UPDATE documents SET status='failed' WHERE id=?", (doc_id,))
            db.add_audit(c, doc_id, "erp_failed", error=str(ex)[:200])
        return
    with db.conn() as c:
        c.execute("UPDATE documents SET status=?, erp_ref=? WHERE id=?",
                  ("processed" if actor == "system" else "approved", ref, doc_id))
        db.add_audit(c, doc_id, "erp_pushed", ref=ref, actor=actor)


def review(doc_id: int, approve: bool, actor: str, corrected: dict | None = None) -> str:
    with db.conn() as c:
        row = c.execute("SELECT status, extraction FROM documents WHERE id=?", (doc_id,)).fetchone()
    if not row:
        raise LookupError("document not found")
    if row["status"] != "needs_review":
        raise ValueError(f"document is {row['status']}, not awaiting review")
    proposed = json.loads(row["extraction"])
    mode = autonomy.get_mode(proposed["doc_type"])
    if not approve:
        autonomy.record_outcome(doc_id, proposed["doc_type"], mode, False)
        with db.conn() as c:
            c.execute("UPDATE documents SET status='rejected' WHERE id=?", (doc_id,))
            db.add_audit(c, doc_id, "rejected", actor=actor)
        return "rejected"
    e = Extraction(**(proposed | (corrected or {})))
    if e.doc_type != "other":
        autonomy.record_outcome(doc_id, proposed["doc_type"], mode,
                                autonomy.agrees(proposed, corrected or {}))
    if e.doc_type == "other":
        raise ValueError("set a concrete doc_type before approving")
    with db.conn() as c:
        c.execute("UPDATE documents SET extraction=? WHERE id=?", (e.model_dump_json(), doc_id))
        db.add_audit(c, doc_id, "human_corrected" if corrected else "human_approved", actor=actor)
    _dispatch(doc_id, e, actor=actor)
    return "approved"


def label(doc_id: int, actual: dict, actor: str) -> bool:
    """Shadow mode: a human handled the item the usual way; compare their result with the AI's proposal."""
    with db.conn() as c:
        row = c.execute("SELECT status, extraction FROM documents WHERE id=?", (doc_id,)).fetchone()
    if not row:
        raise LookupError("document not found")
    if row["status"] != "shadow":
        raise ValueError(f"document is {row['status']}, not a shadow item")
    proposed = json.loads(row["extraction"])
    ok = autonomy.agrees(proposed, actual)
    autonomy.record_outcome(doc_id, proposed["doc_type"], "shadow", ok)
    with db.conn() as c:
        c.execute("UPDATE documents SET status='shadow_done' WHERE id=?", (doc_id,))
        db.add_audit(c, doc_id, "shadow_compared", actor=actor, agree=ok, human=actual)
    return ok
