"""Operating history for the demo database: the assistant has already been running for months, so the admin console is not empty.

Seeds (only into an EMPTY demo database, never into a database the user supplied):
  documents        ~150 requests of the last 90 days (expense, leave, purchase, inquiry) with extraction, status, ERP reference and audit trail
  outcomes         human-vs-AI agreement per type and mode: this is what the autonomy ladder is computed from
  modes            where each type stands today (some earned auto, some wait for a promotion approval, one is still collecting)
  llm_calls        one call per document plus a few failures: latency, tokens and cost for the Ops tab
  actions          past reply drafts: sent as is / edited / rejected / blocked
  eval_cases       cases harvested from user feedback
Everything is derived with a fixed seed from the same fictional roster, so it is identical on every machine. It is clearly simulated history of a
fictional company, not measurements.
"""
import json
import random
from datetime import datetime, timedelta

from . import db

NAMES = ["박서연", "김민수", "이정호", "최지우", "정유진", "한도윤", "오세린", "강태양", "윤하늘", "서지안", "배현우", "임수아", "장민재", "조은서", "신예준", "홍다인"]
EXPENSE_ITEMS = [("고객사 방문 교통비", 18000, 90000), ("팀 회식비", 180000, 680000), ("출장 숙박비", 120000, 520000), ("업무용 도서 구매", 15000, 60000),
                 ("교육 수강료", 200000, 900000), ("서버 모니터링 도구 결제", 300000, 880000), ("행사 부스 설치비", 1200000, 2600000), ("고객 선물", 50000, 300000)]
PURCHASE_ITEMS = ["모니터 2대", "노트북 거치대", "사무용 의자", "화상회의 카메라", "스탠딩 데스크", "프린터 토너", "보안 키 20개", "회의실 TV"]
INQUIRIES = ["연차가 몇 일 남았는지 문의드립니다.", "재택근무 신청 절차가 궁금합니다.", "출입증 재발급은 어디서 하나요?", "퇴직연금 가입 방법을 알고 싶어요.",
             "복지포인트 사용처 문의합니다.", "법인카드 분실 시 절차가 어떻게 되나요?"]
# (type, ordered phases [(mode, n_docs, agree_rate)]) -- the last phase is the current mode
LADDER = {"expense_claim": [("shadow", 24, .88), ("assisted", 34, .94), ("auto", 34, .97)],
          "leave_request": [("shadow", 22, .86), ("assisted", 34, .94)],      # assisted, still collecting: needs a lower bound of 0.95
          "purchase_request": [("shadow", 14, .79)],                          # still collecting
          "inquiry": [("shadow", 23, 1.0)],                                   # 23/23: lower bound 0.86 >= 0.85 -> a promotion to assisted waits for approval
          }


def _ts(now, days_ago, rnd):
    t = now - timedelta(days=days_ago, hours=rnd.randint(0, 9), minutes=rnd.randint(0, 59))
    return t.strftime("%Y-%m-%d %H:%M:%S")


def _doc(kind, rnd, i):
    who = rnd.choice(NAMES)
    if kind == "expense_claim":
        item, lo, hi = rnd.choice(EXPENSE_ITEMS)
        amt = int(round(rnd.uniform(lo, hi), -3))
        if i % 17 == 0:
            amt = None
        text = f"{who}입니다. {item} 정산 요청합니다." + (f" 총 {amt // 10000}만원" + (f" {amt % 10000}원" if amt % 10000 else "") if amt else " 금액은 영수증 참고 바랍니다.")
        ex = dict(doc_type=kind, confidence=round(rnd.uniform(.86, .98), 2), summary=text[:60], requester=who, amount=amt, item=item, urgency="normal")
    elif kind == "leave_request":
        d0 = datetime(2026, rnd.randint(8, 12), rnd.randint(1, 26))
        n = rnd.choice([1, 1, 2, 3])
        dates = None if i % 13 == 0 else (d0.strftime("%Y-%m-%d"), (d0 + timedelta(days=n - 1)).strftime("%Y-%m-%d"))
        text = f"{who}입니다. " + (f"{d0.month}월 {d0.day}일부터 {n}일간 연차 신청합니다." if dates else "다음 주에 연차를 쓰고 싶습니다.")
        ex = dict(doc_type=kind, confidence=round(rnd.uniform(.85, .98), 2), summary=text[:60], requester=who, date_from=dates[0] if dates else None, date_to=dates[1] if dates else None, urgency="normal")
    elif kind == "purchase_request":
        item = rnd.choice(PURCHASE_ITEMS)
        amt = None if i % 9 == 0 else int(round(rnd.uniform(80000, 1800000), -4))
        text = f"{who}입니다. {item} 구매 요청드립니다." + (f" 예상 금액 {amt // 10000}만원." if amt else "")
        ex = dict(doc_type=kind, confidence=round(rnd.uniform(.8, .96), 2), summary=text[:60], requester=who, amount=amt, item=item, urgency=rnd.choice(["normal", "normal", "high"]))
    else:
        text = f"{who}입니다. " + rnd.choice(INQUIRIES)
        ex = dict(doc_type=kind, confidence=round(rnd.uniform(.88, .99), 2), summary=text[:60], requester=who, urgency="low")
    return text, ex


def _status(kind, ex, mode, rnd):
    """Same guardrails as app/pipeline.review_reason: what the pipeline would have done at that time."""
    over = kind == "expense_claim" and (ex.get("amount") or 0) > 1_000_000
    missing = (kind in ("expense_claim", "purchase_request") and ex.get("amount") is None) or (kind == "leave_request" and not ex.get("date_from"))
    if over or missing or ex["confidence"] < .8:
        return "needs_review" if rnd.random() < .12 else ("approved" if rnd.random() < .8 else "rejected"), (
            "amount over approval limit" if over else "amount missing" if kind != "leave_request" and missing else "leave request without dates" if missing else "low confidence")
    return ("shadow_done" if mode == "shadow" else "processed"), None


def seed(now: datetime | None = None) -> bool:
    now = now or datetime.now()
    with db.conn() as c:
        if c.execute("SELECT COUNT(*) n FROM documents").fetchone()["n"] or c.execute("SELECT COUNT(*) n FROM modes").fetchone()["n"]:
            return False
    rnd = random.Random(20261124)
    plan = []                                           # (days_ago, kind, mode, agree)
    for kind, phases in LADDER.items():
        total = sum(n for _, n, _ in phases)
        k = 0
        for mode, n, rate in phases:
            wrong = {int(x) for x in rnd.sample(range(n), max(0, round(n * (1 - rate))))}
            for j in range(n):
                plan.append((int(88 - 86 * (k / max(1, total - 1))) + rnd.randint(0, 1), kind, mode, j not in wrong))
                k += 1
    plan.sort(key=lambda p: -p[0])
    with db.conn() as c:
        for i, (days, kind, mode, agree) in enumerate(plan):
            text, ex = _doc(kind, rnd, i)
            status, reason = _status(kind, ex, mode, rnd)
            ts = _ts(now, days, rnd)
            ref = None
            audit = [{"event": "received", "source": "console", "ts": ts}, {"event": "extracted", "doc_type": kind, "confidence": ex["confidence"]}]
            if status in ("processed", "approved"):
                ref = {"expense_claim": "accounting/expense", "leave_request": "hr/leave", "purchase_request": "procurement/po", "inquiry": "helpdesk/ticket"}[kind] + f"#{i + 1}"
                if status == "approved":
                    audit += [{"event": "sent_to_review", "reason": reason}, {"event": "human_approved", "actor": "정유라"}]
                audit.append({"event": "erp_pushed", "ref": ref, "actor": "system"})
            elif status == "shadow_done":
                audit += [{"event": "shadow_proposal", "note": "AI suggestion only; nothing sent to ERP"}, {"event": "shadow_compared", "actor": "정유라", "agree": agree}]
            elif status == "rejected":
                audit += [{"event": "sent_to_review", "reason": reason}, {"event": "rejected", "actor": "정유라"}]
            else:
                audit += [{"event": "sent_to_review", "reason": reason}]
            cur = c.execute("INSERT INTO documents(created_at,source,text,status,extraction,erp_ref,audit) VALUES(?,?,?,?,?,?,?)",
                            (ts, rnd.choice(["console", "mail", "portal"]), text, status, json.dumps(ex, ensure_ascii=False), ref, json.dumps(audit, ensure_ascii=False)))
            did = cur.lastrowid
            c.execute("INSERT INTO outcomes(document_id,doc_type,mode,agree,created_at) VALUES(?,?,?,?,?)", (did, kind, mode, int(agree), ts))
            slow = rnd.random() < .06
            tin, tout = rnd.randint(480, 980), rnd.randint(90, 210)
            ok = 0 if rnd.random() < .015 else 1
            c.execute("INSERT INTO llm_calls(created_at,document_id,provider,model,prompt_version,input_tokens,output_tokens,latency_ms,cost_usd,ok,error) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                      (ts, did, "openai_compat", "gemini-3.5-flash-lite", "v2", tin, tout, rnd.randint(3200, 6800) if slow else rnd.randint(620, 1900),
                       round((tin * .10 + tout * .40) / 1e6, 6), ok, None if ok else "ReadTimeout: The read operation timed out"))
        for kind, phases in LADDER.items():
            c.execute("INSERT OR REPLACE INTO modes(doc_type,mode) VALUES(?,?)", (kind, phases[-1][0]))
        # reply drafts: 24 past drafts, mostly sent as they were -> a promotion to "pre-drafted" waits for approval
        c.execute("INSERT OR REPLACE INTO modes(doc_type,mode) VALUES('reply_internal','assisted')")
        statuses = ["sent"] * 28 + ["sent_edited"] + ["blocked"]       # 28/29 measured: lower bound 0.83 >= 0.80 -> promotion to pre-drafting waits for approval
        rnd.shuffle(statuses)
        for i, st in enumerate(statuses):
            ts = _ts(now, int(80 - i * 2.6), rnd)
            who = rnd.choice(NAMES)
            c.execute("INSERT INTO actions(user_id,day,todo_key,source_id,kind,to_ref,to_name,external,draft_subject,draft_body,final_subject,final_body,status,edited,note,created_at,decided_at) "
                      "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      ("u_dev1", ts[:10], f"seed{i}", f"mail-seed{i}", "reply_internal", "u_dev2", who, 0, "Re: 확인 요청", "확인했습니다. 오늘 중 회신드리겠습니다.",
                       "Re: 확인 요청", "확인했습니다. 오늘 중 회신드리겠습니다." + (" 추가 자료는 내일 전달드릴게요." if st == "sent_edited" else ""),
                       "sent" if st in ("sent", "sent_edited") else st, int(st == "sent_edited"), "민감 표현이 있어 발송을 막았어요." if st == "blocked" else None, ts, ts))
            if st in ("sent", "sent_edited", "rejected"):
                c.execute("INSERT INTO outcomes(document_id,doc_type,mode,agree,created_at) VALUES(?,?,?,?,?)", (0, "reply_internal", "assisted", int(st == "sent"), ts))
        for i, (kind, label, payload) in enumerate([
                ("todo", "negative", {"title": "광고 메일 확인", "reason": "프로모션 문구가 있음"}), ("todo", "negative", {"title": "주간 뉴스레터 읽기", "reason": "알림성 메일"}),
                ("todo", "positive", {"title": "결제 장애 재발 방지 대책 승인", "reason": "P1 이슈, 담당자 본인"}), ("todo", "positive", {"title": "정보보안 교육 이수", "reason": "마감이 있는 필수 공지"}),
                ("reply", "edited", {"subject": "Re: 일정 확인", "edit": "마감일을 구체적으로 적음"}), ("reply", "rejected", {"subject": "Re: 견적 문의", "edit": "금액 표현 삭제 요청"})]):
            c.execute("INSERT OR IGNORE INTO eval_cases(key,kind,label,payload,created_at) VALUES(?,?,?,?,?)", (f"seed:{i}", kind, label, json.dumps(payload, ensure_ascii=False), now.strftime("%Y-%m-%d %H:%M:%S")))
    return True
