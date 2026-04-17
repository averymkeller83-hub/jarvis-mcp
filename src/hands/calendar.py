"""Calendar handlers — Calendar.app integration via AppleScript.

When ``_LIVE_MODE`` is True, calendar events are queried/created via osascript.
When False (default), returns mock results to preserve test behaviour.
"""

from __future__ import annotations

from src.hands import ControlResult
from src.hands.osascript import run_osascript

# ── Live-mode toggle ─────────────────────────────────────────────────
_LIVE_MODE: bool = True


def _build_check_calendar_script(query: str) -> str:
    """Return AppleScript to query Calendar.app events for a date string."""
    escaped = query.replace('"', '\\"')
    return (
        'tell application "Calendar"\n'
        f'    set targetDate to date "{escaped}"\n'
        "    set eventSummaries to {}\n"
        "    repeat with cal in calendars\n"
        "        set evts to (every event of cal whose start date >= targetDate "
        "and start date < (targetDate + 1 * days))\n"
        "        repeat with evt in evts\n"
        "            set end of eventSummaries to (summary of evt)\n"
        "        end repeat\n"
        "    end repeat\n"
        "    return eventSummaries\n"
        "end tell"
    )


def _build_add_event_script(details: str) -> str:
    """Return AppleScript to create a new calendar event.

    The *details* string is passed as the event summary.  A real implementation
    would parse date/time from the details, but for now we create an all-day
    event today with the given title.
    """
    escaped = details.replace('"', '\\"')
    return (
        'tell application "Calendar"\n'
        "    tell calendar 1\n"
        "        make new event with properties "
        f'{{summary:"{escaped}", start date:(current date), '
        "end date:((current date) + 3600)}\n"
        "    end tell\n"
        "end tell"
    )


async def add_event(details: str) -> ControlResult:
    """Add a calendar event."""
    if not _LIVE_MODE:
        return ControlResult(
            success=True,
            message=f"[mock] Event added: '{details}'",
            action="add_event",
            confirmed=True,
        )

    script = _build_add_event_script(details)
    result = await run_osascript(script)
    if result.success:
        return ControlResult(
            success=True,
            message=f"Event added: '{details}'",
            action="add_event",
            confirmed=True,
        )
    return ControlResult(
        success=False,
        message=f"Failed to add event: {result.stderr}",
        action="add_event",
        confirmed=True,
    )


async def check_calendar(query: str) -> ControlResult:
    """Check the calendar for events matching *query*."""
    if not _LIVE_MODE:
        return ControlResult(
            success=True,
            message=f"[mock] Calendar check for '{query}': no events found",
            action="check_calendar",
            confirmed=True,
        )

    script = _build_check_calendar_script(query)
    result = await run_osascript(script)
    if result.success:
        events = result.stdout if result.stdout else "no events found"
        return ControlResult(
            success=True,
            message=f"Calendar for '{query}': {events}",
            action="check_calendar",
            confirmed=True,
        )
    return ControlResult(
        success=False,
        message=f"Failed to check calendar: {result.stderr}",
        action="check_calendar",
        confirmed=True,
    )
