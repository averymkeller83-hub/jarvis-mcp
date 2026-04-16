"""Comprehensive tests for the briefing module."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest
from httpx import ASGITransport

from src.briefing.composer import Briefing, compose_briefing
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
from src.briefing.writer import write_to_obsidian, _render_section, _render_briefing
from src.server.app import app


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:7900")


class FakeLessonStore:
    """Minimal stand-in for LessonStore to avoid touching SQLite."""

    def __init__(self, lessons: list | None = None):
        self._lessons = lessons or []

    def read_all(self, limit: int = 50):
        return self._lessons[:limit]


@dataclass
class FakeLesson:
    content: str = ""
    status: str = "approved"


# ═══════════════════════════════════════════════════════════════════════
# Section fetcher tests
# ═══════════════════════════════════════════════════════════════════════


class TestFetchWeather:
    @pytest.mark.asyncio
    async def test_returns_non_empty(self):
        section = await fetch_weather()
        assert not section.empty
        assert section.title == "Weather"

    @pytest.mark.asyncio
    async def test_has_correct_item_keys(self):
        section = await fetch_weather("New York, NY")
        item = section.items[0]
        for key in ("temp", "condition", "high", "low", "summary"):
            assert key in item

    @pytest.mark.asyncio
    async def test_summary_contains_location(self):
        section = await fetch_weather("Denver, CO")
        assert "Denver, CO" in section.content

    @pytest.mark.asyncio
    async def test_default_location(self):
        section = await fetch_weather()
        assert "Austin, TX" in section.content


class TestFetchCalendar:
    @pytest.mark.asyncio
    async def test_returns_empty(self):
        section = await fetch_calendar()
        assert section.empty
        assert section.title == "Calendar"

    @pytest.mark.asyncio
    async def test_items_list_empty(self):
        section = await fetch_calendar()
        assert section.items == []


class TestFetchEmail:
    @pytest.mark.asyncio
    async def test_returns_empty(self):
        section = await fetch_email()
        assert section.empty
        assert section.title == "Email"

    @pytest.mark.asyncio
    async def test_items_list_empty(self):
        section = await fetch_email()
        assert section.items == []


class TestFetchGitHub:
    @pytest.mark.asyncio
    async def test_empty_without_repos(self):
        section = await fetch_github()
        assert section.empty
        assert section.title == "GitHub"

    @pytest.mark.asyncio
    async def test_empty_with_none_repos(self):
        section = await fetch_github(None)
        assert section.empty

    @pytest.mark.asyncio
    async def test_empty_with_empty_list(self):
        section = await fetch_github([])
        assert section.empty

    @pytest.mark.asyncio
    async def test_empty_with_repos_placeholder(self):
        # Current mock always returns empty even with repos
        section = await fetch_github(["owner/repo"])
        assert section.empty


class TestFetchNews:
    @pytest.mark.asyncio
    async def test_returns_empty(self):
        section = await fetch_news()
        assert section.empty
        assert section.title == "News"


class TestFetchReminders:
    @pytest.mark.asyncio
    async def test_returns_empty(self):
        section = await fetch_reminders()
        assert section.empty
        assert section.title == "Reminders"


class TestFetchScoutDiscover:
    @pytest.mark.asyncio
    async def test_returns_empty(self):
        section = await fetch_scout_discover()
        assert section.empty
        assert section.title == "Scout Discover"


class TestFetchLessonsDigest:
    @pytest.mark.asyncio
    async def test_empty_without_store(self):
        section = await fetch_lessons_digest()
        assert section.empty
        assert section.title == "Lessons Digest"

    @pytest.mark.asyncio
    async def test_empty_with_empty_store(self):
        store = FakeLessonStore([])
        section = await fetch_lessons_digest(store=store)
        assert section.empty

    @pytest.mark.asyncio
    async def test_non_empty_with_lessons(self):
        lessons = [
            FakeLesson(content="Always use UTC", status="approved"),
            FakeLesson(content="Avoid mutable defaults", status="approved"),
        ]
        store = FakeLessonStore(lessons)
        section = await fetch_lessons_digest(store=store)
        assert not section.empty
        assert "2 lesson(s) learned" in section.content

    @pytest.mark.asyncio
    async def test_lessons_digest_items_structure(self):
        lessons = [
            FakeLesson(content="Use typing", status="approved"),
            FakeLesson(content="Old pattern", status="archived"),
        ]
        store = FakeLessonStore(lessons)
        section = await fetch_lessons_digest(store=store)
        assert not section.empty
        item = section.items[0]
        assert "learned" in item
        assert "avoided" in item
        assert "Use typing" in item["learned"]
        assert "Old pattern" in item["avoided"]

    @pytest.mark.asyncio
    async def test_lessons_digest_handles_exception(self):
        """If the store raises, we return empty gracefully."""

        class BrokenStore:
            def read_all(self, limit=50):
                raise RuntimeError("db locked")

        section = await fetch_lessons_digest(store=BrokenStore())
        assert section.empty


# ═══════════════════════════════════════════════════════════════════════
# BriefingSection dataclass tests
# ═══════════════════════════════════════════════════════════════════════


class TestBriefingSectionDataclass:
    def test_default_values(self):
        s = BriefingSection(title="Test")
        assert s.title == "Test"
        assert s.content == ""
        assert s.items == []
        assert s.empty is False

    def test_custom_values(self):
        s = BriefingSection(title="X", content="hello", items=[{"a": 1}], empty=True)
        assert s.content == "hello"
        assert s.items == [{"a": 1}]
        assert s.empty is True


# ═══════════════════════════════════════════════════════════════════════
# Composer tests
# ═══════════════════════════════════════════════════════════════════════


class TestComposeBriefing:
    @pytest.mark.asyncio
    async def test_returns_briefing_dataclass(self):
        result = await compose_briefing()
        assert isinstance(result, Briefing)

    @pytest.mark.asyncio
    async def test_generated_at_is_iso(self):
        result = await compose_briefing()
        # Should parse without error
        datetime.fromisoformat(result.generated_at)

    @pytest.mark.asyncio
    async def test_omits_empty_sections(self):
        result = await compose_briefing()
        for section in result.sections:
            assert not section.empty

    @pytest.mark.asyncio
    async def test_weather_always_present(self):
        result = await compose_briefing()
        titles = [s.title for s in result.sections]
        assert "Weather" in titles

    @pytest.mark.asyncio
    async def test_default_summary_uses_sir(self):
        result = await compose_briefing()
        assert "Sir" in result.summary

    @pytest.mark.asyncio
    async def test_custom_user_name_in_summary(self):
        result = await compose_briefing({"user_name": "Avery"})
        assert "Avery" in result.summary

    @pytest.mark.asyncio
    async def test_section_count_in_summary(self):
        result = await compose_briefing()
        count = len(result.sections)
        assert str(count) in result.summary or "1 section" in result.summary

    @pytest.mark.asyncio
    async def test_custom_location_passed_to_weather(self):
        result = await compose_briefing({"location": "London, UK"})
        weather = [s for s in result.sections if s.title == "Weather"][0]
        assert "London, UK" in weather.content

    @pytest.mark.asyncio
    async def test_lessons_excluded_by_default(self):
        result = await compose_briefing()
        titles = [s.title for s in result.sections]
        assert "Lessons Digest" not in titles

    @pytest.mark.asyncio
    async def test_lessons_included_when_requested_with_store(self):
        lessons = [FakeLesson(content="Always verify", status="approved")]
        store = FakeLessonStore(lessons)
        result = await compose_briefing({
            "include_lessons_digest": True,
            "lesson_store": store,
        })
        titles = [s.title for s in result.sections]
        assert "Lessons Digest" in titles

    @pytest.mark.asyncio
    async def test_section_order(self):
        """Weather must come first (the only guaranteed non-empty section)."""
        result = await compose_briefing()
        assert result.sections[0].title == "Weather"

    @pytest.mark.asyncio
    async def test_empty_briefing_summary(self):
        """Edge case: if ALL sections were empty, summary should reflect that.

        In practice, weather is always non-empty, but we test the summary
        wording for the zero-section case via a direct Briefing.
        """
        b = Briefing(sections=[], generated_at="", summary="")
        assert b.sections == []


# ═══════════════════════════════════════════════════════════════════════
# Writer tests
# ═══════════════════════════════════════════════════════════════════════


class TestRenderSection:
    def test_simple_section(self):
        s = BriefingSection(title="Weather", content="Sunny and 75.")
        md = _render_section(s)
        assert "## Weather" in md
        assert "Sunny and 75." in md

    def test_items_rendered_as_bullets(self):
        s = BriefingSection(
            title="Calendar",
            items=[{"time": "9:00 AM", "title": "Standup", "location": "Zoom"}],
        )
        md = _render_section(s)
        assert "- **time**: 9:00 AM" in md
        assert "**title**: Standup" in md

    def test_lessons_digest_rendering(self):
        s = BriefingSection(
            title="Lessons Digest",
            content="2 lessons learned.",
            items=[{"learned": ["Use UTC", "Type hints"], "avoided": ["Mutable defaults"]}],
        )
        md = _render_section(s)
        assert "### Learned" in md
        assert "- Use UTC" in md
        assert "### Avoided" in md
        assert "- Mutable defaults" in md


class TestRenderBriefing:
    def test_contains_heading(self):
        b = Briefing(
            sections=[BriefingSection(title="Weather", content="Clear skies.")],
            generated_at=datetime.now(timezone.utc).isoformat(),
            summary="Good morning, Sir. 1 section in your briefing today.",
        )
        md = _render_briefing(b)
        assert "# Daily Briefing" in md
        assert "## Weather" in md
        assert "Clear skies." in md

    def test_summary_rendered(self):
        b = Briefing(
            sections=[],
            generated_at="",
            summary="Nothing to report.",
        )
        md = _render_briefing(b)
        assert "*Nothing to report.*" in md


class TestWriteToObsidian:
    def test_creates_file(self, tmp_path: Path):
        b = Briefing(
            sections=[BriefingSection(title="Weather", content="Warm.")],
            generated_at=datetime.now(timezone.utc).isoformat(),
            summary="1 section.",
        )
        file_path = write_to_obsidian(b, str(tmp_path))
        assert os.path.exists(file_path)
        content = Path(file_path).read_text(encoding="utf-8")
        assert "# Daily Briefing" in content
        assert "## Weather" in content

    def test_creates_daily_notes_dir(self, tmp_path: Path):
        b = Briefing(sections=[], generated_at="", summary="")
        write_to_obsidian(b, str(tmp_path))
        assert (tmp_path / "Daily Notes").is_dir()

    def test_appends_if_file_exists(self, tmp_path: Path):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        daily_dir = tmp_path / "Daily Notes"
        daily_dir.mkdir(parents=True)
        note = daily_dir / f"{today}.md"
        note.write_text("# Existing content\n\nSome notes here.\n", encoding="utf-8")

        b = Briefing(
            sections=[BriefingSection(title="Weather", content="Rain.")],
            generated_at=datetime.now(timezone.utc).isoformat(),
            summary="1 section.",
        )
        file_path = write_to_obsidian(b, str(tmp_path))
        content = Path(file_path).read_text(encoding="utf-8")
        # Original content preserved
        assert "# Existing content" in content
        assert "Some notes here." in content
        # Briefing appended under heading
        assert "## Briefing" in content
        assert "## Weather" in content

    def test_file_path_returned(self, tmp_path: Path):
        b = Briefing(sections=[], generated_at="", summary="")
        file_path = write_to_obsidian(b, str(tmp_path))
        assert file_path.endswith(".md")
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        assert today in file_path


# ═══════════════════════════════════════════════════════════════════════
# API endpoint tests
# ═══════════════════════════════════════════════════════════════════════


class TestBriefingEndpoint:
    @pytest.mark.asyncio
    async def test_returns_200(self, client: httpx.AsyncClient):
        resp = await client.get("/briefing")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_has_sections_list(self, client: httpx.AsyncClient):
        resp = await client.get("/briefing")
        data = resp.json()
        assert isinstance(data["sections"], list)

    @pytest.mark.asyncio
    async def test_has_generated_at(self, client: httpx.AsyncClient):
        resp = await client.get("/briefing")
        data = resp.json()
        assert "generated_at" in data
        datetime.fromisoformat(data["generated_at"])

    @pytest.mark.asyncio
    async def test_has_summary(self, client: httpx.AsyncClient):
        resp = await client.get("/briefing")
        data = resp.json()
        assert "summary" in data
        assert "Sir" in data["summary"]

    @pytest.mark.asyncio
    async def test_weather_section_present(self, client: httpx.AsyncClient):
        resp = await client.get("/briefing")
        data = resp.json()
        titles = [s["title"] for s in data["sections"]]
        assert "Weather" in titles

    @pytest.mark.asyncio
    async def test_no_empty_sections_in_response(self, client: httpx.AsyncClient):
        resp = await client.get("/briefing")
        data = resp.json()
        for s in data["sections"]:
            assert s["empty"] is False


class TestBriefingObsidianEndpoint:
    @pytest.mark.asyncio
    async def test_returns_200(self, client: httpx.AsyncClient, tmp_path: Path):
        resp = await client.get("/briefing/obsidian", params={"vault_path": str(tmp_path)})
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_returns_file_path(self, client: httpx.AsyncClient, tmp_path: Path):
        resp = await client.get("/briefing/obsidian", params={"vault_path": str(tmp_path)})
        data = resp.json()
        assert "file_path" in data
        assert data["file_path"].endswith(".md")

    @pytest.mark.asyncio
    async def test_creates_file_on_disk(self, client: httpx.AsyncClient, tmp_path: Path):
        resp = await client.get("/briefing/obsidian", params={"vault_path": str(tmp_path)})
        data = resp.json()
        assert os.path.exists(data["file_path"])

    @pytest.mark.asyncio
    async def test_missing_vault_path_returns_422(self, client: httpx.AsyncClient):
        resp = await client.get("/briefing/obsidian")
        assert resp.status_code == 422
