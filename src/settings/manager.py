"""Settings manager — reads/writes TOML config files as source of truth."""

from __future__ import annotations

import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import toml

CONFIG_DIR: Path = Path(__file__).resolve().parent.parent.parent / "config"

# ── Default values ──────────────────────────────────────────────────────

DEFAULT_PERSONALITY: dict[str, Any] = {
    "identity": {
        "assistant_name": "JARVIS",
        "user_display_name": "Sir",
    },
    "voice": {
        "profile": "default",
        "wake_word_enabled": False,
        "hotkey": "alt+space",
    },
    "behavior": {
        "use_claude_for_chat": False,
        "do_not_disturb": False,
    },
}

DEFAULT_SCOUT_SOURCES: dict[str, Any] = {
    "sources": {},
}

DEFAULT_CONTACTS: dict[str, Any] = {
    "nicknames": {},
}

DEFAULT_CONTROL_TIERS: dict[str, Any] = {
    "low_stakes": [
        "alarm", "cancel_alarm", "timer", "play", "pause", "skip",
        "previous", "volume", "volume_up", "volume_down", "turn_on",
        "turn_off", "thermostat", "scene", "lock", "unlock", "check_calendar",
    ],
    "high_stakes": [
        "message", "remind", "add_to_list", "call", "facetime", "add_event",
    ],
}

DEFAULT_NOTIFICATIONS: dict[str, Any] = {
    "morning_briefing": {"macos": False, "telegram": True, "voice": True, "silent": False},
    "scout_time_sensitive": {"macos": False, "telegram": True, "voice": False, "silent": False},
    "scout_curated": {"macos": False, "telegram": False, "voice": False, "silent": True},
    "control_confirm": {"macos": True, "telegram": False, "voice": True, "silent": False},
    "control_done": {"macos": False, "telegram": False, "voice": True, "silent": True},
    "lessons_propose": {"macos": False, "telegram": True, "voice": False, "silent": False},
    "calendar_reminder": {"macos": True, "telegram": False, "voice": True, "silent": False},
    "ci_failure": {"macos": False, "telegram": True, "voice": False, "silent": False},
    "error_report": {"macos": False, "telegram": True, "voice": False, "silent": False},
}

DEFAULT_BRIEFING: dict[str, Any] = {
    "time": "07:00",
    "timezone": "America/New_York",
    "sections_enabled": {
        "weather": True,
        "calendar": True,
        "tasks": True,
        "scout": True,
        "lessons": True,
    },
}

DEFAULT_PRIVACY: dict[str, Any] = {
    "telemetry_enabled": False,
    "local_only": True,
    "auto_delete_logs_days": 30,
}


# ── File helpers ────────────────────────────────────────────────────────

def _toml_path(name: str) -> Path:
    return CONFIG_DIR / f"{name}.toml"


def _read_toml(name: str, defaults: dict[str, Any]) -> dict[str, Any]:
    path = _toml_path(name)
    if path.exists():
        return toml.load(path)
    return dict(defaults)


def _write_toml(name: str, data: dict[str, Any]) -> bool:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    path = _toml_path(name)
    with open(path, "w") as f:
        toml.dump(data, f)
    return True


# ── Section-specific loaders/savers ─────────────────────────────────────

def load_personality() -> dict[str, Any]:
    return _read_toml("personality", DEFAULT_PERSONALITY)


def save_personality(data: dict[str, Any]) -> bool:
    return _write_toml("personality", data)


def load_scout_sources() -> dict[str, Any]:
    return _read_toml("scout_sources", DEFAULT_SCOUT_SOURCES)


def save_scout_sources(data: dict[str, Any]) -> bool:
    return _write_toml("scout_sources", data)


def load_contacts_nicknames() -> dict[str, Any]:
    return _read_toml("contacts_nicknames", DEFAULT_CONTACTS)


def save_contacts_nicknames(data: dict[str, Any]) -> bool:
    return _write_toml("contacts_nicknames", data)


def load_control_tiers() -> dict[str, Any]:
    return _read_toml("control_tiers", DEFAULT_CONTROL_TIERS)


def save_control_tiers(data: dict[str, Any]) -> bool:
    return _write_toml("control_tiers", data)


def load_notifications() -> dict[str, Any]:
    return _read_toml("notifications", DEFAULT_NOTIFICATIONS)


def save_notifications(data: dict[str, Any]) -> bool:
    return _write_toml("notifications", data)


def load_briefing() -> dict[str, Any]:
    return _read_toml("briefing", DEFAULT_BRIEFING)


def save_briefing(data: dict[str, Any]) -> bool:
    return _write_toml("briefing", data)


def load_privacy() -> dict[str, Any]:
    return _read_toml("privacy", DEFAULT_PRIVACY)


def save_privacy(data: dict[str, Any]) -> bool:
    return _write_toml("privacy", data)


# ── Section registry ────────────────────────────────────────────────────

_SECTION_MAP: dict[str, tuple[Any, Any]] = {
    "personality": (load_personality, save_personality),
    "voice": (load_personality, save_personality),       # voice lives inside personality.toml
    "behavior": (load_personality, save_personality),    # behavior lives inside personality.toml
    "scout_sources": (load_scout_sources, save_scout_sources),
    "contacts": (load_contacts_nicknames, save_contacts_nicknames),
    "control_tiers": (load_control_tiers, save_control_tiers),
    "briefing": (load_briefing, save_briefing),
    "notifications": (load_notifications, save_notifications),
    "privacy": (load_privacy, save_privacy),
}


# ── Aggregate functions ─────────────────────────────────────────────────

def load_all_settings() -> dict[str, Any]:
    """Load and merge all config files into one dict with section keys."""
    personality_data = load_personality()
    return {
        "personality": personality_data.get("identity", personality_data),
        "voice": personality_data.get("voice", {}),
        "behavior": personality_data.get("behavior", {}),
        "scout_sources": load_scout_sources(),
        "contacts": load_contacts_nicknames(),
        "control_tiers": load_control_tiers(),
        "briefing": load_briefing(),
        "notifications": load_notifications(),
        "privacy": load_privacy(),
    }


def save_setting(section: str, key: str, value: Any) -> bool:
    """Write a single setting to the appropriate TOML file."""
    if section not in _SECTION_MAP:
        return False
    loader, saver = _SECTION_MAP[section]
    data = loader()
    # For nested personality sub-sections, update within the right key
    if section in ("voice", "behavior") and section in data:
        data[section][key] = value
    else:
        data[key] = value
    return saver(data)


def save_section(section: str, data: dict[str, Any]) -> bool:
    """Write an entire section to the appropriate TOML file."""
    if section not in _SECTION_MAP:
        return False
    _, saver = _SECTION_MAP[section]
    # For voice/behavior, merge into personality file
    if section in ("voice", "behavior"):
        personality = load_personality()
        personality[section] = data
        return save_personality(personality)
    return saver(data)


def export_all_data(export_path: str) -> str:
    """Create a zip of all config/ + memory/ dirs, return zip path."""
    project_root = CONFIG_DIR.parent
    memory_dir = project_root / "memory"

    if not export_path:
        export_path = str(Path(tempfile.gettempdir()) / "jarvis_export.zip")

    with zipfile.ZipFile(export_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Add config files
        if CONFIG_DIR.exists():
            for file in CONFIG_DIR.rglob("*"):
                if file.is_file():
                    arcname = f"config/{file.relative_to(CONFIG_DIR)}"
                    zf.write(file, arcname)
        # Add memory files
        if memory_dir.exists():
            for file in memory_dir.rglob("*"):
                if file.is_file():
                    arcname = f"memory/{file.relative_to(memory_dir)}"
                    zf.write(file, arcname)

    return export_path
