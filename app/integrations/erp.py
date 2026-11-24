"""ERP connector. Posts to ERP_URL if set, otherwise writes to the built-in mock ERP table."""
import json
import os

import httpx

from .. import db

KIND = {
    "expense_claim": "accounting/expense",
    "leave_request": "hr/leave",
    "purchase_request": "procurement/order",
    "inquiry": "cs/ticket",
}


def push(doc_type: str, payload: dict) -> str:
    kind = KIND[doc_type]
    url = os.getenv("ERP_URL")
    if url:
        r = httpx.post(f"{url.rstrip('/')}/{kind}", json=payload, timeout=10)
        r.raise_for_status()
        return f"{kind}#{r.json().get('id', '?')}"
    with db.conn() as c:
        cur = c.execute("INSERT INTO erp_records(kind,payload) VALUES(?,?)",
                        (kind, json.dumps(payload, ensure_ascii=False)))
        return f"{kind}#{cur.lastrowid}"
