"""HomeKit scene/device handlers — Shortcuts integration (mock implementations)."""

from __future__ import annotations

from src.hands import ControlResult


async def turn_on(device: str) -> ControlResult:
    """Turn on a HomeKit device — returns mock success."""
    return ControlResult(
        success=True,
        message=f"[mock] Turned on {device}",
        action="turn_on",
        confirmed=True,
    )


async def turn_off(device: str) -> ControlResult:
    """Turn off a HomeKit device — returns mock success."""
    return ControlResult(
        success=True,
        message=f"[mock] Turned off {device}",
        action="turn_off",
        confirmed=True,
    )


async def set_thermostat(temp: str) -> ControlResult:
    """Set thermostat temperature — returns mock success."""
    return ControlResult(
        success=True,
        message=f"[mock] Thermostat set to {temp}",
        action="thermostat",
        confirmed=True,
    )


async def trigger_scene(scene_name: str) -> ControlResult:
    """Trigger a HomeKit scene — returns mock success."""
    return ControlResult(
        success=True,
        message=f"[mock] Scene '{scene_name}' triggered",
        action="scene",
        confirmed=True,
    )


async def lock_device(device: str) -> ControlResult:
    """Lock a device — returns mock success."""
    return ControlResult(
        success=True,
        message=f"[mock] Locked {device}",
        action="lock",
        confirmed=True,
    )


async def unlock_device(device: str) -> ControlResult:
    """Unlock a device — returns mock success."""
    return ControlResult(
        success=True,
        message=f"[mock] Unlocked {device}",
        action="unlock",
        confirmed=True,
    )
