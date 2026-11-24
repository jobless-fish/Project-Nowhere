"""Tiny stand-in for the company IdP. Real deployments: OIDC/SAML SSO; tokens are verified by each service."""
import base64
import hashlib
import hmac
import json
import os
import time

from fastapi import Header, HTTPException

from .store import store


def _secret() -> bytes:
    return os.getenv("WORLD_SECRET", "dev-only-secret").encode()


def sign(sub: str, ttl: int = 3600) -> str:
    body = base64.urlsafe_b64encode(json.dumps({"sub": sub, "exp": int(time.time()) + ttl}).encode()).decode()
    return f"{body}.{hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()}"


def current_user(authorization: str | None = Header(default=None)):
    try:
        scheme, token = (authorization or "").split(" ", 1)
        body, sig = token.rsplit(".", 1)
        ok = scheme.lower() == "bearer" and hmac.compare_digest(
            sig, hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest())
        claims = json.loads(base64.urlsafe_b64decode(body))
        if not ok or claims["exp"] < time.time() or claims["sub"] not in store.users:
            raise ValueError
    except Exception:
        raise HTTPException(401, "invalid or expired token")
    return store.users[claims["sub"]]
