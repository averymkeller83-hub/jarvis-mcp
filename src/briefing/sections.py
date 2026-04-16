"""Briefing section fetchers — each returns a BriefingSection dataclass."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BriefingSection:
    """A single section of the daily briefing."""

    title: str
    content: str = ""
    items: list[dict] = field(default_factory=list)
    empty: bool = False


# ── Weather ──────────────────────────────────────────────────────────


async def fetch_weather(location: str | None = None) -> BriefingSection:
    """Return current weather for *location*.

    Always returns a non-empty section (mock data for now).
    """
    loc = location or "Austin, TX"
    items = [
        {
            "temp": 78,
            "condition": "Partly cloudy",
            "high": 85,
            "low": 68,
            "summary": f"Partly cloudy in {loc}. High of 85 °F, low of 68 °F.",
        }
    ]
    return BriefingSection(
        title="Weather",
        content=items[0]["summary"],
        items=items,
        empty=False,
    )


# ── Calendar ─────────────────────────────────────────────────────────


async def fetch_calendar() -> BriefingSection:
    """Return today's calendar events.

    Returns empty when no events are found.
    """
    # Placeholder — will integrate with Apple Calendar MCP later.
    return BriefingSection(title="Calendar", empty=True)


# ── Email ────────────────────────────────────────────────────────────


async def fetch_email() -> BriefingSection:
    """Return unread mail summary.

    Returns empty when nothing unread.
    """
    return BriefingSection(title="Email", empty=True)


# ── GitHub ───────────────────────────────────────────────────────────


async def fetch_github(repos: list[str] | None = None) -> BriefingSection:
    """Return recent GitHub activity for the given *repos*.

    Returns empty when no repos are configured or no activity found.
    """
    if not repos:
        return BriefingSection(title="GitHub", empty=True)

    # Placeholder — will call GitHub MCP tools later.
    return BriefingSection(title="GitHub", empty=True)


# ── News ─────────────────────────────────────────────────────────────


async def fetch_news() -> BriefingSection:
    """Return top headlines from RSS / HN.

    Returns empty when no news is available.
    """
    return BriefingSection(title="News", empty=True)


# ── Reminders ────────────────────────────────────────────────────────


async def fetch_reminders() -> BriefingSection:
    """Return pending reminders.

    Returns empty when there are none.
    """
    return BriefingSection(title="Reminders", empty=True)


# ── Scout Discover ───────────────────────────────────────────────────


async def fetch_scout_discover() -> BriefingSection:
    """Return recent scout finds (tool / service candidates).

    Returns empty when there are no new finds.
    """
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
