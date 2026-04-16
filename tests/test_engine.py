"""Comprehensive tests for the Proactive Engine."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from httpx import ASGITransport

from src.engine.notifications import DEFAULT_MATRIX, Notification, send_notification, should_notify
from src.engine.scheduler import ProactiveEngine, ScheduledTask
from src.engine.tasks import (
    daily_scout_scan,
    hourly_scout_scan,
    lesson_pruning_check,
    morning_briefing,
    register_default_tasks,
    sandbox_cleanup,
    session_lesson_sweep,
)
from src.server.app import app


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def engine() -> ProactiveEngine:
    return ProactiveEngine()


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:7900")


# ── ProactiveEngine: register / unregister ──────────────────────────


async def test_register_adds_task(engine: ProactiveEngine):
    cb = AsyncMock(return_value={"ok": True})
    engine.register("test_task", cb, interval_seconds=60)
    schedule = engine.get_schedule()
    assert len(schedule) == 1
    assert schedule[0]["name"] == "test_task"
    assert schedule[0]["interval_seconds"] == 60
    assert schedule[0]["enabled"] is True


async def test_register_disabled_task(engine: ProactiveEngine):
    cb = AsyncMock()
    engine.register("disabled_task", cb, interval_seconds=60, enabled=False)
    schedule = engine.get_schedule()
    assert len(schedule) == 1
    assert schedule[0]["enabled"] is False


async def test_unregister_removes_task(engine: ProactiveEngine):
    cb = AsyncMock()
    engine.register("to_remove", cb, interval_seconds=60)
    assert len(engine.get_schedule()) == 1
    engine.unregister("to_remove")
    assert len(engine.get_schedule()) == 0


async def test_unregister_nonexistent_is_noop(engine: ProactiveEngine):
    engine.unregister("ghost")
    assert len(engine.get_schedule()) == 0


# ── get_schedule ────────────────────────────────────────────────────


async def test_get_schedule_returns_correct_fields(engine: ProactiveEngine):
    cb = AsyncMock()
    engine.register("sched_task", cb, interval_seconds=3600)
    info = engine.get_schedule()[0]
    assert set(info.keys()) == {"name", "interval_seconds", "last_run", "next_run", "enabled"}
    assert info["last_run"] is None
    assert info["next_run"] is not None


async def test_get_schedule_empty_on_fresh_engine(engine: ProactiveEngine):
    assert engine.get_schedule() == []


# ── is_due ──────────────────────────────────────────────────────────


async def test_is_due_for_overdue_task(engine: ProactiveEngine):
    past = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
    task = ScheduledTask(
        name="overdue", callback=AsyncMock(), interval_seconds=60, next_run=past
    )
    assert engine.is_due(task) is True


async def test_is_due_for_future_task(engine: ProactiveEngine):
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    task = ScheduledTask(
        name="future", callback=AsyncMock(), interval_seconds=60, next_run=future
    )
    assert engine.is_due(task) is False


async def test_is_due_for_disabled_task(engine: ProactiveEngine):
    past = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
    task = ScheduledTask(
        name="disabled",
        callback=AsyncMock(),
        interval_seconds=60,
        next_run=past,
        enabled=False,
    )
    assert engine.is_due(task) is False


# ── tick ────────────────────────────────────────────────────────────


async def test_tick_runs_due_tasks(engine: ProactiveEngine):
    cb = AsyncMock(return_value={"ran": True})
    engine.register("due_task", cb, interval_seconds=60)
    # Force next_run into the past
    engine._tasks["due_task"].next_run = (
        datetime.now(timezone.utc) - timedelta(seconds=5)
    ).isoformat()

    ran = await engine.tick()
    assert "due_task" in ran
    cb.assert_called_once()


async def test_tick_skips_non_due_tasks(engine: ProactiveEngine):
    cb = AsyncMock(return_value={"ran": True})
    engine.register("not_due", cb, interval_seconds=60)
    engine._tasks["not_due"].next_run = (
        datetime.now(timezone.utc) + timedelta(hours=1)
    ).isoformat()

    ran = await engine.tick()
    assert ran == []
    cb.assert_not_called()


async def test_tick_updates_last_run(engine: ProactiveEngine):
    cb = AsyncMock(return_value={})
    engine.register("tracked", cb, interval_seconds=120)
    engine._tasks["tracked"].next_run = (
        datetime.now(timezone.utc) - timedelta(seconds=1)
    ).isoformat()

    await engine.tick()
    info = engine.get_schedule()[0]
    assert info["last_run"] is not None


async def test_tick_continues_after_task_failure(engine: ProactiveEngine):
    failing = AsyncMock(side_effect=RuntimeError("boom"))
    passing = AsyncMock(return_value={"ok": True})

    engine.register("fail_task", failing, interval_seconds=60)
    engine.register("pass_task", passing, interval_seconds=60)

    # Force both into the past
    now_past = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat()
    engine._tasks["fail_task"].next_run = now_past
    engine._tasks["pass_task"].next_run = now_past

    ran = await engine.tick()
    # Both should have attempted to run
    assert "fail_task" in ran
    assert "pass_task" in ran
    passing.assert_called_once()


# ── run_task ────────────────────────────────────────────────────────


async def test_run_task_executes_successfully(engine: ProactiveEngine):
    cb = AsyncMock(return_value={"value": 42})
    engine.register("manual", cb, interval_seconds=300)

    result = await engine.run_task("manual")
    assert result["success"] is True
    assert result["result"] == {"value": 42}
    assert result["ran_at"] is not None
    assert result["name"] == "manual"


async def test_run_task_unknown_returns_failure(engine: ProactiveEngine):
    result = await engine.run_task("nonexistent")
    assert result["success"] is False
    assert result["ran_at"] is None


async def test_run_task_handles_exception(engine: ProactiveEngine):
    cb = AsyncMock(side_effect=ValueError("bad"))
    engine.register("broken", cb, interval_seconds=60)

    result = await engine.run_task("broken")
    assert result["success"] is False
    assert result["result"] is None
    assert result["ran_at"] is not None  # still records the attempt


# ── start / stop lifecycle ──────────────────────────────────────────


async def test_engine_start_stop(engine: ProactiveEngine):
    assert engine.running is False
    await engine.start()
    assert engine.running is True
    await engine.stop()
    assert engine.running is False


async def test_engine_double_start_is_safe(engine: ProactiveEngine):
    await engine.start()
    await engine.start()  # should not raise
    assert engine.running is True
    await engine.stop()


async def test_engine_stop_when_not_started(engine: ProactiveEngine):
    await engine.stop()  # should not raise
    assert engine.running is False


# ── Task functions ──────────────────────────────────────────────────


@patch("src.engine.tasks.run_discovery", new_callable=AsyncMock, return_value=[])
@patch("src.engine.tasks.get_hourly_sources", return_value=[])
async def test_hourly_scout_scan(mock_sources, mock_discovery):
    result = await hourly_scout_scan()
    assert result["finds_count"] == 0
    assert result["sources_scanned"] == 0
    mock_sources.assert_called_once()
    mock_discovery.assert_called_once()


@patch("src.engine.tasks.run_discovery", new_callable=AsyncMock, return_value=[])
@patch("src.engine.tasks.get_daily_sources", return_value=[])
async def test_daily_scout_scan(mock_sources, mock_discovery):
    result = await daily_scout_scan()
    assert result["finds_count"] == 0
    assert result["sources_scanned"] == 0
    mock_sources.assert_called_once()
    mock_discovery.assert_called_once()


@patch("src.engine.tasks.compose_briefing", new_callable=AsyncMock)
async def test_morning_briefing_basic(mock_compose):
    from src.briefing.composer import Briefing

    mock_compose.return_value = Briefing(
        sections=[], generated_at="2026-04-15T07:30:00+00:00", summary="Good morning."
    )
    result = await morning_briefing()
    assert result["sections_count"] == 0
    assert result["written_to_obsidian"] is False
    assert result["file_path"] is None


@patch("src.engine.tasks.write_to_obsidian", return_value="/vault/Daily Notes/2026-04-15.md")
@patch("src.engine.tasks.compose_briefing", new_callable=AsyncMock)
async def test_morning_briefing_writes_obsidian(mock_compose, mock_write):
    from src.briefing.composer import Briefing

    mock_compose.return_value = Briefing(
        sections=[], generated_at="2026-04-15T07:30:00+00:00", summary="Good morning."
    )
    result = await morning_briefing(config={"obsidian_vault": "/vault"})
    assert result["written_to_obsidian"] is True
    assert result["file_path"] == "/vault/Daily Notes/2026-04-15.md"
    mock_write.assert_called_once()


async def test_sandbox_cleanup():
    result = await sandbox_cleanup()
    assert result["cleaned_count"] == 0


async def test_lesson_pruning_check_empty():
    result = await lesson_pruning_check(store_path=":memory:")
    assert result["stale_count"] == 0
    assert result["stale_lessons"] == []


async def test_lesson_pruning_check_with_stale():
    from src.lessons.store import Lesson, LessonStore

    store = LessonStore(db_path=":memory:")
    old_date = datetime.now(timezone.utc) - timedelta(days=120)
    lesson = Lesson(
        content="Old lesson",
        category="general",
        created_at=old_date,
        source="explicit",
        status="approved",
    )
    store.write(lesson)

    # Patch LessonStore to use our in-memory store
    with patch("src.engine.tasks.LessonStore", return_value=store):
        result = await lesson_pruning_check(store_path=":memory:")
    assert result["stale_count"] == 1
    assert result["stale_lessons"][0]["content"] == "Old lesson"


async def test_session_lesson_sweep_finds_corrections():
    messages = [
        "No, that's wrong, I said use UTC everywhere",
        "Thanks, that looks good now",
        "You forgot to test the edge case",
    ]
    result = await session_lesson_sweep(messages)
    assert result["corrections_found"] == 2
    assert len(result["drafts"]) == 2


async def test_session_lesson_sweep_clean_messages():
    messages = [
        "Looks great, thanks!",
        "Can you add a docstring?",
        "Perfect.",
    ]
    result = await session_lesson_sweep(messages)
    assert result["corrections_found"] == 0
    assert result["drafts"] == []


# ── register_default_tasks ──────────────────────────────────────────


async def test_register_default_tasks_creates_all():
    eng = ProactiveEngine()
    register_default_tasks(eng)
    schedule = eng.get_schedule()
    names = {t["name"] for t in schedule}
    assert names == {
        "hourly_scout_scan",
        "daily_scout_scan",
        "morning_briefing",
        "sandbox_cleanup",
        "lesson_pruning_check",
    }


async def test_register_default_tasks_intervals():
    eng = ProactiveEngine()
    register_default_tasks(eng)
    by_name = {t["name"]: t for t in eng.get_schedule()}
    assert by_name["hourly_scout_scan"]["interval_seconds"] == 3600
    assert by_name["daily_scout_scan"]["interval_seconds"] == 86400
    assert by_name["morning_briefing"]["interval_seconds"] == 86400
    assert by_name["sandbox_cleanup"]["interval_seconds"] == 86400
    assert by_name["lesson_pruning_check"]["interval_seconds"] == 604800


# ── Notifications ───────────────────────────────────────────────────


async def test_notification_dataclass():
    n = Notification(
        event_type="scout_find",
        title="New find",
        body="Found something interesting",
        channels=["macos", "silent"],
    )
    assert n.event_type == "scout_find"
    assert n.title == "New find"
    assert n.body == "Found something interesting"
    assert n.channels == ["macos", "silent"]


async def test_notification_default_channels():
    n = Notification(event_type="test", title="T", body="B")
    assert n.channels == []


async def test_should_notify_default_matrix():
    assert should_notify("scout_find", "macos") is True
    assert should_notify("scout_find", "silent") is True
    assert should_notify("scout_find", "telegram") is False
    assert should_notify("briefing_ready", "voice") is True
    assert should_notify("task_failed", "macos") is True


async def test_should_notify_custom_matrix():
    custom = {"custom_event": ["telegram", "voice"]}
    assert should_notify("custom_event", "telegram", matrix=custom) is True
    assert should_notify("custom_event", "macos", matrix=custom) is False
    assert should_notify("unknown_event", "macos", matrix=custom) is False


async def test_should_notify_unknown_event():
    assert should_notify("totally_unknown", "macos") is False


async def test_send_notification_silent_channel():
    n = Notification(
        event_type="lesson_drafted",
        title="Lesson ready",
        body="A lesson was drafted",
        channels=["silent"],
    )
    result = await send_notification(n, config={"test_mode": True})
    assert "silent" in result["sent_to"]
    assert result["event_type"] == "lesson_drafted"


async def test_send_notification_macos_test_mode():
    n = Notification(
        event_type="scout_find",
        title="New find",
        body="Found something",
        channels=["macos"],
    )
    result = await send_notification(n, config={"test_mode": True})
    assert "macos" in result["sent_to"]


async def test_send_notification_telegram_stub():
    n = Notification(
        event_type="test",
        title="Test",
        body="Test body",
        channels=["telegram"],
    )
    result = await send_notification(n, config={"test_mode": True})
    assert "telegram" in result["sent_to"]


async def test_send_notification_voice_stub():
    n = Notification(
        event_type="test",
        title="Test",
        body="Test body",
        channels=["voice"],
    )
    result = await send_notification(n, config={"test_mode": True})
    assert "voice" in result["sent_to"]


# ── Server endpoint tests ──────────────────────────────────────────


async def test_engine_schedule_endpoint(client: httpx.AsyncClient):
    resp = await client.get("/engine/schedule")
    assert resp.status_code == 200
    data = resp.json()
    assert "tasks" in data
    assert isinstance(data["tasks"], list)


async def test_engine_status_endpoint(client: httpx.AsyncClient):
    resp = await client.get("/engine/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "running" in data
    assert "task_count" in data
    assert isinstance(data["running"], bool)
    assert isinstance(data["task_count"], int)


async def test_engine_run_unknown_task(client: httpx.AsyncClient):
    resp = await client.post("/engine/run/nonexistent_task")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False


async def test_engine_start_endpoint(client: httpx.AsyncClient):
    resp = await client.post("/engine/start")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "started"


async def test_engine_stop_endpoint(client: httpx.AsyncClient):
    resp = await client.post("/engine/stop")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "stopped"


async def test_status_includes_engine_service(client: httpx.AsyncClient):
    resp = await client.get("/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["services"]["engine"] == "available"
