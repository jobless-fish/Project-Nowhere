"""Read-only Gmail connector: your own inbox becomes the assistant's input.

* Scope is `gmail.readonly` only. There is no send_mail, so the assistant cannot send, delete, label or archive anything.
* Credentials come from environment variables (never files): GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN.
  `python scripts/gmail_auth.py` prints the refresh token once.
* Every mail is treated as external and untrusted text (the injection guard still applies).
* Mail text is sent to the configured LLM provider to build the briefing: use it with your own mailbox, not with other people's data.
"""
import base64
import html
import os
import re
import time

from .sources import Item, User

API = "https://gmail.googleapis.com/gmail/v1/users/me"
TOKEN_URL = "https://oauth2.googleapis.com/token"
QUERY = "in:inbox newer_than:3d -category:promotions -category:social -category:forums"
MAX_MAILS = 40
MAX_BODY = 4000


class GmailError(RuntimeError):
    """A readable reason (sent to the UI), never a token."""


def _b64(data: str) -> str:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", "replace")


def _text(payload: dict) -> str:
    """text/plain if present, else tag-stripped text/html, searched through nested multipart."""
    plain, rich = [], []

    def walk(p):
        mt, data = p.get("mimeType", ""), (p.get("body") or {}).get("data")
        if data and mt == "text/plain":
            plain.append(_b64(data))
        elif data and mt == "text/html":
            rich.append(_b64(data))
        for c in p.get("parts") or []:
            walk(c)
    walk(payload)
    if plain:
        return "\n".join(plain).strip()
    stripped = re.sub(r"(?is)<(script|style).*?</\1>", " ", "\n".join(rich))
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", stripped))).strip()


def _sender(raw: str) -> tuple[str, str]:
    m = re.match(r'\s*"?([^"<]*?)"?\s*<([^>]+)>', raw or "")
    if m:
        return (m.group(1).strip() or m.group(2)), m.group(2).strip().lower()
    return (raw or "").strip(), (raw or "").strip().lower()


class GmailSource:
    def __init__(self, http, client_id=None, client_secret=None, refresh_token=None, name=None):
        self.http = http
        self.cid = client_id or os.getenv("GMAIL_CLIENT_ID", "")
        self.secret = client_secret or os.getenv("GMAIL_CLIENT_SECRET", "")
        self.refresh = refresh_token or os.getenv("GMAIL_REFRESH_TOKEN", "")
        self.name = name or os.getenv("GMAIL_USER_NAME", "나")
        self._tok, self._exp = "", 0.0

    def _token(self) -> str:
        if time.time() < self._exp - 60:
            return self._tok
        if not (self.cid and self.secret and self.refresh):
            raise GmailError("Gmail 연결 정보가 없어요. GMAIL_CLIENT_ID / GMAIL_CLIENT_SECRET / GMAIL_REFRESH_TOKEN 환경변수를 확인해 주세요.")
        r = self.http.post(TOKEN_URL, data={"client_id": self.cid, "client_secret": self.secret, "refresh_token": self.refresh, "grant_type": "refresh_token"})
        if r.status_code != 200:
            raise GmailError("Gmail 인증이 거절됐어요. 새로 인증해야 할 수 있어요(scripts/gmail_auth.py).")
        j = r.json()
        self._tok, self._exp = j["access_token"], time.time() + j.get("expires_in", 3600)
        return self._tok

    def _get(self, path, **params):
        r = self.http.get(API + path, params=params, headers={"Authorization": f"Bearer {self._token()}"})
        if r.status_code == 429:
            raise GmailError("Gmail 요청 한도를 넘었어요. 잠시 뒤 다시 시도해 주세요.")
        if r.status_code in (401, 403):
            raise GmailError("Gmail 읽기 권한이 없어요. gmail.readonly 권한으로 다시 인증해 주세요.")
        r.raise_for_status()
        return r.json()

    def users(self) -> list[User]:
        return [User("me", self.name, "employee", "개인")]

    def fetch(self, user: User, hours: int = 24) -> list[Item]:
        ids = [m["id"] for m in self._get("/messages", q=QUERY, maxResults=MAX_MAILS).get("messages", [])]
        out, now = [], time.time()
        for mid in ids:
            m = self._get(f"/messages/{mid}", format="full")
            h = {x["name"].lower(): x["value"] for x in m.get("payload", {}).get("headers", [])}
            name, addr = _sender(h.get("from", ""))
            age = round((now - int(m.get("internalDate", 0)) / 1000) / 3600, 1)
            if age > max(hours, 72):
                continue
            body = _text(m.get("payload", {})) or m.get("snippet", "")
            out.append(Item(f"mail-{mid}", "mail", h.get("subject", "(제목 없음)"), body[:MAX_BODY], name, age,
                            [user.id], external=True, reply_to=f"ext:{addr}"))
        return out
