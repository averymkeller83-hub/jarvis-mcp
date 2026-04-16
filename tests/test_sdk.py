"""Tests for the Agent SDK framework."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from src.sdk.context import SharedContext, ScopedContext
from src.sdk.events import EventBus


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
