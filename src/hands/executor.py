"""Central CONTROL dispatcher — maps verb intents to handler functions."""

from __future__ import annotations

from src.hands import ControlResult
from src.hands.alarms import cancel_alarm, set_alarm, set_timer
from src.hands.calendar import add_event, check_calendar
from src.hands.calls import facetime_call, hang_up, make_call
from src.hands.homekit import (
    lock_device,
    set_thermostat,
    trigger_scene,
    turn_off,
    turn_on,
    unlock_device,
)
from src.hands.messaging import send_imessage, send_telegram
from src.hands.music import (
    pause,
    play,
    previous,
    set_volume,
    skip,
    volume_down,
    volume_up,
)
from src.hands.reminders import add_to_list, set_reminder


# ── Risk tiers ────────────────────────────────────────────────────────

LOW_STAKES: set[str] = {
    "alarm",
    "cancel_alarm",
    "timer",
    "play",
    "pause",
    "skip",
    "previous",
    "volume",
    "volume_up",
    "volume_down",
    "turn_on",
    "turn_off",
    "thermostat",
    "scene",
    "lock",
    "unlock",
    "check_calendar",
}

HIGH_STAKES: set[str] = {
    "message",
    "remind",
    "add_to_list",
    "call",
    "facetime",
    "add_event",
}


def risk_tier(verb: str) -> str:
    """Return ``'low'`` or ``'high'`` for the given verb."""
    if verb in LOW_STAKES:
        return "low"
    if verb in HIGH_STAKES:
        return "high"
    return "high"  # unknown verbs default to high-stakes


# ── Verb → handler dispatch table ─────────────────────────────────────

async def _dispatch(verb: str, target: str | None, payload: str | None) -> ControlResult:
    """Route a verb to its concrete handler and return the result."""
    match verb:
        # Messaging
        case "message":
            return await send_imessage(target or "unknown", payload or "")
        # Reminders
        case "remind":
            return await set_reminder(payload or "", due=target)
        case "add_to_list":
            return await add_to_list(payload or "", list_name=target or "default")
        # Alarms & timers
        case "alarm":
            return await set_alarm(target or "")
        case "cancel_alarm":
            return await cancel_alarm()
        case "timer":
            return await set_timer(target or "")
        # Music
        case "play":
            return await play(payload or target or "")
        case "pause":
            return await pause()
        case "skip":
            return await skip()
        case "previous":
            return await previous()
        case "volume":
            level = int(target) if target and target.isdigit() else 50
            return await set_volume(level)
        case "volume_up":
            return await volume_up()
        case "volume_down":
            return await volume_down()
        # HomeKit
        case "turn_on":
            return await turn_on(target or "device")
        case "turn_off":
            return await turn_off(target or "device")
        case "thermostat":
            return await set_thermostat(target or "72")
        case "scene":
            return await trigger_scene(payload or target or "")
        case "lock":
            return await lock_device(target or "door")
        case "unlock":
            return await unlock_device(target or "door")
        # Calls
        case "call":
            return await make_call(target or "unknown")
        case "facetime":
            return await facetime_call(target or "unknown")
        case "hang_up":
            return await hang_up()
        # Calendar
        case "add_event":
            return await add_event(payload or "")
        case "check_calendar":
            return await check_calendar(target or "today")
        case _:
            return ControlResult(
                success=False,
                message=f"Unknown verb: {verb}",
                action=verb,
                confirmed=False,
            )


# ── Public entry point ────────────────────────────────────────────────

def _confirmation_message(verb: str, target: str | None, payload: str | None) -> str:
    """Build a human-readable confirmation prompt for high-stakes actions."""
    match verb:
        case "message":
            return f"I'm about to text {target} '{payload}' — send?"
        case "remind":
            due_part = f" at {target}" if target else ""
            return f"I'm about to set a reminder: '{payload}'{due_part} — confirm?"
        case "add_to_list":
            return f"I'm about to add '{payload}' to {target} list — confirm?"
        case "call":
            return f"I'm about to call {target} — proceed?"
        case "facetime":
            return f"I'm about to FaceTime {target} — proceed?"
        case "add_event":
            return f"I'm about to add a calendar event: '{payload}' — confirm?"
        case _:
            return f"I'm about to execute {verb} — confirm?"


async def execute_control(
    intent: dict,
    confirmed: bool = False,
) -> ControlResult:
    """Execute a CONTROL intent.

    Parameters
    ----------
    intent:
        ``{"verb": str, "target": str | None, "payload": str | None}``
    confirmed:
        If ``True``, skip the confirmation check for high-stakes actions.

    Returns
    -------
    ControlResult
        Outcome with ``confirmed=False`` if user must still approve.
    """
    verb = intent.get("verb", "")
    target = intent.get("target")
    payload = intent.get("payload")

    tier = risk_tier(verb)

    if tier == "high" and not confirmed:
        return ControlResult(
            success=True,
            message=_confirmation_message(verb, target, payload),
            action=verb,
            confirmed=False,
        )

    return await _dispatch(verb, target, payload)
