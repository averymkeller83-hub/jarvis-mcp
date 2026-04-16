"""Reminder handlers — Reminders.app integration.

When ``_LIVE_MODE`` is True, reminders are created via real AppleScript.
When False (default), returns mock results to preserve test behaviour.
"""

from __future__ import annotations

from src.hands import ControlResult
from src.hands.osascript import check_app_running, launch_app, run_osascript

# ── Live-mode toggle ─────────────────────────────────────────────────
_LIVE_MODE: bool = False


def _build_reminder_script(task: str, due: str | None = None) -> str:
    """Return the AppleScript that would create a Reminder."""
    escaped_task = task.replace('"', '\\"')
    lines = [
        'tell application "Reminders"',
        f'    set newReminder to make new reminder with properties '
        f'{{name:"{escaped_task}"}}',
    ]
    if due:
        escaped_due = due.replace('"', '\\"')
        lines.append(f'    set due date of newReminder to date "{escaped_due}"')
    lines.append("end tell")
    return "\n".join(lines)


def _build_add_to_list_script(item: str, list_name: str) -> str:
    """Return AppleScript that adds *item* to a specific Reminders list."""
    escaped_item = item.replace('"', '\\"')
    escaped_list = list_name.replace('"', '\\"')
    return (
        'tell application "Reminders"\n'
        f'    tell list "{escaped_list}"\n'
        f'        make new reminder with properties {{name:"{escaped_item}"}}\n'
        "    end tell\n"
        "end tell"
    )


async def _ensure_reminders_app() -> bool:
    """Auto-fix: kill unresponsive Reminders.app and relaunch."""
    if await check_app_running("Reminders"):
        return True
    result = await launch_app("Reminders")
    if not result.success:
        return False
    import asyncio

    await asyncio.sleep(1.0)
    return await check_app_running("Reminders")


async def _kill_and_relaunch_reminders() -> bool:
    """Kill Reminders.app and relaunch — last-resort auto-fix."""
    kill_script = (
        'tell application "Reminders" to quit\n'
        "delay 1\n"
        'tell application "Reminders" to activate'
    )
    result = await run_osascript(kill_script, timeout=15.0)
    if not result.success:
        return False
    import asyncio

    await asyncio.sleep(1.5)
    return await check_app_running("Reminders")


async def set_reminder(task: str, due: str | None = None) -> ControlResult:
    """Create a reminder in Reminders.app."""
    script = _build_reminder_script(task, due)
    due_part = f" at {due}" if due else ""

    if not _LIVE_MODE:
        return ControlResult(
            success=True,
            message=f"[mock] Reminder set: '{task}'{due_part} | script: {script}",
            action="remind",
            confirmed=True,
        )

    # ── Live execution ───────────────────────────────────────────────
    if not await _ensure_reminders_app():
        return ControlResult(
            success=False,
            message="Reminders.app is not running and could not be launched",
            action="remind",
            confirmed=True,
        )

    result = await run_osascript(script)
    if result.success:
        return ControlResult(
            success=True,
            message=f"Reminder set: '{task}'{due_part}",
            action="remind",
            confirmed=True,
        )

    # Retry after kill+relaunch
    if await _kill_and_relaunch_reminders():
        retry = await run_osascript(script)
        if retry.success:
            return ControlResult(
                success=True,
                message=f"Reminder set (after recovery): '{task}'{due_part}",
                action="remind",
                confirmed=True,
            )

    return ControlResult(
        success=False,
        message=f"Failed to create reminder: {result.stderr}",
        action="remind",
        confirmed=True,
    )


async def add_to_list(item: str, list_name: str) -> ControlResult:
    """Add an item to a named Reminders list."""
    script = _build_add_to_list_script(item, list_name)

    if not _LIVE_MODE:
        return ControlResult(
            success=True,
            message=f"[mock] Added '{item}' to {list_name} list",
            action="add_to_list",
            confirmed=True,
        )

    # ── Live execution ───────────────────────────────────────────────
    if not await _ensure_reminders_app():
        return ControlResult(
            success=False,
            message="Reminders.app is not running and could not be launched",
            action="add_to_list",
            confirmed=True,
        )

    result = await run_osascript(script)
    if result.success:
        return ControlResult(
            success=True,
            message=f"Added '{item}' to {list_name} list",
            action="add_to_list",
            confirmed=True,
        )

    return ControlResult(
        success=False,
        message=f"Failed to add to list: {result.stderr}",
        action="add_to_list",
        confirmed=True,
    )
