"""BaseAgent class and @trigger decorator for the Jarvis Agent SDK."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentConfig:
    """Declares agent metadata and permission requirements."""

    name: str
    description: str
    permissions: list[str] = field(default_factory=list)
    schedule: str | None = None
    version: str = "0.1.0"


def trigger(trigger_type: str, *, event: str | None = None):
    """Decorator marking a method as an agent trigger.

    Args:
        trigger_type: One of "scheduled", "user_invoked", "event".
        event: Required when trigger_type is "event" — the event name
               to subscribe to on the EventBus.
    """
    def decorator(func):
        func._trigger_meta = {
            "type": trigger_type,
            "event": event,
        }
        return func
    return decorator


class BaseAgent:
    """Base class for all Jarvis agents.

    Subclasses must set ``config`` as a class attribute.
    ``context`` and ``_event_bus`` are injected by ``AgentManager``.
    """

    config: AgentConfig

    def __init__(self) -> None:
        from src.sdk.context import ScopedContext
        from src.sdk.events import EventBus

        self.context: ScopedContext | None = None
        self._event_bus: EventBus | None = None

    async def on_start(self) -> None:
        """Called when the agent is started. Override for setup logic."""
        pass

    async def on_stop(self) -> None:
        """Called when the agent is stopped. Override for cleanup."""
        pass

    async def emit(self, event_name: str, data: dict) -> None:
        """Publish an event to the EventBus."""
        if self._event_bus is None:
            return
        await self._event_bus.emit(event_name, data, source=self.config.name)
