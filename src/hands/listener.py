"""Unified message listener — polls all enabled two-way channels."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Callable, Coroutine

import toml

from src.hands.types import IncomingMessage, SendResult

logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"

# Channel → (poll_fn module path, send_fn module path, poll interval seconds)
CHANNEL_REGISTRY: dict[str, dict[str, Any]] = {
    "imessage": {"poll_interval": 5},
    "telegram": {"poll_interval": 1},  # long-poll handles delay internally
    "discord": {"poll_interval": 5},
    "slack": {"poll_interval": 5},
    "email": {"poll_interval": 30},
}


def _load_communication_config() -> dict:
    """Load communication.toml."""
    comm_path = CONFIG_DIR / "communication.toml"
    if not comm_path.exists():
        return {}
    try:
        return toml.load(comm_path)
    except Exception:
        return {}


class MessageListener:
    """Polls enabled two-way channels and routes responses back."""

    def __init__(
        self,
        response_fn: Callable[[str], Coroutine[Any, Any, str]] | None = None,
    ) -> None:
        self.response_fn = response_fn or self._default_response
        self.running = False
        self._tasks: list[asyncio.Task] = []
        self._last_seen: dict[str, Any] = {
            "imessage": 0,
            "telegram": 0,
            "discord": "0",
            "slack": "0",
            "email": "1",
        }

    @staticmethod
    async def _default_response(message: str) -> str:
        return f"Echo: {message}"

    async def start(self) -> None:
        """Start polling loops for all enabled two-way channels."""
        if self.running:
            return
        self.running = True
        config = _load_communication_config()
        enabled = config.get("channels", {}).get("enabled", [])

        for channel in enabled:
            if channel in CHANNEL_REGISTRY and channel != "macos_notifications":
                # Merge toml config with vault secrets
                from src.security.vault import load_channel_config

                channel_config = load_channel_config(channel) or {}
                task = asyncio.create_task(
                    self._poll_loop(channel, channel_config),
                    name=f"listener-{channel}",
                )
                self._tasks.append(task)
                logger.info("Started listener for %s", channel)

    async def stop(self) -> None:
        """Stop all polling loops."""
        self.running = False
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        logger.info("Message listener stopped")

    async def _poll_loop(self, channel: str, channel_config: dict) -> None:
        """Poll a single channel continuously."""
        interval = CHANNEL_REGISTRY.get(channel, {}).get("poll_interval", 10)

        while self.running:
            try:
                messages = await self._poll_channel(channel, channel_config)
                for msg in messages:
                    await self._handle_message(channel, channel_config, msg)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error polling %s", channel)
            await asyncio.sleep(interval)

    async def _poll_channel(
        self, channel: str, channel_config: dict
    ) -> list[IncomingMessage]:
        """Dispatch to the right poll function."""
        if channel == "imessage":
            from src.hands.messaging import poll_imessage

            msgs, new_rowid = await poll_imessage(self._last_seen["imessage"])
            self._last_seen["imessage"] = new_rowid
            return msgs

        elif channel == "telegram":
            from src.hands.telegram import poll as tg_poll

            msgs = await tg_poll(channel_config, self._last_seen["telegram"])
            if msgs:
                # Track highest update_id
                last_raw = msgs[-1].raw
                self._last_seen["telegram"] = last_raw.get("update_id", 0)
            return msgs

        elif channel == "discord":
            from src.hands.discord_bot import poll as dc_poll

            msgs = await dc_poll(channel_config, self._last_seen["discord"])
            if msgs:
                self._last_seen["discord"] = msgs[-1].raw.get("id", "0")
            return msgs

        elif channel == "slack":
            from src.hands.slack_bot import poll as sl_poll

            msgs = await sl_poll(channel_config, self._last_seen["slack"])
            if msgs:
                self._last_seen["slack"] = msgs[-1].raw.get("ts", "0")
            return msgs

        elif channel == "email":
            from src.hands.email_client import poll as em_poll

            msgs = await em_poll(channel_config, self._last_seen["email"])
            return msgs

        return []

    async def _handle_message(
        self, channel: str, channel_config: dict, msg: IncomingMessage
    ) -> None:
        """Process incoming message: get response, send it back."""
        logger.info("Incoming [%s] from %s: %s", channel, msg.sender, msg.text)
        try:
            response_text = await self.response_fn(msg.text)
        except Exception:
            logger.exception("Response generation failed for %s message", channel)
            response_text = "Apologies — I encountered an error processing that."

        await self._send_response(channel, channel_config, response_text)

    async def _send_response(
        self, channel: str, channel_config: dict, text: str
    ) -> SendResult | None:
        """Send response back on the same channel."""
        if channel == "imessage":
            target = _load_communication_config().get("imessage", {}).get("target")
            if not target:
                target = _load_communication_config().get("channels", {}).get("imessage_target")
            if target:
                from src.hands.messaging import send_imessage

                await send_imessage(target, text)
            return None

        elif channel == "telegram":
            from src.hands.telegram import send as tg_send

            return await tg_send(channel_config, text)

        elif channel == "discord":
            from src.hands.discord_bot import send as dc_send

            return await dc_send(channel_config, text)

        elif channel == "slack":
            from src.hands.slack_bot import send as sl_send

            return await sl_send(channel_config, text)

        elif channel == "email":
            from src.hands.email_client import send as em_send

            return await em_send(channel_config, text)

        return None
