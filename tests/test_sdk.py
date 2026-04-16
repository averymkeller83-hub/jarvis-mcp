"""Tests for the Agent SDK framework."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

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
