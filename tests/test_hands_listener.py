"""Tests for the unified message listener."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.hands.listener import MessageListener, CHANNEL_REGISTRY, _load_communication_config
from src.hands.types import IncomingMessage


class TestChannelRegistry:
    def test_all_channels_present(self):
        assert set(CHANNEL_REGISTRY.keys()) == {
            "imessage", "telegram", "discord", "slack", "email",
        }

    def test_poll_intervals_are_positive(self):
        for ch, info in CHANNEL_REGISTRY.items():
            assert info["poll_interval"] > 0, f"{ch} has non-positive interval"


class TestMessageListenerInit:
    def test_default_response_fn(self):
        ml = MessageListener()
        assert ml.response_fn is not None
        assert ml.running is False

    def test_custom_response_fn(self):
        async def my_fn(msg: str) -> str:
            return "ok"
        ml = MessageListener(response_fn=my_fn)
        assert ml.response_fn is my_fn

    @pytest.mark.asyncio
    async def test_default_response_echoes(self):
        ml = MessageListener()
        result = await ml.response_fn("hello")
        assert result == "Echo: hello"


class TestMessageListenerStartStop:
    @pytest.mark.asyncio
    async def test_start_sets_running(self):
        with patch("src.hands.listener._load_communication_config", return_value={
            "channels": {"enabled": []},
        }):
            ml = MessageListener()
            await ml.start()
            assert ml.running is True
            await ml.stop()
            assert ml.running is False

    @pytest.mark.asyncio
    async def test_start_ignores_macos_notifications(self):
        with patch("src.hands.listener._load_communication_config", return_value={
            "channels": {"enabled": ["macos_notifications", "telegram"]},
            "telegram": {"bot_token": "t", "chat_id": "c"},
        }):
            ml = MessageListener()
            # Patch the poll loop to avoid real polling
            ml._poll_loop = AsyncMock()
            await ml.start()
            # Only telegram task created, not macos_notifications
            assert len(ml._tasks) == 1
            await ml.stop()

    @pytest.mark.asyncio
    async def test_start_idempotent(self):
        with patch("src.hands.listener._load_communication_config", return_value={
            "channels": {"enabled": []},
        }):
            ml = MessageListener()
            await ml.start()
            await ml.start()  # second call should be a no-op
            assert ml.running is True
            await ml.stop()

    @pytest.mark.asyncio
    async def test_stop_clears_tasks(self):
        with patch("src.hands.listener._load_communication_config", return_value={
            "channels": {"enabled": []},
        }):
            ml = MessageListener()
            await ml.start()
            await ml.stop()
            assert ml._tasks == []


class TestMessageListenerPolling:
    @pytest.mark.asyncio
    async def test_poll_channel_telegram(self):
        ml = MessageListener()
        msg = IncomingMessage(
            text="hi", sender="user", channel="telegram",
            timestamp=datetime.now(timezone.utc),
            raw={"update_id": 42},
        )
        with patch("src.hands.telegram.poll", new_callable=AsyncMock, return_value=[msg]):
            result = await ml._poll_channel("telegram", {"bot_token": "t", "chat_id": "c"})
            assert len(result) == 1
            assert result[0].text == "hi"
            assert ml._last_seen["telegram"] == 42

    @pytest.mark.asyncio
    async def test_poll_channel_discord(self):
        ml = MessageListener()
        msg = IncomingMessage(
            text="hey", sender="avery", channel="discord",
            timestamp=datetime.now(timezone.utc),
            raw={"id": "200"},
        )
        with patch("src.hands.discord_bot.poll", new_callable=AsyncMock, return_value=[msg]):
            result = await ml._poll_channel("discord", {"bot_token": "t"})
            assert len(result) == 1
            assert ml._last_seen["discord"] == "200"

    @pytest.mark.asyncio
    async def test_poll_channel_slack(self):
        ml = MessageListener()
        msg = IncomingMessage(
            text="sup", sender="U123", channel="slack",
            timestamp=datetime.now(timezone.utc),
            raw={"ts": "999.000"},
        )
        with patch("src.hands.slack_bot.poll", new_callable=AsyncMock, return_value=[msg]):
            result = await ml._poll_channel("slack", {"bot_token": "t"})
            assert len(result) == 1
            assert ml._last_seen["slack"] == "999.000"

    @pytest.mark.asyncio
    async def test_poll_channel_unknown_returns_empty(self):
        ml = MessageListener()
        result = await ml._poll_channel("carrier_pigeon", {})
        assert result == []


class TestMessageListenerHandleMessage:
    @pytest.mark.asyncio
    async def test_handle_message_sends_response(self):
        async def echo(msg: str) -> str:
            return f"Reply: {msg}"

        ml = MessageListener(response_fn=echo)
        msg = IncomingMessage(
            text="ping", sender="user", channel="telegram",
            timestamp=datetime.now(timezone.utc),
        )
        with patch.object(ml, "_send_response", new_callable=AsyncMock) as mock_send:
            await ml._handle_message("telegram", {"bot_token": "t"}, msg)
            mock_send.assert_called_once_with("telegram", {"bot_token": "t"}, "Reply: ping")

    @pytest.mark.asyncio
    async def test_handle_message_error_in_response_fn(self):
        async def bad_fn(msg: str) -> str:
            raise ValueError("boom")

        ml = MessageListener(response_fn=bad_fn)
        msg = IncomingMessage(
            text="test", sender="user", channel="slack",
            timestamp=datetime.now(timezone.utc),
        )
        with patch.object(ml, "_send_response", new_callable=AsyncMock) as mock_send:
            await ml._handle_message("slack", {}, msg)
            # Should send fallback error message
            mock_send.assert_called_once()
            sent_text = mock_send.call_args[0][2]
            assert "error" in sent_text.lower()


class TestNotificationsUpdate:
    """Test that notifications.py can load channel configs and dispatch."""

    def test_load_channel_config_missing_file(self):
        from src.engine.notifications import _load_channel_config
        with patch("src.engine.notifications.CONFIG_DIR", MagicMock()):
            with patch("src.engine.notifications.CONFIG_DIR.__truediv__") as mock_div:
                mock_path = MagicMock()
                mock_path.exists.return_value = False
                mock_div.return_value = mock_path
                result = _load_channel_config("telegram")
                assert result is None

    @pytest.mark.asyncio
    async def test_send_notification_silent(self):
        from src.engine.notifications import Notification, send_notification
        n = Notification(
            event_type="test_event",
            title="Test",
            body="Testing",
            channels=["silent"],
        )
        result = await send_notification(n)
        assert "silent" in result["sent_to"]
