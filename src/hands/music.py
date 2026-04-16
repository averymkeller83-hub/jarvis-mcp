"""Music playback handlers — Music.app AppleScript (mock implementations)."""

from __future__ import annotations

from src.hands import ControlResult


def _build_music_script(command: str) -> str:
    """Return an AppleScript string for a Music.app command."""
    return f'tell application "Music"\n    {command}\nend tell'


async def play(query: str) -> ControlResult:
    """Play music via Music.app — returns mock success."""
    script = _build_music_script(f'play track "{query}"')
    return ControlResult(
        success=True,
        message=f"[mock] Playing '{query}' | script: {script}",
        action="play",
        confirmed=True,
    )


async def pause() -> ControlResult:
    """Pause Music.app — returns mock success."""
    script = _build_music_script("pause")
    return ControlResult(
        success=True,
        message=f"[mock] Music paused | script: {script}",
        action="pause",
        confirmed=True,
    )


async def skip() -> ControlResult:
    """Skip to next track — returns mock success."""
    script = _build_music_script("next track")
    return ControlResult(
        success=True,
        message=f"[mock] Skipped to next track | script: {script}",
        action="skip",
        confirmed=True,
    )


async def previous() -> ControlResult:
    """Go to previous track — returns mock success."""
    script = _build_music_script("previous track")
    return ControlResult(
        success=True,
        message=f"[mock] Previous track | script: {script}",
        action="previous",
        confirmed=True,
    )


async def set_volume(level: int) -> ControlResult:
    """Set volume to a specific level (0-100) — returns mock success."""
    clamped = max(0, min(100, level))
    script = _build_music_script(f"set sound volume to {clamped}")
    return ControlResult(
        success=True,
        message=f"[mock] Volume set to {clamped} | script: {script}",
        action="volume",
        confirmed=True,
    )


async def volume_up() -> ControlResult:
    """Increase volume by 10 — returns mock success."""
    script = _build_music_script(
        "set sound volume to (sound volume + 10)"
    )
    return ControlResult(
        success=True,
        message=f"[mock] Volume up | script: {script}",
        action="volume_up",
        confirmed=True,
    )


async def volume_down() -> ControlResult:
    """Decrease volume by 10 — returns mock success."""
    script = _build_music_script(
        "set sound volume to (sound volume - 10)"
    )
    return ControlResult(
        success=True,
        message=f"[mock] Volume down | script: {script}",
        action="volume_down",
        confirmed=True,
    )
