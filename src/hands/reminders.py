"""Reminder handlers — Reminders.app integration (mock implementations)."""

from __future__ import annotations

from src.hands import ControlResult


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


async def set_reminder(task: str, due: str | None = None) -> ControlResult:
    """Build reminder AppleScript — returns mock success without executing."""
    script = _build_reminder_script(task, due)
    due_part = f" at {due}" if due else ""
    return ControlResult(
        success=True,
        message=f"[mock] Reminder set: '{task}'{due_part} | script: {script}",
        action="remind",
        confirmed=True,
    )


async def add_to_list(item: str, list_name: str) -> ControlResult:
    """Add an item to a named Reminders list — returns mock success."""
    return ControlResult(
        success=True,
        message=f"[mock] Added '{item}' to {list_name} list",
        action="add_to_list",
        confirmed=True,
    )
