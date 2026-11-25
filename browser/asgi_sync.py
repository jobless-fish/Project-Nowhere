"""Run an ASGI app synchronously, in-process, with no threads and no event loop (browser/Pyodide has neither)."""
import json as _json
from urllib.parse import urlsplit

import httpx


def _inline_threadpool():
    import anyio.to_thread, starlette.concurrency as sc, sys
    async def run_sync(func, *args, **kw):
        kw.pop("limiter", None); kw.pop("abandon_on_cancel", None); kw.pop("cancellable", None)
        return func(*args)
    async def run_in_threadpool(func, *args, **kwargs):
        return func(*args, **kwargs)
    anyio.to_thread.run_sync = run_sync
    sc.run_in_threadpool = run_in_threadpool
    for m in list(sys.modules.values()):
        if m and getattr(m, "run_in_threadpool", None) is not None and getattr(m, "__name__", "").startswith(("fastapi", "starlette")):
            m.run_in_threadpool = run_in_threadpool


def drive(coro):
    try:
        while True:
            coro.send(None)          # a coroutine that really waits on I/O would yield a future here
    except StopIteration as e:
        return e.value


class SyncClient:
    """Looks like httpx.Client for the parts WorldSource uses (get/post/patch with params/json/headers)."""
    def __init__(self, app, base=""):
        self.app, self.base = app, base

    def request(self, method, url, params=None, json=None, headers=None, data=None, content=None, **_):
        path = self.base + url
        q = ""
        if params:
            q = str(httpx.QueryParams({k: v for k, v in params.items() if v is not None}))
        body = b""
        hdrs = {k.lower(): v for k, v in (headers or {}).items()}
        if content is not None:
            body = content
        elif json is not None:
            body = _json.dumps(json).encode(); hdrs["content-type"] = "application/json"
        elif data is not None:
            body = httpx.QueryParams(data).__str__().encode(); hdrs["content-type"] = "application/x-www-form-urlencoded"
        scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": method.upper(), "path": path, "raw_path": path.encode(),
                 "query_string": q.encode(), "root_path": "", "scheme": "http", "server": ("app", 80), "client": ("browser", 0),
                 "headers": [(k.encode(), str(v).encode()) for k, v in hdrs.items()] + [(b"host", b"app")]}
        sent, out = False, {"status": 500, "headers": [], "body": b""}

        async def receive():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            return {"type": "http.disconnect"}

        async def send(msg):
            if msg["type"] == "http.response.start":
                out["status"], out["headers"] = msg["status"], msg["headers"]
            elif msg["type"] == "http.response.body":
                out["body"] += msg.get("body", b"")
        drive(self.app(scope, receive, send))
        return httpx.Response(out["status"], headers=[(k.decode(), v.decode()) for k, v in out["headers"]], content=out["body"],
                              request=httpx.Request(method.upper(), "http://app" + path))

    def get(self, url, **kw): return self.request("GET", url, **kw)
    def post(self, url, **kw): return self.request("POST", url, **kw)
    def patch(self, url, **kw): return self.request("PATCH", url, **kw)
    def put(self, url, **kw): return self.request("PUT", url, **kw)
    def delete(self, url, **kw): return self.request("DELETE", url, **kw)
