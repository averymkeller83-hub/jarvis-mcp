"""User profile — persistent store of what JARVIS learns about the user."""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_PROFILE_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "user_profile.json"
_lock = threading.Lock()


def _read() -> dict[str, Any]:
    if not _PROFILE_PATH.exists():
        return _default_profile()
    try:
        return json.loads(_PROFILE_PATH.read_text())
    except Exception:
        return _default_profile()


def _write(profile: dict[str, Any]) -> None:
    _PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _PROFILE_PATH.write_text(json.dumps(profile, indent=2))


def _default_profile() -> dict[str, Any]:
    return {
        "name": "",
        "preferences": {},
        "interests": [],
        "projects": [],
        "people": [],
        "schedule_patterns": [],
        "facts": [],
        "conversation_style": "",
        "last_updated": "",
    }


def get_profile() -> dict[str, Any]:
    """Return the full user profile."""
    with _lock:
        return _read()


def update_profile(updates: dict[str, Any]) -> dict[str, Any]:
    """Merge updates into the user profile."""
    with _lock:
        profile = _read()
        for key, value in updates.items():
            if key in profile:
                if isinstance(profile[key], list) and isinstance(value, list):
                    # Deduplicate when merging lists
                    existing = set(str(x) for x in profile[key])
                    for item in value:
                        if str(item) not in existing:
                            profile[key].append(item)
                            existing.add(str(item))
                elif isinstance(profile[key], dict) and isinstance(value, dict):
                    profile[key].update(value)
                else:
                    profile[key] = value
        profile["last_updated"] = datetime.now(timezone.utc).isoformat()
        _write(profile)
        return profile


def add_fact(fact: str) -> None:
    """Add a learned fact about the user."""
    with _lock:
        profile = _read()
        if fact not in profile.get("facts", []):
            profile.setdefault("facts", []).append(fact)
            # Keep last 50 facts
            profile["facts"] = profile["facts"][-50:]
            profile["last_updated"] = datetime.now(timezone.utc).isoformat()
            _write(profile)


def add_person(name: str, relationship: str = "") -> None:
    """Add a person the user has mentioned."""
    with _lock:
        profile = _read()
        people = profile.get("people", [])
        existing = [p for p in people if p.get("name", "").lower() == name.lower()]
        if not existing:
            people.append({"name": name, "relationship": relationship})
            profile["people"] = people[-30:]
            profile["last_updated"] = datetime.now(timezone.utc).isoformat()
            _write(profile)


def get_profile_summary() -> str:
    """Return a concise text summary of the user profile for the system prompt."""
    profile = get_profile()
    parts: list[str] = []

    if profile.get("name"):
        parts.append(f"User's name: {profile['name']}")

    if profile.get("interests"):
        parts.append(f"Interests: {', '.join(profile['interests'][:10])}")

    if profile.get("projects"):
        parts.append(f"Active projects: {', '.join(profile['projects'][:8])}")

    if profile.get("people"):
        people_strs = []
        for p in profile["people"][:8]:
            s = p["name"]
            if p.get("relationship"):
                s += f" ({p['relationship']})"
            people_strs.append(s)
        parts.append(f"People mentioned: {', '.join(people_strs)}")

    if profile.get("facts"):
        parts.append(f"Known facts: {'; '.join(profile['facts'][-10:])}")

    if profile.get("preferences"):
        pref_strs = [f"{k}: {v}" for k, v in list(profile["preferences"].items())[:8]]
        parts.append(f"Preferences: {', '.join(pref_strs)}")

    if profile.get("conversation_style"):
        parts.append(f"Conversation style: {profile['conversation_style']}")

    return "\n".join(parts) if parts else ""
