"""Message handlers — iMessage and Telegram.

When ``_LIVE_MODE`` is True, iMessage is sent via real AppleScript execution.
When False (default), returns mock results to preserve test behaviour.
"""

from __future__ import annotations

from src.hands import ControlResult
from src.hands.osascript import check_app_running, launch_app, run_osascript

# ── Live-mode toggle ─────────────────────────────────────────────────
# Set to True to actually execute AppleScript.  False keeps mock behaviour.
_LIVE_MODE: bool = False


def _build_imessage_script(target: str, message: str) -> str:
    """Return the AppleScript that would send an iMessage."""
    escaped_msg = message.replace('"', '\\"')
    return (
        'tell application "Messages"\n'
        f'    set targetBuddy to buddy "{target}" of service "iMessage"\n'
        f'    send "{escaped_msg}" to targetBuddy\n'
        "end tell"
    )


async def _ensure_messages_app() -> bool:
    """Auto-fix: launch Messages.app if it is not running.

    Returns True if the app is (or becomes) available.
    """
    if await check_app_running("Messages"):
        return True
    result = await launch_app("Messages")
    if not result.success:
        return False
    # Brief pause to let the app initialise, then re-check
    import asyncio

    await asyncio.sleep(1.0)
    return await check_app_running("Messages")


async def send_imessage(target: str, message: str) -> ControlResult:
    """Send an iMessage to *target*.

    In mock mode, returns a preview without executing.
    In live mode, launches Messages.app if needed and sends via osascript.
    """
    script = _build_imessage_script(target, message)

    if not _LIVE_MODE:
        return ControlResult(
            success=True,
            message=f"[mock] iMessage to {target}: '{message}' | script: {script}",
            action="message",
            confirmed=True,
        )

    # ── Live execution ───────────────────────────────────────────────
    if not await _ensure_messages_app():
        return ControlResult(
            success=False,
            message="Messages.app is not running and could not be launched",
            action="message",
            confirmed=True,
        )

    result = await run_osascript(script)
    if result.success:
        return ControlResult(
            success=True,
            message=f"iMessage sent to {target}: '{message}'",
            action="message",
            confirmed=True,
        )

    # Auto-fix: if the first attempt failed, try relaunching and retrying
    await launch_app("Messages")
    import asyncio

    await asyncio.sleep(1.5)
    retry = await run_osascript(script)
    if retry.success:
        return ControlResult(
            success=True,
            message=f"iMessage sent to {target} (after retry): '{message}'",
            action="message",
            confirmed=True,
        )

    return ControlResult(
        success=False,
        message=f"Failed to send iMessage: {retry.stderr}",
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
