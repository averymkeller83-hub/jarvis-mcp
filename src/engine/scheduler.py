"""Proactive Engine — background task scheduler for Jarvis."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class ScheduledTask:
    """A single scheduled task entry."""

    name: str
    callback: Callable
    interval_seconds: int
    last_run: str | None = None
    next_run: str = ""
    enabled: bool = True

    def __post_init__(self) -> None:
        if not self.next_run:
            self.next_run = datetime.now(timezone.utc).isoformat()


class ProactiveEngine:
    """Background task scheduler that runs registered tasks on cadence."""

    def __init__(self) -> None:
        self._tasks: dict[str, ScheduledTask] = {}
        self._running = False
        self._loop_task: asyncio.Task | None = None

    # ── Properties ───────────────────────────────────────────────────

    @property
    def running(self) -> bool:
        return self._running

    # ── Task management ──────────────────────────────────────────────

    def register(
        self,
        name: str,
        callback: Callable,
        interval_seconds: int,
        enabled: bool = True,
    ) -> None:
        """Add a task to the registry."""
        self._tasks[name] = ScheduledTask(
            name=name,
            callback=callback,
            interval_seconds=interval_seconds,
            enabled=enabled,
        )

    def unregister(self, name: str) -> None:
        """Remove a task from the registry."""
        self._tasks.pop(name, None)

    def get_schedule(self) -> list[dict[str, Any]]:
        """Return all tasks with their schedule info."""
        result: list[dict[str, Any]] = []
        for t in self._tasks.values():
            result.append({
                "name": t.name,
                "interval_seconds": t.interval_seconds,
                "last_run": t.last_run,
                "next_run": t.next_run,
                "enabled": t.enabled,
            })
        return result

    # ── Execution ────────────────────────────────────────────────────

    def is_due(self, task: ScheduledTask) -> bool:
        """Check whether a task should run now."""
        if not task.enabled:
            return False
        now = datetime.now(timezone.utc)
        next_dt = datetime.fromisoformat(task.next_run)
        return now >= next_dt

    async def run_task(self, name: str) -> dict[str, Any]:
        """Manually execute a specific task, regardless of schedule."""
        task = self._tasks.get(name)
        if task is None:
            return {"name": name, "success": False, "result": None, "ran_at": None}

        now = datetime.now(timezone.utc)
        try:
            result = await task.callback()
            task.last_run = now.isoformat()
            from datetime import timedelta

            task.next_run = (now + timedelta(seconds=task.interval_seconds)).isoformat()
            return {
                "name": name,
                "success": True,
                "result": result,
                "ran_at": task.last_run,
            }
        except Exception:
            logger.exception("Task %s failed", name)
            task.last_run = now.isoformat()
            from datetime import timedelta

            task.next_run = (now + timedelta(seconds=task.interval_seconds)).isoformat()
            return {
                "name": name,
                "success": False,
                "result": None,
                "ran_at": task.last_run,
            }

    async def tick(self) -> list[str]:
        """Check all tasks, run any that are due, return list of names that ran."""
        ran: list[str] = []
        for task in list(self._tasks.values()):
            if self.is_due(task):
                result = await self.run_task(task.name)
                if result["ran_at"] is not None:
                    ran.append(task.name)
        return ran

    # ── Lifecycle ────────────────────────────────────────────────────

    async def _loop(self) -> None:
        """Internal loop that ticks every 60 seconds."""
        while self._running:
            try:
                await self.tick()
            except Exception:
                logger.exception("Engine tick failed")
            await asyncio.sleep(60)

    async def start(self) -> None:
        """Start the engine loop (non-blocking via asyncio.create_task)."""
        if self._running:
            return
        self._running = True
        self._loop_task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        """Stop the engine loop."""
        self._running = False
        if self._loop_task is not None:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
            self._loop_task = None
