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
    "first_contact": ["imessage", "macos"],
}


def _load_channel_config(channel: str) -> dict | None:
    """Read per-channel config from communication.toml + secrets from Keychain."""
    from src.security.vault import load_channel_config

    return load_channel_config(channel)


def _load_imessage_target() -> str | None:
    """Read the iMessage target (phone/email) from communication.toml."""
    conf = _load_channel_config("imessage")
    return conf.get("target") if conf else None


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
        - telegram: Telegram bot API
        - voice: TTS pipeline (synthesize + afplay)
        - email: SMTP client
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
                tg_conf = _load_channel_config("telegram")
                if tg_conf and tg_conf.get("bot_token"):
                    from src.hands.telegram import send as tg_send
                    body = f"{notification.title}\n\n{notification.body}"
                    result = await tg_send(tg_conf, body)
                    if result.success:
                        sent_to.append("telegram")
                    else:
                        logger.warning("Telegram failed: %s", result.message)
                else:
                    logger.warning("Telegram channel enabled but not configured")

            elif channel == "discord":
                dc_conf = _load_channel_config("discord")
                if dc_conf and dc_conf.get("bot_token"):
                    from src.hands.discord_bot import send as dc_send
                    body = f"**{notification.title}**\n{notification.body}"
                    result = await dc_send(dc_conf, body)
                    if result.success:
                        sent_to.append("discord")
                    else:
                        logger.warning("Discord failed: %s", result.message)
                else:
                    logger.warning("Discord channel enabled but not configured")

            elif channel == "slack":
                sl_conf = _load_channel_config("slack")
                if sl_conf and sl_conf.get("bot_token"):
                    from src.hands.slack_bot import send as sl_send
                    body = f"*{notification.title}*\n{notification.body}"
                    result = await sl_send(sl_conf, body)
                    if result.success:
                        sent_to.append("slack")
                    else:
                        logger.warning("Slack failed: %s", result.message)
                else:
                    logger.warning("Slack channel enabled but not configured")

            elif channel == "email":
                em_conf = _load_channel_config("email")
                if em_conf and em_conf.get("smtp_host"):
                    from src.hands.email_client import send as em_send
                    body = f"{notification.title}\n\n{notification.body}"
                    result = await em_send(em_conf, body)
                    if result.success:
                        sent_to.append("email")
                    else:
                        logger.warning("Email failed: %s", result.message)
                else:
                    logger.warning("Email channel enabled but not configured")

            elif channel == "voice":
                try:
                    from src.voice.tts import synthesize
                    import asyncio as _aio

                    tts_text = f"{notification.title}. {notification.body}"
                    tts_result = await synthesize(tts_text)
                    if tts_result.audio_path:
                        proc = await _aio.create_subprocess_exec(
                            "afplay", tts_result.audio_path,
                            stdout=_aio.subprocess.DEVNULL,
                            stderr=_aio.subprocess.DEVNULL,
                        )
                        await proc.wait()
                        sent_to.append("voice")
                    else:
                        logger.warning("Voice TTS produced no audio")
                except Exception as voice_err:
                    logger.warning("Voice notification failed: %s", voice_err)

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
