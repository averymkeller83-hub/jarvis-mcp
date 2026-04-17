"""HomeKit scene/device handlers — Shortcuts integration.

When ``_LIVE_MODE`` is True, HomeKit commands are executed via macOS Shortcuts.
When False (default), returns mock results to preserve test behaviour.
"""

from __future__ import annotations

from src.hands import ControlResult
from src.hands.osascript import run_shortcut

# ── Live-mode toggle ─────────────────────────────────────────────────
_LIVE_MODE: bool = True


async def _homekit_shortcut(
    shortcut_name: str,
    input_text: str | None,
    action: str,
    mock_msg: str,
) -> ControlResult:
    """Common path for HomeKit Shortcut execution."""
    if not _LIVE_MODE:
        return ControlResult(
            success=True,
            message=f"[mock] {mock_msg}",
            action=action,
            confirmed=True,
        )

    result = await run_shortcut(shortcut_name, input_text=input_text)
    if result.success:
        return ControlResult(
            success=True,
            message=mock_msg,
            action=action,
            confirmed=True,
        )
    return ControlResult(
        success=False,
        message=f"HomeKit command failed: {result.stderr}",
        action=action,
        confirmed=True,
    )


async def turn_on(device: str) -> ControlResult:
    """Turn on a HomeKit device."""
    return await _homekit_shortcut(
        f"Turn On {device}", device, "turn_on", f"Turned on {device}",
    )


async def turn_off(device: str) -> ControlResult:
    """Turn off a HomeKit device."""
    return await _homekit_shortcut(
        f"Turn Off {device}", device, "turn_off", f"Turned off {device}",
    )


async def set_thermostat(temp: str) -> ControlResult:
    """Set thermostat temperature."""
    return await _homekit_shortcut(
        "Set Thermostat", temp, "thermostat", f"Thermostat set to {temp}",
    )


async def trigger_scene(scene_name: str) -> ControlResult:
    """Trigger a HomeKit scene."""
    return await _homekit_shortcut(
        scene_name, None, "scene", f"Scene '{scene_name}' triggered",
    )


async def lock_device(device: str) -> ControlResult:
    """Lock a device."""
    return await _homekit_shortcut(
        f"Lock {device}", device, "lock", f"Locked {device}",
    )


async def unlock_device(device: str) -> ControlResult:
    """Unlock a device."""
    return await _homekit_shortcut(
        f"Unlock {device}", device, "unlock", f"Unlocked {device}",
    )
