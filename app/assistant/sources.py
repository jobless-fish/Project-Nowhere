"""Data sources for the assistant. Real connectors (Exchange/Gmail, Slack, Jira, groupware) implement
the same `Source` interface; permission filtering lives in `can_see` and is applied for every source."""
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

DATA = Path(__file__).with_name("demo_data.json")


@dataclass
class User:
    id: str
    name: str
    role: str   # employee | executive
    team: str


@dataclass
class Item:
    id: str
    source: str          # mail | issue | chat | slack | notice | post
    title: str
    body: str
    sender: str
    hours_ago: float
    visible_to: list
    assignee: str | None = None
    escalated: bool = False        # raised to the executives (the only issues an executive may act on without being the assignee)
    external: bool = False
    reply_to: str | None = None   # user:<id> | ext:<email>; only for mail
    severity: str | None = None   # issues only: P1..P4
    done: bool = False            # already handled in the source system: resolved issue, acknowledged notice


class Source(Protocol):
    def users(self) -> list[User]: ...
    def fetch(self, user: User, hours: int) -> list[Item]: ...


def can_see(user: User, it: Item) -> bool:
    v = set(it.visible_to)
    return bool({"all", f"user:{user.id}", f"role:{user.role}", f"team:{user.team}"} & v) or it.assignee == user.id


class FixtureSource:
    def __init__(self, path: Path = DATA):
        raw = json.loads(path.read_text(encoding="utf-8"))
        self._users = [User(**u) for u in raw["users"]]
        self._raw = raw["items"]

    def users(self):
        return self._users

    def fetch(self, user: User, hours: int = 24):
        items = [Item(**{k: v for k, v in r.items() if k != "gold_for"}) for r in self._raw]
        return [i for i in items if i.hours_ago <= hours and can_see(user, i)]

    def gold(self, user_id: str) -> set:
        """Labelled 'must act' items, used only by the evaluation (never shown to the model)."""
        return {r["id"] for r in self._raw if user_id in r.get("gold_for", [])}


def get_source():
    """SOURCE=fixture (default, offline demo) | world (Nowhere systems at WORLD_URL)."""
    import os
    if os.getenv("SOURCE", "fixture") == "world":
        import httpx
        from .world_source import WorldSource
        return WorldSource(httpx.Client(base_url=os.getenv("WORLD_URL", "http://localhost:9000"), timeout=15))
    return FixtureSource()
