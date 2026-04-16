"""Predefined proactive tasks for the Jarvis engine."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from src.briefing.composer import compose_briefing
from src.briefing.writer import write_to_obsidian
from src.lessons.capture import detect_correction, draft_lesson
from src.lessons.store import LessonStore
from src.scout.engine import run_discovery
from src.scout.sandbox import cleanup_expired
from src.scout.sources import get_daily_sources, get_hourly_sources

if TYPE_CHECKING:
    from src.engine.scheduler import ProactiveEngine

logger = logging.getLogger(__name__)


async def hourly_scout_scan() -> dict[str, Any]:
    """Run Scout discovery with hourly sources only."""
    sources = get_hourly_sources()
    cards = await run_discovery(sources)
    return {
        "finds_count": len(cards),
        "sources_scanned": len(sources),
    }


async def daily_scout_scan() -> dict[str, Any]:
    """Run Scout discovery with daily sources."""
    sources = get_daily_sources()
    cards = await run_discovery(sources)
    return {
        "finds_count": len(cards),
        "sources_scanned": len(sources),
    }


async def morning_briefing(config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Compose and optionally deliver a morning briefing."""
    cfg = config or {}
    briefing = await compose_briefing(cfg)

    written_to_obsidian = False
    file_path: str | None = None

    vault_path = cfg.get("obsidian_vault")
    if vault_path:
        file_path = write_to_obsidian(briefing, vault_path)
        written_to_obsidian = True

    return {
        "sections_count": len(briefing.sections),
        "written_to_obsidian": written_to_obsidian,
        "file_path": file_path,
    }


async def sandbox_cleanup() -> dict[str, Any]:
    """Daily sandbox artifact cleanup."""
    # In a real deployment, results would come from a persistent store.
    # For now we operate on an empty list as a no-op placeholder.
    results: list = []
    cleaned = await cleanup_expired(results)
    return {"cleaned_count": cleaned}


async def lesson_pruning_check(store_path: str | None = None) -> dict[str, Any]:
    """Check for stale lessons that may need pruning."""
    path = store_path or ":memory:"
    store = LessonStore(db_path=path)
    stale = store.get_stale(days=90)
    return {
        "stale_count": len(stale),
        "stale_lessons": [
            {"id": l.id, "content": l.content, "category": l.category} for l in stale
        ],
    }


async def session_lesson_sweep(messages: list[str]) -> dict[str, Any]:
    """End-of-session Haiku sweep — scan messages for corrections."""
    drafts: list[dict] = []
    corrections_found = 0

    for msg in messages:
        if detect_correction(msg):
            corrections_found += 1
            draft = draft_lesson(msg)
            drafts.append(draft)

    return {
        "corrections_found": corrections_found,
        "drafts": drafts,
    }


def register_default_tasks(
    engine: ProactiveEngine, config: dict[str, Any] | None = None
) -> None:
    """Register all predefined tasks with correct intervals."""
    cfg = config or {}

    engine.register("hourly_scout_scan", hourly_scout_scan, interval_seconds=3600)
    engine.register("daily_scout_scan", daily_scout_scan, interval_seconds=86400)

    # Morning briefing — set next_run based on briefing_time config
    briefing_time = cfg.get("briefing_time", "07:30")
    engine.register(
        "morning_briefing",
        lambda: morning_briefing(cfg),
        interval_seconds=86400,
    )
    # Adjust next_run for morning briefing to the configured time
    task = engine._tasks["morning_briefing"]
    now = datetime.now(timezone.utc)
    hour, minute = (int(p) for p in briefing_time.split(":"))
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    task.next_run = target.isoformat()

    engine.register("sandbox_cleanup", sandbox_cleanup, interval_seconds=86400)
    engine.register(
        "lesson_pruning_check",
        lesson_pruning_check,
        interval_seconds=604800,
    )
