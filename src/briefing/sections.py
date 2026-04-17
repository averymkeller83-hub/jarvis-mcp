"""Briefing section fetchers — each returns a BriefingSection dataclass."""

from __future__ import annotations

import asyncio
import logging
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class BriefingSection:
    """A single section of the daily briefing."""

    title: str
    content: str = ""
    items: list[dict] = field(default_factory=list)
    empty: bool = False


# ── Weather ──────────────────────────────────────────────────────────


async def fetch_weather(
    location: str | None = None,
    *,
    latitude: float | None = None,
    longitude: float | None = None,
) -> BriefingSection:
    """Return current weather for *location* using Open-Meteo.

    Returns empty on failure.
    """
    from src.integrations.weather import DEFAULT_LOCATION_NAME
    loc = location or DEFAULT_LOCATION_NAME
    try:
        from src.integrations.weather import (
            DEFAULT_LAT,
            DEFAULT_LON,
            fetch_weather_data,
            geocode_location,
        )

        lat = latitude or DEFAULT_LAT
        lon = longitude or DEFAULT_LON

        # If a location string is given (and no explicit lat/lon), geocode it
        if location and latitude is None and longitude is None:
            coords = await geocode_location(location)
            if coords:
                lat, lon = coords

        data = await fetch_weather_data(lat, lon)
        # Always use the user-friendly location label in the summary
        data["summary"] = (
            f"{data['condition']} in {loc}. "
            f"High of {data['high']} °F, low of {data['low']} °F."
        )

        return BriefingSection(
            title="Weather",
            content=data["summary"],
            items=[data],
            empty=False,
        )
    except Exception:
        logger.debug("Weather fetch failed", exc_info=True)
        return BriefingSection(title="Weather", empty=True)


# ── Calendar ─────────────────────────────────────────────────────────


async def fetch_calendar() -> BriefingSection:
    """Return today's calendar events via AppleScript.

    Returns empty when no events are found or Calendar.app is unavailable.
    """
    script = '''
tell application "Calendar"
    set today to current date
    set time of today to 0
    set tomorrow to today + 1 * days
    set output to ""
    repeat with cal in calendars
        repeat with evt in (every event of cal whose start date >= today and start date < tomorrow)
            set evtStart to start date of evt
            set h to hours of evtStart
            set m to minutes of evtStart
            set hStr to text -2 thru -1 of ("0" & h)
            set mStr to text -2 thru -1 of ("0" & m)
            set output to output & hStr & ":" & mStr & " | " & summary of evt & linefeed
        end repeat
    end repeat
    return output
end tell
'''
    try:
        result = await asyncio.to_thread(
            subprocess.run,
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=10,
        )
        raw = result.stdout.strip()
        if not raw:
            return BriefingSection(title="Calendar", empty=True)

        events: list[dict] = []
        for line in raw.splitlines():
            line = line.strip()
            if not line or "|" not in line:
                continue
            parts = line.split("|", 1)
            time_str = parts[0].strip()
            title = parts[1].strip() if len(parts) > 1 else ""
            events.append({"time": time_str, "title": title})

        if not events:
            return BriefingSection(title="Calendar", empty=True)

        content = f"{len(events)} event(s) today."
        return BriefingSection(
            title="Calendar",
            content=content,
            items=events,
            empty=False,
        )
    except Exception:
        logger.debug("Calendar fetch failed", exc_info=True)
        return BriefingSection(title="Calendar", empty=True)


# ── Email ────────────────────────────────────────────────────────────


async def fetch_email() -> BriefingSection:
    """Return unread mail summary from Mail.app via AppleScript.

    Returns empty when nothing unread or Mail.app is unavailable.
    """
    script = '''
tell application "Mail"
    set unreadMessages to (every message of inbox whose read status is false)
    set msgCount to count of unreadMessages
    if msgCount = 0 then return ""
    set output to ""
    set limit to msgCount
    if limit > 10 then set limit to 10
    repeat with i from 1 to limit
        set msg to item i of unreadMessages
        set senderName to sender of msg
        set subj to subject of msg
        set output to output & senderName & " | " & subj & linefeed
    end repeat
    return output
end tell
'''
    try:
        result = await asyncio.to_thread(
            subprocess.run,
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=15,
        )
        raw = result.stdout.strip()
        if not raw:
            return BriefingSection(title="Email", empty=True)

        items: list[dict] = []
        for line in raw.splitlines():
            line = line.strip()
            if not line or "|" not in line:
                continue
            parts = line.split("|", 1)
            sender = parts[0].strip()
            subject = parts[1].strip() if len(parts) > 1 else ""
            items.append({"sender": sender, "subject": subject})

        if not items:
            return BriefingSection(title="Email", empty=True)

        content = f"{len(items)} unread email(s)."
        return BriefingSection(
            title="Email",
            content=content,
            items=items,
            empty=False,
        )
    except Exception:
        logger.debug("Email fetch failed", exc_info=True)
        return BriefingSection(title="Email", empty=True)


# ── GitHub ───────────────────────────────────────────────────────────


async def fetch_github(repos: list[str] | None = None) -> BriefingSection:
    """Return recent GitHub activity for the given *repos*.

    Returns empty when no repos are configured or no activity found.
    """
    if not repos:
        return BriefingSection(title="GitHub", empty=True)

    try:
        from src.integrations.github import fetch_repo_activity

        all_issues: list[dict] = []
        all_prs: list[dict] = []
        ci_statuses: dict[str, str | None] = {}

        for repo in repos:
            try:
                activity = await fetch_repo_activity(repo)
                for issue in activity.get("open_issues", []):
                    issue["repo"] = repo
                    all_issues.append(issue)
                for pr in activity.get("recent_prs", []):
                    pr["repo"] = repo
                    all_prs.append(pr)
                ci_statuses[repo] = activity.get("ci_status")
            except Exception:
                continue

        if not all_issues and not all_prs:
            return BriefingSection(title="GitHub", empty=True)

        items = [
            {"open_issues": all_issues, "recent_prs": all_prs, "ci_status": ci_statuses},
        ]
        parts: list[str] = []
        if all_issues:
            parts.append(f"{len(all_issues)} open issue(s)")
        if all_prs:
            parts.append(f"{len(all_prs)} PR(s)")
        content = ", ".join(parts) + f" across {len(repos)} repo(s)."

        return BriefingSection(
            title="GitHub",
            content=content,
            items=items,
            empty=False,
        )
    except Exception:
        return BriefingSection(title="GitHub", empty=True)


# ── News ─────────────────────────────────────────────────────────────


async def fetch_news(
    *,
    rss_urls: list[str] | None = None,
    hn_enabled: bool = False,
    hn_limit: int = 5,
    hn_min_score: int = 100,
) -> BriefingSection:
    """Return top headlines from RSS / HN.

    Set *hn_enabled* to ``True`` to include Hacker News stories.
    Returns empty when no news sources are configured or no news is available.
    """
    all_items: list[dict] = []

    try:
        if rss_urls:
            from src.integrations.rss import fetch_multiple_feeds

            feeds = await fetch_multiple_feeds(rss_urls, limit_per_feed=5)
            for f in feeds:
                all_items.append({
                    "title": f.get("title", ""),
                    "url": f.get("url", ""),
                    "source": "rss",
                })
    except Exception:
        pass

    if hn_enabled:
        try:
            from src.integrations.hackernews import fetch_top_stories

            stories = await fetch_top_stories(limit=hn_limit, min_score=hn_min_score)
            for s in stories:
                all_items.append({
                    "title": s.get("title", ""),
                    "url": s.get("hn_url", s.get("url", "")),
                    "source": "hackernews",
                    "score": s.get("score", 0),
                })
        except Exception:
            pass

    if not all_items:
        return BriefingSection(title="News", empty=True)

    content = f"{len(all_items)} headline(s) from RSS and Hacker News."
    return BriefingSection(
        title="News",
        content=content,
        items=all_items,
        empty=False,
    )


# ── Reminders ────────────────────────────────────────────────────────


async def fetch_reminders() -> BriefingSection:
    """Return pending (incomplete) reminders via AppleScript.

    Returns empty when there are none or Reminders.app is unavailable.
    """
    script = '''
tell application "Reminders"
    set output to ""
    repeat with rem in (every reminder whose completed is false)
        set dueStr to ""
        try
            set d to due date of rem
            set dueStr to short date string of d
        end try
        set output to output & name of rem & " | " & dueStr & linefeed
    end repeat
    return output
end tell
'''
    try:
        result = await asyncio.to_thread(
            subprocess.run,
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=10,
        )
        raw = result.stdout.strip()
        if not raw:
            return BriefingSection(title="Reminders", empty=True)

        items: list[dict] = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split("|", 1)
            name = parts[0].strip()
            due = parts[1].strip() if len(parts) > 1 else ""
            items.append({"name": name, "due": due})

        if not items:
            return BriefingSection(title="Reminders", empty=True)

        content = f"{len(items)} pending reminder(s)."
        return BriefingSection(
            title="Reminders",
            content=content,
            items=items,
            empty=False,
        )
    except Exception:
        logger.debug("Reminders fetch failed", exc_info=True)
        return BriefingSection(title="Reminders", empty=True)


# ── Scout Discover ───────────────────────────────────────────────────


async def fetch_scout_discover() -> BriefingSection:
    """Return recent scout finds (tool / service candidates).

    Runs the real Scout discovery pipeline and returns top results.
    """
    try:
        from src.scout.engine import run_discovery
        from src.scout.cards import card_to_dict

        user_context = {
            "stack": ["python", "fastapi", "react", "typescript", "mcp", "claude", "ai", "agent"],
            "projects": ["jarvis", "magic-puffs", "clawwork", "sakura-radio"],
            "recent_topics": ["mcp", "dashboard", "scout", "voice", "tts", "integration"],
        }
        cards = await run_discovery(user_context=user_context)
        if not cards:
            return BriefingSection(title="Scout Discover", empty=True)

        items = [card_to_dict(c) for c in cards[:5]]
        content = f"{len(items)} new tool/service discovery(s)."
        return BriefingSection(
            title="Scout Discover",
            content=content,
            items=items,
            empty=False,
        )
    except Exception:
        logger.debug("Scout discover failed", exc_info=True)
        return BriefingSection(title="Scout Discover", empty=True)


# ── Lessons Digest ───────────────────────────────────────────────────


async def fetch_lessons_digest(store=None) -> BriefingSection:
    """Return a weekly lessons-learned digest.

    Returns empty unless a *store* with data is explicitly provided.
    """
    if store is None:
        return BriefingSection(title="Lessons Digest", empty=True)

    try:
        lessons = store.read_all(limit=20)
    except Exception:
        return BriefingSection(title="Lessons Digest", empty=True)

    if not lessons:
        return BriefingSection(title="Lessons Digest", empty=True)

    learned = [l.content for l in lessons if l.status == "approved"]
    avoided = [l.content for l in lessons if l.status == "archived"]

    if not learned and not avoided:
        return BriefingSection(title="Lessons Digest", empty=True)

    items = [{"learned": learned, "avoided": avoided}]
    parts: list[str] = []
    if learned:
        parts.append(f"{len(learned)} lesson(s) learned")
    if avoided:
        parts.append(f"{len(avoided)} lesson(s) to avoid")
    content = ". ".join(parts) + "."

    return BriefingSection(
        title="Lessons Digest",
        content=content,
        items=items,
        empty=False,
    )
