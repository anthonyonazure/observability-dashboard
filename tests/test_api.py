"""API smoke tests + ingest endpoint contract."""

from __future__ import annotations

import asyncio
import importlib
import os
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def client():
    tmp = Path(tempfile.mkdtemp()) / "agentlog_test.db"
    os.environ["AGENTLOG_DATABASE_URL"] = f"sqlite+aiosqlite:///{tmp}"
    import agentlog.db

    importlib.reload(agentlog.db)
    import agentlog.api

    importlib.reload(agentlog.api)
    asyncio.run(agentlog.db.init_db())
    yield TestClient(agentlog.api.app)
    tmp.unlink(missing_ok=True)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_ingest_then_dashboard_shows_run(client):
    body = {
        "id": uuid.uuid4().hex[:10],
        "agent": "test-agent",
        "started_at": datetime.now(UTC).isoformat(),
        "duration_ms": 1234,
        "status": "ok",
        "summary": "did a thing",
        "metrics": {"foo": "bar"},
        "cost_usd": 0.0123,
        "tokens_in": 1000,
        "tokens_out": 200,
    }
    r = client.post("/v1/runs", json=body)
    assert r.status_code == 200, r.text

    # Dashboard renders
    page = client.get("/?window=24")
    assert page.status_code == 200
    assert "test-agent" in page.text
    assert "did a thing" in page.text


def test_agent_detail_renders(client):
    r = client.get("/agent/test-agent")
    assert r.status_code == 200
    assert "test-agent" in r.text
