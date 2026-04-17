"""Dynamic context builder — gathers live system state for the JARVIS system prompt."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


async def build_context() -> str:
    """Build a context block with current time, calendar, reminders, weather, etc.

    This gets injected into the system prompt so JARVIS has situational awareness
    and can be proactive about the user's day.
    """
    parts: list[str] = []

    # Current time
    now = datetime.now()
    utc_now = datetime.now(timezone.utc)
    parts.append(f"Current time: {now.strftime('%A, %B %d, %Y at %-I:%M %p')}")

    # Time-of-day greeting hint
    hour = now.hour
    if hour < 12:
        parts.append("Time of day: morning")
    elif hour < 17:
        parts.append("Time of day: afternoon")
    else:
        parts.append("Time of day: evening")

    # Calendar events
    try:
        from src.briefing.sections import fetch_calendar
        cal = await fetch_calendar()
        if not cal.empty and cal.items:
            events = [f"  - {e.get('time', '?')} {e.get('title', '?')}" for e in cal.items[:5]]
            parts.append(f"Today's calendar:\n" + "\n".join(events))
        else:
            parts.append("Today's calendar: No events scheduled")
    except Exception:
        pass

    # Pending reminders
    try:
        from src.briefing.sections import fetch_reminders
        rem = await fetch_reminders()
        if not rem.empty and rem.items:
            reminders = [f"  - {r.get('name', '?')}" + (f" (due: {r['due']})" if r.get("due") else "") for r in rem.items[:5]]
            parts.append(f"Pending reminders:\n" + "\n".join(reminders))
    except Exception:
        pass

    # Weather (brief)
    try:
        from src.briefing.sections import fetch_weather
        w = await fetch_weather()
        if not w.empty and w.content:
            parts.append(f"Weather: {w.content}")
    except Exception:
        pass

    # Recent activity (last few events)
    try:
        from src.engine.event_bus import EventBus
        # If there's a global event bus, peek at recent events
        # This is best-effort — skip if not available
    except Exception:
        pass

    # User profile
    try:
        from src.chat.user_profile import get_profile_summary
        profile = get_profile_summary()
        if profile:
            parts.append(f"User profile:\n{profile}")
    except Exception:
        pass

    return "\n".join(parts)
