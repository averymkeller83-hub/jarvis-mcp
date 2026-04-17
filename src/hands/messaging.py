"""Message handlers — iMessage and Telegram.

When ``_LIVE_MODE`` is True, iMessage is sent via real AppleScript execution.
When False (default), returns mock results to preserve test behaviour.
"""

from __future__ import annotations

from pathlib import Path

import toml

from src.hands import ControlResult
from src.hands.osascript import check_app_running, launch_app, run_osascript

# ── Live-mode toggle ─────────────────────────────────────────────────
_CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"


def _is_live_mode() -> bool:
    """Check if iMessage live mode is enabled via communication.toml."""
    comm_path = _CONFIG_DIR / "communication.toml"
    if not comm_path.exists():
        return False
    try:
        data = toml.load(comm_path)
        enabled = data.get("channels", {}).get("enabled", [])
        return "imessage" in enabled
    except Exception:
        return False


def _build_imessage_script(target: str, message: str) -> str:
    """Return the AppleScript that would send an iMessage.

    Uses the modern approach: iterate services to find the buddy by handle,
    which works on macOS Ventura+ where service names are not fixed.
    """
    escaped_msg = message.replace('"', '\\"').replace("\n", "\\n")
    escaped_target = target.replace('"', '\\"')
    return (
        'tell application "Messages"\n'
        '    set targetService to 1st service whose service type = iMessage\n'
        f'    set targetBuddy to buddy "{escaped_target}" of targetService\n'
        f'    send "{escaped_msg}" to targetBuddy\n'
        'end tell'
    )


async def _ensure_messages_app() -> bool:
    """Auto-fix: launch Messages.app if it is not running.

    Returns True if the app is (or becomes) available.
    """
    if await check_app_running("Messages"):
        return True
    result = await launch_app("Messages")
    if not result.success:
        return False
    # Brief pause to let the app initialise, then re-check
    import asyncio

    await asyncio.sleep(1.0)
    return await check_app_running("Messages")


def _normalize_phone(target: str) -> str:
    """Strip spaces, dashes, parens from phone numbers for iMessage lookup."""
    if target.startswith("+") or target[0:1].isdigit():
        return "".join(c for c in target if c.isdigit() or c == "+")
    return target


async def send_imessage(target: str, message: str) -> ControlResult:
    """Send an iMessage to *target*.

    In mock mode, returns a preview without executing.
    In live mode, launches Messages.app if needed and sends via osascript.
    """
    target = _normalize_phone(target)
    script = _build_imessage_script(target, message)

    if not _is_live_mode():
        return ControlResult(
            success=True,
            message=f"[mock] iMessage to {target}: '{message}' | script: {script}",
            action="message",
            confirmed=True,
        )

    # ── Live execution ───────────────────────────────────────────────
    if not await _ensure_messages_app():
        return ControlResult(
            success=False,
            message="Messages.app is not running and could not be launched",
            action="message",
            confirmed=True,
        )

    result = await run_osascript(script)
    if result.success:
        return ControlResult(
            success=True,
            message=f"iMessage sent to {target}: '{message}'",
            action="message",
            confirmed=True,
        )

    # Auto-fix: if the first attempt failed, try relaunching and retrying
    await launch_app("Messages")
    import asyncio

    await asyncio.sleep(1.5)
    retry = await run_osascript(script)
    if retry.success:
        return ControlResult(
            success=True,
            message=f"iMessage sent to {target} (after retry): '{message}'",
            action="message",
            confirmed=True,
        )

    return ControlResult(
        success=False,
        message=f"Failed to send iMessage: {retry.stderr}",
        action="message",
        confirmed=True,
    )


async def send_telegram(target: str, message: str) -> ControlResult:
    """Send via Telegram using the real backend if configured, else mock."""
    from src.security.vault import load_channel_config

    tg_conf = load_channel_config("telegram")
    if tg_conf and tg_conf.get("bot_token") and tg_conf.get("chat_id"):
        from src.hands.telegram import send as tg_send

        result = await tg_send(tg_conf, message)
        return ControlResult(
            success=result.success,
            message=result.message,
            action="message",
            confirmed=True,
        )
    return ControlResult(
        success=False,
        message=f"Telegram not configured — set bot_token and chat_id in communication.toml",
        action="message",
        confirmed=True,
    )


# ── iMessage polling ────────────────────────────────────────────────

def _get_allowed_senders() -> set[str]:
    """Load allowed iMessage senders from communication.toml.

    Only messages from these handles are processed. Returns empty set to allow all.
    """
    comm_path = _CONFIG_DIR / "communication.toml"
    if not comm_path.exists():
        return set()
    try:
        data = toml.load(comm_path)
        senders = data.get("imessage", {}).get("allowed_senders", [])
        # Normalize phone numbers
        return {_normalize_phone(s) if s[0:1] in ("+", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9") else s.lower() for s in senders}
    except Exception:
        return set()


async def poll_imessage(since_rowid: int = 0) -> tuple[list, int]:
    """Poll ~/Library/Messages/chat.db for new messages.

    Only returns messages from allowed_senders configured in communication.toml.
    If no allowed_senders are configured, returns nothing (safe default).

    Returns (list[IncomingMessage], latest_rowid).
    """
    import asyncio
    import sqlite3
    from datetime import datetime, timezone

    from src.hands.types import IncomingMessage

    db_path = Path.home() / "Library" / "Messages" / "chat.db"
    if not db_path.exists():
        return [], since_rowid

    allowed = _get_allowed_senders()
    if not allowed:
        # No allowed senders configured — skip polling to avoid reading all messages
        return [], since_rowid

    def _query():
        messages = []
        latest = since_rowid
        try:
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT m.ROWID, m.text, m.is_from_me, m.date, h.id as handle_id "
                "FROM message m "
                "LEFT JOIN handle h ON m.handle_id = h.ROWID "
                "WHERE m.ROWID > ? AND m.is_from_me = 0 AND m.text IS NOT NULL "
                "ORDER BY m.ROWID",
                (since_rowid,),
            )
            for row in cursor:
                handle = row["handle_id"] or ""
                # Filter to allowed senders only
                normalized = _normalize_phone(handle) if handle and handle[0:1] in ("+", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9") else handle.lower()
                if normalized not in allowed:
                    latest = max(latest, row["ROWID"])
                    continue
                messages.append(
                    IncomingMessage(
                        text=row["text"],
                        sender=handle,
                        channel="imessage",
                        timestamp=datetime.now(timezone.utc),
                        raw={"rowid": row["ROWID"]},
                    )
                )
                latest = max(latest, row["ROWID"])
            conn.close()
        except Exception:
            pass
        return messages, latest

    return await asyncio.to_thread(_query)
