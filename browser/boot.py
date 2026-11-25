"""Starts the whole product (company systems + assistant API) INSIDE the browser, in Pyodide, for the GitHub Pages demo.

Same code as the server (`app/`, `world/`); only the plumbing differs because a browser tab has no sockets and no threads:
  * requests arrive from the page's fetch() and are handed to the ASGI apps in-process (asgi_sync.py), the way the combined server does over loopback;
  * background work that the server puts in threads runs inline;
  * the model is the rule-based engine (no key, no cost, nothing leaves the tab); data lives in the tab's memory and is gone on reload.
"""
import os
import secrets
import sys
import types

os.environ.update({"LLM_PROVIDER": "mock", "DEFAULT_MODE": "auto", "SOURCE": "world", "DOCFLOW_DB": "/tmp/nowhere.db",
                   "ASSISTANT_WEBHOOK_SECRET": secrets.token_urlsafe(32)})
sys.path.insert(0, "/srv")

# httpx imports `ssl`; the browser build has no TLS stack and this demo makes no network calls, so a stub is enough.
ssl = types.ModuleType("ssl")


class SSLContext:
    def __init__(self, *a, **k): pass
    def __getattr__(self, n): return lambda *a, **k: None


class SSLError(OSError): pass


ssl.SSLContext, ssl.SSLError = SSLContext, SSLError
ssl.create_default_context = lambda *a, **k: SSLContext()
ssl.SSLZeroReturnError = ssl.SSLWantReadError = ssl.SSLWantWriteError = ssl.SSLSyscallError = ssl.SSLEOFError = SSLError
ssl.CERT_NONE, ssl.CERT_REQUIRED, ssl.PROTOCOL_TLS_CLIENT, ssl.PROTOCOL_TLS = 0, 2, 16, 2
ssl.OP_NO_SSLv2 = ssl.OP_NO_SSLv3 = 0
ssl.HAS_ALPN = False
ssl.SSLSocket = ssl.SSLObject = ssl.MemoryBIO = object
ssl.Purpose = types.SimpleNamespace(SERVER_AUTH=1, CLIENT_AUTH=2)
ssl.TLSVersion = types.SimpleNamespace(TLSv1_2=771)
ssl.VerifyMode = int
sys.modules.setdefault("ssl", ssl)

import asgi_sync  # noqa: E402

asgi_sync._inline_threadpool()

from app import db, seed_history  # noqa: E402
from app.assistant import router as assistant_router  # noqa: E402
from app.assistant.world_source import WorldSource  # noqa: E402
from app.main import app as assistant_app  # noqa: E402
from world import npc, services  # noqa: E402
from world.main import app as world_app  # noqa: E402

npc.SYNC = True                                   # colleagues' replies are produced inline instead of in a thread
services.notify_assistant = lambda user_id: None  # the attendance webhook is a network call; the page calls clock-in itself

world = asgi_sync.SyncClient(world_app)
assistant = asgi_sync.SyncClient(assistant_app)
assistant_router.get_source = lambda: WorldSource(world)
db.init()
seed_history.seed()


def handle(method, url, headers, body):
    """-> (status, [[name, value], ...], body bytes). `url` is the path the page asked for (/api/... or /world/...)."""
    path, _, query = url.partition("?")
    if path.startswith("/api/") or path == "/api":
        client, path = assistant, path[4:] or "/"
    elif path.startswith("/world/") or path == "/world":
        client, path = world, path[6:] or "/"
    else:
        return 404, [], b""
    hdrs = {k: v for k, v in dict(headers).items() if k.lower() not in ("host", "content-length")}
    from urllib.parse import parse_qsl
    r = client.request(method, path, params=dict(parse_qsl(query)) or None, headers=hdrs, content=body.encode() if body else None)
    return r.status_code, [[k, v] for k, v in r.headers.items()], r.content
