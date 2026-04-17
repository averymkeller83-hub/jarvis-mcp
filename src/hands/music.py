"""Music playback handlers — Music.app AppleScript.

When ``_LIVE_MODE`` is True, commands are sent to Music.app via osascript.
When False (default), returns mock results to preserve test behaviour.
"""

from __future__ import annotations

from src.hands import ControlResult
from src.hands.osascript import check_app_running, launch_app, run_osascript

# ── Live-mode toggle ─────────────────────────────────────────────────
_LIVE_MODE: bool = True


def _build_music_script(command: str) -> str:
    """Return an AppleScript string for a Music.app command."""
    return f'tell application "Music"\n    {command}\nend tell'


async def _ensure_music_app() -> bool:
    """Auto-fix: launch Music.app if it is not running."""
    if await check_app_running("Music"):
        return True
    result = await launch_app("Music")
    if not result.success:
        return False
    import asyncio

    await asyncio.sleep(1.0)
    return await check_app_running("Music")


async def _exec_music(command: str, action: str, mock_msg: str) -> ControlResult:
    """Common path: build script, run in mock or live mode."""
    script = _build_music_script(command)

    if not _LIVE_MODE:
        return ControlResult(
            success=True,
            message=f"[mock] {mock_msg} | script: {script}",
            action=action,
            confirmed=True,
        )

    # ── Live execution ───────────────────────────────────────────────
    if not await _ensure_music_app():
        return ControlResult(
            success=False,
            message="Music.app is not running and could not be launched",
            action=action,
            confirmed=True,
        )

    result = await run_osascript(script)
    if result.success:
        return ControlResult(
            success=True,
            message=mock_msg.replace("[mock] ", ""),
            action=action,
            confirmed=True,
        )

    # Retry once after relaunch
    await launch_app("Music")
    import asyncio

    await asyncio.sleep(1.5)
    retry = await run_osascript(script)
    if retry.success:
        return ControlResult(
            success=True,
            message=f"{mock_msg.replace('[mock] ', '')} (after retry)",
            action=action,
            confirmed=True,
        )

    return ControlResult(
        success=False,
        message=f"Music command failed: {retry.stderr}",
        action=action,
        confirmed=True,
    )


async def play(query: str) -> ControlResult:
    """Play music via Music.app."""
    escaped = query.replace('"', '\\"')
    command = (
        f'set searchResults to search playlist "Library" for "{escaped}"\n'
        "    if (count of searchResults) > 0 then\n"
        "        play item 1 of searchResults\n"
        "    else\n"
        f'        play track "{escaped}"\n'
        "    end if"
    )
    return await _exec_music(command, "play", f"Playing '{query}'")


async def pause() -> ControlResult:
    """Pause Music.app."""
    return await _exec_music("pause", "pause", "Music paused")


async def skip() -> ControlResult:
    """Skip to next track."""
    return await _exec_music("next track", "skip", "Skipped to next track")


async def previous() -> ControlResult:
    """Go to previous track."""
    return await _exec_music("previous track", "previous", "Previous track")


async def set_volume(level: int) -> ControlResult:
    """Set volume to a specific level (0-100)."""
    clamped = max(0, min(100, level))
    return await _exec_music(
        f"set sound volume to {clamped}",
        "volume",
        f"Volume set to {clamped}",
    )


async def volume_up() -> ControlResult:
    """Increase volume by 10."""
    return await _exec_music(
        "set sound volume to (sound volume + 10)",
        "volume_up",
        "Volume up",
    )


async def volume_down() -> ControlResult:
    """Decrease volume by 10."""
    return await _exec_music(
        "set sound volume to (sound volume - 10)",
        "volume_down",
        "Volume down",
    )
