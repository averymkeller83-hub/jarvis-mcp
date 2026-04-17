"""Server-side chat history — JSON file backed, thread-safe."""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_STORE_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "chat_history.json"
_MAX_MESSAGES = 500  # keep last N messages to avoid unbounded growth
_lock = threading.Lock()


def _read() -> list[dict[str, Any]]:
    if not _STORE_PATH.exists():
        return []
    try:
        return json.loads(_STORE_PATH.read_text())
    except Exception:
        return []


def _write(messages: list[dict[str, Any]]) -> None:
    _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _STORE_PATH.write_text(json.dumps(messages, indent=None))


def append_message(role: str, text: str, surface: str | None = None) -> dict[str, Any]:
    """Add a message to the chat history. Returns the stored message."""
    msg = {
        "role": role,
        "text": text,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if surface:
        msg["surface"] = surface

    with _lock:
        messages = _read()
        messages.append(msg)
        # Trim to max
        if len(messages) > _MAX_MESSAGES:
            messages = messages[-_MAX_MESSAGES:]
        _write(messages)

    return msg


def get_history(limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    """Return chat history, newest last. Supports pagination."""
    with _lock:
        messages = _read()
    if offset:
        messages = messages[:-offset] if offset < len(messages) else []
    return messages[-limit:]


def get_conversation_buffer(limit: int = 20) -> list[dict[str, str]]:
    """Return recent messages formatted for the Anthropic SDK conversation."""
    with _lock:
        messages = _read()
    recent = messages[-limit:]
    buffer = []
    for m in recent:
        role = "user" if m["role"] == "user" else "assistant"
        buffer.append({"role": role, "content": m["text"]})
    return buffer


def clear_history() -> None:
    """Delete all chat history."""
    with _lock:
        _write([])
