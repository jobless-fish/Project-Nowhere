"""One deployable process: the Nowhere company systems, the assistant API and the built web app on a single port.

    /            built web app (web/dist)        /api/...    assistant + document pipeline
    /world/...   company systems (SSO, mail, chat, tracker, portal, HR)

Components still talk to each other over real HTTP (loopback), exactly like they would across hosts,
so permissions, tokens and the signed clock-in webhook behave the same as in the split deployment.
Run:  uvicorn server:combined --port 8000       (PORT env is honoured by the Docker image)
"""
import os
from contextlib import asynccontextmanager
from pathlib import Path

PORT = os.getenv("PORT", "8000")
# Defaults for a self-contained demo. Every one can be overridden from the environment.
os.environ.setdefault("SOURCE", "world")
os.environ.setdefault("WORLD_URL", f"http://127.0.0.1:{PORT}/world")
os.environ.setdefault("ASSISTANT_URL", f"http://127.0.0.1:{PORT}/api")
os.environ.setdefault("LLM_PROVIDER", "mock")      # no key, no cost; set LLM_PROVIDER=openai|claude for a real model
os.environ.setdefault("DEFAULT_MODE", "auto")
os.environ.setdefault("DOCFLOW_DB", os.getenv("DOCFLOW_DB", "/tmp/nowhere.db"))

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


combined = FastAPI(title="Project Nowhere", lifespan=lifespan, docs_url=None, redoc_url=None)
combined.mount("/api", assistant_app)
combined.mount("/world", world_app)
if DIST.exists():
    combined.mount("/", StaticFiles(directory=DIST, html=True), name="web")
