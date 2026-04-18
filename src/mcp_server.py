"""JARVIS MCP Server — exposes Jarvis capabilities as MCP tools for Claude Desktop.

This is the bridge that turns Claude into JARVIS. Every tool here is
callable from Claude Desktop when this server is registered in
claude_desktop_config.json.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure the project root is on sys.path so `from src.xxx` imports work
# regardless of how/where this script is launched.
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import toml
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("jarvis")

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


def _load_config() -> dict:
    """Load jarvis.toml."""
    try:
        return toml.load(CONFIG_DIR / "jarvis.toml")
    except Exception:
        return {}


def _load_comm_config() -> dict:
    """Load communication.toml."""
    try:
        return toml.load(CONFIG_DIR / "communication.toml")
    except Exception:
        return {}


# ── Briefing & Awareness ────────────────────────────────────────────


@mcp.tool()
async def get_briefing() -> str:
    """Compose and return today's morning briefing with weather, calendar, email, news, and reminders."""
    from src.briefing.composer import compose_briefing
    from src.briefing.news_sources import get_rss_urls_for_enabled
    from src.settings.manager import load_news_sources

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


@mcp.tool()
async def get_weather(location: str = "") -> str:
    """Get the current weather. Leave location empty for your configured default (Bloomington, IN)."""
    from src.briefing.sections import fetch_weather

    result = await fetch_weather(location or None)
    return result.content if result.content else "Weather data unavailable."


@mcp.tool()
async def get_status() -> str:
    """Get JARVIS system status — what's running, what's healthy."""
    cfg = _load_config()
    loc = cfg.get("location", {}).get("name", "Unknown")
    name = cfg.get("personality", {}).get("assistant_name", "JARVIS")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"{name} online. Location: {loc}. Time: {now}. All systems nominal."


# ── Calendar ────────────────────────────────────────────────────────


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
            set evtStart to start date of evt
            set h to hours of evtStart
            set m to minutes of evtStart
            set hStr to text -2 thru -1 of ("0" & h)
            set mStr to text -2 thru -1 of ("0" & m)
            set output to output & hStr & ":" & mStr & " — " & summary of evt & linefeed
        end repeat
    end repeat
    return output
end tell
'''
    result = await run_osascript(script, timeout=10.0)
    if result.success and result.stdout.strip():
        return "Today's events:\n" + result.stdout.strip()
    if result.success:
        return "No events on your calendar today."
    return "Could not access Calendar."


@mcp.tool()
async def add_calendar_event(title: str, date: str, time: str = "", calendar_name: str = "") -> str:
    """Add an event to macOS Calendar.

    Args:
        title: Event title.
        date: Date string like "2026-04-18" or "tomorrow".
        time: Optional time like "14:00" or "2pm". All-day if omitted.
        calendar_name: Optional calendar name. Uses default if empty.
    """
    from src.hands.osascript import run_osascript

    escaped_title = title.replace('"', '\\"')
    # Build AppleScript for creating the event
    if time:
        script = f'''
tell application "Calendar"
    set targetDate to current date
    set dateStr to "{date} {time}"
    set newEvent to make new event at end of events of first calendar with properties {{summary:"{escaped_title}", start date:targetDate, end date:targetDate + 1 * hours}}
    return "Created: {escaped_title}"
end tell
'''
    else:
        script = f'''
tell application "Calendar"
    set targetDate to current date
    set newEvent to make new event at end of events of first calendar with properties {{summary:"{escaped_title}", start date:targetDate, allday event:true}}
    return "Created: {escaped_title}"
end tell
'''
    result = await run_osascript(script, timeout=10.0)
    if result.success:
        return f"Calendar event created: {title}"
    return f"Failed to create event: {result.stderr}"


# ── Reminders ───────────────────────────────────────────────────────


@mcp.tool()
async def get_reminders() -> str:
    """Get all pending (incomplete) reminders from macOS Reminders."""
    from src.hands.osascript import run_osascript

    script = '''
tell application "Reminders"
    set output to ""
    repeat with rem in (every reminder whose completed is false)
        set dueStr to ""
        try
            set d to due date of rem
            set dueStr to " (due: " & short date string of d & ")"
        end try
        set output to output & "• " & name of rem & dueStr & linefeed
    end repeat
    return output
end tell
'''
    result = await run_osascript(script, timeout=10.0)
    if result.success and result.stdout.strip():
        return "Pending reminders:\n" + result.stdout.strip()
    if result.success:
        return "No pending reminders."
    return "Could not access Reminders."


@mcp.tool()
async def set_reminder(text: str, list_name: str = "") -> str:
    """Create a new reminder in macOS Reminders.

    Args:
        text: Reminder text.
        list_name: Optional list name. Uses default list if empty.
    """
    from src.hands.osascript import run_osascript

    escaped = text.replace('"', '\\"')
    if list_name:
        escaped_list = list_name.replace('"', '\\"')
        script = f'tell application "Reminders" to make new reminder in list "{escaped_list}" with properties {{name:"{escaped}"}}'
    else:
        script = f'tell application "Reminders" to make new reminder with properties {{name:"{escaped}"}}'
    result = await run_osascript(script)
    if result.success:
        return f"Reminder set: {text}"
    return f"Failed to set reminder: {result.stderr}"


# ── Messaging ───────────────────────────────────────────────────────


@mcp.tool()
async def send_imessage(target: str, message: str) -> str:
    """Send an iMessage. Target is a phone number (+18121234567) or email."""
    from src.hands.messaging import send_imessage as _send

    result = await _send(target, message)
    return result.message


@mcp.tool()
async def send_telegram(message: str) -> str:
    """Send a Telegram message via the configured JARVIS bot."""
    comm = _load_comm_config()
    tg = comm.get("telegram", {})
    token = tg.get("bot_token")
    chat_id = tg.get("chat_id")
    if not token or not chat_id:
        return "Telegram not configured in communication.toml."

    import httpx

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json={"chat_id": chat_id, "text": message})
            if resp.status_code == 200:
                return f"Telegram message sent."
            return f"Telegram error: {resp.text}"
    except Exception as e:
        return f"Telegram failed: {e}"


@mcp.tool()
async def send_notification(title: str, body: str) -> str:
    """Send a macOS notification."""
    from src.hands.osascript import run_osascript

    escaped_title = title.replace('"', '\\"')
    escaped_body = body.replace('"', '\\"')
    script = f'display notification "{escaped_body}" with title "{escaped_title}"'
    result = await run_osascript(script)
    if result.success:
        return f"Notification sent: {title}"
    return f"Failed: {result.stderr}"


# ── Contacts ────────────────────────────────────────────────────────


@mcp.tool()
async def lookup_contact(name: str) -> str:
    """Look up a contact by name in macOS Contacts. Returns name, phone, email."""
    from src.hands.osascript import run_osascript

    escaped = name.replace('"', '\\"')
    script = f'''
tell application "Contacts"
    set matches to every person whose name contains "{escaped}"
    if (count of matches) = 0 then return "No contact found for: {escaped}"
    set p to item 1 of matches
    set fullName to name of p
    set phoneNum to ""
    set emailAddr to ""
    try
        set phoneNum to value of first phone of p
    end try
    try
        set emailAddr to value of first email of p
    end try
    return fullName & " | " & phoneNum & " | " & emailAddr
end tell
'''
    result = await run_osascript(script, timeout=10.0)
    if result.success and result.stdout.strip():
        parts = result.stdout.strip().split("|")
        if len(parts) >= 3:
            return f"Name: {parts[0].strip()}\nPhone: {parts[1].strip()}\nEmail: {parts[2].strip()}"
        return result.stdout.strip()
    return f"Contact lookup failed for '{name}'."


# ── Music ───────────────────────────────────────────────────────────


@mcp.tool()
async def play_music(query: str = "") -> str:
    """Play music in Apple Music. Pass a song/artist/playlist name, or empty to resume playback."""
    from src.hands.osascript import run_osascript

    if not query:
        result = await run_osascript('tell application "Music" to play')
        return "Resuming playback." if result.success else f"Failed: {result.stderr}"

    escaped = query.replace('"', '\\"')
    script = f'''
tell application "Music"
    set results to (every track whose name contains "{escaped}" or artist contains "{escaped}")
    if (count of results) > 0 then
        play item 1 of results
        set t to item 1 of results
        return "Now playing: " & name of t & " by " & artist of t
    else
        return "No tracks found for: {escaped}"
    end if
end tell
'''
    result = await run_osascript(script, timeout=10.0)
    if result.success:
        return result.stdout.strip()
    return f"Failed: {result.stderr}"


@mcp.tool()
async def pause_music() -> str:
    """Pause Apple Music playback."""
    from src.hands.osascript import run_osascript

    result = await run_osascript('tell application "Music" to pause')
    return "Music paused." if result.success else f"Failed: {result.stderr}"


@mcp.tool()
async def skip_track() -> str:
    """Skip to the next track in Apple Music."""
    from src.hands.osascript import run_osascript

    result = await run_osascript('tell application "Music" to next track')
    if result.success:
        info = await run_osascript(
            'tell application "Music" to return name of current track & " by " & artist of current track'
        )
        if info.success:
            return f"Skipped. Now playing: {info.stdout.strip()}"
        return "Skipped to next track."
    return f"Failed: {result.stderr}"


@mcp.tool()
async def set_volume(level: int) -> str:
    """Set system volume (0-100)."""
    clamped = max(0, min(100, level))
    from src.hands.osascript import run_osascript

    result = await run_osascript(f"set volume output volume {clamped}")
    return f"Volume set to {clamped}%." if result.success else f"Failed: {result.stderr}"


# ── Alarms & Timers ─────────────────────────────────────────────────


@mcp.tool()
async def set_alarm(time: str, label: str = "JARVIS Alarm") -> str:
    """Set an alarm. Time should be like '7:00 AM' or '14:30'."""
    from src.hands.osascript import run_osascript

    escaped = label.replace('"', '\\"')
    # Use Reminders as an alarm proxy (with due date/time)
    script = f'''
tell application "Reminders"
    set newReminder to make new reminder with properties {{name:"{escaped}", due date:current date}}
    return "Alarm set: {escaped} at {time}"
end tell
'''
    result = await run_osascript(script)
    if result.success:
        return f"Alarm set: {label} at {time}"
    return f"Failed to set alarm: {result.stderr}"


@mcp.tool()
async def set_timer(minutes: int, label: str = "Timer") -> str:
    """Set a timer that fires a notification after the given minutes."""
    # Use a background delayed notification
    from src.hands.osascript import run_osascript

    escaped = label.replace('"', '\\"')
    seconds = minutes * 60
    script = f'delay {seconds}\ndisplay notification "Timer done: {escaped}" with title "JARVIS Timer" sound name "Glass"'
    # Run asynchronously — don't await the full delay
    asyncio.create_task(_run_timer(seconds, escaped))
    return f"Timer set: {label} — {minutes} minute(s). I'll notify you when it's done."


async def _run_timer(seconds: int, label: str) -> None:
    """Background coroutine for timer."""
    await asyncio.sleep(seconds)
    from src.hands.osascript import run_osascript

    await run_osascript(
        f'display notification "Timer done: {label}" with title "JARVIS Timer" sound name "Glass"'
    )


# ── HomeKit ─────────────────────────────────────────────────────────


@mcp.tool()
async def homekit_control(device: str, action: str) -> str:
    """Control a HomeKit device via Shortcuts.

    Args:
        device: Device name (e.g. "Living Room Lights").
        action: Action like "on", "off", "toggle", or a brightness percentage.
    """
    from src.hands.osascript import run_osascript

    # Use Shortcuts to control HomeKit — requires a shortcut named "JARVIS HomeKit"
    escaped_device = device.replace('"', '\\"')
    escaped_action = action.replace('"', '\\"')
    script = f'tell application "Shortcuts Events" to run shortcut "JARVIS HomeKit" with input "{escaped_device}|{escaped_action}"'
    result = await run_osascript(script, timeout=15.0)
    if result.success:
        return f"HomeKit: {device} → {action}"
    return f"HomeKit control failed. Make sure the 'JARVIS HomeKit' shortcut exists. Error: {result.stderr}"


# ── Apps ────────────────────────────────────────────────────────────


@mcp.tool()
async def open_app(app_name: str) -> str:
    """Open a macOS application by name."""
    from src.hands.osascript import launch_app

    result = await launch_app(app_name)
    if result.success:
        return f"Opened {app_name}."
    return f"Failed to open {app_name}: {result.stderr}"


# ── Scout ───────────────────────────────────────────────────────────


@mcp.tool()
async def run_scout() -> str:
    """Run a Scout discovery scan — finds relevant tools, repos, and news for your stack."""
    from src.scout.context import build_user_context
    from src.scout.engine import run_discovery

    user_context = build_user_context()
    cards = await run_discovery(user_context=user_context)
    if not cards:
        return "Scout found nothing new."
    lines = [f"Scout found {len(cards)} item(s):\n"]
    for c in cards[:8]:
        lines.append(f"• **{c.name}** — {c.pitch}")
        if c.match_reason:
            lines.append(f"  Match: {c.match_reason}")
    return "\n".join(lines)


# ── Lessons ─────────────────────────────────────────────────────────


@mcp.tool()
async def get_lessons(category: str = "") -> str:
    """List lessons JARVIS has learned. Optionally filter by category (trust, code, memory, communication, general)."""
    from src.lessons.store import LessonStore

    store = LessonStore()
    if category:
        lessons = store.read_by_category(category, limit=15)
    else:
        lessons = store.read_all(limit=15)
    if not lessons:
        return "No lessons recorded yet."
    lines = [f"{len(lessons)} lesson(s):\n"]
    for l in lessons:
        pin = "📌 " if l.pinned else ""
        lines.append(f"• {pin}[{l.category}] {l.content}")
    return "\n".join(lines)


@mcp.tool()
async def learn(content: str, category: str = "general") -> str:
    """Teach JARVIS something new — a lesson, pattern, or preference to remember.

    Categories: trust, code, memory, communication, general.
    """
    from src.lessons.store import Lesson, LessonStore

    store = LessonStore()
    lesson = Lesson(content=content, category=category, source="explicit")
    lesson_id = store.write(lesson)
    return f"Learned: {content} (category: {category}, id: {lesson_id})"


# ── User Profile ────────────────────────────────────────────────────


@mcp.tool()
async def get_user_profile() -> str:
    """Get what JARVIS knows about you — interests, projects, people, preferences."""
    from src.chat.user_profile import get_profile

    profile = get_profile()
    parts: list[str] = []
    if profile.get("name"):
        parts.append(f"Name: {profile['name']}")
    if profile.get("interests"):
        parts.append(f"Interests: {', '.join(profile['interests'][:10])}")
    if profile.get("projects"):
        parts.append(f"Projects: {', '.join(profile['projects'][:10])}")
    if profile.get("people"):
        people_strs = []
        for p in profile["people"][:10]:
            s = p.get("name", "")
            if p.get("relationship"):
                s += f" ({p['relationship']})"
            people_strs.append(s)
        parts.append(f"People: {', '.join(people_strs)}")
    if profile.get("facts"):
        parts.append(f"Facts: {'; '.join(profile['facts'][-10:])}")
    if profile.get("preferences"):
        pref_strs = [f"{k}: {v}" for k, v in list(profile["preferences"].items())[:8]]
        parts.append(f"Preferences: {', '.join(pref_strs)}")
    return "\n".join(parts) if parts else "No profile data yet."


@mcp.tool()
async def remember_about_user(fact: str) -> str:
    """Remember a fact about the user (preferences, habits, projects, etc.)."""
    from src.chat.user_profile import add_fact

    add_fact(fact)
    return f"Noted: {fact}"


@mcp.tool()
async def remember_person(name: str, relationship: str = "") -> str:
    """Remember a person the user has mentioned (friend, coworker, family, etc.)."""
    from src.chat.user_profile import add_person

    add_person(name, relationship)
    return f"Remembered: {name}" + (f" ({relationship})" if relationship else "")


# ── Email ───────────────────────────────────────────────────────────


@mcp.tool()
async def get_unread_email(limit: int = 10) -> str:
    """Get unread emails from Mail.app. Returns sender and subject for each."""
    from src.hands.osascript import run_osascript

    script = f'''
tell application "Mail"
    set unreadMessages to (every message of inbox whose read status is false)
    set msgCount to count of unreadMessages
    if msgCount = 0 then return "No unread emails."
    set output to ""
    set lim to msgCount
    if lim > {limit} then set lim to {limit}
    repeat with i from 1 to lim
        set msg to item i of unreadMessages
        set senderName to sender of msg
        set subj to subject of msg
        set output to output & "• " & senderName & " — " & subj & linefeed
    end repeat
    return output
end tell
'''
    result = await run_osascript(script, timeout=15.0)
    if result.success and result.stdout.strip():
        return result.stdout.strip()
    if result.success:
        return "No unread emails."
    return "Could not access Mail."


# ── Voice / TTS ─────────────────────────────────────────────────────


@mcp.tool()
async def speak(text: str, voice: str = "Daniel") -> str:
    """Speak text aloud using macOS text-to-speech.

    Args:
        text: What to say.
        voice: macOS voice name (e.g. Daniel, Samantha, Alex). Default: Daniel.
    """
    escaped = text.replace('"', '\\"')
    proc = await asyncio.create_subprocess_exec(
        "say", "-v", voice, escaped,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
    if proc.returncode == 0:
        return f"Spoke: {text[:80]}..."
    return f"TTS failed: {stderr.decode()}"


# ── Notes ───────────────────────────────────────────────────────────


@mcp.tool()
async def create_note(title: str, body: str, folder: str = "Notes") -> str:
    """Create a note in macOS Notes app."""
    from src.hands.osascript import run_osascript

    escaped_title = title.replace('"', '\\"')
    escaped_body = body.replace('"', '\\"')
    escaped_folder = folder.replace('"', '\\"')
    script = f'''
tell application "Notes"
    set targetFolder to first folder whose name is "{escaped_folder}"
    make new note at targetFolder with properties {{name:"{escaped_title}", body:"{escaped_body}"}}
    return "Note created: {escaped_title}"
end tell
'''
    result = await run_osascript(script, timeout=10.0)
    if result.success:
        return f"Note created: {title}"
    return f"Failed to create note: {result.stderr}"


# ── Maps ────────────────────────────────────────────────────────────


@mcp.tool()
async def search_maps(query: str) -> str:
    """Search Apple Maps for a location or business."""
    from src.hands.osascript import run_osascript

    escaped = query.replace('"', '\\"')
    # Open Maps with search query
    script = f'open location "maps://?q={escaped}"'
    result = await run_osascript(script)
    if result.success:
        return f"Opened Maps searching for: {query}"
    return f"Failed to open Maps: {result.stderr}"


# ── System Utilities ────────────────────────────────────────────────


@mcp.tool()
async def get_screen_time() -> str:
    """Get today's screen time summary (if available)."""
    from src.hands.osascript import run_osascript

    # Screen time isn't directly accessible via AppleScript, but we can
    # check how long the system has been awake
    script = '''
set uptime to do shell script "uptime | awk '{print $3, $4}' | sed 's/,//'"
return "System uptime: " & uptime
'''
    result = await run_osascript(script, timeout=5.0)
    if result.success:
        return result.stdout.strip()
    return "Could not get screen time info."


@mcp.tool()
async def do_not_disturb(enabled: bool) -> str:
    """Toggle Do Not Disturb / Focus mode on macOS."""
    from src.hands.osascript import run_osascript

    if enabled:
        script = 'do shell script "defaults -currentHost write com.apple.notificationcenterui doNotDisturb -boolean true && killall NotificationCenter 2>/dev/null; true"'
    else:
        script = 'do shell script "defaults -currentHost write com.apple.notificationcenterui doNotDisturb -boolean false && killall NotificationCenter 2>/dev/null; true"'
    result = await run_osascript(script)
    state = "on" if enabled else "off"
    if result.success:
        return f"Do Not Disturb: {state}"
    return f"Failed to toggle DND: {result.stderr}"


# ── Code Agents (Claude Code dispatch) ──────────────────────────────

_CLAUDE_BIN = "/Users/averykeller/.npm-global/bin/claude"

_KNOWN_PROJECTS: dict[str, str] = {
    "jarvis": "/Users/averykeller/Desktop/projects/jarvis-mcp",
    "jarvis-mcp": "/Users/averykeller/Desktop/projects/jarvis-mcp",
    "magic-puffs": "/Users/averykeller/Desktop/projects/magic-puffs-website",
    "tree-truffles": "/Users/averykeller/Desktop/projects/magic-puffs-website",
    "clawwork": "/Users/averykeller/Desktop/projects/clawwork-dashboard",
    "clawwork-earnings": "/Users/averykeller/Desktop/projects/clawwork-earnings",
    "noise-agency": "/Users/averykeller/Desktop/projects/noise-agency",
    "horizon": "/Users/averykeller/Desktop/projects/horizon-lead-gen",
    "sakura-radio": "/Users/averykeller/Desktop/projects/sakura-radio",
    "chess-agent": "/Users/averykeller/Desktop/projects/chess-agent",
}

# Track background agents
_background_agents: dict[str, dict] = {}


def _resolve_project(project: str) -> str:
    """Resolve a project name or path to an absolute directory."""
    if project in _KNOWN_PROJECTS:
        return _KNOWN_PROJECTS[project]
    p = Path(project).expanduser()
    if p.is_dir():
        return str(p)
    # Try as a subdirectory of ~/Desktop/projects/
    candidate = Path.home() / "Desktop" / "projects" / project
    if candidate.is_dir():
        return str(candidate)
    return str(p)


@mcp.tool()
async def list_projects() -> str:
    """List known projects that code agents can work on."""
    lines = ["Available projects:\n"]
    seen: set[str] = set()
    for name, path in _KNOWN_PROJECTS.items():
        if path not in seen:
            exists = Path(path).is_dir()
            status = "" if exists else " (not found)"
            lines.append(f"• **{name}** — {path}{status}")
            seen.add(path)
    return "\n".join(lines)


@mcp.tool()
async def dispatch_code_agent(task: str, project: str = "jarvis-mcp", max_turns: int = 25) -> str:
    """Dispatch a Claude Code agent to perform a coding task in a project.

    The agent has full access to read/write files, run tests, and use git.
    This waits for the agent to finish and returns the result.

    Args:
        task: What the agent should do (e.g. "fix the login bug", "add unit tests for auth module").
        project: Project name (e.g. "jarvis", "magic-puffs", "clawwork") or full path.
        max_turns: Maximum number of turns the agent can take (default 25).
    """
    cwd = _resolve_project(project)
    if not Path(cwd).is_dir():
        return f"Project directory not found: {cwd}"

    try:
        proc = await asyncio.create_subprocess_exec(
            _CLAUDE_BIN,
            "--dangerously-skip-permissions",
            "-p", task,
            "--output-format", "json",
            "--max-turns", str(max_turns),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=600)
        raw = stdout.decode()

        try:
            data = json.loads(raw)
            result_text = data.get("result", "")
            cost = data.get("total_cost_usd", 0)
            turns = data.get("num_turns", 0)
            duration = data.get("duration_ms", 0)

            summary = f"Agent completed in {duration / 1000:.1f}s ({turns} turns, ${cost:.4f}).\n\n{result_text}"
            return summary
        except json.JSONDecodeError:
            return f"Agent finished but output was not valid JSON:\n{raw[:2000]}"

    except asyncio.TimeoutError:
        return "Agent timed out after 10 minutes. The task may be too large — try breaking it down."
    except Exception as e:
        return f"Failed to dispatch agent: {e}"


@mcp.tool()
async def dispatch_background_agent(task: str, project: str = "jarvis-mcp", max_turns: int = 25) -> str:
    """Dispatch a Claude Code agent in the background — returns immediately.

    You'll get a macOS notification when it finishes. Use check_background_agent to see results.

    Args:
        task: What the agent should do.
        project: Project name or full path.
        max_turns: Maximum turns (default 25).
    """
    import uuid

    cwd = _resolve_project(project)
    if not Path(cwd).is_dir():
        return f"Project directory not found: {cwd}"

    agent_id = str(uuid.uuid4())[:8]
    _background_agents[agent_id] = {
        "task": task,
        "project": project,
        "status": "running",
        "result": None,
        "started": datetime.now(timezone.utc).isoformat(),
    }

    async def _run_agent():
        try:
            proc = await asyncio.create_subprocess_exec(
                _CLAUDE_BIN,
                "--dangerously-skip-permissions",
                "-p", task,
                "--output-format", "json",
                "--max-turns", str(max_turns),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=600)
            raw = stdout.decode()

            try:
                data = json.loads(raw)
                result_text = data.get("result", "")
                cost = data.get("total_cost_usd", 0)
                turns = data.get("num_turns", 0)
                _background_agents[agent_id]["status"] = "completed"
                _background_agents[agent_id]["result"] = result_text
                _background_agents[agent_id]["cost"] = cost
                _background_agents[agent_id]["turns"] = turns
                notify_body = f"Done: {task[:60]}... ({turns} turns, ${cost:.4f})"
            except json.JSONDecodeError:
                _background_agents[agent_id]["status"] = "completed"
                _background_agents[agent_id]["result"] = raw[:2000]
                notify_body = f"Done: {task[:80]}"

        except asyncio.TimeoutError:
            _background_agents[agent_id]["status"] = "timed_out"
            _background_agents[agent_id]["result"] = "Timed out after 10 minutes."
            notify_body = f"Timed out: {task[:80]}"
        except Exception as e:
            _background_agents[agent_id]["status"] = "failed"
            _background_agents[agent_id]["result"] = str(e)
            notify_body = f"Failed: {task[:80]}"

        # Send macOS notification (must pipe stdout/stderr to avoid corrupting MCP transport)
        escaped = notify_body.replace('"', '\\"')
        proc2 = await asyncio.create_subprocess_exec(
            "osascript", "-e",
            f'display notification "{escaped}" with title "JARVIS Agent [{agent_id}]" sound name "Glass"',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc2.communicate()

    asyncio.create_task(_run_agent())
    return f"Agent dispatched (id: {agent_id}). Working on: {task}\nProject: {cwd}\nI'll notify you when it's done. Use check_background_agent('{agent_id}') to check status."


@mcp.tool()
async def check_background_agent(agent_id: str = "") -> str:
    """Check the status of background code agents.

    Leave agent_id empty to see all agents, or pass a specific ID.
    """
    if not _background_agents:
        return "No background agents have been dispatched."

    if agent_id:
        agent = _background_agents.get(agent_id)
        if not agent:
            return f"No agent found with id: {agent_id}"
        lines = [
            f"Agent {agent_id}:",
            f"  Task: {agent['task']}",
            f"  Project: {agent['project']}",
            f"  Status: {agent['status']}",
            f"  Started: {agent['started']}",
        ]
        if agent.get("result"):
            lines.append(f"  Result:\n{agent['result']}")
        if agent.get("cost"):
            lines.append(f"  Cost: ${agent['cost']:.4f}")
        return "\n".join(lines)

    # List all
    lines = [f"{len(_background_agents)} background agent(s):\n"]
    for aid, agent in _background_agents.items():
        status_icon = {"running": "...", "completed": "done", "failed": "FAIL", "timed_out": "TIMEOUT"}.get(agent["status"], "?")
        lines.append(f"• [{aid}] {status_icon} — {agent['task'][:60]}")
    return "\n".join(lines)


# ── Voice Mode ─────────────────────────────────────────────────────

# Runtime flag — NOT persisted to config file.
_voice_mode_enabled: bool = False
_voice_mode_voice: str = "Daniel"


def _init_voice_mode() -> None:
    """Seed voice-mode defaults from jarvis.toml [voice] section."""
    global _voice_mode_enabled, _voice_mode_voice
    cfg = _load_config().get("voice", {})
    _voice_mode_enabled = bool(cfg.get("enabled", False))
    _voice_mode_voice = cfg.get("voice_name", "Daniel")


# Run once at import time so the flag matches the config on startup.
_init_voice_mode()


@mcp.tool()
async def enable_voice_mode(voice: str = "") -> str:
    """Turn on JARVIS voice narration. All jarvis_say calls will speak aloud.

    Args:
        voice: Optional macOS voice name to use (e.g. Daniel, Samantha, Alex).
               Defaults to the voice set in jarvis.toml or "Daniel".
    """
    global _voice_mode_enabled, _voice_mode_voice
    _voice_mode_enabled = True
    if voice:
        _voice_mode_voice = voice
    return f"Voice mode enabled (voice: {_voice_mode_voice}). I'll narrate my responses, sir."


@mcp.tool()
async def disable_voice_mode() -> str:
    """Turn off JARVIS voice narration."""
    global _voice_mode_enabled
    _voice_mode_enabled = False
    return "Voice mode disabled. Back to the quiet life."


@mcp.tool()
async def jarvis_say(text: str) -> str:
    """JARVIS narrates a response — speaks it aloud (if voice mode is on) AND returns the text.

    Use this instead of `speak` when JARVIS is narrating his own responses.
    Unlike `speak`, this always returns the text (for display) and only
    invokes TTS when voice mode is enabled.

    Args:
        text: The text JARVIS should narrate.
    """
    if _voice_mode_enabled:
        proc = await asyncio.create_subprocess_exec(
            "say", "-v", _voice_mode_voice, text,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        if proc.returncode != 0:
            return f"{text}\n\n(TTS error: {stderr.decode().strip()})"
    return text


# ── Clipboard ───────────────────────────────────────────────────────


@mcp.tool()
async def get_clipboard() -> str:
    """Get the current contents of the macOS clipboard."""
    proc = await asyncio.create_subprocess_exec(
        "pbpaste",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
    text = stdout.decode()
    if not text:
        return "Clipboard is empty."
    return f"Clipboard contents:\n{text[:2000]}"


@mcp.tool()
async def set_clipboard(text: str) -> str:
    """Copy text to the macOS clipboard."""
    proc = await asyncio.create_subprocess_exec(
        "pbcopy",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await asyncio.wait_for(proc.communicate(input=text.encode()), timeout=5)
    if proc.returncode == 0:
        return f"Copied to clipboard ({len(text)} chars)."
    return "Failed to copy to clipboard."


# ── URL Opening ─────────────────────────────────────────────────────


@mcp.tool()
async def open_url(url: str) -> str:
    """Open a URL in the default browser."""
    proc = await asyncio.create_subprocess_exec(
        "open", url,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
    if proc.returncode == 0:
        return f"Opened: {url}"
    return f"Failed to open URL: {stderr.decode()}"


# ── Scheduled Tasks (LaunchAgents) ──────────────────────────────────

_LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"
_TASK_PREFIX = "com.jarvis.task."


def _task_plist_path(name: str) -> Path:
    safe_name = name.replace(" ", "-").replace("/", "-").lower()
    return _LAUNCH_AGENTS_DIR / f"{_TASK_PREFIX}{safe_name}.plist"


def _build_plist(name: str, interval_minutes: int, task_prompt: str) -> str:
    """Build a LaunchAgent plist that runs a Claude CLI prompt on a schedule."""
    safe_name = name.replace(" ", "-").replace("/", "-").lower()
    label = f"{_TASK_PREFIX}{safe_name}"
    interval_seconds = interval_minutes * 60
    project_root = str(Path(__file__).resolve().parent.parent)

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{label}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{_CLAUDE_BIN}</string>
        <string>--dangerously-skip-permissions</string>
        <string>-p</string>
        <string>{task_prompt}</string>
        <string>--output-format</string>
        <string>json</string>
        <string>--max-turns</string>
        <string>10</string>
    </array>
    <key>WorkingDirectory</key>
    <string>{project_root}</string>
    <key>StartInterval</key>
    <integer>{interval_seconds}</integer>
    <key>RunAtLoad</key>
    <false/>
    <key>StandardOutPath</key>
    <string>{project_root}/logs/task-{safe_name}.stdout.log</string>
    <key>StandardErrorPath</key>
    <string>{project_root}/logs/task-{safe_name}.stderr.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PYTHONPATH</key>
        <string>{project_root}</string>
        <key>PATH</key>
        <string>/usr/local/bin:/opt/homebrew/bin:/Users/averykeller/.npm-global/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>"""


@mcp.tool()
async def schedule_task(name: str, interval_minutes: int, task: str) -> str:
    """Schedule a recurring JARVIS task that runs automatically.

    Creates a macOS LaunchAgent that runs the task on a timer using Claude CLI.

    Args:
        name: Short name for the task (e.g. "email-check", "morning-briefing").
        interval_minutes: How often to run, in minutes (e.g. 60 for hourly, 120 for every 2 hours).
        task: What to do each time (e.g. "Check unread emails and send a Telegram summary if anything important").
    """
    plist_path = _task_plist_path(name)

    # Ensure logs directory exists
    logs_dir = Path(__file__).resolve().parent.parent / "logs"
    logs_dir.mkdir(exist_ok=True)

    # Write the plist
    plist_content = _build_plist(name, interval_minutes, task)
    plist_path.write_text(plist_content)

    # Load the agent
    proc = await asyncio.create_subprocess_exec(
        "launchctl", "load", str(plist_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)

    if proc.returncode == 0:
        return f"Scheduled: '{name}' — runs every {interval_minutes} minutes.\nTask: {task}"
    return f"Created plist but failed to load: {stderr.decode()}"


@mcp.tool()
async def list_scheduled_tasks() -> str:
    """List all JARVIS scheduled tasks."""
    _LAUNCH_AGENTS_DIR.mkdir(exist_ok=True)
    tasks = list(_LAUNCH_AGENTS_DIR.glob(f"{_TASK_PREFIX}*.plist"))

    if not tasks:
        return "No scheduled tasks."

    lines = [f"{len(tasks)} scheduled task(s):\n"]
    for plist_path in tasks:
        name = plist_path.stem.replace(_TASK_PREFIX, "")
        # Check if loaded
        proc = await asyncio.create_subprocess_exec(
            "launchctl", "list", f"{_TASK_PREFIX}{name}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        status = "running" if proc.returncode == 0 else "stopped"
        lines.append(f"• **{name}** — {status}")

    return "\n".join(lines)


@mcp.tool()
async def remove_scheduled_task(name: str) -> str:
    """Remove a JARVIS scheduled task.

    Args:
        name: The task name used when it was created.
    """
    plist_path = _task_plist_path(name)

    if not plist_path.exists():
        return f"No task found named '{name}'."

    # Unload first
    proc = await asyncio.create_subprocess_exec(
        "launchctl", "unload", str(plist_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()

    # Delete the plist
    plist_path.unlink()
    return f"Removed scheduled task: '{name}'"


# ── Run ─────────────────────────────────────────────────────────────


if __name__ == "__main__":
    mcp.run(transport="stdio")
