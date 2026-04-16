"""Notification dispatcher for the Proactive Engine."""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Default notification matrix: event_type -> list of channels
DEFAULT_MATRIX: dict[str, list[str]] = {
    "scout_find": ["macos", "silent"],
    "briefing_ready": ["macos", "voice"],
    "lesson_drafted": ["silent"],
    "sandbox_cleaned": ["silent"],
    "task_failed": ["macos"],
}


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
        - telegram: Telegram bot API (stubbed)
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

            elif channel == "telegram":
                # Stubbed — would call Telegram Bot API
                logger.info("Telegram notification (stub): %s", notification.title)
                sent_to.append("telegram")

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
