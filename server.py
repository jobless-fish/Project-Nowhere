"""One deployable process: the Nowhere company systems, the assistant API and the built web app on a single port.

    /            built web app (web/dist)        /api/...    assistant + document pipeline
    /world/...   company systems (SSO, mail, chat, tracker, portal, HR)

Components still talk to each other over real HTTP (loopback), exactly like they would across hosts,
so permissions, tokens and the signed clock-in webhook behave the same as in the split deployment.
Run:  uvicorn server:combined --port 8000       (PORT env is honoured by the Docker image)
"""
import os
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

PORT = os.getenv("PORT", "8000")
# Defaults for a self-contained demo. Every one can be overridden from the environment.
os.environ.setdefault("SOURCE", "world")
# The internal addresses (assistant -> company systems, attendance webhook) must match the port uvicorn really listens on, whatever
# --port the user chose. If the user did not set them, they are learnt from the first request (see AutoAddress below).
_AUTO_ADDR = "WORLD_URL" not in os.environ and "ASSISTANT_URL" not in os.environ
if _AUTO_ADDR:   # best guess until the first request arrives
    os.environ["WORLD_URL"] = f"http://127.0.0.1:{PORT}/world"
    os.environ["ASSISTANT_URL"] = f"http://127.0.0.1:{PORT}/api"
os.environ.setdefault("LLM_PROVIDER", "mock")      # no key, no cost; set LLM_PROVIDER=openai|claude for a real model
os.environ.setdefault("DEFAULT_MODE", "auto")
# Data file: portable default (the OS temp dir; there is no /tmp on Windows). With no DOCFLOW_DB set this is a throw-away DEMO,
# so it starts empty every time. If you set DOCFLOW_DB yourself, that file is never touched or deleted.
if "DOCFLOW_DB" not in os.environ:
    _demo_db = Path(tempfile.gettempdir()) / "nowhere-demo.db"
    for _f in (_demo_db, Path(f"{_demo_db}-wal"), Path(f"{_demo_db}-shm")):
        _f.unlink(missing_ok=True)
    os.environ["DOCFLOW_DB"] = str(_demo_db)

from fastapi import FastAPI  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from app import db  # noqa: E402
from app.main import app as assistant_app  # noqa: E402
from world.main import app as world_app  # noqa: E402

DIST = Path(__file__).parent / "web" / "dist"


@asynccontextmanager
async def lifespan(_):
    db.init()          # mounted sub-apps do not run their own lifespan
    yield


_app = FastAPI(title="Project Nowhere", lifespan=lifespan, docs_url=None, redoc_url=None)
_app.mount("/api", assistant_app)
_app.mount("/world", world_app)
if DIST.exists():
    _app.mount("/", StaticFiles(directory=DIST, html=True), name="web")


class AutoAddress:
    """ASGI wrapper: the server socket address of the first request is the real host:port, so internal calls work on any --port."""

    def __init__(self, app):
        self.app, self.learnt = app, not _AUTO_ADDR

    async def __call__(self, scope, receive, send):
        if not self.learnt and scope["type"] in ("http", "websocket") and scope.get("server") and scope["server"][1]:
            host, port = scope["server"]
            host = "127.0.0.1" if host in ("0.0.0.0", "::", "::1", "localhost") else host
            os.environ["WORLD_URL"] = f"http://{host}:{port}/world"
            os.environ["ASSISTANT_URL"] = f"http://{host}:{port}/api"
            self.learnt = True
        await self.app(scope, receive, send)


combined = AutoAddress(_app)
