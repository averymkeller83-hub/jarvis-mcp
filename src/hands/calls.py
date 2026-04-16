"""Phone/FaceTime handlers — URL scheme integration.

When ``_LIVE_MODE`` is True, calls are initiated via ``open tel:``/``open facetime:``.
When False (default), returns mock results to preserve test behaviour.
"""

from __future__ import annotations

from src.hands import ControlResult
from src.hands.osascript import open_url, run_osascript

# ── Live-mode toggle ─────────────────────────────────────────────────
_LIVE_MODE: bool = False


async def make_call(contact: str) -> ControlResult:
    """Initiate a phone call via ``tel:`` URL scheme."""
    url = f"tel:{contact}"

    if not _LIVE_MODE:
        return ControlResult(
            success=True,
            message=f"[mock] Calling {contact} | url: {url}",
            action="call",
            confirmed=True,
        )

    result = await open_url(url)
    if result.success:
        return ControlResult(
            success=True,
            message=f"Calling {contact}",
            action="call",
            confirmed=True,
        )
    return ControlResult(
        success=False,
        message=f"Failed to call {contact}: {result.stderr}",
        action="call",
        confirmed=True,
    )


async def facetime_call(contact: str) -> ControlResult:
    """Initiate FaceTime via ``facetime:`` URL scheme."""
    url = f"facetime:{contact}"

    if not _LIVE_MODE:
        return ControlResult(
            success=True,
            message=f"[mock] FaceTime {contact} | url: {url}",
            action="facetime",
            confirmed=True,
        )

    result = await open_url(url)
    if result.success:
        return ControlResult(
            success=True,
            message=f"FaceTime {contact}",
            action="facetime",
            confirmed=True,
        )
    return ControlResult(
        success=False,
        message=f"Failed to FaceTime {contact}: {result.stderr}",
        action="facetime",
        confirmed=True,
    )


async def hang_up() -> ControlResult:
    """Hang up the current call via AppleScript."""
    if not _LIVE_MODE:
        return ControlResult(
            success=True,
            message="[mock] Call ended",
            action="hang_up",
            confirmed=True,
        )

    # Use AppleScript to close FaceTime — best-effort
    script = 'tell application "FaceTime" to quit'
    result = await run_osascript(script)
    if result.success:
        return ControlResult(
            success=True,
            message="Call ended",
            action="hang_up",
            confirmed=True,
        )
    return ControlResult(
        success=False,
        message=f"Failed to hang up: {result.stderr}",
        action="hang_up",
        confirmed=True,
    )
