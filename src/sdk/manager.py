"""AgentManager — central coordinator for agent lifecycle."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.engine.scheduler import ProactiveEngine
from src.sdk.base import BaseAgent
from src.sdk.context import SharedContext, ScopedContext
from src.sdk.events import EventBus
from src.sdk.loader import discover_agents
from src.sdk.permissions import (
    approve_agent as _approve_in_file,
    is_approved,
    load_permissions,
    save_permissions,
    validate_permissions,
)

logger = logging.getLogger(__name__)

# Cron shorthand to interval_seconds (simplified for v1.5)
_CRON_INTERVALS: dict[str, int] = {
    "0 */4 * * *": 14400,       # every 4 hours
    "0 * * * *": 3600,          # every hour
    "0 0 * * *": 86400,         # daily at midnight
}
_DEFAULT_INTERVAL = 86400


def _cron_to_interval(cron: str) -> int:
    """Convert a cron expression to interval seconds (best-effort)."""
    return _CRON_INTERVALS.get(cron, _DEFAULT_INTERVAL)


class AgentManager:
    """Manages agent discovery, registration, permissions, and lifecycle."""

    def __init__(
        self,
        engine: ProactiveEngine,
        config_dir: Path,
        builtin_dir: Path | None = None,
        user_dir: Path | None = None,
    ) -> None:
        self.engine = engine
        self.config_dir = Path(config_dir)
        self.builtin_dir = builtin_dir
        self.user_dir = user_dir

        self.event_bus = EventBus()
        self._context = SharedContext(
            store_path=self.config_dir / "agent_context.toml"
        )

        self.agents: dict[str, BaseAgent] = {}
        self.states: dict[str, str] = {}
        self._permissions_path = self.config_dir / "agent_permissions.toml"

    # ── Registration ────────────────────────────────────────────────

    def register(self, agent: BaseAgent, builtin: bool = False) -> None:
        """Register an agent, inject dependencies, wire triggers."""
        name = agent.config.name

        # Inject context + event bus
        agent.context = ScopedContext(self._context, namespace=name)
        agent._event_bus = self.event_bus

        self.agents[name] = agent

        if builtin:
            # Auto-approve built-in agents
            self._persist_permission(name, agent.config.permissions, approved=True)
            self.states[name] = "running"
            self._wire_triggers(agent)
        else:
            # User agents start pending
            perms = load_permissions(self._permissions_path)
            if is_approved(perms, name):
                self.states[name] = "running"
                self._wire_triggers(agent)
            else:
                self._persist_permission(
                    name, agent.config.permissions, approved=False
                )
                self.states[name] = "pending"

    def _persist_permission(
        self, name: str, permissions: list[str], approved: bool
    ) -> None:
        perms = load_permissions(self._permissions_path)
        now = datetime.now(timezone.utc).isoformat()
        perms[name] = {
            "approved": approved,
            "permissions": permissions,
        }
        if approved:
            perms[name]["approved_at"] = now
        else:
            perms[name]["discovered_at"] = now
        save_permissions(self._permissions_path, perms)

    def _wire_triggers(self, agent: BaseAgent) -> None:
        """Register scheduled triggers into ProactiveEngine and event
        triggers into EventBus."""
        name = agent.config.name

        for attr_name in dir(agent):
            method = getattr(agent, attr_name, None)
            meta = getattr(method, "_trigger_meta", None)
            if meta is None:
                continue

            trigger_type = meta["type"]

            if trigger_type == "scheduled" and agent.config.schedule:
                interval = _cron_to_interval(agent.config.schedule)

                async def _scheduled_cb(_m=method, _n=name):
                    result = await asyncio.wait_for(_m(), timeout=60)
                    if isinstance(result, dict):
                        await self._context.set(f"{_n}.last_result", result)
                    return result

                self.engine.register(
                    f"agent:{name}", _scheduled_cb, interval_seconds=interval
                )

            elif trigger_type == "event":
                event_name = meta.get("event")
                if event_name:

                    async def _event_cb(data, _m=method, _n=name):
                        result = await asyncio.wait_for(_m(data), timeout=60)
                        if isinstance(result, dict):
                            await self._context.set(f"{_n}.last_result", result)
                        return result

                    self.event_bus.subscribe(event_name, _event_cb)

    def _unwire_triggers(self, agent: BaseAgent) -> None:
        name = agent.config.name
        self.engine.unregister(f"agent:{name}")

    # ── Lifecycle ───────────────────────────────────────────────────

    async def approve(self, name: str) -> None:
        agent = self.agents.get(name)
        if agent is None:
            return
        _approve_in_file(self._permissions_path, name)
        self.states[name] = "running"
        self._wire_triggers(agent)
        await agent.on_start()
        await self.event_bus.emit(
            "agent_started", {"agent_name": name}, source="manager"
        )

    async def stop_agent(self, name: str) -> None:
        agent = self.agents.get(name)
        if agent is None:
            return
        self._unwire_triggers(agent)
        self.states[name] = "stopped"
        await agent.on_stop()
        await self.event_bus.emit(
            "agent_stopped", {"agent_name": name, "reason": "manual"}, source="manager"
        )

    async def start_agent(self, name: str) -> None:
        agent = self.agents.get(name)
        if agent is None:
            return
        perms = load_permissions(self._permissions_path)
        if not is_approved(perms, name):
            return
        self._wire_triggers(agent)
        self.states[name] = "running"
        await agent.on_start()
        await self.event_bus.emit(
            "agent_started", {"agent_name": name}, source="manager"
        )

    async def invoke(self, name: str, params: dict) -> dict:
        """Run an agent's user_invoked trigger."""
        agent = self.agents.get(name)
        if agent is None:
            return {"error": f"Agent '{name}' not found"}
        if self.states.get(name) != "running":
            return {"error": f"Agent '{name}' is not running (state: {self.states.get(name)})"}

        for attr_name in dir(agent):
            method = getattr(agent, attr_name, None)
            meta = getattr(method, "_trigger_meta", None)
            if meta and meta["type"] == "user_invoked":
                try:
                    result = await asyncio.wait_for(method(params), timeout=60)
                    if isinstance(result, dict):
                        await self._context.set(f"{name}.last_result", result)
                    return result
                except Exception as exc:
                    self.states[name] = "error"
                    error_msg = str(exc)
                    await self._context.set(f"{name}.last_error", error_msg)
                    return {"error": error_msg}

        return {"error": f"Agent '{name}' has no user_invoked trigger"}

    # ── Discovery ───────────────────────────────────────────────────

    async def discover_and_register(self) -> list[str]:
        """Scan filesystem, register all found agents. Returns list of names."""
        dirs: list[Path] = []
        if self.builtin_dir and self.builtin_dir.is_dir():
            dirs.append(self.builtin_dir)
        if self.user_dir and self.user_dir.is_dir():
            dirs.append(self.user_dir)

        if not dirs:
            return []

        found = discover_agents(dirs)
        registered: list[str] = []

        for agent in found:
            if agent.config.name in self.agents:
                continue
            # Built-in agents come from the builtin_dir
            is_builtin = self.builtin_dir is not None
            self.register(agent, builtin=is_builtin)
            registered.append(agent.config.name)

        return registered

    # ── Queries ─────────────────────────────────────────────────────

    def list_agents(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for name, agent in self.agents.items():
            result.append({
                "name": name,
                "description": agent.config.description,
                "status": self.states.get(name, "unknown"),
                "permissions": agent.config.permissions,
                "schedule": agent.config.schedule,
                "version": agent.config.version,
            })
        return result

    def get_agent(self, name: str) -> dict[str, Any] | None:
        agent = self.agents.get(name)
        if agent is None:
            return None
        return {
            "name": name,
            "description": agent.config.description,
            "status": self.states.get(name, "unknown"),
            "permissions": agent.config.permissions,
            "schedule": agent.config.schedule,
            "version": agent.config.version,
        }
