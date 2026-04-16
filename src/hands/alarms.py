"""Alarm and timer handlers — Shortcuts integration.

When ``_LIVE_MODE`` is True, alarms and timers use macOS Shortcuts or
osascript notifications.  When False (default), returns mock results.
"""

from __future__ import annotations

import re

from src.hands import ControlResult
from src.hands.osascript import run_osascript, run_shortcut

# ── Live-mode toggle ─────────────────────────────────────────────────
_LIVE_MODE: bool = False

# ── Duration parser ───────────────────────────────────────────────────

_DURATION_PATTERN = re.compile(
    r"(\d+)\s*(seconds?|secs?|s|minutes?|mins?|m|hours?|hrs?|h)",
    re.IGNORECASE,
)

_UNIT_TO_SECONDS: dict[str, int] = {
    "second": 1,
    "seconds": 1,
    "sec": 1,
    "secs": 1,
    "s": 1,
    "minute": 60,
    "minutes": 60,
    "min": 60,
    "mins": 60,
    "m": 60,
    "hour": 3600,
    "hours": 3600,
    "hr": 3600,
    "hrs": 3600,
    "h": 3600,
}


def _parse_duration(text: str) -> int:
    """Parse a human-readable duration string into total seconds.

    Supports compound durations like ``"1 hour 30 minutes"``.
    Returns 0 if nothing is parseable.
    """
    total = 0
    for match in _DURATION_PATTERN.finditer(text):
        amount = int(match.group(1))
        unit = match.group(2).lower()
        total += amount * _UNIT_TO_SECONDS.get(unit, 0)
    return total


# ── Handlers ──────────────────────────────────────────────────────────

async def set_alarm(time_str: str) -> ControlResult:
    """Set an alarm via Shortcuts."""
    if not _LIVE_MODE:
        return ControlResult(
            success=True,
            message=f"[mock] Alarm set for {time_str}",
            action="alarm",
            confirmed=True,
        )

    result = await run_shortcut("Set Alarm", input_text=time_str)
    if result.success:
        return ControlResult(
            success=True,
            message=f"Alarm set for {time_str}",
            action="alarm",
            confirmed=True,
        )
    return ControlResult(
        success=False,
        message=f"Failed to set alarm: {result.stderr}",
        action="alarm",
        confirmed=True,
    )


async def set_timer(duration: str) -> ControlResult:
    """Set a timer — uses Shortcuts or osascript notification fallback."""
    seconds = _parse_duration(duration)
    label = f"{seconds}s" if seconds > 0 else duration

    if not _LIVE_MODE:
        return ControlResult(
            success=True,
            message=f"[mock] Timer set for {label} ({duration})",
            action="timer",
            confirmed=True,
        )

    # Try Shortcuts first
    result = await run_shortcut("Set Timer", input_text=str(seconds) if seconds > 0 else duration)
    if result.success:
        return ControlResult(
            success=True,
            message=f"Timer set for {label}",
            action="timer",
            confirmed=True,
        )

    # Fallback: osascript notification after delay
    if seconds > 0:
        notify_script = (
            f"delay {seconds}\n"
            'display notification "Timer complete!" '
            f'with title "Jarvis Timer" subtitle "{duration}"'
        )
        fallback = await run_osascript(notify_script, timeout=float(seconds + 5))
        if fallback.success:
            return ControlResult(
                success=True,
                message=f"Timer set for {label} (notification fallback)",
                action="timer",
                confirmed=True,
            )

    return ControlResult(
        success=False,
        message=f"Failed to set timer: {result.stderr}",
        action="timer",
        confirmed=True,
    )


async def cancel_alarm() -> ControlResult:
    """Cancel the current alarm via Shortcuts."""
    if not _LIVE_MODE:
        return ControlResult(
            success=True,
            message="[mock] Alarm cancelled",
            action="cancel_alarm",
            confirmed=True,
        )

    result = await run_shortcut("Cancel Alarm")
    if result.success:
        return ControlResult(
            success=True,
            message="Alarm cancelled",
            action="cancel_alarm",
            confirmed=True,
        )
    return ControlResult(
        success=False,
        message=f"Failed to cancel alarm: {result.stderr}",
        action="cancel_alarm",
        confirmed=True,
    )
