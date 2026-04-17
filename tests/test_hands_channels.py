"""Tests for messaging channel backends."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.hands.types import IncomingMessage, SendResult


class TestSharedTypes:
    def test_send_result_success(self):
        r = SendResult(success=True, message="Sent", channel="telegram")
        assert r.success is True
        assert r.message == "Sent"
        assert r.channel == "telegram"

    def test_send_result_failure(self):
        r = SendResult(success=False, message="Failed", channel="discord")
        assert r.success is False
        assert r.channel == "discord"

    def test_incoming_message_fields(self):
        now = datetime.now(timezone.utc)
        m = IncomingMessage(
            text="hello",
            sender="user123",
            channel="slack",
            timestamp=now,
            raw={"ts": "123.456"},
        )
        assert m.text == "hello"
        assert m.sender == "user123"
        assert m.channel == "slack"
        assert m.timestamp == now
        assert m.raw == {"ts": "123.456"}

    def test_incoming_message_default_raw(self):
        now = datetime.now(timezone.utc)
        m = IncomingMessage(
            text="hi",
            sender="bob",
            channel="telegram",
            timestamp=now,
        )
        assert m.raw == {}
