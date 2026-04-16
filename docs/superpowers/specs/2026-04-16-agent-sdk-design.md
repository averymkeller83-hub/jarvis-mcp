# Agent SDK v1.5 Design Spec

## Goal

Add a Python agent framework to Jarvis MCP so developers can build custom agents (job search, meal planning, study, etc.) that plug into the daemon, share data, react to events, and are managed through the API.

## Architecture

Thin SDK layer on top of the existing `ProactiveEngine`. Agents are Python classes extending `BaseAgent`, discovered from the filesystem at startup, registered into the engine, and managed through a new `AgentManager`. Inter-agent communication uses a shared key-value context store backed by TOML and a lightweight in-process async event bus.

No new processes, no IPC, no external dependencies. Everything runs inside the existing FastAPI daemon.

## Scope

**In scope:**
- `BaseAgent` class with `AgentConfig`, `@trigger` decorator, lifecycle hooks
- `SharedContext` key-value store (TOML-backed, namespaced per agent)
- `EventBus` (async pub/sub, in-process, transient)
- `AgentManager` (discovery, registration, lifecycle, permission validation)
- Permission system (`config/agent_permissions.toml`, approve/deny at registration)
- Auto-discovery from `src/agents/` (built-in) and `agents/` (user-created)
- Two built-in agents: Briefing and Scout (refactored from existing modules)
- API endpoints for agent management
- Tests for all new modules

**Out of scope (deferred to v2):**
- CLI tool for agent install/remove
- Standalone process agents (subprocess isolation)
- Agent marketplace or distribution
- Agent-to-agent direct messaging (use event bus instead)
- Mission Control dashboard (separate spec)

---

## Module Structure

```
jarvis-mcp/
  src/
    sdk/                    # The agent framework
      __init__.py
      base.py               # BaseAgent, AgentConfig, @trigger
      context.py            # SharedContext store
      events.py             # EventBus
      loader.py             # Discovery + import from filesystem
      manager.py            # AgentManager — lifecycle, registration, permissions
      permissions.py        # Permission declarations and validation
    agents/                 # Built-in agents
      __init__.py
      briefing.py           # BriefingAgent — wraps compose_briefing()
      scout.py              # ScoutAgent — wraps run_discovery()
  agents/                   # User-created agents (gitignored)
  config/
    agent_permissions.toml  # Per-agent permission approvals
    agent_context.toml      # Shared context store
  tests/
    test_sdk.py             # SDK framework tests
    test_agents.py          # Built-in agent tests
```

---

## 1. BaseAgent API

### AgentConfig

Dataclass declaring agent metadata and requirements:

```python
@dataclass
class AgentConfig:
    name: str                          # Unique identifier, snake_case
    description: str                   # Human-readable, shown in API/dashboard
    permissions: list[str]             # Required capabilities
    schedule: str | None = None        # Cron expression, or None for event/user-only
    version: str = "0.1.0"
```

### Available Permissions

Agents declare which capabilities they need from this set:

- `web_requests` — make outbound HTTP calls
- `send_notifications` — send messages via notification channels
- `read_calendar` — read Calendar.app events
- `read_reminders` — read Reminders.app items
- `read_contacts` — access contact nicknames
- `file_read` — read files on disk
- `file_write` — write files on disk
- `execute_control` — trigger CONTROL actions (inherits tier rules)
- `shell_exec` — run shell commands (high-stakes, requires explicit approval)

### BaseAgent Class

```python
class BaseAgent:
    config: AgentConfig                # Must be set by subclass
    context: SharedContext             # Injected by AgentManager
    _event_bus: EventBus               # Injected by AgentManager

    async def on_start(self) -> None:
        """Called when agent is started. Override for setup logic."""
        pass

    async def on_stop(self) -> None:
        """Called when agent is stopped. Override for cleanup."""
        pass

    async def emit(self, event_name: str, data: dict) -> None:
        """Publish an event to the bus."""
        await self._event_bus.emit(event_name, data, source=self.config.name)
```

### @trigger Decorator

Marks methods for specific trigger types:

```python
@trigger("scheduled")
async def daily_scan(self) -> dict: ...

@trigger("user_invoked")
async def run_now(self, params: dict) -> dict: ...

@trigger("event", event="briefing_composing")
async def contribute(self, event_data: dict) -> dict: ...
```

- `"scheduled"` — registered into ProactiveEngine at the agent's cron schedule. Only one `@trigger("scheduled")` per agent.
- `"user_invoked"` — called via `POST /agents/{name}/run`. Only one per agent.
- `"event"` — subscribed to a named event on the EventBus. Multiple allowed per agent.

All trigger methods must be async. Return value (dict) is automatically written to shared context at `{agent_name}.last_result`.

---

## 2. SharedContext Store

Key-value store backed by `config/agent_context.toml`.

### Interface

```python
class SharedContext:
    async def get(self, key: str, default=None) -> Any: ...
    async def set(self, key: str, value: Any) -> None: ...
    async def delete(self, key: str) -> bool: ...
    async def list(self, prefix: str = "") -> list[str]: ...
    async def clear_namespace(self, namespace: str) -> int: ...
```

### Rules

- Keys are dot-namespaced: `agent_name.key_name`
- Agents can read any key across all namespaces
- Agents can only write to their own namespace (AgentManager wraps each agent's context with a `ScopedContext` that prefixes writes with the agent's name and rejects writes to other namespaces)
- Values must be TOML-serializable: str, int, float, bool, list, dict
- Writes are atomic (write to tmp file, then rename)
- The store is loaded into memory at startup and flushed to disk on every write
- `clear_namespace()` is called when an agent is uninstalled

### Briefing Integration

The briefing composer checks shared context for contributions from other agents. Any agent that writes to `{name}.briefing_section` (a dict with `title` and `body` keys) gets included in the morning briefing automatically.

---

## 3. EventBus

In-process async pub/sub for transient communication between agents.

### Interface

```python
class EventBus:
    def subscribe(self, event_name: str, callback: Callable) -> None: ...
    async def emit(self, event_name: str, data: dict, source: str) -> None: ...
    def unsubscribe(self, event_name: str, callback: Callable) -> None: ...
    def list_subscriptions(self) -> dict[str, list[str]]: ...
```

### Behavior

- `emit()` fires all subscribers concurrently via `asyncio.gather(return_exceptions=True)`
- Failed subscribers are logged but do not block the emitter or other subscribers
- Events are not persisted — they exist only at runtime
- Each event payload includes `_source` (emitting agent name) and `_timestamp`

### Built-in Events (emitted by Jarvis core)

| Event | Emitted When | Payload |
|---|---|---|
| `briefing_composing` | Briefing agent starts building | `{"briefing_time": "07:00"}` |
| `briefing_ready` | Briefing is composed | `{"section_count": 5}` |
| `scout_new_finds` | Scout discovers new items | `{"count": 3, "finds": [...]}` |
| `setup_complete` | First-run setup finishes | `{"user_name": "...", "step_count": 13}` |
| `agent_started` | Any agent starts | `{"agent_name": "..."}` |
| `agent_stopped` | Any agent stops | `{"agent_name": "...", "reason": "..."}` |
| `user_message` | User sends a message via chat/voice | `{"text": "...", "source": "voice"}` |

---

## 4. AgentManager

Central coordinator for agent lifecycle.

### Responsibilities

- **Discovery:** scans `src/agents/` and `agents/` for Python files containing `BaseAgent` subclasses
- **Validation:** checks `AgentConfig` is valid, permissions are from the known set
- **Permission check:** reads `config/agent_permissions.toml`, blocks unapproved agents
- **Registration:** instantiates agents, injects `SharedContext` and `EventBus`, registers scheduled triggers into `ProactiveEngine`, subscribes event triggers to `EventBus`
- **Lifecycle:** calls `on_start()` / `on_stop()`, tracks agent state (running/pending/stopped/error)
- **User invocation:** routes `POST /agents/{name}/run` to the agent's `@trigger("user_invoked")` method

### Agent States

```
discovered → pending (needs permission approval)
pending → running (approved, started)
running → stopped (manually stopped or shutdown)
running → error (unhandled exception, logged, auto-retried on next schedule)
stopped → running (manually restarted)
```

### Permission File Format

`config/agent_permissions.toml`:

```toml
[briefing]
approved = true
permissions = ["read_calendar", "read_reminders", "web_requests", "send_notifications"]
approved_at = "2026-04-16T12:00:00Z"

[scout]
approved = true
permissions = ["web_requests", "send_notifications"]
approved_at = "2026-04-16T12:00:00Z"

[job_search]
approved = false
permissions = ["web_requests", "send_notifications"]
discovered_at = "2026-04-16T14:30:00Z"
```

Built-in agents (`src/agents/`) are auto-approved. User agents (`agents/`) require explicit approval.

---

## 5. Built-in Agents

### BriefingAgent

```python
class BriefingAgent(BaseAgent):
    config = AgentConfig(
        name="briefing",
        description="Composes the daily morning briefing",
        permissions=["read_calendar", "read_reminders", "web_requests", "send_notifications"],
        schedule=None,  # Dynamically set from briefing_time config
    )
```

- `@trigger("scheduled")` — calls `compose_briefing()` with current news config, emits `briefing_composing` before and `briefing_ready` after, writes result to `briefing.latest` in shared context
- Schedule is read from `config/` at startup (user's configured briefing_time), converted to cron
- Existing `/briefing` endpoint continues to work — it calls the agent's method directly as a fallback
- No changes to `src/briefing/` modules — the agent calls them, doesn't replace them

### ScoutAgent

```python
class ScoutAgent(BaseAgent):
    config = AgentConfig(
        name="scout",
        description="Discovers tools, repos, and resources",
        permissions=["web_requests", "send_notifications"],
        schedule="0 */4 * * *",  # Every 4 hours
    )
```

- `@trigger("scheduled")` — calls `run_discovery()`, writes to `scout.latest_finds`, emits `scout_new_finds`
- `@trigger("user_invoked")` — runs discovery immediately when user requests
- Existing `/scout/discover` endpoint still works unchanged

---

## 6. API Endpoints

All new endpoints under `/agents`:

| Method | Path | Description |
|---|---|---|
| `GET` | `/agents` | List all agents with status, config, last run |
| `GET` | `/agents/{name}` | Agent detail: config, permissions, context data, run history |
| `POST` | `/agents/{name}/run` | User-invoke the agent (triggers `@trigger("user_invoked")`) |
| `PUT` | `/agents/{name}/approve` | Approve a pending agent's permissions |
| `POST` | `/agents/{name}/stop` | Stop a running agent |
| `POST` | `/agents/{name}/start` | Start a stopped/approved agent |
| `GET` | `/agents/{name}/context` | Read agent's shared context namespace |
| `GET` | `/events` | List all event bus subscriptions |

The existing `/status` endpoint is updated to include agent counts:

```json
{
  "services": {
    "agents": "available",
    "agent_count": 2,
    "agents_running": 2,
    "agents_pending": 0
  }
}
```

---

## 7. Error Handling

- Agent `@trigger` methods are wrapped in try/except. Failures are logged, agent state set to `error`, and the error is written to shared context at `{name}.last_error`.
- Scheduled agents that fail are retried on the next schedule tick (not immediately).
- Event subscribers that fail do not affect the emitter or other subscribers.
- Agent discovery errors (import failures, invalid config) are logged and the agent is skipped — it doesn't block other agents from loading.
- Timeout: scheduled and user-invoked triggers have a 60-second timeout. If exceeded, the task is cancelled and an error is logged.

---

## 8. Testing Strategy

- **Unit tests** for each SDK module: `BaseAgent` instantiation, `SharedContext` read/write/namespace enforcement, `EventBus` pub/sub and error isolation, `AgentManager` discovery and lifecycle, permission validation
- **Integration tests** for built-in agents: BriefingAgent produces a briefing, ScoutAgent produces finds, both write to shared context correctly
- **API tests** for all `/agents` endpoints via httpx + ASGITransport (same pattern as existing tests)
- **Event flow tests**: agent A emits, agent B receives, shared context is updated
- Mock filesystem for agent discovery tests (tmp_path with .py files containing agent classes)

Target: 60-80 new tests across `test_sdk.py` and `test_agents.py`.
