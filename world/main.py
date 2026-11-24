"""FinBridge internal systems as one ASGI app (each router is an independent system with its own API)."""
from fastapi import FastAPI

from . import services as s

app = FastAPI(title="FinBridge internal systems")
for r in (s.sso, s.mail, s.chat, s.tracker, s.portal, s.hr):
    app.include_router(r)
