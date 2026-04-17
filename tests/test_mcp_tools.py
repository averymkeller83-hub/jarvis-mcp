"""Tests for MCP server messaging tools."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.hands.types import SendResult


class TestMcpMessagingTools:
    """Test the new send_* MCP tools."""

    @pytest.mark.asyncio
    async def test_send_telegram_not_configured(self):
        from src.mcp_server import send_telegram
        with patch("src.mcp_server._load_channel_config", return_value=None):
            result = await send_telegram("hello")
            assert "not configured" in result.lower()

    @pytest.mark.asyncio
    async def test_send_telegram_success(self):
        from src.mcp_server import send_telegram
        conf = {"bot_token": "123:ABC", "chat_id": "999"}
        sr = SendResult(success=True, message="Sent to Telegram", channel="telegram")
        with patch("src.mcp_server._load_channel_config", return_value=conf):
            with patch("src.hands.telegram.send", new_callable=AsyncMock, return_value=sr):
                result = await send_telegram("hello")
                assert "Sent to Telegram" in result

    @pytest.mark.asyncio
    async def test_send_discord_not_configured(self):
        from src.mcp_server import send_discord
        with patch("src.mcp_server._load_channel_config", return_value=None):
            result = await send_discord("hello")
            assert "not configured" in result.lower()

    @pytest.mark.asyncio
    async def test_send_discord_success(self):
        from src.mcp_server import send_discord
        conf = {"bot_token": "MTIz.abc", "channel_id": "444"}
        sr = SendResult(success=True, message="Sent to Discord", channel="discord")
        with patch("src.mcp_server._load_channel_config", return_value=conf):
            with patch("src.hands.discord_bot.send", new_callable=AsyncMock, return_value=sr):
                result = await send_discord("hello")
                assert "Sent to Discord" in result

    @pytest.mark.asyncio
    async def test_send_slack_not_configured(self):
        from src.mcp_server import send_slack
        with patch("src.mcp_server._load_channel_config", return_value=None):
            result = await send_slack("hello")
            assert "not configured" in result.lower()

    @pytest.mark.asyncio
    async def test_send_slack_success(self):
        from src.mcp_server import send_slack
        conf = {"bot_token": "xoxb-123", "channel_id": "C01234"}
        sr = SendResult(success=True, message="Sent to Slack", channel="slack")
        with patch("src.mcp_server._load_channel_config", return_value=conf):
            with patch("src.hands.slack_bot.send", new_callable=AsyncMock, return_value=sr):
                result = await send_slack("hello")
                assert "Sent to Slack" in result

    @pytest.mark.asyncio
    async def test_send_email_not_configured(self):
        from src.mcp_server import send_email
        with patch("src.mcp_server._load_channel_config", return_value=None):
            result = await send_email("hello")
            assert "not configured" in result.lower()

    @pytest.mark.asyncio
    async def test_send_email_success(self):
        from src.mcp_server import send_email
        conf = {"smtp_host": "smtp.gmail.com", "username": "u", "password": "p", "recipient": "r"}
        sr = SendResult(success=True, message="Email sent", channel="email")
        with patch("src.mcp_server._load_channel_config", return_value=conf):
            with patch("src.hands.email_client.send", new_callable=AsyncMock, return_value=sr):
                result = await send_email("hello")
                assert "Email sent" in result

    @pytest.mark.asyncio
    async def test_send_notification_tool_defaults(self):
        from src.mcp_server import send_notification_tool
        with patch("src.engine.notifications.send_notification", new_callable=AsyncMock) as mock_sn:
            mock_sn.return_value = {"sent_to": ["silent"], "event_type": "user_request"}
            result = await send_notification_tool("Test", "Body")
            assert "silent" in result

    @pytest.mark.asyncio
    async def test_send_notification_tool_explicit_channels(self):
        from src.mcp_server import send_notification_tool
        with patch("src.engine.notifications.send_notification", new_callable=AsyncMock) as mock_sn:
            mock_sn.return_value = {"sent_to": ["macos", "telegram"], "event_type": "user_request"}
            result = await send_notification_tool("Alert", "Something happened", "macos,telegram")
            assert "macos" in result
            assert "telegram" in result

    @pytest.mark.asyncio
    async def test_send_notification_tool_no_channels(self):
        from src.mcp_server import send_notification_tool
        with patch("src.engine.notifications.send_notification", new_callable=AsyncMock) as mock_sn:
            mock_sn.return_value = {"sent_to": [], "event_type": "user_request"}
            result = await send_notification_tool("Alert", "Body")
            assert "no channels" in result.lower()
