"""Tests for built-in agents (Briefing and Scout)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.agents.briefing import BriefingAgent
from src.agents.scout import ScoutAgent
from src.sdk.context import SharedContext, ScopedContext
from src.sdk.events import EventBus


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def bus() -> EventBus:
    return EventBus()


@pytest.fixture
def ctx(tmp_path: Path) -> SharedContext:
    return SharedContext(store_path=tmp_path / "agent_context.toml")


def _wire_agent(agent, ctx, bus):
    agent.context = ScopedContext(ctx, namespace=agent.config.name)
    agent._event_bus = bus
    return agent


# ── BriefingAgent ───────────────────────────────────────────────────


def test_briefing_agent_config():
    agent = BriefingAgent()
    assert agent.config.name == "briefing"
    assert "read_calendar" in agent.config.permissions
    assert "web_requests" in agent.config.permissions


@pytest.mark.asyncio
async def test_briefing_agent_scheduled(bus, ctx):
    agent = _wire_agent(BriefingAgent(), ctx, bus)

    events_received = []
    bus.subscribe("briefing_composing", lambda d: events_received.append(("composing", d)))
    bus.subscribe("briefing_ready", lambda d: events_received.append(("ready", d)))

    with patch("src.agents.briefing.compose_briefing", new_callable=AsyncMock) as mock_compose:
        from src.briefing.composer import Briefing
        from src.briefing.sections import BriefingSection
        mock_compose.return_value = Briefing(
            sections=[BriefingSection(title="Weather", content="Sunny", empty=False)],
            generated_at="2026-04-16T07:00:00Z",
            summary="1 section",
        )
        result = await agent.compose()

    assert result["section_count"] == 1
    stored = await ctx.get("briefing.last_result")
    assert stored is not None
    assert len(events_received) == 2
    assert events_received[0][0] == "composing"
    assert events_received[1][0] == "ready"


@pytest.mark.asyncio
async def test_briefing_agent_user_invoked(bus, ctx):
    agent = _wire_agent(BriefingAgent(), ctx, bus)

    with patch("src.agents.briefing.compose_briefing", new_callable=AsyncMock) as mock_compose:
        from src.briefing.composer import Briefing
        mock_compose.return_value = Briefing(
            sections=[], generated_at="2026-04-16T07:00:00Z", summary="Nothing"
        )
        result = await agent.run_now({})

    assert result["section_count"] == 0


# ── ScoutAgent ──────────────────────────────────────────────────────


def test_scout_agent_config():
    agent = ScoutAgent()
    assert agent.config.name == "scout"
    assert agent.config.schedule == "0 */4 * * *"
    assert "web_requests" in agent.config.permissions


@pytest.mark.asyncio
async def test_scout_agent_scheduled(bus, ctx):
    agent = _wire_agent(ScoutAgent(), ctx, bus)

    events_received = []
    bus.subscribe("scout_new_finds", lambda d: events_received.append(d))

    with patch("src.agents.scout.run_discovery", new_callable=AsyncMock) as mock_disc:
        mock_disc.return_value = ["card1", "card2"]
        result = await agent.scan()

    assert result["finds_count"] == 2
    assert len(events_received) == 1
    assert events_received[0]["count"] == 2


@pytest.mark.asyncio
async def test_scout_agent_user_invoked(bus, ctx):
    agent = _wire_agent(ScoutAgent(), ctx, bus)

    with patch("src.agents.scout.run_discovery", new_callable=AsyncMock) as mock_disc:
        mock_disc.return_value = []
        result = await agent.run_now({})

    assert result["finds_count"] == 0


# ── API Tests ───────────────────────────────────────────────────────

import httpx
from httpx import ASGITransport

from src.server.app import app


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:7900")


@pytest.mark.asyncio
async def test_get_agents(client: httpx.AsyncClient):
    resp = await client.get("/agents")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["agents"], list)
    assert "count" in data


@pytest.mark.asyncio
async def test_get_agent_detail(client: httpx.AsyncClient):
    resp = await client.get("/agents")
    agents = resp.json()["agents"]
    if agents:
        name = agents[0]["name"]
        resp = await client.get(f"/agents/{name}")
        assert resp.status_code == 200
        assert resp.json()["name"] == name


@pytest.mark.asyncio
async def test_get_agent_not_found(client: httpx.AsyncClient):
    resp = await client.get("/agents/nonexistent_agent_xyz")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_agent_context(client: httpx.AsyncClient):
    resp = await client.get("/agents")
    agents = resp.json()["agents"]
    if agents:
        name = agents[0]["name"]
        resp = await client.get(f"/agents/{name}/context")
        assert resp.status_code == 200
        assert isinstance(resp.json(), dict)


@pytest.mark.asyncio
async def test_get_events(client: httpx.AsyncClient):
    resp = await client.get("/events")
    assert resp.status_code == 200
    data = resp.json()
    assert "subscriptions" in data


@pytest.mark.asyncio
async def test_status_includes_agents(client: httpx.AsyncClient):
    resp = await client.get("/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "agents" in data["services"]
