"""Comprehensive tests for the Lessons module — store + capture."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.lessons.capture import categorize, detect_correction, draft_lesson
from src.lessons.store import Lesson, LessonStore


# ── fixtures ──────────────────────────────────────────────────────────


@pytest.fixture()
def store() -> LessonStore:
    """Return a LessonStore backed by an in-memory database."""
    return LessonStore(db_path=":memory:")


@pytest.fixture()
def sample_lesson() -> Lesson:
    return Lesson(content="Always verify before claiming done.", category="trust")


# ── LessonStore CRUD ─────────────────────────────────────────────────


class TestLessonStoreCRUD:
    def test_write_and_read_all(self, store: LessonStore, sample_lesson: Lesson) -> None:
        returned_id = store.write(sample_lesson)
        assert returned_id == sample_lesson.id
        lessons = store.read_all()
        assert len(lessons) == 1
        assert lessons[0].content == sample_lesson.content

    def test_count(self, store: LessonStore, sample_lesson: Lesson) -> None:
        assert store.count() == 0
        store.write(sample_lesson)
        assert store.count() == 1

    def test_archive(self, store: LessonStore, sample_lesson: Lesson) -> None:
        store.write(sample_lesson)
        assert store.archive(sample_lesson.id) is True
        assert store.count() == 0  # archived lessons excluded from count
        assert store.read_all() == []

    def test_archive_nonexistent_returns_false(self, store: LessonStore) -> None:
        assert store.archive("nonexistent-id") is False

    def test_pin_and_unpin(self, store: LessonStore, sample_lesson: Lesson) -> None:
        store.write(sample_lesson)
        assert store.pin(sample_lesson.id) is True
        pinned = store.read_pinned()
        assert len(pinned) == 1
        assert pinned[0].pinned is True

        assert store.unpin(sample_lesson.id) is True
        assert store.read_pinned() == []


# ── read_pinned ──────────────────────────────────────────────────────


class TestReadPinned:
    def test_only_pinned_and_approved(self, store: LessonStore) -> None:
        approved_pinned = Lesson(content="pinned+approved", pinned=True, status="approved")
        approved_unpinned = Lesson(content="unpinned+approved", pinned=False, status="approved")
        archived_pinned = Lesson(content="pinned+archived", pinned=True, status="archived")

        store.write(approved_pinned)
        store.write(approved_unpinned)
        store.write(archived_pinned)

        results = store.read_pinned()
        assert len(results) == 1
        assert results[0].id == approved_pinned.id


# ── read_by_category ─────────────────────────────────────────────────


class TestReadByCategory:
    def test_filters_by_category(self, store: LessonStore) -> None:
        store.write(Lesson(content="trust lesson", category="trust"))
        store.write(Lesson(content="code lesson", category="code"))
        store.write(Lesson(content="another code lesson", category="code"))

        trust = store.read_by_category("trust")
        assert len(trust) == 1
        assert trust[0].category == "trust"

        code = store.read_by_category("code")
        assert len(code) == 2

    def test_respects_limit(self, store: LessonStore) -> None:
        for i in range(5):
            store.write(Lesson(content=f"lesson {i}", category="general"))
        assert len(store.read_by_category("general", limit=3)) == 3


# ── get_stale ─────────────────────────────────────────────────────────


class TestGetStale:
    def test_old_unretrieved_lessons_are_stale(self, store: LessonStore) -> None:
        old = Lesson(
            content="old lesson",
            created_at=datetime.now(timezone.utc) - timedelta(days=120),
        )
        store.write(old)
        stale = store.get_stale(days=90)
        assert len(stale) == 1
        assert stale[0].id == old.id

    def test_recent_lessons_not_stale(self, store: LessonStore) -> None:
        recent = Lesson(content="fresh lesson")
        store.write(recent)
        assert store.get_stale(days=90) == []

    def test_pinned_excluded(self, store: LessonStore) -> None:
        old_pinned = Lesson(
            content="pinned old",
            pinned=True,
            created_at=datetime.now(timezone.utc) - timedelta(days=120),
        )
        store.write(old_pinned)
        assert store.get_stale(days=90) == []

    def test_stale_by_last_retrieved(self, store: LessonStore) -> None:
        lesson = Lesson(
            content="retrieved long ago",
            created_at=datetime.now(timezone.utc) - timedelta(days=200),
            last_retrieved_at=datetime.now(timezone.utc) - timedelta(days=100),
        )
        store.write(lesson)
        assert len(store.get_stale(days=90)) == 1


# ── mark_retrieved ────────────────────────────────────────────────────


class TestMarkRetrieved:
    def test_updates_timestamp(self, store: LessonStore) -> None:
        lesson = Lesson(content="to be retrieved")
        store.write(lesson)
        assert store.read_all()[0].last_retrieved_at is None

        store.mark_retrieved(lesson.id)
        updated = store.read_all()[0]
        assert updated.last_retrieved_at is not None
        assert (datetime.now(timezone.utc) - updated.last_retrieved_at).total_seconds() < 5


# ── detect_correction ─────────────────────────────────────────────────


class TestDetectCorrection:
    @pytest.mark.parametrize(
        "msg",
        [
            "No, don't do that",
            "no stop doing that",
            "That's wrong",
            "You forgot to save the file",
            "that's not right",
            "that's not what I asked for",
            "You lied about the output",
            "I already told you that",
            "That is wrong",
            "Try again",
            "that's not done",
            "You didn't test it",
            "you didn't verify the result",
            "you didn't actually run it",
            "no, I said use Python",
            "no, not that",
        ],
    )
    def test_catches_corrections(self, msg: str) -> None:
        assert detect_correction(msg) is True

    @pytest.mark.parametrize(
        "msg",
        [
            "Great job!",
            "Can you help me with this?",
            "Please create a new file",
            "What time is it?",
            "I like this approach",
            "Let's move on",
        ],
    )
    def test_ignores_normal_messages(self, msg: str) -> None:
        assert detect_correction(msg) is False


# ── draft_lesson ──────────────────────────────────────────────────────


class TestDraftLesson:
    def test_produces_valid_structure(self) -> None:
        result = draft_lesson("You didn't test the output")
        assert "content" in result
        assert "category" in result
        assert result["source"] == "heuristic"
        assert result["status"] == "pending_approval"

    def test_includes_context(self) -> None:
        result = draft_lesson("Wrong", context="User asked for JSON, got YAML")
        assert "Context:" in result["content"]

    def test_category_trust(self) -> None:
        result = draft_lesson("You didn't verify the result")
        assert result["category"] == "trust"

    def test_category_code(self) -> None:
        result = draft_lesson("The function has a bug")
        assert result["category"] == "code"

    def test_category_general_fallback(self) -> None:
        result = draft_lesson("That's just not right at all")
        assert result["category"] == "general"


# ── categorize ────────────────────────────────────────────────────────


class TestCategorize:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("you need to verify before saying done", "trust"),
            ("the function raises an error", "code"),
            ("I already told you about that variable", "memory"),
            ("your tone is too verbose", "communication"),
            ("something completely unrelated", "general"),
            ("always confirm the test passes", "trust"),
            ("fix the import bug", "code"),
            ("you forgot the context", "memory"),
        ],
    )
    def test_maps_keywords_correctly(self, text: str, expected: str) -> None:
        assert categorize(text) == expected
