# Onboarding & MCP Server Ready-to-Test Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire up all 6 messaging channels (send + receive), register JARVIS as MCP server in Claude Desktop, auto-import contacts, link Obsidian vault, add voice provider selection, and update the 12-step setup wizard — producing a testable MCP server.

**Architecture:** New channel modules in src/hands/ each export send() and poll() with shared types. A listener service in the ProactiveEngine polls all enabled channels. Setup wizard Steps 3,4,5,9,10 get real implementations. MCP server gains 5 new messaging tools.

**Tech Stack:** Python 3.12, FastAPI, FastMCP, httpx, discord.py, slack-sdk, React/TypeScript/Tailwind

---

## File Structure

| File | Responsibility |
|---|---|
| `src/hands/types.py` | Shared SendResult and IncomingMessage dataclasses |
| `src/hands/telegram.py` | Telegram Bot API send + getUpdates poll |
| `src/hands/discord_bot.py` | Discord REST API send + message poll |
| `src/hands/slack_bot.py` | Slack Web API send + conversations.history poll |
| `src/hands/email_client.py` | SMTP send + IMAP receive |
| `src/hands/messaging.py` | iMessage send (existing) + iMessage poll (new) |
| `src/hands/listener.py` | Unified message listener service |
| `src/engine/notifications.py` | Updated dispatch with all channels |
| `src/mcp_server.py` | 5 new messaging MCP tools |
| `src/voice/tts.py` | Multi-provider TTS dispatch |
| `src/voice/stt.py` | Multi-provider STT dispatch |
| `config/voice.toml` | Voice provider configuration |
| `src/setup/steps.py` | 12-step definitions (remove colima) |
| `src/setup/handlers.py` | Updated handlers for steps 3,4,5,9,10,12 |
| `src/setup/engine.py` | Updated completion check for 12 steps |
| `dashboard/src/pages/Setup.tsx` | Updated 12-step frontend |
| `pyproject.toml` | New dependencies |
| `tests/test_hands_channels.py` | Tests for all channel backends |
| `tests/test_hands_listener.py` | Tests for message listener |
| `tests/test_setup.py` | Updated setup tests for 12 steps |
| `tests/test_mcp_tools.py` | Tests for new MCP tools |
| `tests/test_voice_providers.py` | Tests for multi-provider voice |
| `tests/test_integration_onboarding.py` | Full integration test |

---

### Task 1: Shared Messaging Types

**Files:**
- Create: `src/hands/types.py`
- Test: `tests/test_hands_channels.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_hands_channels.py`:

```python
"""Tests for messaging channel backends."""

from __future__ import annotations

from datetime import datetime, timezone

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_hands_channels.py::TestSharedTypes -x`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.hands.types'"

- [ ] **Step 3: Write minimal implementation**

Create `src/hands/types.py`:

```python
"""Shared types for messaging channel backends."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SendResult:
    """Outcome of sending a message through any channel."""

    success: bool
    message: str
    channel: str


@dataclass
class IncomingMessage:
    """A message received from any channel."""

    text: str
    sender: str
    channel: str
    timestamp: datetime
    raw: dict = field(default_factory=dict)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/averykeller/Desktop/projects/jarvis-mcp && python -m pytest tests/test_hands_channels.py::TestSharedTypes -x`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/hands/types.py tests/test_hands_channels.py
git commit -m "feat(hands): add shared SendResult and IncomingMessage types"
```

---

### Task 2: Telegram Backend

**Files:**
- Create: `src/hands/telegram.py`
- Test: `tests/test_hands_channels.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_hands_channels.py`:

```python
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from src.hands.telegram import send as telegram_send, poll as telegram_poll, test_connection as telegram_test_connection


class TestTelegramBackend:
    @pytest.mark.asyncio
    async def test_send_success(self):
        config = {"bot_token": "123456:ABC-DEF", "chat_id": "987654"}
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True, "result": {"message_id": 1}}
        mock_response.raise_for_status = MagicMock()

        with patch("src.hands.telegram.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            result = await telegram_send(config, "Hello from JARVIS")
            assert result.success is True
            assert result.channel == "telegram"
            assert "Hello from JARVIS" in result.message
            mock_client.post.assert_called_once()
            call_url = mock_client.post.call_args[0][0]
            assert "sendMessage" in call_url
            assert "123456:ABC-DEF" in call_url

    @pytest.mark.asyncio
    async def test_send_failure(self):
        config = {"bot_token": "bad-token", "chat_id": "987654"}
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"ok": False, "description": "Unauthorized"}
        mock_response.raise_for_status = MagicMock(side_effect=httpx.HTTPStatusError("401", request=MagicMock(), response=mock_response))

        with patch("src.hands.telegram.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            result = await telegram_send(config, "Hello")
            assert result.success is False
            assert result.channel == "telegram"

    @pytest.mark.asyncio
    async def test_poll_returns_messages(self):
        config = {"bot_token": "123456:ABC-DEF", "chat_id": "987654"}
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "result": [
                {
                    "update_id": 100,
                    "message": {
                        "message_id": 1,
                        "from": {"id": 111, "first_name": "Avery"},
                        "chat": {"id": 987654},
                        "date": 1713300000,
                        "text": "Hey JARVIS",
                    },
                },
                {
                    "update_id": 101,
                    "message": {
                        "message_id": 2,
                        "from": {"id": 111, "first_name": "Avery"},
                        "chat": {"id": 987654},
                        "date": 1713300010,
                        "text": "What's the weather?",
                    },
                },
            ],
        }
        mock_response.raise_for_status = MagicMock()

        with patch("src.hands.telegram.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            messages = await telegram_poll(config, last_update_id=99)
            assert len(messages) == 2
            assert messages[0].text == "Hey JARVIS"
            assert messages[0].sender == "Avery"
            assert messages[0].channel == "telegram"
            assert messages[1].text == "What's the weather?"
            call_url = mock_client.get.call_args[0][0]
            assert "getUpdates" in call_url

    @pytest.mark.asyncio
    async def test_poll_empty_returns_empty_list(self):
        config = {"bot_token": "123456:ABC-DEF", "chat_id": "987654"}
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True, "result": []}
        mock_response.raise_for_status = MagicMock()

        with patch("src.hands.telegram.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            messages = await telegram_poll(config, last_update_id=0)
            assert messages == []

    @pytest.mark.asyncio
    async def test_test_connection_success(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True, "result": {"username": "jarvis_bot"}}
        mock_response.raise_for_status = MagicMock()

        with patch("src.hands.telegram.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            ok = await telegram_test_connection("123456:ABC-DEF")
            assert ok is True

    @pytest.mark.asyncio
    async def test_test_connection_failure(self):
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.raise_for_status = MagicMock(side_effect=httpx.HTTPStatusError("401", request=MagicMock(), response=mock_response))

        with patch("src.hands.telegram.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            ok = await telegram_test_connection("bad-token")
            assert ok is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/averykeller/Desktop/projects/jarvis-mcp && python -m pytest tests/test_hands_channels.py::TestTelegramBackend -x`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.hands.telegram'"

- [ ] **Step 3: Write minimal implementation**

Create `src/hands/telegram.py`:

```python
"""Telegram Bot API — send messages and poll for updates via httpx."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from src.hands.types import IncomingMessage, SendResult

logger = logging.getLogger(__name__)

BASE_URL = "https://api.telegram.org/bot{token}"


async def send(config: dict, message: str) -> SendResult:
    """Send a message via Telegram Bot API.

    Config keys: bot_token, chat_id.
    """
    token = config["bot_token"]
    chat_id = config["chat_id"]
    url = f"{BASE_URL.format(token=token)}/sendMessage"

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                json={"chat_id": chat_id, "text": message},
                timeout=10.0,
            )
            resp.raise_for_status()
            return SendResult(
                success=True,
                message=f"Telegram message sent: '{message}'",
                channel="telegram",
            )
    except Exception as exc:
        logger.warning("Telegram send failed: %s", exc)
        return SendResult(
            success=False,
            message=f"Telegram send failed: {exc}",
            channel="telegram",
        )


async def poll(config: dict, last_update_id: int = 0) -> list[IncomingMessage]:
    """Poll for new messages using getUpdates.

    Config keys: bot_token, chat_id.
    Returns list of IncomingMessage for updates with update_id > last_update_id.
    """
    token = config["bot_token"]
    url = f"{BASE_URL.format(token=token)}/getUpdates"

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url,
                params={"offset": last_update_id + 1, "timeout": 30},
                timeout=35.0,
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("Telegram poll failed: %s", exc)
        return []

    messages: list[IncomingMessage] = []
    for update in data.get("result", []):
        msg = update.get("message", {})
        text = msg.get("text", "")
        if not text:
            continue
        from_user = msg.get("from", {})
        sender = from_user.get("first_name", str(from_user.get("id", "unknown")))
        ts = datetime.fromtimestamp(msg.get("date", 0), tz=timezone.utc)
        messages.append(
            IncomingMessage(
                text=text,
                sender=sender,
                channel="telegram",
                timestamp=ts,
                raw=update,
            )
        )

    return messages


async def test_connection(token: str) -> bool:
    """Verify a bot token by calling getMe."""
    url = f"{BASE_URL.format(token=token)}/getMe"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=10.0)
            resp.raise_for_status()
            data = resp.json()
            return data.get("ok", False) and bool(data.get("result", {}).get("username"))
    except Exception:
        return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/averykeller/Desktop/projects/jarvis-mcp && python -m pytest tests/test_hands_channels.py::TestTelegramBackend -x`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add src/hands/telegram.py tests/test_hands_channels.py
git commit -m "feat(hands): add Telegram bot send, poll, and test_connection"
```

---

### Task 3: Discord Backend

**Files:**
- Create: `src/hands/discord_bot.py`
- Test: `tests/test_hands_channels.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_hands_channels.py`:

```python
from src.hands.discord_bot import send as discord_send, poll as discord_poll, test_connection as discord_test_connection


class TestDiscordBackend:
    @pytest.mark.asyncio
    async def test_send_success(self):
        config = {"bot_token": "MTIz.abc.def", "server_id": "111222333", "channel_id": "444555666"}
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "789", "content": "Hello"}
        mock_response.raise_for_status = MagicMock()

        with patch("src.hands.discord_bot.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            result = await discord_send(config, "Hello from JARVIS")
            assert result.success is True
            assert result.channel == "discord"
            mock_client.post.assert_called_once()
            call_url = mock_client.post.call_args[0][0]
            assert "444555666" in call_url
            assert "messages" in call_url

    @pytest.mark.asyncio
    async def test_send_failure(self):
        config = {"bot_token": "bad", "server_id": "111", "channel_id": "444"}
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.raise_for_status = MagicMock(side_effect=httpx.HTTPStatusError("401", request=MagicMock(), response=mock_response))

        with patch("src.hands.discord_bot.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            result = await discord_send(config, "Hello")
            assert result.success is False
            assert result.channel == "discord"

    @pytest.mark.asyncio
    async def test_poll_returns_messages(self):
        config = {"bot_token": "MTIz.abc.def", "server_id": "111", "channel_id": "444"}
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "id": "900",
                "content": "Hello JARVIS",
                "author": {"id": "222", "username": "avery"},
                "timestamp": "2026-04-16T12:00:00+00:00",
            },
        ]
        mock_response.raise_for_status = MagicMock()

        with patch("src.hands.discord_bot.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            messages = await discord_poll(config, last_message_id="800")
            assert len(messages) == 1
            assert messages[0].text == "Hello JARVIS"
            assert messages[0].sender == "avery"
            assert messages[0].channel == "discord"
            call_url = mock_client.get.call_args[0][0]
            assert "444" in call_url

    @pytest.mark.asyncio
    async def test_poll_empty(self):
        config = {"bot_token": "MTIz.abc.def", "server_id": "111", "channel_id": "444"}
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_response.raise_for_status = MagicMock()

        with patch("src.hands.discord_bot.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            messages = await discord_poll(config, last_message_id="0")
            assert messages == []

    @pytest.mark.asyncio
    async def test_test_connection_success(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "123", "username": "jarvis_bot"}
        mock_response.raise_for_status = MagicMock()

        with patch("src.hands.discord_bot.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            ok = await discord_test_connection("MTIz.abc.def")
            assert ok is True

    @pytest.mark.asyncio
    async def test_test_connection_failure(self):
        with patch("src.hands.discord_bot.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.HTTPStatusError("401", request=MagicMock(), response=MagicMock())
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            ok = await discord_test_connection("bad-token")
            assert ok is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/averykeller/Desktop/projects/jarvis-mcp && python -m pytest tests/test_hands_channels.py::TestDiscordBackend -x`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.hands.discord_bot'"

- [ ] **Step 3: Write minimal implementation**

Create `src/hands/discord_bot.py`:

```python
"""Discord bot — send messages and poll via REST API using httpx."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from src.hands.types import IncomingMessage, SendResult

logger = logging.getLogger(__name__)

BASE_URL = "https://discord.com/api/v10"


async def send(config: dict, message: str) -> SendResult:
    """Send a message to a Discord channel via REST API.

    Config keys: bot_token, server_id, channel_id.
    """
    token = config["bot_token"]
    channel_id = config["channel_id"]
    url = f"{BASE_URL}/channels/{channel_id}/messages"

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                json={"content": message},
                headers={"Authorization": f"Bot {token}"},
                timeout=10.0,
            )
            resp.raise_for_status()
            return SendResult(
                success=True,
                message=f"Discord message sent: '{message}'",
                channel="discord",
            )
    except Exception as exc:
        logger.warning("Discord send failed: %s", exc)
        return SendResult(
            success=False,
            message=f"Discord send failed: {exc}",
            channel="discord",
        )


async def poll(config: dict, last_message_id: str = "0") -> list[IncomingMessage]:
    """Poll for new messages in a Discord channel.

    Config keys: bot_token, channel_id.
    Returns messages with ID > last_message_id.
    """
    token = config["bot_token"]
    channel_id = config["channel_id"]
    url = f"{BASE_URL}/channels/{channel_id}/messages"

    try:
        async with httpx.AsyncClient() as client:
            params = {"after": last_message_id, "limit": 50}
            resp = await client.get(
                url,
                params=params,
                headers={"Authorization": f"Bot {token}"},
                timeout=10.0,
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("Discord poll failed: %s", exc)
        return []

    messages: list[IncomingMessage] = []
    for msg in data:
        content = msg.get("content", "")
        if not content:
            continue
        author = msg.get("author", {})
        sender = author.get("username", str(author.get("id", "unknown")))
        ts_str = msg.get("timestamp", "")
        try:
            ts = datetime.fromisoformat(ts_str)
        except (ValueError, TypeError):
            ts = datetime.now(timezone.utc)
        messages.append(
            IncomingMessage(
                text=content,
                sender=sender,
                channel="discord",
                timestamp=ts,
                raw=msg,
            )
        )

    return messages


async def test_connection(token: str) -> bool:
    """Verify a bot token by calling GET /users/@me."""
    url = f"{BASE_URL}/users/@me"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url,
                headers={"Authorization": f"Bot {token}"},
                timeout=10.0,
            )
            resp.raise_for_status()
            data = resp.json()
            return bool(data.get("id") and data.get("username"))
    except Exception:
        return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/averykeller/Desktop/projects/jarvis-mcp && python -m pytest tests/test_hands_channels.py::TestDiscordBackend -x`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add src/hands/discord_bot.py tests/test_hands_channels.py
git commit -m "feat(hands): add Discord bot send, poll, and test_connection"
```

---

### Task 4: Slack Backend

**Files:**
- Create: `src/hands/slack_bot.py`
- Test: `tests/test_hands_channels.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_hands_channels.py`:

```python
from src.hands.slack_bot import send as slack_send, poll as slack_poll, test_connection as slack_test_connection


class TestSlackBackend:
    @pytest.mark.asyncio
    async def test_send_success(self):
        config = {"bot_token": "xoxb-123-456-abc", "channel_id": "C01234567"}
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True, "channel": "C01234567", "ts": "1713300000.000100"}
        mock_response.raise_for_status = MagicMock()

        with patch("src.hands.slack_bot.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            result = await slack_send(config, "Hello from JARVIS")
            assert result.success is True
            assert result.channel == "slack"
            mock_client.post.assert_called_once()
            call_url = mock_client.post.call_args[0][0]
            assert "chat.postMessage" in call_url

    @pytest.mark.asyncio
    async def test_send_failure_ok_false(self):
        config = {"bot_token": "xoxb-bad", "channel_id": "C01234567"}
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": False, "error": "channel_not_found"}
        mock_response.raise_for_status = MagicMock()

        with patch("src.hands.slack_bot.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            result = await slack_send(config, "Hello")
            assert result.success is False
            assert result.channel == "slack"
            assert "channel_not_found" in result.message

    @pytest.mark.asyncio
    async def test_poll_returns_messages(self):
        config = {"bot_token": "xoxb-123-456-abc", "channel_id": "C01234567"}
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "messages": [
                {"type": "message", "user": "U111", "text": "Hey JARVIS", "ts": "1713300000.000100"},
                {"type": "message", "user": "U111", "text": "Do something", "ts": "1713300010.000200"},
            ],
        }
        mock_response.raise_for_status = MagicMock()

        with patch("src.hands.slack_bot.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            messages = await slack_poll(config, oldest_ts="0")
            assert len(messages) == 2
            assert messages[0].text == "Hey JARVIS"
            assert messages[0].sender == "U111"
            assert messages[0].channel == "slack"

    @pytest.mark.asyncio
    async def test_poll_empty(self):
        config = {"bot_token": "xoxb-123-456-abc", "channel_id": "C01234567"}
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True, "messages": []}
        mock_response.raise_for_status = MagicMock()

        with patch("src.hands.slack_bot.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            messages = await slack_poll(config, oldest_ts="0")
            assert messages == []

    @pytest.mark.asyncio
    async def test_test_connection_success(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True, "user_id": "U123", "team": "MyTeam"}
        mock_response.raise_for_status = MagicMock()

        with patch("src.hands.slack_bot.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            ok = await slack_test_connection("xoxb-123-456-abc")
            assert ok is True

    @pytest.mark.asyncio
    async def test_test_connection_failure(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": False, "error": "invalid_auth"}
        mock_response.raise_for_status = MagicMock()

        with patch("src.hands.slack_bot.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            ok = await slack_test_connection("xoxb-bad")
            assert ok is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/averykeller/Desktop/projects/jarvis-mcp && python -m pytest tests/test_hands_channels.py::TestSlackBackend -x`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.hands.slack_bot'"

- [ ] **Step 3: Write minimal implementation**

Create `src/hands/slack_bot.py`:

```python
"""Slack bot — send messages and poll via Slack Web API using httpx."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from src.hands.types import IncomingMessage, SendResult

logger = logging.getLogger(__name__)

BASE_URL = "https://slack.com/api"


async def send(config: dict, message: str) -> SendResult:
    """Send a message via Slack chat.postMessage.

    Config keys: bot_token, channel_id.
    """
    token = config["bot_token"]
    channel_id = config["channel_id"]
    url = f"{BASE_URL}/chat.postMessage"

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                json={"channel": channel_id, "text": message},
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0,
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get("ok"):
                error = data.get("error", "unknown error")
                return SendResult(
                    success=False,
                    message=f"Slack send failed: {error}",
                    channel="slack",
                )
            return SendResult(
                success=True,
                message=f"Slack message sent: '{message}'",
                channel="slack",
            )
    except Exception as exc:
        logger.warning("Slack send failed: %s", exc)
        return SendResult(
            success=False,
            message=f"Slack send failed: {exc}",
            channel="slack",
        )


async def poll(config: dict, oldest_ts: str = "0") -> list[IncomingMessage]:
    """Poll for new messages via conversations.history.

    Config keys: bot_token, channel_id.
    """
    token = config["bot_token"]
    channel_id = config["channel_id"]
    url = f"{BASE_URL}/conversations.history"

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url,
                params={"channel": channel_id, "oldest": oldest_ts, "limit": 50},
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0,
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("Slack poll failed: %s", exc)
        return []

    if not data.get("ok"):
        return []

    messages: list[IncomingMessage] = []
    for msg in data.get("messages", []):
        if msg.get("type") != "message":
            continue
        text = msg.get("text", "")
        if not text:
            continue
        sender = msg.get("user", "unknown")
        ts_str = msg.get("ts", "0")
        try:
            ts = datetime.fromtimestamp(float(ts_str), tz=timezone.utc)
        except (ValueError, TypeError):
            ts = datetime.now(timezone.utc)
        messages.append(
            IncomingMessage(
                text=text,
                sender=sender,
                channel="slack",
                timestamp=ts,
                raw=msg,
            )
        )

    return messages


async def test_connection(token: str) -> bool:
    """Verify a Slack bot token via auth.test."""
    url = f"{BASE_URL}/auth.test"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("ok", False)
    except Exception:
        return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/averykeller/Desktop/projects/jarvis-mcp && python -m pytest tests/test_hands_channels.py::TestSlackBackend -x`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add src/hands/slack_bot.py tests/test_hands_channels.py
git commit -m "feat(hands): add Slack bot send, poll, and test_connection"
```

---

### Task 5: Email Backend

**Files:**
- Create: `src/hands/email_client.py`
- Test: `tests/test_hands_channels.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_hands_channels.py`:

```python
from src.hands.email_client import send as email_send, poll as email_poll, test_connection as email_test_connection


class TestEmailBackend:
    @pytest.mark.asyncio
    async def test_send_success(self):
        config = {
            "smtp_host": "smtp.gmail.com",
            "smtp_port": 587,
            "username": "user@gmail.com",
            "password": "app-pass",
            "imap_host": "imap.gmail.com",
            "recipient": "user@gmail.com",
        }

        with patch("src.hands.email_client.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = None  # smtplib doesn't return on success
            result = await email_send(config, "Hello from JARVIS")
            assert result.success is True
            assert result.channel == "email"
            mock_thread.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_send_failure(self):
        config = {
            "smtp_host": "smtp.gmail.com",
            "smtp_port": 587,
            "username": "user@gmail.com",
            "password": "bad-pass",
            "imap_host": "imap.gmail.com",
            "recipient": "user@gmail.com",
        }

        with patch("src.hands.email_client.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.side_effect = Exception("SMTP auth failed")
            result = await email_send(config, "Hello")
            assert result.success is False
            assert result.channel == "email"
            assert "SMTP auth failed" in result.message

    @pytest.mark.asyncio
    async def test_poll_returns_messages(self):
        config = {
            "smtp_host": "smtp.gmail.com",
            "smtp_port": 587,
            "username": "user@gmail.com",
            "password": "app-pass",
            "imap_host": "imap.gmail.com",
            "recipient": "user@gmail.com",
        }

        mock_emails = [
            IncomingMessage(
                text="Hello JARVIS, check my calendar",
                sender="avery@gmail.com",
                channel="email",
                timestamp=datetime.now(timezone.utc),
                raw={"uid": "5", "subject": "Task"},
            ),
        ]

        with patch("src.hands.email_client.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = mock_emails
            messages = await email_poll(config, since_uid="1")
            assert len(messages) == 1
            assert messages[0].text == "Hello JARVIS, check my calendar"
            assert messages[0].sender == "avery@gmail.com"
            assert messages[0].channel == "email"

    @pytest.mark.asyncio
    async def test_poll_empty(self):
        config = {
            "smtp_host": "smtp.gmail.com",
            "smtp_port": 587,
            "username": "user@gmail.com",
            "password": "app-pass",
            "imap_host": "imap.gmail.com",
            "recipient": "user@gmail.com",
        }

        with patch("src.hands.email_client.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = []
            messages = await email_poll(config, since_uid="1")
            assert messages == []

    @pytest.mark.asyncio
    async def test_test_connection_success(self):
        config = {
            "smtp_host": "smtp.gmail.com",
            "smtp_port": 587,
            "username": "user@gmail.com",
            "password": "app-pass",
            "imap_host": "imap.gmail.com",
            "recipient": "user@gmail.com",
        }

        with patch("src.hands.email_client.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = True
            ok = await email_test_connection(config)
            assert ok is True

    @pytest.mark.asyncio
    async def test_test_connection_failure(self):
        config = {
            "smtp_host": "smtp.gmail.com",
            "smtp_port": 587,
            "username": "user@gmail.com",
            "password": "bad",
            "imap_host": "imap.gmail.com",
            "recipient": "user@gmail.com",
        }

        with patch("src.hands.email_client.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.side_effect = Exception("Auth failed")
            ok = await email_test_connection(config)
            assert ok is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/averykeller/Desktop/projects/jarvis-mcp && python -m pytest tests/test_hands_channels.py::TestEmailBackend -x`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.hands.email_client'"

- [ ] **Step 3: Write minimal implementation**

Create `src/hands/email_client.py`:

```python
"""Email backend — SMTP send and IMAP receive using stdlib."""

from __future__ import annotations

import asyncio
import email
import imaplib
import logging
import smtplib
from datetime import datetime, timezone
from email.mime.text import MIMEText

from src.hands.types import IncomingMessage, SendResult

logger = logging.getLogger(__name__)


def _send_smtp(config: dict, message: str) -> None:
    """Synchronous SMTP send — runs in a thread."""
    smtp_host = config["smtp_host"]
    smtp_port = config["smtp_port"]
    username = config["username"]
    password = config["password"]
    recipient = config["recipient"]

    msg = MIMEText(message)
    msg["Subject"] = "JARVIS"
    msg["From"] = username
    msg["To"] = recipient

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(username, password)
        server.send_message(msg)


def _poll_imap(config: dict, since_uid: str = "1") -> list[IncomingMessage]:
    """Synchronous IMAP poll — runs in a thread."""
    imap_host = config["imap_host"]
    username = config["username"]
    password = config["password"]

    messages: list[IncomingMessage] = []

    with imaplib.IMAP4_SSL(imap_host) as mail:
        mail.login(username, password)
        mail.select("INBOX")
        _, data = mail.search(None, "UNSEEN")
        if not data or not data[0]:
            return []

        for uid in data[0].split():
            _, msg_data = mail.fetch(uid, "(RFC822)")
            if not msg_data or not msg_data[0]:
                continue
            raw_email = msg_data[0]
            if isinstance(raw_email, tuple):
                raw_email = raw_email[1]
            msg = email.message_from_bytes(raw_email)
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        payload = part.get_payload(decode=True)
                        if payload:
                            body = payload.decode("utf-8", errors="replace")
                        break
            else:
                payload = msg.get_payload(decode=True)
                if payload:
                    body = payload.decode("utf-8", errors="replace")

            sender = msg.get("From", "unknown")
            subject = msg.get("Subject", "")

            messages.append(
                IncomingMessage(
                    text=body.strip() if body.strip() else subject,
                    sender=sender,
                    channel="email",
                    timestamp=datetime.now(timezone.utc),
                    raw={"uid": uid.decode() if isinstance(uid, bytes) else str(uid), "subject": subject},
                )
            )

    return messages


def _test_connections(config: dict) -> bool:
    """Test both SMTP and IMAP connections synchronously."""
    # Test SMTP
    smtp_host = config["smtp_host"]
    smtp_port = config["smtp_port"]
    username = config["username"]
    password = config["password"]

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(username, password)

    # Test IMAP
    imap_host = config["imap_host"]
    with imaplib.IMAP4_SSL(imap_host) as mail:
        mail.login(username, password)

    return True


async def send(config: dict, message: str) -> SendResult:
    """Send an email via SMTP.

    Config keys: smtp_host, smtp_port, username, password, imap_host, recipient.
    """
    try:
        await asyncio.to_thread(_send_smtp, config, message)
        return SendResult(
            success=True,
            message=f"Email sent to {config.get('recipient', 'unknown')}",
            channel="email",
        )
    except Exception as exc:
        logger.warning("Email send failed: %s", exc)
        return SendResult(
            success=False,
            message=f"Email send failed: {exc}",
            channel="email",
        )


async def poll(config: dict, since_uid: str = "1") -> list[IncomingMessage]:
    """Poll for unread emails via IMAP.

    Config keys: imap_host, username, password.
    """
    try:
        return await asyncio.to_thread(_poll_imap, config, since_uid)
    except Exception as exc:
        logger.warning("Email poll failed: %s", exc)
        return []


async def test_connection(config: dict) -> bool:
    """Test SMTP and IMAP connections."""
    try:
        return await asyncio.to_thread(_test_connections, config)
    except Exception:
        return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/averykeller/Desktop/projects/jarvis-mcp && python -m pytest tests/test_hands_channels.py::TestEmailBackend -x`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add src/hands/email_client.py tests/test_hands_channels.py
git commit -m "feat(hands): add email SMTP send and IMAP poll backend"
```

---

### Task 6: iMessage Polling

**Files:**
- Modify: `src/hands/messaging.py`
- Test: `tests/test_hands_channels.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_hands_channels.py`:

```python
import sqlite3

from src.hands.messaging import poll_imessage


class TestIMessagePoll:
    @pytest.mark.asyncio
    async def test_poll_returns_messages(self, tmp_path):
        """Create a mock chat.db and poll it."""
        db_path = tmp_path / "chat.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE message (
                ROWID INTEGER PRIMARY KEY,
                text TEXT,
                handle_id INTEGER,
                date INTEGER,
                is_from_me INTEGER DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE handle (
                ROWID INTEGER PRIMARY KEY,
                id TEXT
            )
        """)
        conn.execute("INSERT INTO handle (ROWID, id) VALUES (1, '+18121234567')")
        conn.execute("INSERT INTO message (ROWID, text, handle_id, date, is_from_me) VALUES (1, 'Hey JARVIS', 1, 700000000000000000, 0)")
        conn.execute("INSERT INTO message (ROWID, text, handle_id, date, is_from_me) VALUES (2, 'Whats up', 1, 700000001000000000, 0)")
        conn.commit()
        conn.close()

        messages, last_rowid = await poll_imessage(since_rowid=0, db_path=str(db_path))
        assert len(messages) == 2
        assert messages[0].text == "Hey JARVIS"
        assert messages[0].sender == "+18121234567"
        assert messages[0].channel == "imessage"
        assert messages[1].text == "Whats up"
        assert last_rowid == 2

    @pytest.mark.asyncio
    async def test_poll_respects_since_rowid(self, tmp_path):
        db_path = tmp_path / "chat.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE message (
                ROWID INTEGER PRIMARY KEY,
                text TEXT,
                handle_id INTEGER,
                date INTEGER,
                is_from_me INTEGER DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE handle (
                ROWID INTEGER PRIMARY KEY,
                id TEXT
            )
        """)
        conn.execute("INSERT INTO handle (ROWID, id) VALUES (1, '+18121234567')")
        conn.execute("INSERT INTO message (ROWID, text, handle_id, date, is_from_me) VALUES (1, 'Old msg', 1, 700000000000000000, 0)")
        conn.execute("INSERT INTO message (ROWID, text, handle_id, date, is_from_me) VALUES (2, 'New msg', 1, 700000001000000000, 0)")
        conn.commit()
        conn.close()

        messages, last_rowid = await poll_imessage(since_rowid=1, db_path=str(db_path))
        assert len(messages) == 1
        assert messages[0].text == "New msg"
        assert last_rowid == 2

    @pytest.mark.asyncio
    async def test_poll_empty(self, tmp_path):
        db_path = tmp_path / "chat.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE message (
                ROWID INTEGER PRIMARY KEY,
                text TEXT,
                handle_id INTEGER,
                date INTEGER,
                is_from_me INTEGER DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE handle (
                ROWID INTEGER PRIMARY KEY,
                id TEXT
            )
        """)
        conn.commit()
        conn.close()

        messages, last_rowid = await poll_imessage(since_rowid=0, db_path=str(db_path))
        assert messages == []
        assert last_rowid == 0

    @pytest.mark.asyncio
    async def test_poll_skips_is_from_me(self, tmp_path):
        db_path = tmp_path / "chat.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE message (
                ROWID INTEGER PRIMARY KEY,
                text TEXT,
                handle_id INTEGER,
                date INTEGER,
                is_from_me INTEGER DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE handle (
                ROWID INTEGER PRIMARY KEY,
                id TEXT
            )
        """)
        conn.execute("INSERT INTO handle (ROWID, id) VALUES (1, '+18121234567')")
        conn.execute("INSERT INTO message (ROWID, text, handle_id, date, is_from_me) VALUES (1, 'Sent by me', 1, 700000000000000000, 1)")
        conn.execute("INSERT INTO message (ROWID, text, handle_id, date, is_from_me) VALUES (2, 'From them', 1, 700000001000000000, 0)")
        conn.commit()
        conn.close()

        messages, last_rowid = await poll_imessage(since_rowid=0, db_path=str(db_path))
        assert len(messages) == 1
        assert messages[0].text == "From them"
        assert last_rowid == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/averykeller/Desktop/projects/jarvis-mcp && python -m pytest tests/test_hands_channels.py::TestIMessagePoll -x`
Expected: FAIL with "cannot import name 'poll_imessage' from 'src.hands.messaging'"

- [ ] **Step 3: Write minimal implementation**

Add the following to the end of `src/hands/messaging.py` (after the existing `send_telegram` function):

```python
# At top of file, add these imports (after existing imports):
import asyncio
import sqlite3
from datetime import datetime, timezone
from src.hands.types import IncomingMessage

# Default iMessage database path
_DEFAULT_CHAT_DB = str(Path.home() / "Library/Messages/chat.db")


async def poll_imessage(
    since_rowid: int = 0,
    db_path: str = _DEFAULT_CHAT_DB,
) -> tuple[list[IncomingMessage], int]:
    """Poll the iMessage database for new incoming messages.

    Args:
        since_rowid: Only return messages with ROWID > this value.
        db_path: Path to chat.db (overridable for testing).

    Returns:
        Tuple of (list of messages, latest ROWID seen).
    """
    def _query() -> tuple[list[IncomingMessage], int]:
        messages: list[IncomingMessage] = []
        latest_rowid = since_rowid

        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT m.ROWID, m.text, m.date, m.is_from_me, h.id as handle
                FROM message m
                LEFT JOIN handle h ON m.handle_id = h.ROWID
                WHERE m.ROWID > ? AND m.is_from_me = 0 AND m.text IS NOT NULL AND m.text != ''
                ORDER BY m.ROWID
                """,
                (since_rowid,),
            )
            for row in cursor:
                rowid = row["ROWID"]
                if rowid > latest_rowid:
                    latest_rowid = rowid
                # macOS iMessage dates are nanoseconds since 2001-01-01
                raw_date = row["date"] or 0
                # Convert to a UTC datetime (approximate — good enough for ordering)
                try:
                    epoch_seconds = raw_date / 1_000_000_000 + 978307200
                    ts = datetime.fromtimestamp(epoch_seconds, tz=timezone.utc)
                except (ValueError, OSError, OverflowError):
                    ts = datetime.now(timezone.utc)

                messages.append(
                    IncomingMessage(
                        text=row["text"],
                        sender=row["handle"] or "unknown",
                        channel="imessage",
                        timestamp=ts,
                        raw={"rowid": rowid},
                    )
                )
            conn.close()
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning("iMessage poll failed: %s", exc)

        return messages, latest_rowid

    return await asyncio.to_thread(_query)
```

**Important:** The actual edit should:
1. Add `import asyncio`, `import sqlite3`, `from datetime import datetime, timezone` to the existing imports at the top of the file.
2. Add `from src.hands.types import IncomingMessage` to imports.
3. Add `_DEFAULT_CHAT_DB` constant after `_CONFIG_DIR`.
4. Add the `poll_imessage` function at the end of the file.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/averykeller/Desktop/projects/jarvis-mcp && python -m pytest tests/test_hands_channels.py::TestIMessagePoll -x`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/hands/messaging.py tests/test_hands_channels.py
git commit -m "feat(hands): add iMessage polling from chat.db"
```

---

### Task 7: Notification System Update

**Files:**
- Modify: `src/engine/notifications.py`
- Test: `tests/test_hands_channels.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_hands_channels.py`:

```python
from src.engine.notifications import Notification, send_notification, DEFAULT_MATRIX


class TestNotificationDispatch:
    @pytest.mark.asyncio
    async def test_telegram_dispatch(self):
        notif = Notification(
            event_type="first_contact",
            title="JARVIS is ready",
            body="Hello sir",
            channels=["telegram"],
        )
        with patch("src.engine.notifications._load_channel_config") as mock_cfg:
            mock_cfg.return_value = {"bot_token": "123:ABC", "chat_id": "987"}
            with patch("src.hands.telegram.send", new_callable=AsyncMock) as mock_send:
                mock_send.return_value = SendResult(success=True, message="Sent", channel="telegram")
                result = await send_notification(notif)
                assert "telegram" in result["sent_to"]
                mock_send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_discord_dispatch(self):
        notif = Notification(
            event_type="first_contact",
            title="JARVIS",
            body="Hello",
            channels=["discord"],
        )
        with patch("src.engine.notifications._load_channel_config") as mock_cfg:
            mock_cfg.return_value = {"bot_token": "MTIz", "server_id": "111", "channel_id": "444"}
            with patch("src.hands.discord_bot.send", new_callable=AsyncMock) as mock_send:
                mock_send.return_value = SendResult(success=True, message="Sent", channel="discord")
                result = await send_notification(notif)
                assert "discord" in result["sent_to"]

    @pytest.mark.asyncio
    async def test_slack_dispatch(self):
        notif = Notification(
            event_type="first_contact",
            title="JARVIS",
            body="Hello",
            channels=["slack"],
        )
        with patch("src.engine.notifications._load_channel_config") as mock_cfg:
            mock_cfg.return_value = {"bot_token": "xoxb-123", "channel_id": "C01"}
            with patch("src.hands.slack_bot.send", new_callable=AsyncMock) as mock_send:
                mock_send.return_value = SendResult(success=True, message="Sent", channel="slack")
                result = await send_notification(notif)
                assert "slack" in result["sent_to"]

    @pytest.mark.asyncio
    async def test_email_dispatch(self):
        notif = Notification(
            event_type="first_contact",
            title="JARVIS",
            body="Hello",
            channels=["email"],
        )
        email_cfg = {
            "smtp_host": "smtp.gmail.com", "smtp_port": 587,
            "username": "u@g.com", "password": "p",
            "imap_host": "imap.gmail.com", "recipient": "u@g.com",
        }
        with patch("src.engine.notifications._load_channel_config") as mock_cfg:
            mock_cfg.return_value = email_cfg
            with patch("src.hands.email_client.send", new_callable=AsyncMock) as mock_send:
                mock_send.return_value = SendResult(success=True, message="Sent", channel="email")
                result = await send_notification(notif)
                assert "email" in result["sent_to"]

    def test_default_matrix_includes_telegram(self):
        assert "telegram" in DEFAULT_MATRIX.get("first_contact", [])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/averykeller/Desktop/projects/jarvis-mcp && python -m pytest tests/test_hands_channels.py::TestNotificationDispatch -x`
Expected: FAIL with "cannot import name '_load_channel_config'" or similar

- [ ] **Step 3: Write minimal implementation**

Replace `src/engine/notifications.py` with the updated version. Key changes:
1. Add `_load_channel_config(channel: str) -> dict | None` function that reads the `[channel_name]` section from `config/communication.toml`.
2. Update `DEFAULT_MATRIX` to include telegram and other channels in appropriate events.
3. Add `elif channel == "telegram":` block that calls `from src.hands.telegram import send as telegram_send` and dispatches with the loaded config.
4. Add similar blocks for `discord`, `slack`, and `email`.
5. Keep all existing behavior (macos, imessage, voice, silent) intact.

```python
"""Notification dispatcher for the Proactive Engine."""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import toml

logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"

# Default notification matrix: event_type -> list of channels
DEFAULT_MATRIX: dict[str, list[str]] = {
    "scout_find": ["macos", "silent"],
    "briefing_ready": ["macos", "imessage"],
    "lesson_drafted": ["silent"],
    "sandbox_cleaned": ["silent"],
    "task_failed": ["macos"],
    "first_contact": ["imessage", "telegram", "macos"],
}


def _load_imessage_target() -> str | None:
    """Read the iMessage target (phone/email) from communication.toml."""
    comm_path = CONFIG_DIR / "communication.toml"
    if not comm_path.exists():
        return None
    try:
        data = toml.load(comm_path)
        return data.get("channels", {}).get("imessage_target") or data.get("imessage", {}).get("target")
    except Exception:
        return None


def _load_channel_config(channel: str) -> dict | None:
    """Load the config section for a specific channel from communication.toml."""
    comm_path = CONFIG_DIR / "communication.toml"
    if not comm_path.exists():
        return None
    try:
        data = toml.load(comm_path)
        section = data.get(channel)
        if section and isinstance(section, dict):
            return section
        return None
    except Exception:
        return None


@dataclass
class Notification:
    """A single notification to be dispatched."""

    event_type: str
    title: str
    body: str
    channels: list[str] = field(default_factory=list)


def should_notify(
    event_type: str, channel: str, matrix: dict[str, list[str]] | None = None
) -> bool:
    """Check whether a given event_type should fire on a given channel."""
    m = matrix if matrix is not None else DEFAULT_MATRIX
    allowed = m.get(event_type, [])
    return channel in allowed


async def send_notification(
    notification: Notification,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Dispatch a notification to all appropriate channels.

    Channels:
        - macos: native display notification via osascript
        - imessage: iMessage via AppleScript
        - telegram: Telegram Bot API
        - discord: Discord REST API
        - slack: Slack Web API
        - email: SMTP
        - voice: TTS pipeline (stubbed)
        - silent: log only, no push
    """
    cfg = config or {}
    matrix = cfg.get("notification_matrix")
    test_mode = cfg.get("test_mode", False)

    # Determine channels: explicit on the notification, or from the matrix
    channels = notification.channels
    if not channels:
        m = matrix if matrix is not None else DEFAULT_MATRIX
        channels = m.get(notification.event_type, ["silent"])

    sent_to: list[str] = []

    for channel in channels:
        if not should_notify(notification.event_type, channel, matrix):
            if channel not in ("silent",) and notification.channels:
                # Explicit channels bypass the matrix check
                pass
            elif channel == "silent":
                pass
            else:
                continue

        try:
            if channel == "macos":
                if not test_mode:
                    safe_body = notification.body.replace("\\", "\\\\").replace('"', '\\"')
                    safe_title = notification.title.replace("\\", "\\\\").replace('"', '\\"')
                    subprocess.run(
                        [
                            "osascript",
                            "-e",
                            f'display notification "{safe_body}" '
                            f'with title "{safe_title}"',
                        ],
                        check=False,
                        capture_output=True,
                        timeout=5,
                    )
                sent_to.append("macos")

            elif channel == "imessage":
                target = _load_imessage_target()
                if target:
                    from src.hands.messaging import send_imessage
                    body = f"{notification.title}\n\n{notification.body}"
                    result = await send_imessage(target, body)
                    if result.success:
                        sent_to.append("imessage")
                    else:
                        logger.warning("iMessage failed: %s", result.message)
                else:
                    logger.warning("iMessage channel enabled but no target configured")

            elif channel == "telegram":
                chan_cfg = _load_channel_config("telegram")
                if chan_cfg:
                    from src.hands.telegram import send as telegram_send
                    body = f"{notification.title}\n\n{notification.body}"
                    result = await telegram_send(chan_cfg, body)
                    if result.success:
                        sent_to.append("telegram")
                    else:
                        logger.warning("Telegram failed: %s", result.message)
                else:
                    logger.warning("Telegram channel enabled but no config found")

            elif channel == "discord":
                chan_cfg = _load_channel_config("discord")
                if chan_cfg:
                    from src.hands.discord_bot import send as discord_send
                    body = f"{notification.title}\n\n{notification.body}"
                    result = await discord_send(chan_cfg, body)
                    if result.success:
                        sent_to.append("discord")
                    else:
                        logger.warning("Discord failed: %s", result.message)
                else:
                    logger.warning("Discord channel enabled but no config found")

            elif channel == "slack":
                chan_cfg = _load_channel_config("slack")
                if chan_cfg:
                    from src.hands.slack_bot import send as slack_send
                    body = f"{notification.title}\n\n{notification.body}"
                    result = await slack_send(chan_cfg, body)
                    if result.success:
                        sent_to.append("slack")
                    else:
                        logger.warning("Slack failed: %s", result.message)
                else:
                    logger.warning("Slack channel enabled but no config found")

            elif channel == "email":
                chan_cfg = _load_channel_config("email")
                if chan_cfg:
                    from src.hands.email_client import send as email_send
                    body = f"{notification.title}\n\n{notification.body}"
                    result = await email_send(chan_cfg, body)
                    if result.success:
                        sent_to.append("email")
                    else:
                        logger.warning("Email failed: %s", result.message)
                else:
                    logger.warning("Email channel enabled but no config found")

            elif channel == "voice":
                # Stubbed — would call TTS pipeline
                logger.info("Voice notification (stub): %s", notification.title)
                sent_to.append("voice")

            elif channel == "silent":
                logger.info(
                    "Silent notification [%s]: %s — %s",
                    notification.event_type,
                    notification.title,
                    notification.body,
                )
                sent_to.append("silent")

            else:
                logger.warning("Unknown notification channel: %s", channel)

        except Exception:
            logger.exception("Failed to send notification via %s", channel)

    return {
        "sent_to": sent_to,
        "event_type": notification.event_type,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/averykeller/Desktop/projects/jarvis-mcp && python -m pytest tests/test_hands_channels.py::TestNotificationDispatch -x`
Expected: PASS (5 passed)

**WARNING:** This modifies an existing file. Run the full existing notification tests too:
Run: `cd /Users/averykeller/Desktop/projects/jarvis-mcp && python -m pytest tests/ -k "notification" -x`

- [ ] **Step 5: Commit**

```bash
git add src/engine/notifications.py tests/test_hands_channels.py
git commit -m "feat(notifications): add telegram, discord, slack, email dispatch"
```

---

### Task 8: Message Listener Service

**Files:**
- Create: `src/hands/listener.py`
- Create: `tests/test_hands_listener.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_hands_listener.py`:

```python
"""Tests for the unified message listener service."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.hands.types import IncomingMessage, SendResult
from src.hands.listener import MessageListener


class TestMessageListener:
    def test_init_defaults(self):
        listener = MessageListener()
        assert listener.running is False
        assert listener._channels == {}

    @pytest.mark.asyncio
    async def test_start_sets_running(self):
        listener = MessageListener()
        with patch.object(listener, "_load_channels", return_value={}):
            await listener.start()
            assert listener.running is True
            await listener.stop()
            assert listener.running is False

    @pytest.mark.asyncio
    async def test_stop_when_not_running(self):
        listener = MessageListener()
        await listener.stop()
        assert listener.running is False

    def test_load_channels_reads_config(self, tmp_path):
        import toml
        comm_path = tmp_path / "communication.toml"
        comm_path.write_text(toml.dumps({
            "channels": {"primary": "telegram", "enabled": ["telegram", "imessage"]},
            "telegram": {"bot_token": "123:ABC", "chat_id": "987"},
            "imessage": {"target": "+18121234567"},
        }))
        listener = MessageListener(config_dir=tmp_path)
        channels = listener._load_channels()
        assert "telegram" in channels
        assert "imessage" in channels

    def test_load_channels_empty_when_no_config(self, tmp_path):
        listener = MessageListener(config_dir=tmp_path)
        channels = listener._load_channels()
        assert channels == {}

    @pytest.mark.asyncio
    async def test_process_incoming_calls_response_fn(self):
        listener = MessageListener()
        mock_response = AsyncMock(return_value="Weather is sunny")
        listener.response_fn = mock_response

        msg = IncomingMessage(
            text="What's the weather?",
            sender="Avery",
            channel="telegram",
            timestamp=datetime.now(timezone.utc),
        )

        with patch("src.hands.telegram.send", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = SendResult(success=True, message="Sent", channel="telegram")
            await listener._process_incoming(msg, {"bot_token": "123", "chat_id": "987"})
            mock_response.assert_awaited_once_with("What's the weather?")
            mock_send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_last_seen_defaults(self):
        listener = MessageListener()
        assert listener.get_last_seen("telegram") == 0
        assert listener.get_last_seen("discord") == "0"
        assert listener.get_last_seen("slack") == "0"
        assert listener.get_last_seen("email") == "1"
        assert listener.get_last_seen("imessage") == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/averykeller/Desktop/projects/jarvis-mcp && python -m pytest tests/test_hands_listener.py -x`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.hands.listener'"

- [ ] **Step 3: Write minimal implementation**

Create `src/hands/listener.py`:

```python
"""Unified message listener — polls all enabled channels for incoming messages."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Callable, Coroutine

import toml

from src.hands.types import IncomingMessage, SendResult

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"

# Polling intervals per channel (seconds)
POLL_INTERVALS: dict[str, float] = {
    "imessage": 5.0,
    "telegram": 1.0,  # long-poll handles the wait
    "discord": 5.0,
    "slack": 5.0,
    "email": 30.0,
}

# Default "last seen" values per channel type
_LAST_SEEN_DEFAULTS: dict[str, Any] = {
    "telegram": 0,
    "discord": "0",
    "slack": "0",
    "email": "1",
    "imessage": 0,
}


class MessageListener:
    """Polls all enabled two-way channels and routes responses."""

    def __init__(
        self,
        config_dir: Path | None = None,
        response_fn: Callable[[str], Coroutine[Any, Any, str]] | None = None,
    ) -> None:
        self.config_dir = config_dir or DEFAULT_CONFIG_DIR
        self.response_fn = response_fn or self._default_response
        self.running = False
        self._channels: dict[str, dict] = {}
        self._last_seen: dict[str, Any] = {}
        self._tasks: list[asyncio.Task] = []

    @staticmethod
    async def _default_response(text: str) -> str:
        return f"JARVIS received: {text}"

    def _load_channels(self) -> dict[str, dict]:
        """Load enabled channel configs from communication.toml."""
        comm_path = self.config_dir / "communication.toml"
        if not comm_path.exists():
            return {}
        try:
            data = toml.load(comm_path)
            enabled = data.get("channels", {}).get("enabled", [])
            channels: dict[str, dict] = {}
            for ch in enabled:
                section = data.get(ch, {})
                if section or ch == "imessage":
                    channels[ch] = section
            return channels
        except Exception as exc:
            logger.warning("Failed to load channel config: %s", exc)
            return {}

    def get_last_seen(self, channel: str) -> Any:
        """Return the last-seen marker for a channel."""
        if channel in self._last_seen:
            return self._last_seen[channel]
        return _LAST_SEEN_DEFAULTS.get(channel, 0)

    async def start(self) -> None:
        """Start polling all enabled channels."""
        self._channels = self._load_channels()
        self.running = True

        for channel, config in self._channels.items():
            if channel == "macos_notifications":
                continue  # one-way only
            interval = POLL_INTERVALS.get(channel, 10.0)
            task = asyncio.create_task(
                self._poll_loop(channel, config, interval),
                name=f"listener-{channel}",
            )
            self._tasks.append(task)

        logger.info("MessageListener started for %d channel(s)", len(self._tasks))

    async def stop(self) -> None:
        """Stop all polling loops."""
        self.running = False
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        logger.info("MessageListener stopped")

    async def _poll_loop(self, channel: str, config: dict, interval: float) -> None:
        """Continuously poll a single channel."""
        while self.running:
            try:
                messages = await self._poll_channel(channel, config)
                for msg in messages:
                    await self._process_incoming(msg, config)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error polling %s", channel)
            await asyncio.sleep(interval)

    async def _poll_channel(self, channel: str, config: dict) -> list[IncomingMessage]:
        """Poll a single channel for new messages."""
        if channel == "telegram":
            from src.hands.telegram import poll as telegram_poll
            last = self.get_last_seen("telegram")
            messages = await telegram_poll(config, last_update_id=last)
            if messages:
                # Update last_seen to the highest update_id
                max_update_id = max(
                    m.raw.get("update_id", last) for m in messages
                )
                self._last_seen["telegram"] = max_update_id
            return messages

        elif channel == "discord":
            from src.hands.discord_bot import poll as discord_poll
            last = self.get_last_seen("discord")
            messages = await discord_poll(config, last_message_id=last)
            if messages:
                max_id = max(m.raw.get("id", last) for m in messages)
                self._last_seen["discord"] = max_id
            return messages

        elif channel == "slack":
            from src.hands.slack_bot import poll as slack_poll
            last = self.get_last_seen("slack")
            messages = await slack_poll(config, oldest_ts=last)
            if messages:
                max_ts = max(m.raw.get("ts", last) for m in messages)
                self._last_seen["slack"] = max_ts
            return messages

        elif channel == "email":
            from src.hands.email_client import poll as email_poll
            last = self.get_last_seen("email")
            messages = await email_poll(config, since_uid=last)
            if messages:
                max_uid = max(m.raw.get("uid", last) for m in messages)
                self._last_seen["email"] = max_uid
            return messages

        elif channel == "imessage":
            from src.hands.messaging import poll_imessage
            last = self.get_last_seen("imessage")
            messages, new_last = await poll_imessage(since_rowid=last)
            self._last_seen["imessage"] = new_last
            return messages

        return []

    async def _process_incoming(self, msg: IncomingMessage, config: dict) -> None:
        """Process an incoming message: get response and send it back."""
        try:
            response_text = await self.response_fn(msg.text)
        except Exception:
            logger.exception("Response function failed for message: %s", msg.text)
            response_text = "I encountered an error processing your message."

        # Send response back via the same channel
        try:
            await self._send_response(msg.channel, config, response_text)
        except Exception:
            logger.exception("Failed to send response on %s", msg.channel)

    async def _send_response(self, channel: str, config: dict, text: str) -> SendResult:
        """Send a response back on the originating channel."""
        if channel == "telegram":
            from src.hands.telegram import send as telegram_send
            return await telegram_send(config, text)
        elif channel == "discord":
            from src.hands.discord_bot import send as discord_send
            return await discord_send(config, text)
        elif channel == "slack":
            from src.hands.slack_bot import send as slack_send
            return await slack_send(config, text)
        elif channel == "email":
            from src.hands.email_client import send as email_send
            return await email_send(config, text)
        elif channel == "imessage":
            from src.hands.messaging import send_imessage
            target = config.get("target", "")
            result = await send_imessage(target, text)
            return SendResult(success=result.success, message=result.message, channel="imessage")
        return SendResult(success=False, message=f"Unknown channel: {channel}", channel=channel)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/averykeller/Desktop/projects/jarvis-mcp && python -m pytest tests/test_hands_listener.py -x`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add src/hands/listener.py tests/test_hands_listener.py
git commit -m "feat(hands): add unified MessageListener for all channels"
```

---

### Task 9: MCP Server New Tools

**Files:**
- Modify: `src/mcp_server.py`
- Create: `tests/test_mcp_tools.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_mcp_tools.py`:

```python
"""Tests for new MCP messaging tools."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from src.hands.types import SendResult


class TestMCPMessagingTools:
    @pytest.mark.asyncio
    async def test_send_telegram_tool(self):
        from src.mcp_server import send_telegram_msg

        mock_cfg = {"bot_token": "123:ABC", "chat_id": "987"}
        with patch("src.mcp_server._load_channel_config", return_value=mock_cfg):
            with patch("src.hands.telegram.send", new_callable=AsyncMock) as mock_send:
                mock_send.return_value = SendResult(success=True, message="Sent via Telegram", channel="telegram")
                result = await send_telegram_msg("Hello from Claude")
                assert "Sent via Telegram" in result
                mock_send.assert_awaited_once_with(mock_cfg, "Hello from Claude")

    @pytest.mark.asyncio
    async def test_send_telegram_no_config(self):
        from src.mcp_server import send_telegram_msg

        with patch("src.mcp_server._load_channel_config", return_value=None):
            result = await send_telegram_msg("Hello")
            assert "not configured" in result.lower()

    @pytest.mark.asyncio
    async def test_send_discord_tool(self):
        from src.mcp_server import send_discord_msg

        mock_cfg = {"bot_token": "MTIz", "server_id": "111", "channel_id": "444"}
        with patch("src.mcp_server._load_channel_config", return_value=mock_cfg):
            with patch("src.hands.discord_bot.send", new_callable=AsyncMock) as mock_send:
                mock_send.return_value = SendResult(success=True, message="Sent via Discord", channel="discord")
                result = await send_discord_msg("Hello from Claude")
                assert "Sent via Discord" in result

    @pytest.mark.asyncio
    async def test_send_slack_tool(self):
        from src.mcp_server import send_slack_msg

        mock_cfg = {"bot_token": "xoxb-123", "channel_id": "C01"}
        with patch("src.mcp_server._load_channel_config", return_value=mock_cfg):
            with patch("src.hands.slack_bot.send", new_callable=AsyncMock) as mock_send:
                mock_send.return_value = SendResult(success=True, message="Sent via Slack", channel="slack")
                result = await send_slack_msg("Hello from Claude")
                assert "Sent via Slack" in result

    @pytest.mark.asyncio
    async def test_send_email_tool(self):
        from src.mcp_server import send_email_msg

        mock_cfg = {
            "smtp_host": "smtp.gmail.com", "smtp_port": 587,
            "username": "u@g.com", "password": "p",
            "imap_host": "imap.gmail.com", "recipient": "u@g.com",
        }
        with patch("src.mcp_server._load_channel_config", return_value=mock_cfg):
            with patch("src.hands.email_client.send", new_callable=AsyncMock) as mock_send:
                mock_send.return_value = SendResult(success=True, message="Email sent", channel="email")
                result = await send_email_msg("Important update", "Details here")
                assert "Email sent" in result

    @pytest.mark.asyncio
    async def test_send_notification_tool_routes_to_primary(self):
        from src.mcp_server import send_notification_msg

        with patch("src.mcp_server._load_primary_channel", return_value="telegram"):
            mock_cfg = {"bot_token": "123:ABC", "chat_id": "987"}
            with patch("src.mcp_server._load_channel_config", return_value=mock_cfg):
                with patch("src.hands.telegram.send", new_callable=AsyncMock) as mock_send:
                    mock_send.return_value = SendResult(success=True, message="Sent", channel="telegram")
                    result = await send_notification_msg("Hello")
                    assert "Sent" in result

    @pytest.mark.asyncio
    async def test_send_notification_no_primary(self):
        from src.mcp_server import send_notification_msg

        with patch("src.mcp_server._load_primary_channel", return_value=None):
            result = await send_notification_msg("Hello")
            assert "no primary channel" in result.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/averykeller/Desktop/projects/jarvis-mcp && python -m pytest tests/test_mcp_tools.py -x`
Expected: FAIL with ImportError

- [ ] **Step 3: Write minimal implementation**

Add to `src/mcp_server.py` (after the existing `get_calendar_today` tool and before the `if __name__` block):

```python
# ── Channel config helpers ──────────────────────────────────────────

def _load_channel_config(channel: str) -> dict | None:
    """Load config for a specific channel from communication.toml."""
    comm_path = CONFIG_DIR / "communication.toml"
    if not comm_path.exists():
        return None
    try:
        data = toml.load(comm_path)
        section = data.get(channel)
        if section and isinstance(section, dict):
            return section
        return None
    except Exception:
        return None


def _load_primary_channel() -> str | None:
    """Load the primary channel name from communication.toml."""
    comm_path = CONFIG_DIR / "communication.toml"
    if not comm_path.exists():
        return None
    try:
        data = toml.load(comm_path)
        return data.get("channels", {}).get("primary")
    except Exception:
        return None


# ── Telegram ────────────────────────────────────────────────────────

@mcp.tool()
async def send_telegram_msg(message: str) -> str:
    """Send a Telegram message to the configured chat."""
    cfg = _load_channel_config("telegram")
    if not cfg:
        return "Telegram is not configured. Run setup step 3 to add credentials."
    from src.hands.telegram import send as _send
    result = await _send(cfg, message)
    return result.message


# ── Discord ─────────────────────────────────────────────────────────

@mcp.tool()
async def send_discord_msg(message: str) -> str:
    """Send a Discord message to the configured channel."""
    cfg = _load_channel_config("discord")
    if not cfg:
        return "Discord is not configured. Run setup step 3 to add credentials."
    from src.hands.discord_bot import send as _send
    result = await _send(cfg, message)
    return result.message


# ── Slack ───────────────────────────────────────────────────────────

@mcp.tool()
async def send_slack_msg(message: str) -> str:
    """Send a Slack message to the configured channel."""
    cfg = _load_channel_config("slack")
    if not cfg:
        return "Slack is not configured. Run setup step 3 to add credentials."
    from src.hands.slack_bot import send as _send
    result = await _send(cfg, message)
    return result.message


# ── Email ───────────────────────────────────────────────────────────

@mcp.tool()
async def send_email_msg(subject: str, body: str) -> str:
    """Send an email with the given subject and body."""
    cfg = _load_channel_config("email")
    if not cfg:
        return "Email is not configured. Run setup step 3 to add credentials."
    from src.hands.email_client import send as _send
    full_message = f"Subject: {subject}\n\n{body}"
    result = await _send(cfg, full_message)
    return result.message


# ── Notification (auto-route) ───────────────────────────────────────

@mcp.tool()
async def send_notification_msg(message: str) -> str:
    """Send a notification via the user's primary messaging channel."""
    primary = _load_primary_channel()
    if not primary:
        return "No primary channel configured. Run setup step 3."
    cfg = _load_channel_config(primary)
    if not cfg and primary not in ("macos_notifications", "imessage"):
        return f"No primary channel configured — {primary} has no credentials."

    if primary == "telegram":
        from src.hands.telegram import send as _send
        result = await _send(cfg, message)
        return result.message
    elif primary == "discord":
        from src.hands.discord_bot import send as _send
        result = await _send(cfg, message)
        return result.message
    elif primary == "slack":
        from src.hands.slack_bot import send as _send
        result = await _send(cfg, message)
        return result.message
    elif primary == "email":
        from src.hands.email_client import send as _send
        result = await _send(cfg, message)
        return result.message
    elif primary == "imessage":
        from src.hands.messaging import send_imessage
        target = cfg.get("target", "") if cfg else ""
        result = await send_imessage(target, message)
        return result.message
    elif primary == "macos_notifications":
        import subprocess
        safe = message.replace("\\", "\\\\").replace('"', '\\"')
        subprocess.run(
            ["osascript", "-e", f'display notification "{safe}" with title "JARVIS"'],
            check=False, capture_output=True, timeout=5,
        )
        return "macOS notification sent."
    return f"Unknown primary channel: {primary}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/averykeller/Desktop/projects/jarvis-mcp && python -m pytest tests/test_mcp_tools.py -x`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add src/mcp_server.py tests/test_mcp_tools.py
git commit -m "feat(mcp): add send_telegram, send_discord, send_slack, send_email, send_notification tools"
```

---

### Task 10: Voice Provider Config

**Files:**
- Modify: `src/voice/tts.py`
- Modify: `src/voice/stt.py`
- Create: `config/voice.toml`
- Create: `tests/test_voice_providers.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_voice_providers.py`:

```python
"""Tests for multi-provider voice support."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from src.voice.tts import synthesize, PROVIDERS as TTS_PROVIDERS, TTSResult
from src.voice.stt import transcribe, PROVIDERS as STT_PROVIDERS, STTResult


class TestTTSProviders:
    def test_tts_provider_list(self):
        expected = {"fish_audio", "claude_tts", "elevenlabs", "openai_tts", "system"}
        assert set(TTS_PROVIDERS) == expected

    @pytest.mark.asyncio
    async def test_synthesize_fish_audio(self, tmp_path):
        cache_dir = str(tmp_path / "tts")
        with patch("src.voice.tts._load_voice_config") as mock_cfg:
            mock_cfg.return_value = {"provider": "fish_audio", "api_key": "sk-test"}
            result = await synthesize("Hello sir", cache_dir=cache_dir)
            assert isinstance(result, TTSResult)
            assert result.text == "Hello sir"

    @pytest.mark.asyncio
    async def test_synthesize_system_macos(self, tmp_path):
        cache_dir = str(tmp_path / "tts")
        with patch("src.voice.tts._load_voice_config") as mock_cfg:
            mock_cfg.return_value = {"provider": "system"}
            with patch("src.voice.tts._system_say", new_callable=AsyncMock) as mock_say:
                mock_say.return_value = str(tmp_path / "tts" / "out.wav")
                # Create the mock file
                Path(tmp_path / "tts").mkdir(parents=True, exist_ok=True)
                Path(tmp_path / "tts" / "out.wav").write_bytes(b"RIFF_MOCK")
                result = await synthesize("Hello sir", cache_dir=cache_dir)
                assert isinstance(result, TTSResult)

    @pytest.mark.asyncio
    async def test_synthesize_claude_tts(self, tmp_path):
        cache_dir = str(tmp_path / "tts")
        with patch("src.voice.tts._load_voice_config") as mock_cfg:
            mock_cfg.return_value = {"provider": "claude_tts"}
            result = await synthesize("Hello sir", cache_dir=cache_dir)
            assert isinstance(result, TTSResult)

    @pytest.mark.asyncio
    async def test_synthesize_elevenlabs(self, tmp_path):
        cache_dir = str(tmp_path / "tts")
        with patch("src.voice.tts._load_voice_config") as mock_cfg:
            mock_cfg.return_value = {"provider": "elevenlabs", "api_key": "sk-el"}
            result = await synthesize("Hello sir", cache_dir=cache_dir)
            assert isinstance(result, TTSResult)

    @pytest.mark.asyncio
    async def test_synthesize_openai_tts(self, tmp_path):
        cache_dir = str(tmp_path / "tts")
        with patch("src.voice.tts._load_voice_config") as mock_cfg:
            mock_cfg.return_value = {"provider": "openai_tts", "api_key": "sk-oai"}
            result = await synthesize("Hello sir", cache_dir=cache_dir)
            assert isinstance(result, TTSResult)

    @pytest.mark.asyncio
    async def test_synthesize_cache_still_works(self, tmp_path):
        cache_dir = str(tmp_path / "tts")
        with patch("src.voice.tts._load_voice_config") as mock_cfg:
            mock_cfg.return_value = {"provider": "fish_audio", "api_key": "sk-test"}
            first = await synthesize("cached", cache_dir=cache_dir)
            assert first.source == "api"
            second = await synthesize("cached", cache_dir=cache_dir)
            assert second.source == "cache"


class TestSTTProviders:
    def test_stt_provider_list(self):
        expected = {"whisper_local", "openai_whisper", "deepgram", "system"}
        assert set(STT_PROVIDERS) == expected

    @pytest.mark.asyncio
    async def test_transcribe_whisper_local(self):
        with patch("src.voice.stt._load_voice_config") as mock_cfg:
            mock_cfg.return_value = {"provider": "whisper_local"}
            result = await transcribe("test.wav")
            assert isinstance(result, STTResult)
            assert result.source == "local"

    @pytest.mark.asyncio
    async def test_transcribe_openai_whisper(self):
        with patch("src.voice.stt._load_voice_config") as mock_cfg:
            mock_cfg.return_value = {"provider": "openai_whisper", "api_key": "sk-oai"}
            result = await transcribe("test.wav")
            assert isinstance(result, STTResult)

    @pytest.mark.asyncio
    async def test_transcribe_deepgram(self):
        with patch("src.voice.stt._load_voice_config") as mock_cfg:
            mock_cfg.return_value = {"provider": "deepgram", "api_key": "dg-key"}
            result = await transcribe("test.wav")
            assert isinstance(result, STTResult)

    @pytest.mark.asyncio
    async def test_transcribe_system(self):
        with patch("src.voice.stt._load_voice_config") as mock_cfg:
            mock_cfg.return_value = {"provider": "system"}
            result = await transcribe("test.wav")
            assert isinstance(result, STTResult)

    @pytest.mark.asyncio
    async def test_transcribe_fallback_still_works(self):
        """When local confidence is low, cloud fallback fires regardless of provider."""
        with patch("src.voice.stt._load_voice_config") as mock_cfg:
            mock_cfg.return_value = {"provider": "whisper_local"}
            result = await transcribe("test.wav", mock_confidence=0.3)
            assert result.source == "cloud"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/averykeller/Desktop/projects/jarvis-mcp && python -m pytest tests/test_voice_providers.py -x`
Expected: FAIL with ImportError (PROVIDERS not exported, _load_voice_config not found)

- [ ] **Step 3: Write minimal implementation**

**Modify `src/voice/tts.py`:** Add provider dispatch. Key changes:
1. Add `PROVIDERS` list constant: `["fish_audio", "claude_tts", "elevenlabs", "openai_tts", "system"]`
2. Add `_load_voice_config()` that reads `config/voice.toml` `[tts]` section. Returns `{"provider": "fish_audio"}` as default if file missing.
3. Add `async def _system_say(text: str, cache_dir: str) -> str` that uses `subprocess` to run `say` command with output to file.
4. Modify `synthesize()` to call `_load_voice_config()` and dispatch to the correct provider. All non-system providers currently use the existing mock (write `RIFF_MOCK_WAV_DATA` to cache) — the real API calls are stubs that write mock data. The key architectural point is the dispatch exists.
5. Keep all existing caching logic intact.

```python
"""Text-to-Speech engine — multi-provider with local phrase cache."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import toml

logger = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = "cache/tts"
CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"

PROVIDERS: list[str] = ["fish_audio", "claude_tts", "elevenlabs", "openai_tts", "system"]

COMMON_PHRASES: list[str] = [
    "Good morning, {user_name}.",
    "Good afternoon, {user_name}.",
    "Good evening, {user_name}.",
    "Done.",
    "Sent.",
    "Cancelled.",
    "Alarm set for {time}.",
    "Reminder set.",
    "Here's what I found.",
    "Nothing to report, {user_name}.",
    "Right away, {user_name}.",
    "On it.",
    "Understood.",
    "One moment, please.",
    "Working on it now.",
    "All clear, {user_name}.",
    "Task complete.",
    "Message sent.",
    "File saved.",
    "Connection established.",
    "Updated successfully.",
    "I'll handle that.",
    "As you wish, {user_name}.",
    "Ready when you are.",
    "Standing by.",
    "Briefing ready, {user_name}.",
    "No new notifications.",
    "You have new messages.",
    "Search complete.",
    "System nominal.",
]


@dataclass
class TTSResult:
    """Result from a text-to-speech synthesis."""

    audio_path: str
    text: str
    source: str  # "cache" | "api"
    duration_ms: int


def _load_voice_config() -> dict:
    """Load TTS config from config/voice.toml [tts] section."""
    voice_path = CONFIG_DIR / "voice.toml"
    if not voice_path.exists():
        return {"provider": "fish_audio"}
    try:
        data = toml.load(voice_path)
        return data.get("tts", {"provider": "fish_audio"})
    except Exception:
        return {"provider": "fish_audio"}


def get_cache_path(text: str, cache_dir: str = DEFAULT_CACHE_DIR) -> str:
    """Return a deterministic cache file path for the given text."""
    digest = hashlib.md5(text.encode()).hexdigest()  # noqa: S324
    return str(Path(cache_dir) / f"{digest}.wav")


def is_cached(text: str, cache_dir: str = DEFAULT_CACHE_DIR) -> bool:
    """Check whether a cached audio file already exists for *text*."""
    return Path(get_cache_path(text, cache_dir)).exists()


async def _system_say(text: str, cache_dir: str) -> str:
    """Synthesize via macOS `say` command. Returns path to output file."""
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    out_path = get_cache_path(text, cache_dir)
    await asyncio.to_thread(
        subprocess.run,
        ["say", "-o", out_path, "--data-format=LEI16@22050", text],
        check=True,
        capture_output=True,
        timeout=15,
    )
    return out_path


async def _mock_api_call(text: str, cache_dir: str) -> str:
    """Mock API call for providers without real implementation yet."""
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    cache_path = get_cache_path(text, cache_dir)
    Path(cache_path).write_bytes(b"RIFF_MOCK_WAV_DATA")
    return cache_path


async def synthesize(
    text: str,
    cache_dir: str = DEFAULT_CACHE_DIR,
    user_name: str = "Sir",
) -> TTSResult:
    """Synthesize speech for *text*, dispatching to the configured provider.

    1. Expand template variables ({user_name}, etc.).
    2. Check cache — if hit, return immediately with source="cache".
    3. On miss — dispatch to the configured TTS provider.
    """
    expanded = text.replace("{user_name}", user_name).replace("{time}", "7 AM")
    cache_path = get_cache_path(expanded, cache_dir)

    if Path(cache_path).exists():
        return TTSResult(
            audio_path=cache_path,
            text=expanded,
            source="cache",
            duration_ms=0,
        )

    # Cache miss — dispatch to provider
    voice_cfg = _load_voice_config()
    provider = voice_cfg.get("provider", "fish_audio")
    start = time.monotonic()

    if provider == "system":
        try:
            audio_path = await _system_say(expanded, cache_dir)
        except Exception:
            logger.warning("macOS say failed, falling back to mock")
            audio_path = await _mock_api_call(expanded, cache_dir)
    elif provider in ("fish_audio", "claude_tts", "elevenlabs", "openai_tts"):
        # All cloud providers use mock for now — real API calls TBD
        audio_path = await _mock_api_call(expanded, cache_dir)
    else:
        logger.warning("Unknown TTS provider '%s', using mock", provider)
        audio_path = await _mock_api_call(expanded, cache_dir)

    elapsed = int((time.monotonic() - start) * 1000)

    return TTSResult(
        audio_path=audio_path,
        text=expanded,
        source="api",
        duration_ms=max(elapsed, 1),
    )


async def generate_phrase_cache(
    user_name: str = "Sir",
    cache_dir: str = DEFAULT_CACHE_DIR,
) -> int:
    """Pre-generate cached audio for all COMMON_PHRASES."""
    generated = 0
    for phrase in COMMON_PHRASES:
        expanded = phrase.replace("{user_name}", user_name).replace("{time}", "7 AM")
        if not is_cached(expanded, cache_dir):
            await synthesize(phrase, cache_dir=cache_dir, user_name=user_name)
            generated += 1
    return generated


def invalidate_cache(cache_dir: str = DEFAULT_CACHE_DIR) -> int:
    """Remove all cached TTS files. Returns the number of files removed."""
    cache = Path(cache_dir)
    if not cache.exists():
        return 0
    removed = 0
    for f in cache.iterdir():
        if f.is_file():
            f.unlink()
            removed += 1
    return removed
```

**Modify `src/voice/stt.py`:** Add provider dispatch. Key changes:
1. Add `PROVIDERS` list constant: `["whisper_local", "openai_whisper", "deepgram", "system"]`
2. Add `_load_voice_config()` that reads `config/voice.toml` `[stt]` section.
3. Modify `transcribe()` to check provider. All providers currently return mock data. The dispatch structure is in place.

```python
"""Speech-to-Text engine — multi-provider with local-first fallback."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path

import toml

logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"

PROVIDERS: list[str] = ["whisper_local", "openai_whisper", "deepgram", "system"]


@dataclass
class STTResult:
    """Result from a speech-to-text transcription."""

    text: str
    confidence: float
    source: str  # "local" | "cloud"
    duration_ms: int


def _load_voice_config() -> dict:
    """Load STT config from config/voice.toml [stt] section."""
    voice_path = CONFIG_DIR / "voice.toml"
    if not voice_path.exists():
        return {"provider": "whisper_local"}
    try:
        data = toml.load(voice_path)
        return data.get("stt", {"provider": "whisper_local"})
    except Exception:
        return {"provider": "whisper_local"}


async def transcribe_whisper_local(
    audio_path: str,
    *,
    mock_confidence: float | None = None,
) -> STTResult:
    """Transcribe audio via local Whisper.cpp subprocess (mocked)."""
    confidence = mock_confidence if mock_confidence is not None else 0.92
    return STTResult(
        text="Hello Jarvis",
        confidence=confidence,
        source="local",
        duration_ms=850,
    )


async def transcribe_whisper_cloud(audio_path: str) -> STTResult:
    """Transcribe audio via OpenAI Whisper API (mocked)."""
    return STTResult(
        text="Hello Jarvis",
        confidence=0.97,
        source="cloud",
        duration_ms=1200,
    )


async def _transcribe_deepgram(audio_path: str) -> STTResult:
    """Transcribe audio via Deepgram API (mocked)."""
    return STTResult(
        text="Hello Jarvis",
        confidence=0.95,
        source="cloud",
        duration_ms=600,
    )


async def _transcribe_system(audio_path: str) -> STTResult:
    """Transcribe audio via macOS dictation (mocked)."""
    return STTResult(
        text="Hello Jarvis",
        confidence=0.85,
        source="local",
        duration_ms=1500,
    )


async def transcribe(
    audio_path: str,
    *,
    fallback_threshold: float = 0.7,
    mock_confidence: float | None = None,
) -> STTResult:
    """Transcribe audio with provider-aware local-first strategy.

    1. Dispatch to the configured STT provider.
    2. If confidence < fallback_threshold, re-send to cloud Whisper API.
    """
    voice_cfg = _load_voice_config()
    provider = voice_cfg.get("provider", "whisper_local")

    start = time.monotonic()

    if provider == "whisper_local":
        local_result = await transcribe_whisper_local(
            audio_path, mock_confidence=mock_confidence
        )
    elif provider == "openai_whisper":
        local_result = await transcribe_whisper_cloud(audio_path)
        elapsed = int((time.monotonic() - start) * 1000)
        local_result.duration_ms = max(local_result.duration_ms, elapsed)
        return local_result  # Cloud provider, no fallback needed
    elif provider == "deepgram":
        local_result = await _transcribe_deepgram(audio_path)
        elapsed = int((time.monotonic() - start) * 1000)
        local_result.duration_ms = max(local_result.duration_ms, elapsed)
        return local_result
    elif provider == "system":
        local_result = await _transcribe_system(audio_path)
    else:
        logger.warning("Unknown STT provider '%s', using whisper_local", provider)
        local_result = await transcribe_whisper_local(
            audio_path, mock_confidence=mock_confidence
        )

    if local_result.confidence < fallback_threshold:
        cloud_result = await transcribe_whisper_cloud(audio_path)
        elapsed = int((time.monotonic() - start) * 1000)
        cloud_result.duration_ms = elapsed
        return cloud_result

    elapsed = int((time.monotonic() - start) * 1000)
    local_result.duration_ms = max(local_result.duration_ms, elapsed)
    return local_result


def is_whisper_installed() -> bool:
    """Check whether the whisper.cpp binary is available (mocked -> True)."""
    return True
```

**Create `config/voice.toml`:**

```toml
[tts]
provider = "fish_audio"
# api_key = "sk-..."

[stt]
provider = "whisper_local"
# model = "base"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/averykeller/Desktop/projects/jarvis-mcp && python -m pytest tests/test_voice_providers.py -x`
Expected: PASS (12 passed)

**WARNING:** Also run existing voice tests to verify no regressions:
Run: `cd /Users/averykeller/Desktop/projects/jarvis-mcp && python -m pytest tests/test_voice.py -x`
Expected: PASS (all existing tests still pass)

- [ ] **Step 5: Commit**

```bash
git add src/voice/tts.py src/voice/stt.py config/voice.toml tests/test_voice_providers.py
git commit -m "feat(voice): add multi-provider TTS/STT dispatch with config"
```

---

### Task 11: Setup Step Renumbering

**Files:**
- Modify: `src/setup/steps.py`
- Modify: `src/setup/handlers.py`
- Modify: `src/setup/engine.py`

- [ ] **Step 1: Write the failing test**

The existing tests will break after renumbering. First update `tests/test_setup.py` to expect 12 steps:

Replace these test functions/assertions:
- `test_create_setup_steps_returns_13` -> rename to `test_create_setup_steps_returns_12`, assert `len(steps) == 12`
- `test_optional_steps_count` -> assert `len(optional) == 10` (was 11)
- `test_step_numbers_sequential` -> assert `numbers == list(range(1, 13))` (was `range(1, 14)`)
- `test_advance_stops_at_end` -> assert `state.current_step == 12` (was 13)
- Remove `test_handle_colima_check`
- `test_handle_briefing_prefs` -> step 9, complete_step(state, 9)
- `test_handle_briefing_prefs_defaults` -> step 9
- `test_handle_voice_setup` -> step 10, complete_step(state, 10)
- `test_handle_first_scan` -> step 11, complete_step(state, 11)
- `test_handle_done_default_name` -> step 12, complete_step(state, 12)
- `test_handle_done_personalised` -> step 12
- `test_step_handlers_dict_has_all_13` -> rename, assert 12 handlers
- `test_start_setup` -> assert 12 steps
- `test_is_setup_complete_true_when_required_done` -> complete steps 1 and 4, check last step (12)
- `test_get_setup_progress_initial` -> total 12
- `test_get_setup_progress_partial` -> update expected math for 12 total
- `test_setup_start_endpoint` -> total_steps == 12
- Full walkthrough: remove step 9 (colima), renumber steps 10-13 -> 9-12
- Remove import of `handle_colima_check`

**This is the most complex change.** Write all updated test assertions in a single edit to `tests/test_setup.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/averykeller/Desktop/projects/jarvis-mcp && python -m pytest tests/test_setup.py -x`
Expected: FAIL (step count mismatches, missing colima handler references, etc.)

- [ ] **Step 3: Write minimal implementation**

**Modify `src/setup/steps.py`:**
- Remove line `(9, "colima_check", "Check Docker/Colima availability", False),` from the definitions list.
- Renumber: old step 10 becomes 9, old 11 becomes 10, old 12 becomes 11, old 13 becomes 12.
- Update descriptions to match:
  - `(9, "briefing_prefs", "Briefing time and Obsidian vault", False),`
  - `(10, "voice_setup", "Test microphone and TTS", False),`
  - `(11, "first_scan", "Run initial Scout discovery", False),`
  - `(12, "done", "Setup complete", False),`

**Modify `src/setup/handlers.py`:**
- Remove `handle_colima_check` from `STEP_HANDLERS`.
- Add `check_docker_available` as a standalone utility function (extract from handle_colima_check, return bool).
- Update `handle_briefing_prefs` to call `complete_step(state, 9, result)`.
- Update `handle_voice_setup` to call `complete_step(state, 10, result)`.
- Update `handle_first_scan` to call `complete_step(state, 11, result)`.
- Update `handle_done` to call `complete_step(state, 12, result)`.
- Update `STEP_HANDLERS` dict:
  ```python
  STEP_HANDLERS: dict[int, callable] = {
      1: handle_welcome,
      2: handle_personalization,
      3: handle_communication,
      4: handle_claude_connection,
      5: handle_contacts,
      6: handle_services,
      7: handle_scout_sources,
      8: handle_github_auth,
      9: handle_briefing_prefs,
      10: handle_voice_setup,
      11: handle_first_scan,
      12: handle_done,
  }
  ```

**Modify `src/setup/engine.py`:**
- Update `start_setup()` docstring from "13 steps" to "12 steps".
- `is_setup_complete()` already checks `state.steps[-1].completed` — no code change needed.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/averykeller/Desktop/projects/jarvis-mcp && python -m pytest tests/test_setup.py -x`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/setup/steps.py src/setup/handlers.py src/setup/engine.py tests/test_setup.py
git commit -m "refactor(setup): remove colima step, renumber to 12 steps"
```

---

### Task 12: Step 3 Handler — Expanded Communication

**Files:**
- Modify: `src/setup/handlers.py`
- Test: `tests/test_setup.py` (append new tests)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_setup.py`:

```python
class TestExpandedCommunication:
    @pytest.mark.asyncio
    async def test_telegram_credentials_saved(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.setup.handlers.CONFIG_DIR", tmp_path)
        config = {
            "channels": ["telegram"],
            "primary": "telegram",
            "telegram_bot_token": "123456:ABC-DEF",
            "telegram_chat_id": "987654321",
        }
        state = SetupState(steps=create_setup_steps(), current_step=3, started_at="t")
        state, result = await handle_communication(state, config)
        assert result["primary"] == "telegram"

        import toml as toml_lib
        data = toml_lib.load(tmp_path / "communication.toml")
        assert data["telegram"]["bot_token"] == "123456:ABC-DEF"
        assert data["telegram"]["chat_id"] == "987654321"

    @pytest.mark.asyncio
    async def test_discord_credentials_saved(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.setup.handlers.CONFIG_DIR", tmp_path)
        config = {
            "channels": ["discord"],
            "primary": "discord",
            "discord_bot_token": "MTIz.abc.def",
            "discord_server_id": "111222333",
            "discord_channel_id": "444555666",
        }
        state = SetupState(steps=create_setup_steps(), current_step=3, started_at="t")
        state, result = await handle_communication(state, config)

        import toml as toml_lib
        data = toml_lib.load(tmp_path / "communication.toml")
        assert data["discord"]["bot_token"] == "MTIz.abc.def"
        assert data["discord"]["server_id"] == "111222333"
        assert data["discord"]["channel_id"] == "444555666"

    @pytest.mark.asyncio
    async def test_slack_credentials_saved(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.setup.handlers.CONFIG_DIR", tmp_path)
        config = {
            "channels": ["slack"],
            "primary": "slack",
            "slack_bot_token": "xoxb-123-456-abc",
            "slack_channel_id": "C01234567",
        }
        state = SetupState(steps=create_setup_steps(), current_step=3, started_at="t")
        state, result = await handle_communication(state, config)

        import toml as toml_lib
        data = toml_lib.load(tmp_path / "communication.toml")
        assert data["slack"]["bot_token"] == "xoxb-123-456-abc"
        assert data["slack"]["channel_id"] == "C01234567"

    @pytest.mark.asyncio
    async def test_email_credentials_saved(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.setup.handlers.CONFIG_DIR", tmp_path)
        config = {
            "channels": ["email"],
            "primary": "email",
            "email_smtp_host": "smtp.gmail.com",
            "email_smtp_port": 587,
            "email_username": "user@gmail.com",
            "email_password": "app-pass",
            "email_imap_host": "imap.gmail.com",
            "email_recipient": "user@gmail.com",
        }
        state = SetupState(steps=create_setup_steps(), current_step=3, started_at="t")
        state, result = await handle_communication(state, config)

        import toml as toml_lib
        data = toml_lib.load(tmp_path / "communication.toml")
        assert data["email"]["smtp_host"] == "smtp.gmail.com"
        assert data["email"]["smtp_port"] == 587
        assert data["email"]["username"] == "user@gmail.com"

    @pytest.mark.asyncio
    async def test_multiple_channels_all_saved(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.setup.handlers.CONFIG_DIR", tmp_path)
        config = {
            "channels": ["telegram", "discord", "macos_notifications"],
            "primary": "telegram",
            "telegram_bot_token": "123:ABC",
            "telegram_chat_id": "987",
            "discord_bot_token": "MTIz",
            "discord_server_id": "111",
            "discord_channel_id": "444",
        }
        state = SetupState(steps=create_setup_steps(), current_step=3, started_at="t")
        state, result = await handle_communication(state, config)
        assert len(result["enabled"]) == 3

        import toml as toml_lib
        data = toml_lib.load(tmp_path / "communication.toml")
        assert "telegram" in data
        assert "discord" in data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/averykeller/Desktop/projects/jarvis-mcp && python -m pytest tests/test_setup.py::TestExpandedCommunication -x`
Expected: FAIL (telegram section not written to communication.toml)

- [ ] **Step 3: Write minimal implementation**

Update `handle_communication` in `src/setup/handlers.py` to also write per-channel credential sections:

```python
async def handle_communication(
    state: SetupState, config: dict
) -> tuple[SetupState, dict]:
    """Step 3 — Choose communication channels and save per-channel credentials."""
    channels = config.get("channels", ["macos_notifications"])
    primary = config.get("primary", channels[0] if channels else "macos_notifications")

    valid = [c for c in channels if c in SUPPORTED_CHANNELS]
    if not valid:
        valid = ["macos_notifications"]
    if primary not in valid:
        primary = valid[0]

    imessage_target = config.get("imessage_target", "")

    comm_path = CONFIG_DIR / "communication.toml"
    comm_path.parent.mkdir(parents=True, exist_ok=True)
    data: dict = {
        "channels": {
            "primary": primary,
            "enabled": valid,
        },
    }

    # iMessage credentials
    if "imessage" in valid:
        if imessage_target:
            data["channels"]["imessage_target"] = imessage_target
        data["imessage"] = {"target": imessage_target}

    # Telegram credentials
    if "telegram" in valid:
        tg_token = config.get("telegram_bot_token", "")
        tg_chat = config.get("telegram_chat_id", "")
        data["telegram"] = {"bot_token": tg_token, "chat_id": tg_chat}

    # Discord credentials
    if "discord" in valid:
        data["discord"] = {
            "bot_token": config.get("discord_bot_token", ""),
            "server_id": config.get("discord_server_id", ""),
            "channel_id": config.get("discord_channel_id", ""),
        }

    # Slack credentials
    if "slack" in valid:
        data["slack"] = {
            "bot_token": config.get("slack_bot_token", ""),
            "channel_id": config.get("slack_channel_id", ""),
        }

    # Email credentials
    if "email" in valid:
        data["email"] = {
            "smtp_host": config.get("email_smtp_host", ""),
            "smtp_port": config.get("email_smtp_port", 587),
            "username": config.get("email_username", ""),
            "password": config.get("email_password", ""),
            "imap_host": config.get("email_imap_host", ""),
            "recipient": config.get("email_recipient", ""),
        }

    with open(comm_path, "w") as f:
        toml.dump(data, f)

    result = {
        "primary": primary,
        "enabled": valid,
        "available": SUPPORTED_CHANNELS,
        "imessage_target": imessage_target if "imessage" in valid else None,
        "message": f"I'll reach you via {primary}. {len(valid)} channel(s) enabled.",
    }
    state = complete_step(state, 3, result)
    return state, result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/averykeller/Desktop/projects/jarvis-mcp && python -m pytest tests/test_setup.py::TestExpandedCommunication -x`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add src/setup/handlers.py tests/test_setup.py
git commit -m "feat(setup): step 3 saves per-channel credentials to communication.toml"
```

---

### Task 13: Step 4 Handler — Claude Desktop MCP Registration

**Files:**
- Modify: `src/setup/handlers.py`
- Test: `tests/test_setup.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_setup.py`:

```python
import json


class TestClaudeDesktopRegistration:
    @pytest.mark.asyncio
    async def test_registers_jarvis_in_empty_config(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.setup.handlers.CONFIG_DIR", tmp_path)
        claude_config_dir = tmp_path / "claude_desktop"
        claude_config_dir.mkdir()
        claude_config_path = claude_config_dir / "claude_desktop_config.json"
        monkeypatch.setattr(
            "src.setup.handlers._claude_config_path",
            lambda: claude_config_path,
        )
        monkeypatch.setattr("src.setup.handlers._claude_app_exists", lambda: True)
        monkeypatch.setattr("src.setup.handlers._verify_mcp_server", AsyncMock(return_value=True))

        state = SetupState(steps=create_setup_steps(), current_step=4, started_at="t")
        state, result = await handle_claude_connection(state, {})
        assert result["detected"] is True
        assert result["registered"] is True

        cfg = json.loads(claude_config_path.read_text())
        assert "jarvis" in cfg["mcpServers"]

    @pytest.mark.asyncio
    async def test_preserves_existing_mcp_servers(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.setup.handlers.CONFIG_DIR", tmp_path)
        claude_config_dir = tmp_path / "claude_desktop"
        claude_config_dir.mkdir()
        claude_config_path = claude_config_dir / "claude_desktop_config.json"
        existing = {"mcpServers": {"other_tool": {"command": "/bin/other"}}}
        claude_config_path.write_text(json.dumps(existing))
        monkeypatch.setattr(
            "src.setup.handlers._claude_config_path",
            lambda: claude_config_path,
        )
        monkeypatch.setattr("src.setup.handlers._claude_app_exists", lambda: True)
        monkeypatch.setattr("src.setup.handlers._verify_mcp_server", AsyncMock(return_value=True))

        state = SetupState(steps=create_setup_steps(), current_step=4, started_at="t")
        state, result = await handle_claude_connection(state, {})

        cfg = json.loads(claude_config_path.read_text())
        assert "jarvis" in cfg["mcpServers"]
        assert "other_tool" in cfg["mcpServers"]

    @pytest.mark.asyncio
    async def test_already_registered_skips(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.setup.handlers.CONFIG_DIR", tmp_path)
        claude_config_dir = tmp_path / "claude_desktop"
        claude_config_dir.mkdir()
        claude_config_path = claude_config_dir / "claude_desktop_config.json"
        existing = {"mcpServers": {"jarvis": {"command": "/path/to/jarvis-mcp-server.sh"}}}
        claude_config_path.write_text(json.dumps(existing))
        monkeypatch.setattr(
            "src.setup.handlers._claude_config_path",
            lambda: claude_config_path,
        )
        monkeypatch.setattr("src.setup.handlers._claude_app_exists", lambda: True)
        monkeypatch.setattr("src.setup.handlers._verify_mcp_server", AsyncMock(return_value=True))

        state = SetupState(steps=create_setup_steps(), current_step=4, started_at="t")
        state, result = await handle_claude_connection(state, {})
        assert result["registered"] is True
        assert "already" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_claude_not_installed(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.setup.handlers.CONFIG_DIR", tmp_path)
        monkeypatch.setattr("src.setup.handlers._claude_app_exists", lambda: False)
        monkeypatch.setattr(
            "src.setup.handlers._claude_config_path",
            lambda: tmp_path / "nonexistent.json",
        )

        state = SetupState(steps=create_setup_steps(), current_step=4, started_at="t")
        state, result = await handle_claude_connection(state, {})
        assert result["detected"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/averykeller/Desktop/projects/jarvis-mcp && python -m pytest tests/test_setup.py::TestClaudeDesktopRegistration -x`
Expected: FAIL (functions like _claude_config_path don't exist)

- [ ] **Step 3: Write minimal implementation**

Replace `handle_claude_connection` in `src/setup/handlers.py` with the real implementation. Add helper functions:

```python
import json

# Add these helpers above handle_claude_connection:

def _claude_app_exists() -> bool:
    """Check if Claude Desktop is installed."""
    return Path("/Applications/Claude.app").exists()


def _claude_config_path() -> Path:
    """Return the path to Claude Desktop's config file."""
    return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"


def _jarvis_mcp_command() -> str:
    """Return the absolute path to the jarvis MCP server script."""
    return str(Path(__file__).resolve().parent.parent.parent / "scripts" / "jarvis-mcp-server.sh")


async def _verify_mcp_server() -> bool:
    """Verify the MCP server script exists and is executable."""
    script = Path(_jarvis_mcp_command())
    return script.exists() and script.stat().st_mode & 0o111


async def handle_claude_connection(
    state: SetupState, config: dict
) -> tuple[SetupState, dict]:
    """Step 4 — Detect Claude Desktop and register JARVIS as MCP server."""
    detected = _claude_app_exists()
    registered = False
    message = ""

    if not detected:
        message = "Claude Desktop not found. Install from claude.ai/download and retry."
        result = {"detected": False, "registered": False, "message": message}
        state = complete_step(state, 4, result)
        return state, result

    config_path = _claude_config_path()

    # Read or create config
    if config_path.exists():
        try:
            claude_cfg = json.loads(config_path.read_text())
        except (json.JSONDecodeError, OSError):
            claude_cfg = {}
    else:
        claude_cfg = {}

    if "mcpServers" not in claude_cfg:
        claude_cfg["mcpServers"] = {}

    if "jarvis" in claude_cfg["mcpServers"]:
        registered = True
        message = "Claude Desktop detected — JARVIS already registered as MCP server."
    else:
        # Register JARVIS
        claude_cfg["mcpServers"]["jarvis"] = {
            "command": _jarvis_mcp_command(),
            "args": [],
        }
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(claude_cfg, indent=2))
        registered = True
        message = "Claude Desktop detected — JARVIS registered as MCP server."

    # Verify MCP server can start
    server_ok = await _verify_mcp_server()
    if not server_ok:
        message += " Warning: MCP server script not found or not executable."

    result = {"detected": True, "registered": registered, "message": message}
    state = complete_step(state, 4, result)
    return state, result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/averykeller/Desktop/projects/jarvis-mcp && python -m pytest tests/test_setup.py::TestClaudeDesktopRegistration -x`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/setup/handlers.py tests/test_setup.py
git commit -m "feat(setup): step 4 auto-registers JARVIS in Claude Desktop config"
```

---

### Task 14: Step 5 Handler — Auto-Import Contacts

**Files:**
- Modify: `src/setup/handlers.py`
- Test: `tests/test_setup.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_setup.py`:

```python
class TestContactAutoImport:
    @pytest.mark.asyncio
    async def test_auto_import_contacts(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.setup.handlers.CONFIG_DIR", tmp_path)
        mock_contacts = [
            {"name": "Jane Keller", "phones": ["+18121234567"], "emails": ["jane@example.com"]},
            {"name": "John Doe", "phones": ["+15551234567"], "emails": []},
        ]
        monkeypatch.setattr(
            "src.setup.handlers._fetch_macos_contacts",
            AsyncMock(return_value=mock_contacts),
        )

        state = SetupState(steps=create_setup_steps(), current_step=5, started_at="t")
        state, result = await handle_contacts(state, {})
        assert result["count"] == 2
        assert "2 contacts" in result["message"]

        import toml as toml_lib
        contacts = toml_lib.load(tmp_path / "contacts.toml")
        assert len(contacts["contacts"]) == 2
        assert contacts["contacts"][0]["name"] == "Jane Keller"

    @pytest.mark.asyncio
    async def test_auto_import_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.setup.handlers.CONFIG_DIR", tmp_path)
        monkeypatch.setattr(
            "src.setup.handlers._fetch_macos_contacts",
            AsyncMock(return_value=[]),
        )

        state = SetupState(steps=create_setup_steps(), current_step=5, started_at="t")
        state, result = await handle_contacts(state, {})
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_auto_import_failure_graceful(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.setup.handlers.CONFIG_DIR", tmp_path)
        monkeypatch.setattr(
            "src.setup.handlers._fetch_macos_contacts",
            AsyncMock(side_effect=Exception("Contacts access denied")),
        )

        state = SetupState(steps=create_setup_steps(), current_step=5, started_at="t")
        state, result = await handle_contacts(state, {})
        assert result["count"] == 0
        assert "error" in result["message"].lower() or "failed" in result["message"].lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/averykeller/Desktop/projects/jarvis-mcp && python -m pytest tests/test_setup.py::TestContactAutoImport -x`
Expected: FAIL (_fetch_macos_contacts doesn't exist)

- [ ] **Step 3: Write minimal implementation**

Add helper and replace `handle_contacts` in `src/setup/handlers.py`:

```python
async def _fetch_macos_contacts() -> list[dict]:
    """Fetch all contacts from macOS Contacts.app via AppleScript."""
    from src.hands.osascript import run_osascript
    script = '''
    tell application "Contacts"
        set output to ""
        repeat with p in every person
            set n to name of p
            set ph to ""
            try
                set ph to value of phones of p as text
            end try
            set em to ""
            try
                set em to value of emails of p as text
            end try
            set output to output & n & "||" & ph & "||" & em & linefeed
        end repeat
        return output
    end tell
    '''
    result = await run_osascript(script, timeout=30.0)
    if not result.success or not result.stdout.strip():
        return []

    contacts: list[dict] = []
    for line in result.stdout.strip().split("\n"):
        parts = line.split("||")
        if len(parts) < 3:
            continue
        name = parts[0].strip()
        phones = [p.strip() for p in parts[1].split(",") if p.strip()] if parts[1].strip() else []
        emails = [e.strip() for e in parts[2].split(",") if e.strip()] if parts[2].strip() else []
        if name:
            contacts.append({"name": name, "phones": phones, "emails": emails})

    return contacts


async def handle_contacts(state: SetupState, config: dict) -> tuple[SetupState, dict]:
    """Step 5 — Auto-import contacts from macOS Contacts.app."""
    try:
        contacts = await _fetch_macos_contacts()
    except Exception:
        contacts = []
        result = {
            "count": 0,
            "message": "Failed to import contacts. You can add them manually later.",
        }
        state = complete_step(state, 5, result)
        return state, result

    # Save to contacts.toml
    contacts_path = CONFIG_DIR / "contacts.toml"
    contacts_path.parent.mkdir(parents=True, exist_ok=True)
    with open(contacts_path, "w") as f:
        toml.dump({"contacts": contacts}, f)

    count = len(contacts)
    result = {
        "count": count,
        "message": f"Imported {count} contacts from macOS Contacts.",
    }
    state = complete_step(state, 5, result)
    return state, result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/averykeller/Desktop/projects/jarvis-mcp && python -m pytest tests/test_setup.py::TestContactAutoImport -x`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/setup/handlers.py tests/test_setup.py
git commit -m "feat(setup): step 5 auto-imports contacts from macOS Contacts.app"
```

---

### Task 15: Step 9 Handler — Obsidian Vault

**Files:**
- Modify: `src/setup/handlers.py`
- Test: `tests/test_setup.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_setup.py`:

```python
class TestObsidianVaultSetup:
    @pytest.mark.asyncio
    async def test_valid_vault_path(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.setup.handlers.CONFIG_DIR", tmp_path)
        vault = tmp_path / "my_vault"
        vault.mkdir()
        (vault / ".obsidian").mkdir()

        monkeypatch.setattr(
            "src.setup.handlers._claude_config_path",
            lambda: tmp_path / "claude_config.json",
        )

        config = {"obsidian_vault": str(vault), "briefing_time": "08:00"}
        state = SetupState(steps=create_setup_steps(), current_step=9, started_at="t")
        state, result = await handle_briefing_prefs(state, config)
        assert result["obsidian_vault"] == str(vault)
        assert result["vault_valid"] is True
        assert (vault / "Daily Notes").exists()
        assert (vault / "JARVIS").exists()

    @pytest.mark.asyncio
    async def test_invalid_vault_path(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.setup.handlers.CONFIG_DIR", tmp_path)
        config = {"obsidian_vault": "/nonexistent/path", "briefing_time": "07:30"}
        state = SetupState(steps=create_setup_steps(), current_step=9, started_at="t")
        state, result = await handle_briefing_prefs(state, config)
        assert result["vault_valid"] is False

    @pytest.mark.asyncio
    async def test_vault_missing_obsidian_folder(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.setup.handlers.CONFIG_DIR", tmp_path)
        vault = tmp_path / "not_a_vault"
        vault.mkdir()
        config = {"obsidian_vault": str(vault), "briefing_time": "07:30"}
        state = SetupState(steps=create_setup_steps(), current_step=9, started_at="t")
        state, result = await handle_briefing_prefs(state, config)
        assert result["vault_valid"] is False

    @pytest.mark.asyncio
    async def test_no_vault_provided(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.setup.handlers.CONFIG_DIR", tmp_path)
        config = {"briefing_time": "07:30"}
        state = SetupState(steps=create_setup_steps(), current_step=9, started_at="t")
        state, result = await handle_briefing_prefs(state, config)
        assert result["obsidian_vault"] is None
        assert result["briefing_time"] == "07:30"

    @pytest.mark.asyncio
    async def test_briefing_toml_written(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.setup.handlers.CONFIG_DIR", tmp_path)
        vault = tmp_path / "my_vault"
        vault.mkdir()
        (vault / ".obsidian").mkdir()
        monkeypatch.setattr(
            "src.setup.handlers._claude_config_path",
            lambda: tmp_path / "claude_config.json",
        )

        config = {"obsidian_vault": str(vault), "briefing_time": "06:00"}
        state = SetupState(steps=create_setup_steps(), current_step=9, started_at="t")
        state, result = await handle_briefing_prefs(state, config)

        import toml as toml_lib
        data = toml_lib.load(tmp_path / "briefing.toml")
        assert data["briefing_time"] == "06:00"
        assert data["obsidian_vault"] == str(vault)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/averykeller/Desktop/projects/jarvis-mcp && python -m pytest tests/test_setup.py::TestObsidianVaultSetup -x`
Expected: FAIL (vault_valid key not in result)

- [ ] **Step 3: Write minimal implementation**

Replace `handle_briefing_prefs` in `src/setup/handlers.py`:

```python
async def handle_briefing_prefs(
    state: SetupState, config: dict
) -> tuple[SetupState, dict]:
    """Step 9 — Set briefing time and validate/configure Obsidian vault."""
    briefing_time = config.get("briefing_time", "07:30")
    obsidian_vault = config.get("obsidian_vault", None)
    vault_valid = False

    if obsidian_vault:
        vault_path = Path(obsidian_vault)
        if vault_path.exists() and (vault_path / ".obsidian").exists():
            vault_valid = True
            # Create JARVIS folders
            (vault_path / "Daily Notes").mkdir(exist_ok=True)
            (vault_path / "JARVIS").mkdir(exist_ok=True)

            # Write test note
            test_note = vault_path / "JARVIS" / ".jarvis-test.md"
            try:
                test_note.write_text("JARVIS access verified.\n")
                test_note.unlink()
            except OSError:
                vault_valid = False

    # Write briefing config
    briefing_path = CONFIG_DIR / "briefing.toml"
    briefing_path.parent.mkdir(parents=True, exist_ok=True)
    briefing_data: dict = {"briefing_time": briefing_time}
    if obsidian_vault and vault_valid:
        briefing_data["obsidian_vault"] = obsidian_vault
    with open(briefing_path, "w") as f:
        toml.dump(briefing_data, f)

    result = {
        "briefing_time": briefing_time,
        "obsidian_vault": obsidian_vault if vault_valid else None,
        "vault_valid": vault_valid,
        "message": f"Briefing scheduled for {briefing_time}."
        + (f" Obsidian vault linked: {obsidian_vault}" if vault_valid else ""),
    }
    state = complete_step(state, 9, result)
    return state, result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/averykeller/Desktop/projects/jarvis-mcp && python -m pytest tests/test_setup.py::TestObsidianVaultSetup -x`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add src/setup/handlers.py tests/test_setup.py
git commit -m "feat(setup): step 9 validates Obsidian vault and creates folders"
```

---

### Task 16: Step 10 Handler — Voice Provider Selection

**Files:**
- Modify: `src/setup/handlers.py`
- Test: `tests/test_setup.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_setup.py`:

```python
class TestVoiceProviderSetup:
    @pytest.mark.asyncio
    async def test_voice_setup_fish_audio(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.setup.handlers.CONFIG_DIR", tmp_path)
        config = {
            "tts_provider": "fish_audio",
            "tts_api_key": "sk-fish-123",
            "stt_provider": "whisper_local",
        }
        state = SetupState(steps=create_setup_steps(), current_step=10, started_at="t")
        state, result = await handle_voice_setup(state, config)
        assert result["tts_provider"] == "fish_audio"
        assert result["stt_provider"] == "whisper_local"

        import toml as toml_lib
        voice_cfg = toml_lib.load(tmp_path / "voice.toml")
        assert voice_cfg["tts"]["provider"] == "fish_audio"
        assert voice_cfg["tts"]["api_key"] == "sk-fish-123"
        assert voice_cfg["stt"]["provider"] == "whisper_local"

    @pytest.mark.asyncio
    async def test_voice_setup_system_no_key(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.setup.handlers.CONFIG_DIR", tmp_path)
        config = {"tts_provider": "system", "stt_provider": "system"}
        state = SetupState(steps=create_setup_steps(), current_step=10, started_at="t")
        state, result = await handle_voice_setup(state, config)

        import toml as toml_lib
        voice_cfg = toml_lib.load(tmp_path / "voice.toml")
        assert voice_cfg["tts"]["provider"] == "system"
        assert "api_key" not in voice_cfg["tts"]

    @pytest.mark.asyncio
    async def test_voice_setup_defaults(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.setup.handlers.CONFIG_DIR", tmp_path)
        config = {}
        state = SetupState(steps=create_setup_steps(), current_step=10, started_at="t")
        state, result = await handle_voice_setup(state, config)
        assert result["tts_provider"] == "fish_audio"
        assert result["stt_provider"] == "whisper_local"

    @pytest.mark.asyncio
    async def test_voice_setup_invalid_provider_falls_back(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.setup.handlers.CONFIG_DIR", tmp_path)
        config = {"tts_provider": "nonexistent", "stt_provider": "nonexistent"}
        state = SetupState(steps=create_setup_steps(), current_step=10, started_at="t")
        state, result = await handle_voice_setup(state, config)
        # Should fall back to defaults
        assert result["tts_provider"] == "fish_audio"
        assert result["stt_provider"] == "whisper_local"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/averykeller/Desktop/projects/jarvis-mcp && python -m pytest tests/test_setup.py::TestVoiceProviderSetup -x`
Expected: FAIL (voice.toml not written, provider keys not in result)

- [ ] **Step 3: Write minimal implementation**

Replace `handle_voice_setup` in `src/setup/handlers.py`:

```python
TTS_PROVIDERS = ["fish_audio", "claude_tts", "elevenlabs", "openai_tts", "system"]
STT_PROVIDERS = ["whisper_local", "openai_whisper", "deepgram", "system"]


async def handle_voice_setup(
    state: SetupState, config: dict
) -> tuple[SetupState, dict]:
    """Step 10 — Select TTS and STT providers and save to voice.toml."""
    tts_provider = config.get("tts_provider", "fish_audio")
    tts_api_key = config.get("tts_api_key", "")
    stt_provider = config.get("stt_provider", "whisper_local")
    stt_api_key = config.get("stt_api_key", "")

    # Validate providers
    if tts_provider not in TTS_PROVIDERS:
        tts_provider = "fish_audio"
    if stt_provider not in STT_PROVIDERS:
        stt_provider = "whisper_local"

    # Build voice config
    voice_data: dict = {
        "tts": {"provider": tts_provider},
        "stt": {"provider": stt_provider},
    }
    if tts_api_key and tts_provider not in ("system", "claude_tts"):
        voice_data["tts"]["api_key"] = tts_api_key
    if stt_api_key and stt_provider not in ("whisper_local", "system"):
        voice_data["stt"]["api_key"] = stt_api_key

    voice_path = CONFIG_DIR / "voice.toml"
    voice_path.parent.mkdir(parents=True, exist_ok=True)
    with open(voice_path, "w") as f:
        toml.dump(voice_data, f)

    result = {
        "tts_provider": tts_provider,
        "stt_provider": stt_provider,
        "mic_detected": True,
        "tts_working": True,
        "voice_profile": tts_provider,
        "message": f"Voice configured: TTS={tts_provider}, STT={stt_provider}.",
    }
    state = complete_step(state, 10, result)
    return state, result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/averykeller/Desktop/projects/jarvis-mcp && python -m pytest tests/test_setup.py::TestVoiceProviderSetup -x`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/setup/handlers.py tests/test_setup.py
git commit -m "feat(setup): step 10 saves voice provider selection to voice.toml"
```

---

### Task 17: Frontend Setup.tsx Update

**Files:**
- Modify: `dashboard/src/pages/Setup.tsx`

- [ ] **Step 1: Understand the required changes**

The frontend needs these updates (no test for frontend — visual/manual testing):
1. Update `totalSteps` default from 13 to 12.
2. Update `STEP_META` to remove step 9 (Colima), renumber 10-13 to 9-12.
3. **Step 3 form**: Add per-channel credential fields. When a channel checkbox is checked, show its credential fields:
   - Telegram: bot_token, chat_id inputs + help text
   - Discord: bot_token, server_id, channel_id inputs + help text
   - Slack: bot_token, channel_id inputs + help text
   - Email: smtp_host, smtp_port, username, password, imap_host, recipient inputs + help text
4. **Step 4 form**: Show detection result from API (registered checkmark or "Install Claude Desktop" message + retry button).
5. **Step 5 form**: Replace nickname form with auto-detect display showing contact count with checkmark.
6. Remove case 9 (Colima) from the switch.
7. **Step 9 form** (Obsidian): vault path input + validation status indicator.
8. **Step 10 form** (Voice): TTS provider dropdown + conditional API key, STT provider dropdown + conditional API key, test buttons.
9. Update case 11 (First Scan) and case 12 (account creation / Done).
10. Update `isAutoStep` list: `[4, 5, 8].includes(step)` (5 is now auto-detect).
11. Step 12 now handles account creation (moved from 13).
12. Update `handleNext` step 13 reference to step 12.

- [ ] **Step 2: Write the implementation**

Replace the contents of `dashboard/src/pages/Setup.tsx`. Key structural changes:

```typescript
// Updated STEP_META (12 steps):
const STEP_META: Record<number, StepMeta> = {
  1: { title: "Welcome", description: "Welcome to JARVIS — your personal AI assistant.", required: true },
  2: { title: "Personalization", description: "What should JARVIS call you?", required: false },
  3: { title: "Communication", description: "How should JARVIS reach you?", required: false },
  4: { title: "Claude Connection", description: "Detecting Claude Desktop and registering JARVIS as MCP server.", required: true },
  5: { title: "Contacts", description: "Importing your macOS contacts.", required: false },
  6: { title: "Services", description: "Which service ecosystems do you use?", required: false },
  7: { title: "Scout Sources", description: "Where should Scout look for discoveries?", required: false },
  8: { title: "GitHub Auth", description: "Checking GitHub CLI authentication.", required: false },
  9: { title: "Obsidian Vault", description: "Link your Obsidian vault for notes and briefings.", required: false },
  10: { title: "Voice Setup", description: "Choose your voice providers.", required: false },
  11: { title: "First Scan", description: "Running your first Scout discovery scan.", required: false },
  12: { title: "Create Account", description: "Set up your Mission Control login to finish.", required: false },
};

// TTS/STT provider lists for step 10:
const TTS_PROVIDERS = [
  { id: "fish_audio", label: "Fish Audio", needsKey: true },
  { id: "claude_tts", label: "Claude TTS", needsKey: false },
  { id: "elevenlabs", label: "ElevenLabs", needsKey: true },
  { id: "openai_tts", label: "OpenAI TTS", needsKey: true },
  { id: "system", label: "System (macOS say)", needsKey: false },
];

const STT_PROVIDERS = [
  { id: "whisper_local", label: "Whisper (local)", needsKey: false },
  { id: "openai_whisper", label: "OpenAI Whisper API", needsKey: true },
  { id: "deepgram", label: "Deepgram", needsKey: true },
  { id: "system", label: "System (macOS)", needsKey: false },
];
```

For case 3, add conditional credential field blocks per channel. For case 5, replace the nickname form with auto-detect display. For case 9, add obsidian vault path input. For case 10, add TTS/STT provider dropdowns.

- [ ] **Step 3: Manual verification**

Run: `cd /Users/averykeller/Desktop/projects/jarvis-mcp/dashboard && npm run build`
Expected: Build succeeds with no TypeScript errors

- [ ] **Step 4: Commit**

```bash
git add dashboard/src/pages/Setup.tsx
git commit -m "feat(dashboard): update Setup.tsx to 12 steps with channel creds, voice providers"
```

---

### Task 18: Dependencies Update

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Update dependencies**

Add `discord.py` and `slack-sdk` to the dependencies list in `pyproject.toml`:

```toml
dependencies = [
    "fastapi",
    "uvicorn[standard]",
    "httpx",
    "pydantic",
    "pydantic-settings",
    "click",
    "toml",
    "sqlite-utils",
    "bcrypt",
    "PyJWT",
    "discord.py>=2.3",
    "slack-sdk>=3.0",
]
```

- [ ] **Step 2: Install dependencies**

Run: `cd /Users/averykeller/Desktop/projects/jarvis-mcp && pip install "discord.py>=2.3" "slack-sdk>=3.0"`
Expected: Successfully installed

- [ ] **Step 3: Verify imports work**

Run: `python3 -c "import discord; import slack_sdk; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "build: add discord.py and slack-sdk dependencies"
```

---

### Task 19: Integration Testing

**Files:**
- Create: `tests/test_integration_onboarding.py`

- [ ] **Step 1: Write the integration test**

Create `tests/test_integration_onboarding.py`:

```python
"""Integration test — full onboarding walkthrough with 12 steps."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import toml
import httpx
from httpx import ASGITransport

from src.server.app import app
from src.setup.steps import create_setup_steps
from src.setup.engine import start_setup, execute_step, is_setup_complete
from src.hands.types import SendResult


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:7900")


class TestIntegrationOnboarding:
    @pytest.mark.asyncio
    async def test_full_12_step_walkthrough(self, client, tmp_path, monkeypatch):
        """Walk through all 12 setup steps with mock credentials."""
        monkeypatch.setattr("src.setup.handlers.CONFIG_DIR", tmp_path)

        # Mock external dependencies
        monkeypatch.setattr("src.setup.handlers._claude_app_exists", lambda: True)
        claude_cfg_path = tmp_path / "claude_config.json"
        monkeypatch.setattr("src.setup.handlers._claude_config_path", lambda: claude_cfg_path)
        monkeypatch.setattr("src.setup.handlers._verify_mcp_server", AsyncMock(return_value=True))
        monkeypatch.setattr(
            "src.setup.handlers._fetch_macos_contacts",
            AsyncMock(return_value=[
                {"name": "Mom", "phones": ["+1555"], "emails": ["mom@test.com"]},
                {"name": "Dad", "phones": ["+1666"], "emails": []},
            ]),
        )

        # Start
        resp = await client.post("/setup/start")
        assert resp.json()["status"] == "started"
        assert resp.json()["total_steps"] == 12

        # Step 1 — Welcome
        resp = await client.post("/setup/step/1", json={"config": {}})
        assert resp.json()["result"]["assistant_name"] == "JARVIS"

        # Step 2 — Personalization
        resp = await client.post(
            "/setup/step/2",
            json={"config": {"user_name": "Avery", "assistant_name": "JARVIS"}},
        )
        assert resp.json()["result"]["user_name"] == "Avery"

        # Step 3 — Communication with Telegram credentials
        resp = await client.post(
            "/setup/step/3",
            json={"config": {
                "channels": ["telegram", "macos_notifications"],
                "primary": "telegram",
                "telegram_bot_token": "123456:ABC-DEF",
                "telegram_chat_id": "987654321",
            }},
        )
        assert resp.json()["result"]["primary"] == "telegram"

        # Verify communication.toml has telegram section
        comm_data = toml.load(tmp_path / "communication.toml")
        assert comm_data["telegram"]["bot_token"] == "123456:ABC-DEF"

        # Step 4 — Claude connection
        resp = await client.post("/setup/step/4", json={"config": {}})
        assert resp.json()["result"]["detected"] is True
        assert resp.json()["result"]["registered"] is True

        # Verify Claude config was written
        claude_cfg = json.loads(claude_cfg_path.read_text())
        assert "jarvis" in claude_cfg["mcpServers"]

        # Step 5 — Contacts auto-import
        resp = await client.post("/setup/step/5", json={"config": {}})
        assert resp.json()["result"]["count"] == 2

        # Verify contacts.toml
        assert (tmp_path / "contacts.toml").exists()

        # Step 6 — Services
        resp = await client.post(
            "/setup/step/6",
            json={"config": {"services": ["apple", "github"]}},
        )
        assert resp.json()["result"]["count"] == 2

        # Step 7 — Scout sources
        resp = await client.post(
            "/setup/step/7",
            json={"config": {"sources": []}},
        )
        assert resp.json()["step"] == 7

        # Step 8 — GitHub auth
        resp = await client.post("/setup/step/8", json={"config": {}})
        assert resp.json()["result"]["gh_found"] is True

        # Step 9 — Obsidian vault
        vault = tmp_path / "test_vault"
        vault.mkdir()
        (vault / ".obsidian").mkdir()
        resp = await client.post(
            "/setup/step/9",
            json={"config": {"briefing_time": "07:00", "obsidian_vault": str(vault)}},
        )
        assert resp.json()["result"]["vault_valid"] is True
        assert (vault / "Daily Notes").exists()
        assert (vault / "JARVIS").exists()

        # Verify briefing.toml
        briefing_data = toml.load(tmp_path / "briefing.toml")
        assert briefing_data["briefing_time"] == "07:00"

        # Step 10 — Voice setup
        resp = await client.post(
            "/setup/step/10",
            json={"config": {"tts_provider": "system", "stt_provider": "whisper_local"}},
        )
        assert resp.json()["result"]["tts_provider"] == "system"

        # Verify voice.toml
        voice_data = toml.load(tmp_path / "voice.toml")
        assert voice_data["tts"]["provider"] == "system"

        # Step 11 — First scan
        with patch("src.scout.engine.run_discovery", new_callable=AsyncMock) as mock_d:
            mock_d.return_value = []
            resp = await client.post("/setup/step/11", json={"config": {}})
            assert resp.json()["result"]["scan_count"] == 0

        # Step 12 — Done
        resp = await client.post("/setup/step/12", json={"config": {}})
        data = resp.json()
        assert "Avery" in data["result"]["message"]
        assert data["complete"] is True

        # Verify progress is 100%
        resp = await client.get("/setup/progress")
        prog = resp.json()
        assert prog["completed"] == 12
        assert prog["percent"] == 100

    def test_setup_creates_12_steps(self):
        steps = create_setup_steps()
        assert len(steps) == 12
        names = [s.name for s in steps]
        assert "colima_check" not in names
        assert "briefing_prefs" in names
        assert "voice_setup" in names
        assert "done" in names

    @pytest.mark.asyncio
    async def test_listener_start_stop(self, tmp_path):
        from src.hands.listener import MessageListener

        # Create minimal communication.toml
        comm_path = tmp_path / "communication.toml"
        comm_path.write_text(toml.dumps({
            "channels": {"primary": "telegram", "enabled": ["telegram"]},
            "telegram": {"bot_token": "123:ABC", "chat_id": "987"},
        }))

        listener = MessageListener(config_dir=tmp_path)
        await listener.start()
        assert listener.running is True
        await listener.stop()
        assert listener.running is False
```

- [ ] **Step 2: Run test to verify it passes**

Run: `cd /Users/averykeller/Desktop/projects/jarvis-mcp && python -m pytest tests/test_integration_onboarding.py -x -v`
Expected: PASS (3 passed)

- [ ] **Step 3: Run the full test suite**

Run: `cd /Users/averykeller/Desktop/projects/jarvis-mcp && python -m pytest tests/ -x --tb=short`
Expected: ALL tests pass. Pay special attention to:
- `tests/test_setup.py` — all 12-step tests pass
- `tests/test_voice.py` — existing tests unbroken
- `tests/test_hands.py` — existing tests unbroken
- `tests/test_hands_channels.py` — all new channel tests pass
- `tests/test_mcp_tools.py` — all new MCP tool tests pass

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration_onboarding.py
git commit -m "test: add full 12-step integration test for onboarding flow"
```

---

## Dependency Graph

```
Task 1 (types)
  ├── Task 2 (telegram)
  ├── Task 3 (discord)
  ├── Task 4 (slack)
  ├── Task 5 (email)
  └── Task 6 (imessage poll)
        │
        ├── Task 7 (notifications) — depends on 2,3,4,5
        ├── Task 8 (listener) — depends on 2,3,4,5,6
        └── Task 9 (MCP tools) — depends on 2,3,4,5
              │
Task 10 (voice providers) — independent
Task 11 (renumbering) — independent, but all subsequent tasks depend on it
  ├── Task 12 (step 3 expanded) — depends on 11
  ├── Task 13 (step 4 Claude) — depends on 11
  ├── Task 14 (step 5 contacts) — depends on 11
  ├── Task 15 (step 9 obsidian) — depends on 11
  └── Task 16 (step 10 voice) — depends on 11, 10
        │
Task 17 (frontend) — depends on 11
Task 18 (dependencies) — independent, do early
Task 19 (integration) — depends on all
```

## Recommended Execution Order

1. **Task 18** (deps) — unblocks imports
2. **Task 1** (types) — unblocks all channel modules
3. **Tasks 2-6** (channels) — can run in parallel
4. **Task 7** (notifications) — after channels
5. **Task 8** (listener) — after channels
6. **Task 9** (MCP tools) — after channels
7. **Task 10** (voice) — can run in parallel with 2-9
8. **Task 11** (renumber) — breaks existing tests temporarily, commit together with updated tests
9. **Tasks 12-16** (step handlers) — after renumbering, can run in parallel
10. **Task 17** (frontend) — after renumbering
11. **Task 19** (integration) — last

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Renumbering breaks existing tests | HIGH | Task 11 must update tests/test_setup.py in the same commit as the step changes. Run full suite before committing. |
| Existing `test_handle_done` references step 13 | MEDIUM | Must update to step 12 in Task 11. |
| Frontend build breaks from removed cases | MEDIUM | Task 17 must remove case 9 (Colima) and renumber all subsequent cases. |
| `communication.toml` format changes break existing readers | MEDIUM | `_load_imessage_target()` in notifications.py already reads from `channels.imessage_target`; the new format also stores `imessage.target`. Updated code checks both locations. |
| `voice.toml` doesn't exist in prod | LOW | `_load_voice_config()` defaults to `fish_audio`/`whisper_local` if file missing — matches existing behavior. |
| Test isolation — tests touching `communication.toml` in real config dir | HIGH | All tests use `monkeypatch.setattr("src.setup.handlers.CONFIG_DIR", tmp_path)`. Never touch real config. |
| iMessage chat.db schema changes across macOS versions | LOW | The SQL query uses well-documented columns (ROWID, text, handle_id, date, is_from_me). Schema is stable across macOS 13-15. |
| `discord.py` package name confusion | LOW | In pyproject.toml use `"discord.py>=2.3"`. The import is `import discord` — but our module only uses httpx REST API, not the discord.py library directly. The dep is listed for future WebSocket gateway support. |
