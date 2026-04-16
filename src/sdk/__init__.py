"""Jarvis Agent SDK — framework for building custom agents.

Quick start::

    from src.sdk import AgentConfig, BaseAgent, trigger

    class MyAgent(BaseAgent):
        config = AgentConfig(
            name="my_agent",
            description="Does something useful",
            permissions=["web_requests"],
            schedule="0 9 * * *",
        )

        @trigger("scheduled")
        async def daily_run(self) -> dict:
            return {"done": True}
"""

from src.sdk.base import AgentConfig, BaseAgent, trigger
from src.sdk.context import ScopedContext, SharedContext
from src.sdk.events import EventBus
from src.sdk.manager import AgentManager

__all__ = [
    "AgentConfig",
    "AgentManager",
    "BaseAgent",
    "EventBus",
    "ScopedContext",
    "SharedContext",
    "trigger",
]
