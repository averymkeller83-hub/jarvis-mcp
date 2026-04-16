"""EventBus — in-process async pub/sub for agent communication."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Callable

logger = logging.getLogger(__name__)


class EventBus:
    """Lightweight async event bus.

    Subscribers are async callables that receive a single dict argument.
    Failed subscribers are logged but do not block the emitter or other
    subscribers.
    """

    def __init__(self) -> None:
        self._subs: dict[str, list[Callable]] = {}

    def subscribe(self, event_name: str, callback: Callable) -> None:
        self._subs.setdefault(event_name, []).append(callback)

    def unsubscribe(self, event_name: str, callback: Callable) -> None:
        listeners = self._subs.get(event_name, [])
        self._subs[event_name] = [cb for cb in listeners if cb is not callback]

    async def emit(self, event_name: str, data: dict, source: str) -> None:
        payload: dict[str, Any] = {
            **data,
            "_source": source,
            "_timestamp": datetime.now(timezone.utc).isoformat(),
        }
        listeners = self._subs.get(event_name, [])
        if not listeners:
            return

        results = await asyncio.gather(
            *(self._safe_call(cb, payload) for cb in listeners),
            return_exceptions=True,
        )
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning(
                    "EventBus subscriber for %r failed: %s", event_name, result
                )

    async def _safe_call(self, callback: Callable, payload: dict) -> Any:
        return await callback(payload)

    def list_subscriptions(self) -> dict[str, list[str]]:
        return {
            event: [getattr(cb, "__qualname__", repr(cb)) for cb in cbs]
            for event, cbs in self._subs.items()
            if cbs
        }
