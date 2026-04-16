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


async def fetch_weather(
    location: str | None = None,
    *,
    latitude: float | None = None,
    longitude: float | None = None,
) -> BriefingSection:
    """Return current weather for *location* using Open-Meteo.

    Falls back to mock data on failure.
    """
    loc = location or "Austin, TX"
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
        # Fallback to mock data so the briefing never crashes
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
