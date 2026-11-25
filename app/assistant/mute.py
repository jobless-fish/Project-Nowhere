"""Closing the feedback loop: "관련 없음" becomes a personal rule, safely.

What a click should do
  - immediately and only for THAT person: similar items (same kind of message) stop coming back as todos;
  - never rewrite rules for everyone from one click (a single user, a mistake or an attacker could poison the assistant);
  - several people muting the same kind of item is a signal: it appears in the admin console as a CANDIDATE for a human to review;
  - some things cannot be hidden: mandatory notices with a deadline, money/performance signals and P1/P2 issues assigned to you. The click is
    refused with the reason (an employee who already did the training presses "확인했어요" instead).

A "kind of item" is its signature: source + title with numbers, Re:/Fwd:, dates and punctuation removed.
"""
import re

from .. import db
from .obligations import is_obligation

SIGNAL_PREFIXES = ("[갱신]", "[예산]", "[실적]", "[재무]")
_NOISE = re.compile(r"^(re|fwd?|회신|답장)\s*:\s*|\d+|[^\w가-힣]+", re.I)


def signature(source: str, title: str) -> str:
    return f"{source}|{re.sub(r'\s+', ' ', _NOISE.sub(' ', title.lower())).strip()}"[:160]


def sig_of(item) -> str:
    return signature(item.source, item.title)


def guard_reason(source: str, title: str, body: str = "", severity: str | None = None, mine: bool = False) -> str | None:
    """Why this item may not be hidden, or None. Works on what the briefing payload knows (source, title, body)."""
    text = f"{title} {body}"
    if source == "notice" and title.startswith(SIGNAL_PREFIXES):
        return "회사의 숫자(계약 갱신·예산·실적·재무)에서 나온 알림이라 숨길 수 없어요. 처리했다면 '확인했어요'를 눌러 주세요."
    if is_obligation(source, title, body):
        return "마감이 있는 필수 공지라 숨길 수 없어요. 이미 마쳤다면 '확인했어요'를 눌러 기록을 남겨 주세요."
    if source == "issue" and severity in ("P1", "P2") and mine:
        return "내가 맡은 P1·P2 이슈라 숨길 수 없어요. 처리하거나 '해결'로 바꿔 주세요."
    return None


def muted(user_id: str) -> set[str]:
    with db.conn() as c:
        return {r["sig"] for r in c.execute("SELECT sig FROM todo_mute WHERE user_id=?", (user_id,))}


def add(user_id: str, sig: str, title: str, source: str):
    with db.conn() as c:
        c.execute("INSERT OR REPLACE INTO todo_mute(user_id,sig,title,source) VALUES(?,?,?,?)", (user_id, sig, title[:120], source))


def remove(user_id: str, sig: str) -> bool:
    with db.conn() as c:
        return c.execute("DELETE FROM todo_mute WHERE user_id=? AND sig=?", (user_id, sig)).rowcount > 0


def listing(user_id: str) -> list[dict]:
    with db.conn() as c:
        return [dict(r) for r in c.execute("SELECT sig, title, source, created_at FROM todo_mute WHERE user_id=? ORDER BY created_at DESC", (user_id,))]


def personalize(user_id: str, items: list, hidden: set[str] | None = None) -> list:
    """Drop what this person told us they do not want. Guarded items are never dropped, whatever the table says."""
    hidden = muted(user_id) if hidden is None else hidden
    if not hidden:
        return items
    return [i for i in items if sig_of(i) not in hidden
            or guard_reason(i.source, i.title, i.body, getattr(i, "severity", None), getattr(i, "assignee", None) == user_id)]


def candidates(min_users: int = 2) -> list[dict]:
    """Kinds of items several different people hid: material for a human to review, never applied automatically."""
    with db.conn() as c:
        rows = c.execute("SELECT sig, MIN(title) title, MIN(source) source, COUNT(DISTINCT user_id) users FROM todo_mute GROUP BY sig HAVING users >= ? ORDER BY users DESC, sig", (min_users,)).fetchall()
    return [dict(r) for r in rows]
