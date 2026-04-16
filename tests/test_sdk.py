"""Tests for the Agent SDK framework."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from src.sdk.base import AgentConfig, BaseAgent, trigger
from src.sdk.context import SharedContext, ScopedContext
from src.sdk.events import EventBus
from src.sdk.loader import discover_agents
from src.sdk.permissions import (
    VALID_PERMISSIONS,
    approve_agent,
    is_approved,
    load_permissions,
    save_permissions,
    validate_permissions,
)


# ── EventBus ────────────────────────────────────────────────────────


@pytest.fixture
def bus() -> EventBus:
    return EventBus()


@pytest.mark.asyncio
async def test_subscribe_and_emit(bus: EventBus):
    handler = AsyncMock()
    bus.subscribe("test_event", handler)
    await bus.emit("test_event", {"key": "value"}, source="test")
    handler.assert_called_once()
    call_data = handler.call_args[0][0]
    assert call_data["key"] == "value"
    assert call_data["_source"] == "test"
    assert "_timestamp" in call_data


@pytest.mark.asyncio
async def test_emit_no_subscribers(bus: EventBus):
    await bus.emit("nobody_listens", {"x": 1}, source="test")


@pytest.mark.asyncio
async def test_multiple_subscribers(bus: EventBus):
    h1 = AsyncMock()
    h2 = AsyncMock()
    bus.subscribe("multi", h1)
    bus.subscribe("multi", h2)
    await bus.emit("multi", {}, source="test")
    h1.assert_called_once()
    h2.assert_called_once()


@pytest.mark.asyncio
async def test_failed_subscriber_does_not_block(bus: EventBus):
    failing = AsyncMock(side_effect=RuntimeError("boom"))
    succeeding = AsyncMock()
    bus.subscribe("fragile", failing)
    bus.subscribe("fragile", succeeding)
    await bus.emit("fragile", {}, source="test")
    succeeding.assert_called_once()


@pytest.mark.asyncio
async def test_unsubscribe(bus: EventBus):
    handler = AsyncMock()
    bus.subscribe("evt", handler)
    bus.unsubscribe("evt", handler)
    await bus.emit("evt", {}, source="test")
    handler.assert_not_called()


def test_list_subscriptions(bus: EventBus):
    h1 = AsyncMock()
    h2 = AsyncMock()
    bus.subscribe("alpha", h1)
    bus.subscribe("beta", h2)
    subs = bus.list_subscriptions()
    assert "alpha" in subs
    assert "beta" in subs


# ── SharedContext ────────────────────────────────────────────────────


@pytest.fixture
def ctx(tmp_path: Path) -> SharedContext:
    return SharedContext(store_path=tmp_path / "agent_context.toml")


@pytest.mark.asyncio
async def test_set_and_get(ctx: SharedContext):
    await ctx.set("agent.key", "hello")
    assert await ctx.get("agent.key") == "hello"


@pytest.mark.asyncio
async def test_get_default(ctx: SharedContext):
    assert await ctx.get("missing.key", default=42) == 42


@pytest.mark.asyncio
async def test_delete(ctx: SharedContext):
    await ctx.set("agent.temp", "value")
    assert await ctx.delete("agent.temp") is True
    assert await ctx.get("agent.temp") is None


@pytest.mark.asyncio
async def test_delete_nonexistent(ctx: SharedContext):
    assert await ctx.delete("nope.nope") is False


@pytest.mark.asyncio
async def test_list_keys(ctx: SharedContext):
    await ctx.set("scout.finds", [1, 2])
    await ctx.set("scout.count", 2)
    await ctx.set("briefing.time", "07:00")
    keys = await ctx.list(prefix="scout.")
    assert sorted(keys) == ["scout.count", "scout.finds"]


@pytest.mark.asyncio
async def test_clear_namespace(ctx: SharedContext):
    await ctx.set("old.a", 1)
    await ctx.set("old.b", 2)
    await ctx.set("keep.c", 3)
    removed = await ctx.clear_namespace("old")
    assert removed == 2
    assert await ctx.get("old.a") is None
    assert await ctx.get("keep.c") == 3


@pytest.mark.asyncio
async def test_persistence(tmp_path: Path):
    path = tmp_path / "agent_context.toml"
    ctx1 = SharedContext(store_path=path)
    await ctx1.set("agent.persist", "yes")

    ctx2 = SharedContext(store_path=path)
    assert await ctx2.get("agent.persist") == "yes"


# ── ScopedContext ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_scoped_write_adds_prefix(tmp_path: Path):
    ctx = SharedContext(store_path=tmp_path / "ctx.toml")
    scoped = ScopedContext(ctx, namespace="myagent")
    await scoped.set("result", {"score": 95})
    assert await ctx.get("myagent.result") == {"score": 95}


@pytest.mark.asyncio
async def test_scoped_rejects_foreign_namespace(tmp_path: Path):
    ctx = SharedContext(store_path=tmp_path / "ctx.toml")
    scoped = ScopedContext(ctx, namespace="myagent")
    with pytest.raises(PermissionError):
        await scoped.set("other.secret", "nope")


@pytest.mark.asyncio
async def test_scoped_read_any_namespace(tmp_path: Path):
    ctx = SharedContext(store_path=tmp_path / "ctx.toml")
    await ctx.set("foreign.data", "visible")
    scoped = ScopedContext(ctx, namespace="myagent")
    assert await scoped.get("foreign.data") == "visible"


# ── Permissions ─────────────────────────────────────────────────────


def test_valid_permissions_is_complete():
    expected = {
        "web_requests", "send_notifications", "read_calendar",
        "read_reminders", "read_contacts", "file_read", "file_write",
        "execute_control", "shell_exec",
    }
    assert VALID_PERMISSIONS == expected


def test_validate_permissions_all_valid():
    assert validate_permissions(["web_requests", "file_read"]) == []


def test_validate_permissions_returns_invalid():
    result = validate_permissions(["web_requests", "fly_to_moon"])
    assert result == ["fly_to_moon"]


def test_load_permissions_empty(tmp_path: Path):
    perms = load_permissions(tmp_path / "agent_permissions.toml")
    assert perms == {}


def test_save_and_load_permissions(tmp_path: Path):
    path = tmp_path / "agent_permissions.toml"
    data = {
        "scout": {
            "approved": True,
            "permissions": ["web_requests"],
            "approved_at": "2026-04-16T12:00:00Z",
        }
    }
    save_permissions(path, data)
    loaded = load_permissions(path)
    assert loaded["scout"]["approved"] is True


def test_is_approved(tmp_path: Path):
    path = tmp_path / "agent_permissions.toml"
    data = {
        "scout": {"approved": True, "permissions": ["web_requests"]},
        "shady": {"approved": False, "permissions": ["shell_exec"]},
    }
    save_permissions(path, data)
    perms = load_permissions(path)
    assert is_approved(perms, "scout") is True
    assert is_approved(perms, "shady") is False
    assert is_approved(perms, "unknown") is False


def test_approve_agent(tmp_path: Path):
    path = tmp_path / "agent_permissions.toml"
    data = {"pending": {"approved": False, "permissions": ["web_requests"]}}
    save_permissions(path, data)
    approve_agent(path, "pending")
    loaded = load_permissions(path)
    assert loaded["pending"]["approved"] is True
    assert "approved_at" in loaded["pending"]


# ── BaseAgent + @trigger ────────────────────────────────────────────


class DummyAgent(BaseAgent):
    config = AgentConfig(
        name="dummy",
        description="A test agent",
        permissions=["web_requests"],
        schedule="0 9 * * *",
    )

    @trigger("scheduled")
    async def run_scheduled(self) -> dict:
        return {"ran": True}

    @trigger("user_invoked")
    async def run_manual(self, params: dict) -> dict:
        return {"params": params}

    @trigger("event", event="test_event")
    async def on_test(self, event_data: dict) -> dict:
        return {"received": event_data.get("_source")}


def test_agent_config_fields():
    assert DummyAgent.config.name == "dummy"
    assert DummyAgent.config.permissions == ["web_requests"]
    assert DummyAgent.config.schedule == "0 9 * * *"
    assert DummyAgent.config.version == "0.1.0"


def test_trigger_metadata():
    meta = getattr(DummyAgent.run_scheduled, "_trigger_meta", None)
    assert meta is not None
    assert meta["type"] == "scheduled"

    meta2 = getattr(DummyAgent.run_manual, "_trigger_meta", None)
    assert meta2["type"] == "user_invoked"

    meta3 = getattr(DummyAgent.on_test, "_trigger_meta", None)
    assert meta3["type"] == "event"
    assert meta3["event"] == "test_event"


@pytest.mark.asyncio
async def test_agent_emit(tmp_path: Path):
    bus = EventBus()
    ctx = SharedContext(store_path=tmp_path / "ctx.toml")
    agent = DummyAgent()
    agent.context = ScopedContext(ctx, namespace="dummy")
    agent._event_bus = bus

    received = []
    bus.subscribe("ping", lambda data: received.append(data))
    await agent.emit("ping", {"msg": "hello"})
    assert len(received) == 1
    assert received[0]["msg"] == "hello"
    assert received[0]["_source"] == "dummy"


@pytest.mark.asyncio
async def test_agent_lifecycle_hooks(tmp_path: Path):
    class LifecycleAgent(BaseAgent):
        config = AgentConfig(name="lc", description="test", permissions=[])
        started = False
        stopped = False

        async def on_start(self) -> None:
            self.started = True

        async def on_stop(self) -> None:
            self.stopped = True

    agent = LifecycleAgent()
    agent.context = ScopedContext(
        SharedContext(store_path=tmp_path / "ctx.toml"), namespace="lc"
    )
    agent._event_bus = EventBus()
    await agent.on_start()
    assert agent.started is True
    await agent.on_stop()
    assert agent.stopped is True


# ── Loader ──────────────────────────────────────────────────────────


def test_discover_agents_empty_dir(tmp_path: Path):
    agents = discover_agents([tmp_path])
    assert agents == []


def test_discover_agents_finds_agent(tmp_path: Path):
    agent_file = tmp_path / "my_agent.py"
    agent_file.write_text(
        "from src.sdk.base import AgentConfig, BaseAgent, trigger\n"
        "\n"
        "class MyAgent(BaseAgent):\n"
        "    config = AgentConfig(\n"
        "        name='my_agent',\n"
        "        description='test',\n"
        "        permissions=[],\n"
        "    )\n"
        "\n"
        "    @trigger('user_invoked')\n"
        "    async def run_now(self, params: dict) -> dict:\n"
        "        return {'ok': True}\n"
    )
    agents = discover_agents([tmp_path])
    assert len(agents) == 1
    assert agents[0].config.name == "my_agent"


def test_discover_agents_skips_non_agent_files(tmp_path: Path):
    (tmp_path / "util.py").write_text("x = 1\n")
    (tmp_path / "__init__.py").write_text("")
    agents = discover_agents([tmp_path])
    assert agents == []


def test_discover_agents_skips_broken_files(tmp_path: Path):
    (tmp_path / "broken.py").write_text("raise RuntimeError('nope')\n")
    agents = discover_agents([tmp_path])
    assert agents == []


def test_discover_agents_multiple_dirs(tmp_path: Path):
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    dir_a.mkdir()
    dir_b.mkdir()
    (dir_a / "agent_a.py").write_text(
        "from src.sdk.base import AgentConfig, BaseAgent, trigger\n"
        "class AgentA(BaseAgent):\n"
        "    config = AgentConfig(name='a', description='A', permissions=[])\n"
        "    @trigger('user_invoked')\n"
        "    async def run(self, params): return {}\n"
    )
    (dir_b / "agent_b.py").write_text(
        "from src.sdk.base import AgentConfig, BaseAgent, trigger\n"
        "class AgentB(BaseAgent):\n"
        "    config = AgentConfig(name='b', description='B', permissions=[])\n"
        "    @trigger('user_invoked')\n"
        "    async def run(self, params): return {}\n"
    )
    agents = discover_agents([dir_a, dir_b])
    names = {a.config.name for a in agents}
    assert names == {"a", "b"}
