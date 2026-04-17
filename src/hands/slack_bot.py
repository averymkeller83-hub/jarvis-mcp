"""Slack bot — send messages and poll for new messages via Web API."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from src.hands.types import IncomingMessage, SendResult

logger = logging.getLogger(__name__)

BASE_URL = "https://slack.com/api"


async def send(config: dict, message: str) -> SendResult:
    """Send a message to a Slack channel.

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
            data = resp.json()
            if data.get("ok"):
                return SendResult(
                    success=True,
                    message=f"Slack message sent: '{message}'",
                    channel="slack",
                )
            return SendResult(
                success=False,
                message=f"Slack send failed: {data.get('error', 'unknown')}",
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
    """Poll for new messages in a Slack channel.

    Config keys: bot_token, channel_id.
    Returns messages posted after oldest_ts.
    """
    token = config["bot_token"]
    channel_id = config["channel_id"]
    url = f"{BASE_URL}/conversations.history"

    try:
        async with httpx.AsyncClient() as client:
            params = {"channel": channel_id, "limit": 50}
            if oldest_ts != "0":
                params["oldest"] = oldest_ts
            resp = await client.get(
                url,
                params=params,
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0,
            )
            data = resp.json()
            if not data.get("ok"):
                return []
    except Exception as exc:
        logger.warning("Slack poll failed: %s", exc)
        return []

    messages: list[IncomingMessage] = []
    for msg in reversed(data.get("messages", [])):  # Slack returns newest first
        text = msg.get("text", "")
        if not text:
            continue
        # Skip bot messages
        if msg.get("bot_id") or msg.get("subtype") == "bot_message":
            continue
        sender = msg.get("user", "unknown")
        ts_str = msg.get("ts", "0")
        try:
            ts = datetime.fromtimestamp(float(ts_str), tz=timezone.utc)
        except (ValueError, OSError):
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
    """Verify a bot token by calling auth.test."""
    url = f"{BASE_URL}/auth.test"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0,
            )
            data = resp.json()
            return data.get("ok", False)
    except Exception:
        return False
