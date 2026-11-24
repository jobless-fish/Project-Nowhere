import re

# Untrusted text (mail, chat) must never steer the assistant. These checks are code, not prompt.
INJECTION = re.compile(
    r"(이전|위의|앞의|모든)\s*(지시|명령|지침).{0,12}(무시|잊)|ignore\s+(all\s+|any\s+)?(previous|prior)\s+instructions"
    r"|system\s*:|외부로\s*전달|비밀번호를?\s*(알려|전송)", re.I)


def is_suspicious(item) -> bool:
    return bool(INJECTION.search(f"{item.title}\n{item.body}"))


def ground(entries: list[dict], valid_ids: set, banned: set = frozenset()):
    """Keep only entries that cite at least one real source item and none that are banned."""
    kept, dropped = [], 0
    for e in entries:
        ids = [i for i in e.get("source_ids", []) if isinstance(i, str)]
        if not ids or any(i not in valid_ids for i in ids) or any(i in banned for i in ids):
            dropped += 1
            continue
        kept.append({**e, "source_ids": ids})
    return kept, dropped
