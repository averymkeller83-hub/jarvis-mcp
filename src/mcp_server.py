"""JARVIS MCP Server — exposes Jarvis capabilities as MCP tools for Claude."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import toml
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("jarvis")

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


def _load_channel_config(channel: str) -> dict | None:
    """Read per-channel config from communication.toml."""
    comm_path = CONFIG_DIR / "communication.toml"
    if not comm_path.exists():
        return None
    try:
        data = toml.load(comm_path)
        section = data.get(channel, {})
        if section:
            return section
        if channel == "imessage":
            target = data.get("channels", {}).get("imessage_target")
            if target:
                return {"target": target}
        return None
    except Exception:
        return None


# ── Weather ──────────────────────────────────────────────────────────

@mcp.tool()
async def get_weather(location: str = "") -> str:
    """Get the current weather. Leave location empty for default."""
    from src.briefing.sections import fetch_weather
    result = await fetch_weather(location or None)
    return result.content if result.content else "Weather data unavailable."


# ── Briefing ─────────────────────────────────────────────────────────

@mcp.tool()
async def get_briefing() -> str:
    """Compose and return today's morning briefing with weather, news, and calendar."""
    from src.briefing.composer import compose_briefing
    from src.settings.manager import load_news_sources
    from src.briefing.news_sources import get_rss_urls_for_enabled

    news_cfg = load_news_sources()
    enabled = news_cfg.get("enabled", ["hackernews"])
    rss_urls, hn_enabled = get_rss_urls_for_enabled(enabled)
    result = await compose_briefing({"rss_urls": rss_urls, "hn_enabled": hn_enabled})
    summary = result.get("summary", "")
    sections = result.get("sections", [])
    parts = [summary]
    for s in sections:
        parts.append(f"\n## {s.get('title', '')}\n{s.get('content', '')}")
    return "\n".join(parts)


# ── iMessage ─────────────────────────────────────────────────────────

@mcp.tool()
async def send_imessage(target: str, message: str) -> str:
    """Send an iMessage to a contact. Target is a phone number (e.g. +18121234567) or email."""
    from src.hands.messaging import send_imessage as _send
    result = await _send(target, message)
    return result.message


# ── Telegram ────────────────────────────────────────────────────────

@mcp.tool()
async def send_telegram(message: str) -> str:
    """Send a Telegram message using the configured bot."""
    config = _load_channel_config("telegram")
    if not config or not config.get("bot_token"):
        return "Telegram not configured. Run setup to add your bot token."
    from src.hands.telegram import send as tg_send
    result = await tg_send(config, message)
    return result.message


# ── Discord ─────────────────────────────────────────────────────────

@mcp.tool()
async def send_discord(message: str) -> str:
    """Send a Discord message to the configured channel."""
    config = _load_channel_config("discord")
    if not config or not config.get("bot_token"):
        return "Discord not configured. Run setup to add your bot token."
    from src.hands.discord_bot import send as dc_send
    result = await dc_send(config, message)
    return result.message


# ── Slack ───────────────────────────────────────────────────────────

@mcp.tool()
async def send_slack(message: str) -> str:
    """Send a Slack message to the configured channel."""
    config = _load_channel_config("slack")
    if not config or not config.get("bot_token"):
        return "Slack not configured. Run setup to add your bot token."
    from src.hands.slack_bot import send as sl_send
    result = await sl_send(config, message)
    return result.message


# ── Email ───────────────────────────────────────────────────────────

@mcp.tool()
async def send_email(message: str, subject: str = "JARVIS") -> str:
    """Send an email using the configured SMTP account."""
    config = _load_channel_config("email")
    if not config or not config.get("smtp_host"):
        return "Email not configured. Run setup to add your SMTP settings."
    from src.hands.email_client import send as em_send
    result = await em_send(config, message)
    return result.message


# ── Notification ────────────────────────────────────────────────────

@mcp.tool()
async def send_notification_tool(title: str, body: str, channels: str = "") -> str:
    """Send a notification through JARVIS channels.

    Channels is a comma-separated list like 'macos,telegram,imessage'.
    Leave empty to use defaults.
    """
    from src.engine.notifications import Notification, send_notification
    ch_list = [c.strip() for c in channels.split(",") if c.strip()] if channels else []
    n = Notification(event_type="user_request", title=title, body=body, channels=ch_list)
    result = await send_notification(n)
    sent = result.get("sent_to", [])
    if sent:
        return f"Notification sent via: {', '.join(sent)}"
    return "No channels were available to send the notification."


# ── System Status ────────────────────────────────────────────────────

@mcp.tool()
async def get_status() -> str:
    """Get JARVIS system status including running agents and services."""
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get("http://127.0.0.1:7900/status", timeout=5)
            data = resp.json()
            agents_running = data.get("services", {}).get("agents_running", 0)
            return f"JARVIS is running. {agents_running} agent(s) active. All services operational."
    except Exception:
        return "Could not reach JARVIS server."


# ── Scout ────────────────────────────────────────────────────────────

@mcp.tool()
async def run_scout() -> str:
    """Run a Scout discovery scan to find relevant tools, repos, and news."""
    from src.scout.engine import run_discovery
    cards = await run_discovery()
    if not cards:
        return "Scout found nothing new."
    lines = [f"Scout found {len(cards)} item(s):"]
    for c in cards[:5]:
        title = c.get("title", "Untitled") if isinstance(c, dict) else getattr(c, "title", "Untitled")
        lines.append(f"- {title}")
    return "\n".join(lines)


# ── Lessons ──────────────────────────────────────────────────────────

@mcp.tool()
async def get_lessons() -> str:
    """List lessons JARVIS has learned from past interactions."""
    from src.lessons.store import LessonStore
    store = LessonStore()
    lessons = store.list_lessons()
    if not lessons:
        return "No lessons recorded yet."
    lines = [f"{len(lessons)} lesson(s):"]
    for l in lessons[:10]:
        lines.append(f"- {l.get('pattern', 'unknown')}")
    return "\n".join(lines)


# ── Reminders (via Apple Reminders) ──────────────────────────────────

@mcp.tool()
async def set_reminder(text: str) -> str:
    """Set a reminder using macOS Reminders app."""
    from src.hands.osascript import run_osascript
    escaped = text.replace('"', '\\"')
    script = f'tell application "Reminders" to make new reminder with properties {{name:"{escaped}"}}'
    result = await run_osascript(script)
    if result.success:
        return f"Reminder set: {text}"
    return f"Failed to set reminder: {result.stderr}"


# ── Open App ─────────────────────────────────────────────────────────

@mcp.tool()
async def open_app(app_name: str) -> str:
    """Open a macOS application by name."""
    from src.hands.osascript import launch_app
    result = await launch_app(app_name)
    if result.success:
        return f"Opened {app_name}."
    return f"Failed to open {app_name}: {result.stderr}"


# ── Calendar ─────────────────────────────────────────────────────────

@mcp.tool()
async def get_calendar_today() -> str:
    """Get today's calendar events from macOS Calendar."""
    from src.hands.osascript import run_osascript
    script = '''
    set today to current date
    set time of today to 0
    set tomorrow to today + (1 * days)
    tell application "Calendar"
        set output to ""
        repeat with cal in calendars
            set evts to (every event of cal whose start date >= today and start date < tomorrow)
            repeat with evt in evts
                set output to output & (summary of evt) & " at " & (start date of evt) & linefeed
            end repeat
        end repeat
        return output
    end tell
    '''
    result = await run_osascript(script, timeout=10.0)
    if result.success and result.stdout.strip():
        return result.stdout.strip()
    if result.success:
        return "No events on your calendar today."
    return "Could not access Calendar."


# ── Run ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run(transport="stdio")
