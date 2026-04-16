"""Contact resolution — 3-layer lookup (Contacts.app, nicknames, recent cache)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import toml

from src.config import CONFIG_DIR


@dataclass
class ContactMatch:
    """A resolved contact."""

    full_name: str
    phone: str | None = None
    email: str | None = None
    source: str = "contacts"


# ── In-memory recent cache ────────────────────────────────────────────

_recent_cache: dict[str, ContactMatch] = {}


def add_recent(name: str, full_name: str) -> None:
    """Add a name → full_name mapping to the recent conversation cache."""
    _recent_cache[name.lower()] = ContactMatch(
        full_name=full_name, source="recent"
    )


def clear_recent() -> None:
    """Clear the recent conversation cache (useful for testing)."""
    _recent_cache.clear()


# ── Nickname loader ───────────────────────────────────────────────────

def _load_nicknames() -> dict[str, str]:
    """Load nickname → full-name map from ``config/contacts_nicknames.toml``.

    Expected TOML format::

        [nicknames]
        mom = "Jane Keller"
        dad = "Bob Keller"

    Returns an empty dict if the file doesn't exist.
    """
    path = CONFIG_DIR / "contacts_nicknames.toml"
    if not path.exists():
        return {}
    data = toml.load(path)
    return {k.lower(): v for k, v in data.get("nicknames", {}).items()}


# ── Layer 1: macOS Contacts.app (mock) ────────────────────────────────

def _lookup_contacts_app(name: str) -> ContactMatch | None:
    """Look up a contact in macOS Contacts.app — mock, always returns None."""
    return None


# ── Layer 2: Nickname map ─────────────────────────────────────────────

def _lookup_nickname(name: str) -> ContactMatch | None:
    """Resolve a nickname to a full contact name."""
    nicknames = _load_nicknames()
    full_name = nicknames.get(name.lower())
    if full_name:
        return ContactMatch(full_name=full_name, source="nickname")
    return None


# ── Layer 3: Recent conversation cache ────────────────────────────────

def _lookup_recent(name: str) -> ContactMatch | None:
    """Check the recent conversation cache for a name."""
    return _recent_cache.get(name.lower())


# ── Public API ────────────────────────────────────────────────────────

def resolve_contact(name: str) -> ContactMatch | None:
    """Resolve a contact name through 3 layers:

    1. macOS Contacts.app (mock — always None for now)
    2. Nickname map from ``config/contacts_nicknames.toml``
    3. Recent conversation cache (in-memory)

    Returns the first match found, or ``None``.
    """
    # Layer 1
    result = _lookup_contacts_app(name)
    if result:
        return result

    # Layer 2
    result = _lookup_nickname(name)
    if result:
        return result

    # Layer 3
    result = _lookup_recent(name)
    if result:
        return result

    return None


def resolve_ambiguous(name: str) -> list[ContactMatch]:
    """Return all matches across all layers for disambiguation."""
    matches: list[ContactMatch] = []

    result = _lookup_contacts_app(name)
    if result:
        matches.append(result)

    result = _lookup_nickname(name)
    if result:
        matches.append(result)

    result = _lookup_recent(name)
    if result:
        matches.append(result)

    return matches
