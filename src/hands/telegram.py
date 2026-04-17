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
