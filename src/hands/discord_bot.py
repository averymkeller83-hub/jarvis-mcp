"""Discord bot — send messages and poll for new messages via REST API."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from src.hands.types import IncomingMessage, SendResult

logger = logging.getLogger(__name__)

BASE_URL = "https://discord.com/api/v10"


async def send(config: dict, message: str) -> SendResult:
    """Send a message to a Discord channel.

    Config keys: bot_token, channel_id.
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
    Returns messages posted after last_message_id.
    """
    token = config["bot_token"]
    channel_id = config["channel_id"]
    url = f"{BASE_URL}/channels/{channel_id}/messages"

    try:
        async with httpx.AsyncClient() as client:
            params = {"limit": 50}
            if last_message_id != "0":
                params["after"] = last_message_id
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
    for msg in reversed(data):  # Discord returns newest first
        text = msg.get("content", "")
        if not text:
            continue
        author = msg.get("author", {})
        # Skip messages from bots (our own messages)
        if author.get("bot", False):
            continue
        sender = author.get("username", "unknown")
        ts_str = msg.get("timestamp", "")
        try:
            ts = datetime.fromisoformat(ts_str.replace("+00:00", "+00:00"))
        except (ValueError, AttributeError):
            ts = datetime.now(timezone.utc)
        messages.append(
            IncomingMessage(
                text=text,
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
            return bool(data.get("id"))
    except Exception:
        return False
