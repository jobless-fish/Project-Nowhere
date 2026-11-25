"""Groupware access control: who may see which document, and the walls between departments.

Two things matter most and both are enforced HERE, in code, before anything reaches a response:

1. SEARCH never leaks. The permission check runs BEFORE matching, ranking and paging, so a document the person may not open
   contributes nothing: no row, no snippet, no highlighted word, no "N results hidden", no change in the number of pages.
   Searching for the exact title of a hidden document looks identical to searching for a word that does not exist.
   Opening a hidden document by id answers 404 (not 403), so even its existence is not confirmed.
2. DEPARTMENT BARRIERS ("information walls"): for the pairs in BARRIERS, people of one side cannot see anything OWNED by the other side,
   whatever else says "allowed" (a barrier is a deny and a deny always wins), except the oversight group (CEO, compliance team), and every use
   of that exemption is written to the audit log.

Decision order for (person, document): explicit deny > barrier > owner's own department > grants in the document's audience > default deny.
Everything that was refused on purpose goes to the audit log, which only oversight people can read; the person who was refused learns nothing from it.
"""
from __future__ import annotations

# Pairs of departments (dept_key) that must not see each other's documents. Edit here; the tests read this list.
BARRIERS: list[tuple[str, str]] = [
    ("insurance", "sales"),      # underwriting / claims independence from sales
    ("strategy", "marketing"),   # M&A, IR and budget work is non-public until announced
    ("strategy", "sales"),
]
OVERSIGHT_IDS = {"u_ceo"}
OVERSIGHT_UNITS = {"컴플라이언스팀"}      # the audit function may look across walls (and is logged when it does)

WALLED = {d for pair in BARRIERS for d in pair}
AUDIT: list[dict] = []                     # reset with the world


def reset():
    AUDIT.clear()


def blocked_pair(a: str, b: str) -> bool:
    return any({a, b} == {x, y} for x, y in BARRIERS) if a != b else False


def exempt(user: dict) -> bool:
    return user["id"] in OVERSIGHT_IDS or user.get("unit") in OVERSIGHT_UNITS


def _grant(user: dict, g: str) -> bool:
    kind, _, ref = g.partition(":")
    return (g == "all" or (kind == "dept" and user["dept_key"] == ref) or (kind == "unit" and user["unit"] == ref)
            or (kind == "team" and user["team"] == ref) or (kind == "role" and user["role"] == ref) or (kind == "user" and user["id"] == ref))


def decide(user: dict, doc: dict) -> tuple[bool, str]:
    """-> (allowed, reason). `reason` is for the audit log / oversight explanation only, never for the person who is refused."""
    if any(_grant(user, g) for g in doc.get("deny", [])):
        return False, "explicit deny"
    owner = doc.get("owner")
    if owner in WALLED and exempt(user):
        return True, "barrier exempt (oversight)"           # the audit function can read what is behind any wall; each use is logged by the caller
    if owner and blocked_pair(user["dept_key"], owner):
        return False, f"department barrier {user['dept_key']} | {owner}"
    if owner and owner == user["dept_key"]:
        return True, "owner department"
    if any(_grant(user, g) for g in doc.get("audience", [])):
        return True, "granted"
    return False, "not in audience"


def visible(user: dict, docs: list[dict]) -> list[dict]:
    """The ONLY way search and listings get documents: filtered first, so nothing hidden can influence what comes after."""
    return [d for d in docs if decide(user, d)[0]]


def log(user: dict, action: str, doc_id: str | None, reason: str, **extra):
    from datetime import datetime
    AUDIT.append({"ts": datetime.now().isoformat(timespec="seconds"), "user": user["id"], "dept": user["dept_key"], "action": action, "doc": doc_id, "reason": reason, **extra})
    del AUDIT[:-2000]
