"""Alarm and timer handlers — Shortcuts integration (mock implementations)."""

from __future__ import annotations

import re

from src.hands import ControlResult

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
    """Set an alarm via Shortcuts — returns mock success."""
    return ControlResult(
        success=True,
        message=f"[mock] Alarm set for {time_str}",
        action="alarm",
        confirmed=True,
    )


async def set_timer(duration: str) -> ControlResult:
    """Set a timer via Shortcuts — returns mock success."""
    seconds = _parse_duration(duration)
    label = f"{seconds}s" if seconds > 0 else duration
    return ControlResult(
        success=True,
        message=f"[mock] Timer set for {label} ({duration})",
        action="timer",
        confirmed=True,
    )


async def cancel_alarm() -> ControlResult:
    """Cancel the current alarm — returns mock success."""
    return ControlResult(
        success=True,
        message="[mock] Alarm cancelled",
        action="cancel_alarm",
        confirmed=True,
    )
