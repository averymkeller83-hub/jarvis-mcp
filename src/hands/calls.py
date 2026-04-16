"""Phone/FaceTime handlers — URL scheme integration (mock implementations)."""

from __future__ import annotations

from src.hands import ControlResult


async def make_call(contact: str) -> ControlResult:
    """Initiate a phone call via ``tel:`` URL scheme — returns mock success."""
    url = f"tel:{contact}"
    return ControlResult(
        success=True,
        message=f"[mock] Calling {contact} | url: {url}",
        action="call",
        confirmed=True,
    )


async def facetime_call(contact: str) -> ControlResult:
    """Initiate FaceTime via ``facetime:`` URL scheme — returns mock success."""
    url = f"facetime:{contact}"
    return ControlResult(
        success=True,
        message=f"[mock] FaceTime {contact} | url: {url}",
        action="facetime",
        confirmed=True,
    )


async def hang_up() -> ControlResult:
    """Hang up the current call — returns mock success."""
    return ControlResult(
        success=True,
        message="[mock] Call ended",
        action="hang_up",
        confirmed=True,
    )
