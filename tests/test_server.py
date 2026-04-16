"""Tests for the Jarvis MCP Core Daemon API."""

from __future__ import annotations

import pytest
import httpx
from httpx import ASGITransport

from src.server.app import app


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:7900")


@pytest.mark.asyncio
async def test_health_returns_ok(client: httpx.AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.1.0"
    assert isinstance(data["uptime_seconds"], (int, float))


@pytest.mark.asyncio
async def test_status_returns_daemon_running(client: httpx.AsyncClient):
    resp = await client.get("/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["daemon"] == "running"
    assert "router" in data["services"]
    assert data["services"]["router"] == "available"


@pytest.mark.asyncio
async def test_route_classifies_chat_message(client: httpx.AsyncClient):
    resp = await client.post("/route", json={"message": "hello there"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["surface"] == "CHAT"
    assert data["intent"] is None


@pytest.mark.asyncio
async def test_route_classifies_control_message(client: httpx.AsyncClient):
    resp = await client.post("/route", json={"message": "set alarm 7am"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["surface"] == "CONTROL"
    assert data["intent"] is not None
    assert data["intent"]["verb"] == "alarm"


@pytest.mark.asyncio
async def test_route_classifies_local_message(client: httpx.AsyncClient):
    resp = await client.post("/route", json={"message": "show me my briefing"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["surface"] == "LOCAL"
    assert data["intent"] is not None
    assert data["intent"]["verb"] == "briefing"


@pytest.mark.asyncio
async def test_briefing_returns_valid_structure(client: httpx.AsyncClient):
    resp = await client.get("/briefing")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["sections"], list)
    assert len(data["sections"]) == 0
    assert "generated_at" in data


@pytest.mark.asyncio
async def test_lessons_returns_valid_structure(client: httpx.AsyncClient):
    resp = await client.get("/lessons")
    assert resp.status_code == 200
    data = resp.json()
    assert data["lessons"] == []
    assert data["count"] == 0


@pytest.mark.asyncio
async def test_lessons_propose(client: httpx.AsyncClient):
    resp = await client.post("/lessons/propose", json={
        "correction": "Use UTC everywhere",
        "context": "Timezone bug in briefing",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "pending_approval"
    assert "draft" in data


@pytest.mark.asyncio
async def test_scout_discover_returns_valid_structure(client: httpx.AsyncClient):
    resp = await client.post("/scout/discover")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["finds"], list)
    assert len(data["finds"]) == 0
    assert "scanned_at" in data


@pytest.mark.asyncio
async def test_scout_install(client: httpx.AsyncClient):
    resp = await client.post("/scout/install", json={"candidate_id": "test-123"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "not_implemented"


@pytest.mark.asyncio
async def test_settings_returns_config(client: httpx.AsyncClient):
    resp = await client.get("/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert "personality" in data
    assert "voice" in data
    assert "behavior" in data
