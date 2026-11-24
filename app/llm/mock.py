"""Deterministic rule-based stand-in so the demo, tests and CI run without an API key."""
import json
import re
import time
from datetime import date

from .base import LLMClient, LLMResult

KW = {
    "expense_claim": ["경비", "영수증", "정산", "택시", "식대", "출장비"],
    "leave_request": ["휴가", "연차", "반차", "병가"],
    "purchase_request": ["구매", "발주", "구입", "견적"],
    "inquiry": ["문의", "요청드립니다", "알려주세요", "가능한가요"],
}


def _amount(text: str):
    m = re.search(r"(\d[\d,]*)\s*만\s*원", text)
    if m:
        return int(m.group(1).replace(",", "")) * 10000
    m = re.search(r"(\d[\d,]*)\s*원", text)
    return int(m.group(1).replace(",", "")) if m else None


def _dates(text: str):
    ds = re.findall(r"(20\d{2})[-./](\d{1,2})[-./](\d{1,2})", text)
    out = [date(int(y), int(m), int(d)).isoformat() for y, m, d in ds]
    return (out[0] if out else None, out[-1] if out else None)


class MockClient(LLMClient):
    provider = "mock"
    model = "rule-based"

    def complete(self, system: str, user: str) -> LLMResult:
        t0 = time.perf_counter()
        scores = {k: sum(w in user for w in ws) for k, ws in KW.items()}
        best = max(scores, key=scores.get)
        hits = scores[best]
        multi = sum(1 for v in scores.values() if v) > 1
        doc_type = best if hits else "other"
        conf = 0.0 if not hits else min(0.95, 0.6 + 0.15 * hits) - (0.3 if multi else 0)
        d_from, d_to = _dates(user)
        who = re.search(r"([가-힣]{2,4})\s*(?:입니다|드림|올림)", user)
        out = {
            "doc_type": doc_type, "confidence": round(max(conf, 0.2 if not hits else conf), 2),
            "summary": user.strip().splitlines()[0][:60],
            "requester": who.group(1) if who else None,
            "amount": _amount(user), "date_from": d_from, "date_to": d_to,
            "item": None, "urgency": "high" if re.search(r"긴급|급히|오늘 중", user) else "normal",
        }
        text = json.dumps(out, ensure_ascii=False)
        return LLMResult(text, len(user) // 2, len(text) // 2,
                         int((time.perf_counter() - t0) * 1000), self.provider, self.model)
