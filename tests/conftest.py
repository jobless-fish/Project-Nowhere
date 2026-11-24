import os

import pytest

TEST_WEBHOOK_SECRET = "test-webhook-secret-0123456789"
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.delenv("DOCFLOW_API_KEY", raising=False)
    monkeypatch.delenv("ERP_URL", raising=False)
    from app import config
    monkeypatch.setattr(config, "LLM_PROVIDER", "mock")
    monkeypatch.setattr(config, "DEFAULT_MODE", "auto")
    monkeypatch.setattr(config, "SAMPLE_RATE", 0.0)
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "t.db"))
    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _webhook_secret(monkeypatch):
    """The webhook has no built-in default key, so every test that signs one states its key."""
    monkeypatch.setenv("ASSISTANT_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
