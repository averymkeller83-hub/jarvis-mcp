"""Lesson storage and retrieval — SQLite-backed, zero dependencies beyond stdlib."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from uuid import uuid4

VALID_CATEGORIES = {"trust", "code", "memory", "communication", "general"}
VALID_STATUSES = {"approved", "rejected", "archived"}
VALID_SOURCES = {"explicit", "heuristic", "session_sweep"}

COLUMNS = (
    "id",
    "content",
    "category",
    "pinned",
    "created_at",
    "last_retrieved_at",
    "source",
    "status",
)


@dataclass
class Lesson:
    id: str = field(default_factory=lambda: str(uuid4()))
    content: str = ""
    category: str = "general"
    pinned: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_retrieved_at: datetime | None = None
    source: str = "explicit"
    status: str = "approved"


class LessonStore:
    """Persistent lesson store backed by a single SQLite table."""

    def __init__(self, db_path: str = "memory/lessons.db") -> None:
        self._conn = sqlite3.connect(db_path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_table()

    # ── schema ────────────────────────────────────────────────────────

    def _create_table(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS lessons (
                id               TEXT PRIMARY KEY,
                content          TEXT NOT NULL,
                category         TEXT NOT NULL DEFAULT 'general',
                pinned           INTEGER NOT NULL DEFAULT 0,
                created_at       TEXT NOT NULL,
                last_retrieved_at TEXT,
                source           TEXT NOT NULL DEFAULT 'explicit',
                status           TEXT NOT NULL DEFAULT 'approved'
            )
            """
        )
        self._conn.commit()

    # ── helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _row_to_lesson(row: tuple) -> Lesson:
        return Lesson(
            id=row[0],
            content=row[1],
            category=row[2],
            pinned=bool(row[3]),
            created_at=datetime.fromisoformat(row[4]),
            last_retrieved_at=datetime.fromisoformat(row[5]) if row[5] else None,
            source=row[6],
            status=row[7],
        )

    def _rows(self, sql: str, params: tuple = ()) -> list[Lesson]:
        cur = self._conn.execute(sql, params)
        return [self._row_to_lesson(r) for r in cur.fetchall()]

    # ── write / mutate ────────────────────────────────────────────────

    def write(self, lesson: Lesson) -> str:
        """Insert an approved lesson and return its id."""
        self._conn.execute(
            """
            INSERT INTO lessons (id, content, category, pinned, created_at,
                                 last_retrieved_at, source, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                lesson.id,
                lesson.content,
                lesson.category,
                int(lesson.pinned),
                lesson.created_at.isoformat(),
                lesson.last_retrieved_at.isoformat() if lesson.last_retrieved_at else None,
                lesson.source,
                lesson.status,
            ),
        )
        self._conn.commit()
        return lesson.id

    def archive(self, lesson_id: str) -> bool:
        """Set status to archived. Returns True if a row was updated."""
        cur = self._conn.execute(
            "UPDATE lessons SET status = 'archived' WHERE id = ?", (lesson_id,)
        )
        self._conn.commit()
        return cur.rowcount > 0

    def pin(self, lesson_id: str) -> bool:
        cur = self._conn.execute("UPDATE lessons SET pinned = 1 WHERE id = ?", (lesson_id,))
        self._conn.commit()
        return cur.rowcount > 0

    def unpin(self, lesson_id: str) -> bool:
        cur = self._conn.execute("UPDATE lessons SET pinned = 0 WHERE id = ?", (lesson_id,))
        self._conn.commit()
        return cur.rowcount > 0

    def mark_retrieved(self, lesson_id: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "UPDATE lessons SET last_retrieved_at = ? WHERE id = ?", (now, lesson_id)
        )
        self._conn.commit()

    # ── read ──────────────────────────────────────────────────────────

    def read_pinned(self) -> list[Lesson]:
        return self._rows(
            "SELECT * FROM lessons WHERE pinned = 1 AND status = 'approved' ORDER BY created_at DESC"
        )

    def read_by_category(self, category: str, limit: int = 10) -> list[Lesson]:
        return self._rows(
            "SELECT * FROM lessons WHERE category = ? AND status = 'approved' "
            "ORDER BY created_at DESC LIMIT ?",
            (category, limit),
        )

    def read_all(self, limit: int = 50) -> list[Lesson]:
        return self._rows(
            "SELECT * FROM lessons WHERE status = 'approved' ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )

    def get_stale(self, days: int = 90) -> list[Lesson]:
        """Return approved, non-pinned lessons that haven't been retrieved in *days* days.

        If last_retrieved_at is NULL, fall back to created_at for the staleness check.
        """
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        return self._rows(
            """
            SELECT * FROM lessons
            WHERE status = 'approved'
              AND pinned = 0
              AND (
                  (last_retrieved_at IS NOT NULL AND last_retrieved_at < ?)
                  OR
                  (last_retrieved_at IS NULL AND created_at < ?)
              )
            ORDER BY created_at ASC
            """,
            (cutoff, cutoff),
        )

    def count(self) -> int:
        cur = self._conn.execute("SELECT COUNT(*) FROM lessons WHERE status = 'approved'")
        return cur.fetchone()[0]
