"""Calendar handlers — Calendar.app integration (mock implementations)."""

from __future__ import annotations

from src.hands import ControlResult


async def add_event(details: str) -> ControlResult:
    """Add a calendar event — returns mock success."""
    return ControlResult(
        success=True,
        message=f"[mock] Event added: '{details}'",
        action="add_event",
        confirmed=True,
    )


async def check_calendar(query: str) -> ControlResult:
    """Check the calendar — returns mock success."""
    return ControlResult(
        success=True,
        message=f"[mock] Calendar check for '{query}': no events found",
        action="check_calendar",
        confirmed=True,
    )
