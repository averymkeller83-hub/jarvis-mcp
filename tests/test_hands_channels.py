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


# ── Telegram ────────────────────────────────────────────────────────

from src.hands.telegram import send as telegram_send, poll as telegram_poll, test_connection as telegram_test


def _mock_httpx_client(mock_response):
    """Helper: return a patched httpx.AsyncClient context manager."""
    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.get.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


def _ok_response(data, status=200):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = data
    r.raise_for_status = MagicMock()
    return r


def _err_response(status=401):
    r = MagicMock()
    r.status_code = status
    r.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(str(status), request=MagicMock(), response=r)
    )
    return r


class TestTelegramBackend:
    CONF = {"bot_token": "123456:ABC-DEF", "chat_id": "987654"}

    @pytest.mark.asyncio
    async def test_send_success(self):
        resp = _ok_response({"ok": True, "result": {"message_id": 1}})
        with patch("src.hands.telegram.httpx.AsyncClient") as MC:
            mc = _mock_httpx_client(resp)
            MC.return_value = mc
            result = await telegram_send(self.CONF, "Hello")
            assert result.success is True
            assert result.channel == "telegram"
            assert "sendMessage" in mc.post.call_args[0][0]

    @pytest.mark.asyncio
    async def test_send_failure(self):
        resp = _err_response(401)
        with patch("src.hands.telegram.httpx.AsyncClient") as MC:
            MC.return_value = _mock_httpx_client(resp)
            result = await telegram_send(self.CONF, "Hello")
            assert result.success is False

    @pytest.mark.asyncio
    async def test_poll_returns_messages(self):
        resp = _ok_response({
            "ok": True,
            "result": [{
                "update_id": 100,
                "message": {
                    "message_id": 1,
                    "from": {"id": 111, "first_name": "Avery"},
                    "chat": {"id": 987654},
                    "date": 1713300000,
                    "text": "Hey JARVIS",
                },
            }],
        })
        with patch("src.hands.telegram.httpx.AsyncClient") as MC:
            MC.return_value = _mock_httpx_client(resp)
            msgs = await telegram_poll(self.CONF, last_update_id=99)
            assert len(msgs) == 1
            assert msgs[0].text == "Hey JARVIS"
            assert msgs[0].channel == "telegram"

    @pytest.mark.asyncio
    async def test_poll_empty(self):
        resp = _ok_response({"ok": True, "result": []})
        with patch("src.hands.telegram.httpx.AsyncClient") as MC:
            MC.return_value = _mock_httpx_client(resp)
            assert await telegram_poll(self.CONF) == []

    @pytest.mark.asyncio
    async def test_connection_success(self):
        resp = _ok_response({"ok": True, "result": {"username": "jarvis_bot"}})
        with patch("src.hands.telegram.httpx.AsyncClient") as MC:
            MC.return_value = _mock_httpx_client(resp)
            assert await telegram_test("123456:ABC-DEF") is True

    @pytest.mark.asyncio
    async def test_connection_failure(self):
        resp = _err_response(401)
        with patch("src.hands.telegram.httpx.AsyncClient") as MC:
            MC.return_value = _mock_httpx_client(resp)
            assert await telegram_test("bad") is False


# ── Discord ─────────────────────────────────────────────────────────

from src.hands.discord_bot import send as discord_send, poll as discord_poll, test_connection as discord_test


class TestDiscordBackend:
    CONF = {"bot_token": "MTIz.abc", "server_id": "111", "channel_id": "444"}

    @pytest.mark.asyncio
    async def test_send_success(self):
        resp = _ok_response({"id": "789", "content": "Hello"})
        with patch("src.hands.discord_bot.httpx.AsyncClient") as MC:
            mc = _mock_httpx_client(resp)
            MC.return_value = mc
            result = await discord_send(self.CONF, "Hello")
            assert result.success is True
            assert result.channel == "discord"
            assert "444" in mc.post.call_args[0][0]

    @pytest.mark.asyncio
    async def test_send_failure(self):
        resp = _err_response(401)
        with patch("src.hands.discord_bot.httpx.AsyncClient") as MC:
            MC.return_value = _mock_httpx_client(resp)
            result = await discord_send(self.CONF, "Hello")
            assert result.success is False

    @pytest.mark.asyncio
    async def test_poll_returns_messages(self):
        resp = _ok_response([
            {
                "id": "100",
                "content": "Hey JARVIS",
                "author": {"username": "avery", "bot": False},
                "timestamp": "2026-04-16T12:00:00+00:00",
            }
        ])
        with patch("src.hands.discord_bot.httpx.AsyncClient") as MC:
            MC.return_value = _mock_httpx_client(resp)
            msgs = await discord_poll(self.CONF, last_message_id="99")
            assert len(msgs) == 1
            assert msgs[0].text == "Hey JARVIS"
            assert msgs[0].channel == "discord"

    @pytest.mark.asyncio
    async def test_poll_skips_bot_messages(self):
        resp = _ok_response([
            {
                "id": "100",
                "content": "Bot reply",
                "author": {"username": "jarvis", "bot": True},
                "timestamp": "2026-04-16T12:00:00+00:00",
            }
        ])
        with patch("src.hands.discord_bot.httpx.AsyncClient") as MC:
            MC.return_value = _mock_httpx_client(resp)
            msgs = await discord_poll(self.CONF)
            assert msgs == []

    @pytest.mark.asyncio
    async def test_connection_success(self):
        resp = _ok_response({"id": "123", "username": "jarvis"})
        with patch("src.hands.discord_bot.httpx.AsyncClient") as MC:
            MC.return_value = _mock_httpx_client(resp)
            assert await discord_test("MTIz.abc") is True

    @pytest.mark.asyncio
    async def test_connection_failure(self):
        resp = _err_response(401)
        with patch("src.hands.discord_bot.httpx.AsyncClient") as MC:
            MC.return_value = _mock_httpx_client(resp)
            assert await discord_test("bad") is False


# ── Slack ───────────────────────────────────────────────────────────

from src.hands.slack_bot import send as slack_send, poll as slack_poll, test_connection as slack_test


class TestSlackBackend:
    CONF = {"bot_token": "xoxb-123", "channel_id": "C01234"}

    @pytest.mark.asyncio
    async def test_send_success(self):
        resp = _ok_response({"ok": True, "ts": "123.456"})
        with patch("src.hands.slack_bot.httpx.AsyncClient") as MC:
            MC.return_value = _mock_httpx_client(resp)
            result = await slack_send(self.CONF, "Hello")
            assert result.success is True
            assert result.channel == "slack"

    @pytest.mark.asyncio
    async def test_send_failure_api_error(self):
        resp = _ok_response({"ok": False, "error": "channel_not_found"})
        with patch("src.hands.slack_bot.httpx.AsyncClient") as MC:
            MC.return_value = _mock_httpx_client(resp)
            result = await slack_send(self.CONF, "Hello")
            assert result.success is False
            assert "channel_not_found" in result.message

    @pytest.mark.asyncio
    async def test_poll_returns_messages(self):
        resp = _ok_response({
            "ok": True,
            "messages": [
                {"text": "Hey JARVIS", "user": "U123", "ts": "1713300000.000"},
            ],
        })
        with patch("src.hands.slack_bot.httpx.AsyncClient") as MC:
            MC.return_value = _mock_httpx_client(resp)
            msgs = await slack_poll(self.CONF, oldest_ts="0")
            assert len(msgs) == 1
            assert msgs[0].text == "Hey JARVIS"
            assert msgs[0].channel == "slack"

    @pytest.mark.asyncio
    async def test_poll_skips_bot_messages(self):
        resp = _ok_response({
            "ok": True,
            "messages": [
                {"text": "Bot reply", "bot_id": "B123", "ts": "123.456"},
            ],
        })
        with patch("src.hands.slack_bot.httpx.AsyncClient") as MC:
            MC.return_value = _mock_httpx_client(resp)
            assert await slack_poll(self.CONF) == []

    @pytest.mark.asyncio
    async def test_connection_success(self):
        resp = _ok_response({"ok": True, "user": "jarvis"})
        with patch("src.hands.slack_bot.httpx.AsyncClient") as MC:
            MC.return_value = _mock_httpx_client(resp)
            assert await slack_test("xoxb-123") is True

    @pytest.mark.asyncio
    async def test_connection_failure(self):
        resp = _ok_response({"ok": False, "error": "invalid_auth"})
        with patch("src.hands.slack_bot.httpx.AsyncClient") as MC:
            MC.return_value = _mock_httpx_client(resp)
            assert await slack_test("bad") is False


# ── Email ───────────────────────────────────────────────────────────

import smtplib

from src.hands.email_client import send as email_send, poll as email_poll, test_connection as email_test


class TestEmailBackend:
    CONF = {
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "username": "user@gmail.com",
        "password": "app-password",
        "imap_host": "imap.gmail.com",
        "recipient": "user@gmail.com",
    }

    @pytest.mark.asyncio
    async def test_send_success(self):
        with patch("src.hands.email_client.smtplib.SMTP") as MockSMTP:
            mock_server = MagicMock()
            MockSMTP.return_value.__enter__ = MagicMock(return_value=mock_server)
            MockSMTP.return_value.__exit__ = MagicMock(return_value=False)
            result = await email_send(self.CONF, "Hello from JARVIS")
            assert result.success is True
            assert result.channel == "email"

    @pytest.mark.asyncio
    async def test_send_failure(self):
        with patch("src.hands.email_client.smtplib.SMTP") as MockSMTP:
            MockSMTP.return_value.__enter__ = MagicMock(
                side_effect=smtplib.SMTPAuthenticationError(535, b"Bad credentials")
            )
            MockSMTP.return_value.__exit__ = MagicMock(return_value=False)
            result = await email_send(self.CONF, "Hello")
            assert result.success is False

    @pytest.mark.asyncio
    async def test_connection_smtp_fail(self):
        with patch("src.hands.email_client.smtplib.SMTP") as MockSMTP:
            MockSMTP.return_value.__enter__ = MagicMock(
                side_effect=ConnectionError("refused")
            )
            MockSMTP.return_value.__exit__ = MagicMock(return_value=False)
            assert await email_test(self.CONF) is False
