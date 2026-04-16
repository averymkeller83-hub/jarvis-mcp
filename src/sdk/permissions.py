"""Agent permission declarations and validation."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import toml

VALID_PERMISSIONS: set[str] = {
    "web_requests",
    "send_notifications",
    "read_calendar",
    "read_reminders",
    "read_contacts",
    "file_read",
    "file_write",
    "execute_control",
    "shell_exec",
}


def validate_permissions(permissions: list[str]) -> list[str]:
    """Return a list of invalid permission names (empty if all valid)."""
    return [p for p in permissions if p not in VALID_PERMISSIONS]


def load_permissions(path: Path) -> dict[str, Any]:
    """Load agent permissions from TOML file. Returns {} if file missing."""
    if path.exists():
        return toml.load(path)
    return {}


def save_permissions(path: Path, data: dict[str, Any]) -> None:
    """Atomically write permissions to TOML."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w") as f:
        toml.dump(data, f)
    os.replace(tmp, path)


def is_approved(perms: dict[str, Any], agent_name: str) -> bool:
    """Check whether a specific agent is approved."""
    entry = perms.get(agent_name)
    if entry is None:
        return False
    return entry.get("approved", False)


def approve_agent(path: Path, agent_name: str) -> None:
    """Mark an agent as approved and persist the change."""
    data = load_permissions(path)
    if agent_name not in data:
        data[agent_name] = {"permissions": [], "approved": False}
    data[agent_name]["approved"] = True
    data[agent_name]["approved_at"] = datetime.now(timezone.utc).isoformat()
    save_permissions(path, data)
