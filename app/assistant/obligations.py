"""One definition of a notice that obliges the reader to do something by a deadline.

Used by BOTH sides so they cannot drift apart: the briefing must surface such a notice as a todo (even if the model overlooked it), and
"관련 없음" must refuse to hide it (assistant/mute.py). Found by the one-week simulation: the rule said "필수" only, so "11/27 17시까지 제출해 주세요"
(a deadline without the word 필수) was neither surfaced nor protected, and a model that skipped a mandatory notice was never corrected.
"""
import re

_MANDATORY = re.compile(r"필수|(마감|까지|기한|이내).{0,14}(제출|이수|신청|회신|등록|완료)|(제출|이수|신청|회신|등록).{0,14}(마감|까지|기한)")
DUE = re.compile(r"(오늘 중|금일 \d{1,2}시까지|\d{1,2}월 \d{1,2}일까지|\d{1,2}/\d{1,2}(?:\([월화수목금토일]\))?\s*(?:\d{1,2}시)?까지|[월화수목금]요일까지|\d{1,2}시까지)")


def is_obligation(source: str, title: str, body: str = "") -> bool:
    return source == "notice" and bool(_MANDATORY.search(f"{title} {body}"))


def due_text(title: str, body: str = ""):
    m = DUE.search(f"{title} {body}")
    return m.group(1) if m else None
