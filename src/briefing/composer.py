"""Briefing composer — assembles individual sections into a full briefing."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.briefing.sections import (
    BriefingSection,
    fetch_calendar,
    fetch_email,
    fetch_github,
    fetch_lessons_digest,
    fetch_news,
    fetch_reminders,
    fetch_scout_discover,
    fetch_weather,
)


@dataclass
class Briefing:
    """Full daily briefing, ready for serialisation or Obsidian export."""

    sections: list[BriefingSection] = field(default_factory=list)
    generated_at: str = ""
    summary: str = ""


async def compose_briefing(config: dict | None = None) -> Briefing:
    """Build a briefing by fetching every section and dropping empty ones.

    Accepted *config* keys (all optional):
        - ``user_name``           — greeting name (default "Sir")
        - ``location``            — for weather lookup
        - ``github_repos``        — list of ``owner/repo`` strings
        - ``include_lessons_digest`` — bool, set True on weekly runs
    """
    cfg = config or {}
    user_name = cfg.get("user_name", "Sir")
    location = cfg.get("location")
    github_repos = cfg.get("github_repos", [])
    include_lessons = cfg.get("include_lessons_digest", False)
    lesson_store = cfg.get("lesson_store")
    hn_enabled = cfg.get("hn_enabled", True)
    hn_limit = cfg.get("hn_limit", 5)
    hn_min_score = cfg.get("hn_min_score", 100)
    rss_urls = cfg.get("rss_urls", [])

    # Fetch in spec order: Weather → Calendar → Email → GitHub → News
    #   → Reminders → Scout Discover → Lessons Digest
    all_sections = [
        await fetch_weather(location),
        await fetch_calendar(),
        await fetch_email(),
        await fetch_github(github_repos),
        await fetch_news(
            rss_urls=rss_urls,
            hn_enabled=hn_enabled,
            hn_limit=hn_limit,
            hn_min_score=hn_min_score,
        ),
        await fetch_reminders(),
        await fetch_scout_discover(),
    ]

    if include_lessons:
        all_sections.append(await fetch_lessons_digest(store=lesson_store))

    # Silently omit empty sections
    sections = [s for s in all_sections if not s.empty]

    count = len(sections)
    if count == 0:
        summary_text = f"Good morning, {user_name}. Nothing to report today."
    elif count == 1:
        summary_text = f"Good morning, {user_name}. 1 section in your briefing today."
    else:
        summary_text = (
            f"Good morning, {user_name}. {count} sections in your briefing today."
        )

    return Briefing(
        sections=sections,
        generated_at=datetime.now(timezone.utc).isoformat(),
        summary=summary_text,
    )
