"""Colleagues who answer. When the signed-in person writes a chat message or a mail, up to MAX_REPLIES simulated coworkers
reply, in character (rank, department, relationship to the sender) and a few seconds later.

Who may answer is decided HERE, in code (channel members / mail recipients, ranked by relationship). A language model, when one is
plugged in through `llm_hook`, only chooses wording for those candidates; its output is validated (known candidate, no links,
at most MAX_REPLIES) and the rule-based replies take over if it fails. Replies are queued with a delivery time and appear when
the clients next read (store.deliver_due), so the chat shows "typing" first.
"""
import os
import random
import re
import threading
import zlib

MAX_REPLIES = 3
URL = re.compile(r"https?://\S+|www\.\S+|\S+@\S+\.\S+", re.I)
llm_hook = None           # set by server.py when a real model is configured: fn(payload: dict) -> dict | None
SYNC = False              # tests: run the (LLM) work inline instead of in a thread

DL = ["오늘 중", "내일 오전까지", "금요일까지", "오후 중"]
GREET = ("안녕", "반갑", "좋은 아침")
THANKS = ("감사", "고마")
SOCIAL = ("점심", "식사", "커피", "회식", "퇴근", "주말", "저녁")
REPORT = ("완료", "마쳤", "끝냈", "공유드립니다", "보고", "정리했", "올렸", "전달드립니다")
REQUEST = ("부탁", "해 주", "해주", "요청", "가능할까", "주실 수", "주세요", "필요합니다", "확인 바랍니다")
QUESTION = ("?", "어떻게", "언제", "어디", "무엇", "뭐", "왜", "가능한가")

DEPT_ANSWERS = {
    "eng": ["제가 알기로는 로그부터 확인해 보면 좋겠어요. 같이 볼까요?", "배포 이력부터 보면 원인이 좁혀질 것 같아요.", "재현 조건 알려주시면 바로 확인해 볼게요."],
    "sales": ["고객사 쪽 일정부터 확인해 볼게요.", "견적 시트 최신 버전 확인해서 공유드릴게요.", "해당 건은 담당자에게 먼저 물어볼게요."],
    "insurance": ["청구 번호 알려주시면 심사 상태 확인해 드릴게요.", "약관 기준으로는 확인이 필요해서 다시 알려드릴게요."],
    "center": ["고객 응대 이력부터 확인해 볼게요.", "상담 기록 먼저 찾아볼게요."],
    "support": ["규정부터 확인해 보고 답드릴게요.", "담당자에게 먼저 물어보고 알려드릴게요."],
    "legal": ["관련 조항을 확인해서 의견 드리겠습니다."],
    "product": ["유저 인터뷰 기록 기준으로는 이렇게 보고 있어요. 정리해서 알려드릴게요.", "스펙 문서에 정리해 둔 내용이 있어요. 위치 알려드릴게요."],
    "marketing": ["캠페인 성과 기준으로 보면 비슷한 수준이에요. 자료 정리해서 드릴게요."],
    "strategy": ["분기 목표 기준으로 한번 보고 알려드릴게요."],
}
DEFAULT_ANSWERS = ["잘 모르겠어요. 확인해 보고 알려드릴게요.", "저도 확인이 필요해요. 알아보고 말씀드릴게요."]


def classify(text: str) -> str:
    t = text.strip()
    if any(k in t for k in REQUEST):
        return "request"
    if any(k in t for k in QUESTION):
        return "question"
    if any(k in t for k in THANKS):
        return "thanks"
    if any(k in t for k in REPORT):
        return "report"
    if any(k in t for k in SOCIAL):
        return "social"
    if any(k in t for k in GREET):
        return "greeting"
    return "other"


def _rnd(*parts) -> random.Random:
    return random.Random(zlib.crc32("|".join(map(str, parts)).encode()))


def formal(p: dict) -> bool:
    return p["position"] != "팀원" or p["grade"] in ("이사", "C-level")


def _scale() -> float:
    try:
        return float(os.getenv("NPC_DELAY_SCALE", "1"))
    except ValueError:
        return 1.0


def mentioned(store, text: str, members: list) -> list:
    out = [p for p in members if p["name"] in text or f"@{p['name'][1:]}" in text]
    return out


def candidates(store, sender: dict, pool: list, text: str, rnd) -> list:
    """Possible responders, best first: mentioned > the sender's own lead > same unit > same department > everyone else."""
    pool = [p for p in pool if p["id"] != sender["id"] and p["status"] == "재직"]
    ment = mentioned(store, text, pool)
    lead = next((p for p in pool if p["id"] == sender.get("manager_id")), None)

    def rank(p):
        return (0 if p in ment else 1 if p is lead else 2 if p["unit"] == sender["unit"] else 3 if p["dept_key"] == sender["dept_key"] else 4, rnd.random())
    return sorted(pool, key=rank)[:6]


def reply_text(r: dict, sender: dict, intent: str, topic: str, rnd) -> str:
    who = sender["name"][1:] + "님"
    dl = rnd.choice(DL)
    if intent == "request":
        pick = ["확인했습니다. {dl} 처리하도록 하겠습니다.", "알겠습니다. 우선순위 정리해서 회신드리겠습니다.", "네, 바로 챙겨보겠습니다."] if formal(r) else \
               ["네, {dl} 확인해서 알려드릴게요.", "알겠어요. 먼저 살펴보고 공유드릴게요.", "확인했어요! {topic} 오늘 안에 볼게요."]
    elif intent == "question":
        pick = DEPT_ANSWERS.get(r["dept_key"], DEFAULT_ANSWERS)
    elif intent == "report":
        pick = ["수고하셨어요. 확인했습니다.", "잘 마무리됐네요. 고생 많았어요.", "확인했습니다. 다음 단계 있으면 알려주세요."] if formal(r) else ["수고하셨어요!", "오 고생했어요. 확인할게요."]
    elif intent == "thanks":
        pick = ["별말씀을요.", "도움이 됐다니 다행이에요."]
    elif intent == "social":
        pick = ["좋아요, 같이 가요!", "저도 괜찮아요. 몇 시에 볼까요?", "오늘은 일정이 있어서 다음에 같이 해요."]
    elif intent == "greeting":
        pick = ["안녕하세요! 좋은 하루예요.", "네, 안녕하세요."]
    else:
        pick = ["네, 확인했어요.", "알겠습니다."] if formal(r) else ["네 확인했어요!", "오케이, 알겠어요."]
    text = rnd.choice(pick).format(dl=dl, topic=topic, who=who)
    return text


def plan_rules(store, kind: str, sender: dict, pool: list, text: str, subject: str, seed) -> list:
    """-> [{'from': id, 'text': str, 'followup': bool}] with at most MAX_REPLIES entries."""
    rnd = _rnd(*seed)
    intent = classify(text)
    cands = candidates(store, sender, pool, text, rnd)
    if not cands:
        return []
    topic = f"'{(subject or text)[:16]}' 건"
    if kind == "dm":
        n = 1
    elif kind == "chat":
        ment = [c for c in cands if c in mentioned(store, text, cands)]
        base = {"question": 2, "request": 2, "report": 1, "social": 3, "greeting": 2, "thanks": 1}.get(intent, 1)
        n = len(ment) if ment else rnd.randint(max(1, base - 1), base)
    else:  # mail
        n = {"request": 3, "question": 2, "report": 1}.get(intent, 1 if rnd.random() < 0.4 else 0)
        n = min(n, len([c for c in cands if c["id"] in pool_ids(pool)]))
    n = max(0, min(n, MAX_REPLIES, len(cands)))
    out = []
    for r in cands[:n]:
        out.append({"from": r["id"], "text": reply_text(r, sender, intent, topic, rnd), "followup": False})
    # a lead who just received a report sometimes asks for one more thing: work keeps flowing (mail only)
    if kind == "mail" and intent == "report" and out and len(out) < MAX_REPLIES:
        lead = cands[0]
        if formal(lead) and rnd.random() < 0.6:
            out.append({"from": lead["id"], "followup": True, "text": f"{sender['name'][1:]}님, 보고 잘 받았어요. 추가로 핵심 수치만 한 장으로 요약해서 {rnd.choice(DL)} 회신 부탁드립니다."})
    return out[:MAX_REPLIES]


def pool_ids(pool):
    return {p["id"] for p in pool}


def validate_llm(raw, cands: list) -> list:
    ids = {c["id"] for c in cands}
    out, seen = [], set()
    for r in (raw or {}).get("replies", []) if isinstance(raw, dict) else []:
        if not isinstance(r, dict) or r.get("from") not in ids or r["from"] in seen:
            continue
        txt = URL.sub("", str(r.get("text", ""))).strip()[:220]
        if txt:
            seen.add(r["from"])
            out.append({"from": r["from"], "text": txt, "followup": False})
    return out[:MAX_REPLIES]


def _enqueue(store, plans, make):
    t = store.now()
    for i, p in enumerate(plans[:MAX_REPLIES]):
        t += (2.0 + 0.05 * len(p["text"]) + 0.8 * i) * _scale()
        store.pending.append({"due": t, **make(p)})


def respond(store, kind: str, sender: dict, pool: list, text: str, *, subject: str = "", channel: str = "", mail_id: str = "", history=None, external=None) -> int:
    """Schedule the replies. Returns how many are (or will be) coming; clients see 'typing' while store.generating > 0."""
    seed = (sender["id"], text, kind, channel or mail_id)

    def make_chat(p):
        return {"kind": "chat", "channel": channel, "author": p["from"], "text": p["text"]}

    def make_mail(p):
        return {"kind": "mail", "sender": p["from"], "to": [sender["id"]], "subject": ("추가 요청: " + subject[:30]) if p["followup"] else "Re: " + subject.removeprefix("Re: "),
                "body": p["text"] + f"\n\n{store.users[p['from']]['name']} 드림", "thread": mail_id}

    plans = plan_rules(store, kind, sender, pool, text, subject, seed) if not (external and not pool) else []
    if external and not pool:   # a message to someone outside the company: one polite, non-committal automatic acknowledgement
        nm, em = external
        _enqueue(store, [{"from": "ext", "text": "메일 잘 받았습니다. 내부 검토 후 회신드리겠습니다.", "followup": False}],
                 lambda p: {"kind": "mail", "sender": None, "external": em, "external_name": nm, "to": [sender["id"]], "subject": "Re: " + subject.removeprefix("Re: "), "body": p["text"], "thread": mail_id})
        return 1
    make = make_chat if kind in ("chat", "dm") else make_mail
    if llm_hook is None:
        _enqueue(store, plans, make)
        return len(plans)

    cands = candidates(store, sender, pool, text, _rnd(*seed))
    payload = {"kind": kind, "sender": {"name": sender["name"], "title": sender["title"], "dept": sender["dept"]}, "text": text, "subject": subject,
               "history": history or [], "max_replies": MAX_REPLIES,
               "candidates": [{"id": c["id"], "name": c["name"], "title": c["title"], "dept": c["dept"], "position": c["position"], "formal": formal(c)} for c in cands]}

    def work():
        try:
            got = validate_llm(llm_hook(payload), cands)
        except Exception:
            got = []
        if not got:
            got = plans
        _enqueue(store, got, make)
        store.generating -= 1

    store.generating += 1
    if SYNC:
        work()
    else:
        threading.Thread(target=work, daemon=True).start()
    return len(plans)
