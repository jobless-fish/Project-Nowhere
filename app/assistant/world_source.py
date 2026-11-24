"""Connector for the company's own systems (mail server, messenger, tracker, portal) over HTTP.
Permissions are enforced by those systems with the *user's own token*; the assistant never sees more
than the user could open themselves."""
import time
from datetime import datetime

from .sources import Item, User

PAGE = 50


class WorldSource:
    def __init__(self, http, password: str = "demo1234"):
        self.http, self.password = http, password
        self._tokens: dict[str, tuple[str, float]] = {}

    def users(self) -> list[User]:
        r = self.http.get("/sso/users")
        r.raise_for_status()
        return [User(u["id"], u["name"], u["role"], u["team"]) for u in r.json()]

    def _headers(self, user: User) -> dict:
        tok, exp = self._tokens.get(user.id, ("", 0))
        if time.time() > exp - 60:  # real systems: OAuth refresh token per user, kept encrypted
            r = self.http.post("/sso/token", json={"user_id": user.id, "password": self.password})
            r.raise_for_status()
            j = r.json()
            tok, exp = j["access_token"], time.time() + j["expires_in"]
            self._tokens[user.id] = (tok, exp)
        return {"Authorization": f"Bearer {tok}"}

    def _get(self, user, path, **params):
        r = self.http.get(path, params=params, headers=self._headers(user))
        r.raise_for_status()
        return r.json()

    def _paged(self, user, path, hours):
        offset, out = 0, []
        while offset is not None:
            j = self._get(user, path, hours=hours, limit=PAGE, offset=offset)
            out += j["items"]
            offset = j["next_offset"]
        return out

    @staticmethod
    def _hours(ts: str) -> float:
        return round((datetime.now() - datetime.fromisoformat(ts)).total_seconds() / 3600, 1)

    def fetch(self, user: User, hours: int = 24) -> list[Item]:
        mine, items = [user.id], []
        for m in self._paged(user, "/mail/inbox", hours):
            items.append(Item(f"mail-{m['id']}", "mail", m["subject"], m["body"], m["from"]["name"],
                              self._hours(m["ts"]), mine, external=m["external"]))
        for i in self._get(user, "/tracker/issues", hours=max(hours, 48))["items"]:
            items.append(Item(f"iss-{i['id']}", "issue", i["title"], i["body"], i["key"], self._hours(i["ts"]),
                              mine, assignee=i["assignee"]))
        for n in self._get(user, "/portal/notices", hours=72)["items"]:
            items.append(Item(f"ntc-{n['id']}", "notice", n["title"], n["body"], "공지", self._hours(n["ts"]), mine))
        for p in self._get(user, "/portal/posts", hours=72)["items"]:
            items.append(Item(f"post-{p['id']}", "post", p["title"], p["body"], "게시판", self._hours(p["ts"]), mine))
        for ch in self._get(user, "/chat/channels"):
            for m in self._paged(user, f"/chat/channels/{ch['id']}/messages", hours):
                items.append(Item(f"msg-{m['id']}", "chat", f"#{ch['name']}: {m['text'][:30]}", m["text"],
                                  m["author"]["name"], self._hours(m["ts"]), mine))
        return [i for i in items if i.hours_ago <= max(hours, 72)]

    def gold(self, user_id: str) -> set:
        from world.store import GOLD
        return set(GOLD.get(user_id, []))
