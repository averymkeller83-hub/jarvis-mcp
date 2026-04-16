"""Message handlers — iMessage and Telegram (mock implementations)."""

from __future__ import annotations

from src.hands import ControlResult


def _build_imessage_script(target: str, message: str) -> str:
    """Return the AppleScript that would send an iMessage."""
    escaped_msg = message.replace('"', '\\"')
    return (
        'tell application "Messages"\n'
        f'    set targetBuddy to buddy "{target}" of service "iMessage"\n'
        f'    send "{escaped_msg}" to targetBuddy\n'
        "end tell"
    )


async def send_imessage(target: str, message: str) -> ControlResult:
    """Build iMessage AppleScript — returns mock success without executing."""
    script = _build_imessage_script(target, message)
    return ControlResult(
        success=True,
        message=f"[mock] iMessage to {target}: '{message}' | script: {script}",
        action="message",
        confirmed=True,
    )


async def send_telegram(target: str, message: str) -> ControlResult:
    """Placeholder for Telegram bot API — returns mock success."""
    return ControlResult(
        success=True,
        message=f"[mock] Telegram to {target}: '{message}'",
        action="message",
        confirmed=True,
    )
