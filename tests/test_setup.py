"""Comprehensive tests for the 12-step first-run setup flow."""

from __future__ import annotations

import pytest
import httpx
from httpx import ASGITransport
from unittest.mock import AsyncMock, patch

from src.setup.steps import (
    SUPPORTED_CHANNELS,
    SetupState,
    SetupStep,
    advance,
    complete_step,
    create_setup_steps,
    get_step,
    skip_step,
)
from src.setup.handlers import (
    STEP_HANDLERS,
    handle_claude_connection,
    handle_communication,
    handle_contacts,
    handle_done,
    handle_first_scan,
    handle_github_auth,
    handle_obsidian_vault,
    handle_personalization,
    handle_scout_sources,
    handle_services,
    handle_voice_setup,
    handle_welcome,
)
from src.setup.engine import (
    execute_step,
    get_setup_progress,
    is_setup_complete,
    skip_setup_step,
    start_setup,
)
from src.server.app import app


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def steps():
    return create_setup_steps()


@pytest.fixture
def state(steps):
    return SetupState(steps=steps, current_step=1, started_at="2026-01-01T00:00:00Z")


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:7900")


# ── Step definitions ──────────────────────────────────────────────────


def test_create_setup_steps_returns_12(steps):
    assert len(steps) == 12


def test_steps_1_and_4_are_required(steps):
    required = [s for s in steps if s.required]
    assert len(required) == 2
    assert required[0].number == 1
    assert required[1].number == 4


def test_optional_steps_count(steps):
    optional = [s for s in steps if not s.required]
    assert len(optional) == 10


def test_step_numbers_sequential(steps):
    numbers = [s.number for s in steps]
    assert numbers == list(range(1, 13))


def test_step_names_are_strings(steps):
    for s in steps:
        assert isinstance(s.name, str)
        assert len(s.name) > 0


def test_get_step_by_number(state):
    step = get_step(state, 1)
    assert step is not None
    assert step.name == "welcome"


def test_get_step_returns_none_for_invalid(state):
    assert get_step(state, 99) is None


def test_get_step_returns_none_for_zero(state):
    assert get_step(state, 0) is None


def test_advance_moves_to_next(state):
    assert state.current_step == 1
    state = advance(state)
    assert state.current_step == 2


def test_advance_stops_at_end(state):
    for _ in range(20):
        state = advance(state)
    assert state.current_step == 12


def test_skip_step_optional(state):
    state = skip_step(state, 2)
    step = get_step(state, 2)
    assert step.skipped is True


def test_skip_step_fails_for_required_step_1(state):
    with pytest.raises(ValueError, match="required"):
        skip_step(state, 1)


def test_skip_step_fails_for_required_step_4(state):
    with pytest.raises(ValueError, match="required"):
        skip_step(state, 4)


def test_skip_step_fails_for_invalid_number(state):
    with pytest.raises(ValueError, match="does not exist"):
        skip_step(state, 99)


def test_complete_step_marks_done(state):
    result_data = {"msg": "ok"}
    state = complete_step(state, 1, result_data)
    step = get_step(state, 1)
    assert step.completed is True
    assert step.result == {"msg": "ok"}


def test_complete_step_with_no_result(state):
    state = complete_step(state, 6)
    step = get_step(state, 6)
    assert step.completed is True
    assert step.result is None


def test_complete_step_fails_for_invalid(state):
    with pytest.raises(ValueError, match="does not exist"):
        complete_step(state, 99)


def test_supported_channels_list():
    assert "imessage" in SUPPORTED_CHANNELS
    assert "telegram" in SUPPORTED_CHANNELS
    assert "discord" in SUPPORTED_CHANNELS
    assert "slack" in SUPPORTED_CHANNELS
    assert "email" in SUPPORTED_CHANNELS
    assert "macos_notifications" in SUPPORTED_CHANNELS


# ── Handlers ──────────────────────────────────────────────────────────


async def test_handle_welcome_completes(state):
    state, result = await handle_welcome(state, {})
    assert "message" in result
    assert result["assistant_name"] == "JARVIS"
    step = get_step(state, 1)
    assert step.completed is True


async def test_handle_welcome_custom_name(state):
    state, result = await handle_welcome(state, {"assistant_name": "Friday"})
    assert result["assistant_name"] == "Friday"
    assert "Friday" in result["message"]


async def test_handle_personalization(state, tmp_path, monkeypatch):
    monkeypatch.setattr("src.setup.handlers.CONFIG_DIR", tmp_path)
    config = {"user_name": "Avery", "assistant_name": "JARVIS"}
    state, result = await handle_personalization(state, config)
    assert result["user_name"] == "Avery"
    assert result["assistant_name"] == "JARVIS"
    step = get_step(state, 2)
    assert step.completed is True
    personality = tmp_path / "personality.toml"
    assert personality.exists()


async def test_handle_communication_defaults(state, tmp_path, monkeypatch):
    monkeypatch.setattr("src.setup.handlers.CONFIG_DIR", tmp_path)
    state, result = await handle_communication(state, {})
    assert result["primary"] == "macos_notifications"
    assert result["enabled"] == ["macos_notifications"]
    assert "available" in result
    step = get_step(state, 3)
    assert step.completed is True
    assert (tmp_path / "communication.toml").exists()


async def test_handle_communication_multiple_channels(state, tmp_path, monkeypatch):
    monkeypatch.setattr("src.setup.handlers.CONFIG_DIR", tmp_path)
    config = {"channels": ["imessage", "telegram"], "primary": "telegram"}
    state, result = await handle_communication(state, config)
    assert result["primary"] == "telegram"
    assert result["enabled"] == ["imessage", "telegram"]
    assert "telegram" in result["message"]


async def test_handle_communication_invalid_channels(state, tmp_path, monkeypatch):
    monkeypatch.setattr("src.setup.handlers.CONFIG_DIR", tmp_path)
    config = {"channels": ["carrier_pigeon", "smoke_signal"]}
    state, result = await handle_communication(state, config)
    assert result["primary"] == "macos_notifications"
    assert result["enabled"] == ["macos_notifications"]


async def test_handle_communication_invalid_primary(state, tmp_path, monkeypatch):
    monkeypatch.setattr("src.setup.handlers.CONFIG_DIR", tmp_path)
    config = {"channels": ["imessage", "telegram"], "primary": "discord"}
    state, result = await handle_communication(state, config)
    assert result["primary"] == "imessage"  # falls back to first valid


async def test_handle_communication_telegram_credentials(state, tmp_path, monkeypatch):
    monkeypatch.setattr("src.setup.handlers.CONFIG_DIR", tmp_path)
    config = {
        "channels": ["telegram"],
        "primary": "telegram",
        "telegram_bot_token": "123456:ABC-DEF",
        "telegram_chat_id": "987654321",
    }
    state, result = await handle_communication(state, config)
    import toml as toml_lib
    data = toml_lib.load(tmp_path / "communication.toml")
    assert data["telegram"]["bot_token"] == "123456:ABC-DEF"
    assert data["telegram"]["chat_id"] == "987654321"


async def test_handle_communication_discord_credentials(state, tmp_path, monkeypatch):
    monkeypatch.setattr("src.setup.handlers.CONFIG_DIR", tmp_path)
    config = {
        "channels": ["discord"],
        "primary": "discord",
        "discord_bot_token": "MTIz.abc",
        "discord_channel_id": "444",
    }
    state, result = await handle_communication(state, config)
    import toml as toml_lib
    data = toml_lib.load(tmp_path / "communication.toml")
    assert data["discord"]["bot_token"] == "MTIz.abc"


async def test_handle_communication_slack_credentials(state, tmp_path, monkeypatch):
    monkeypatch.setattr("src.setup.handlers.CONFIG_DIR", tmp_path)
    config = {
        "channels": ["slack"],
        "primary": "slack",
        "slack_bot_token": "xoxb-123",
        "slack_channel_id": "C01234",
    }
    state, result = await handle_communication(state, config)
    import toml as toml_lib
    data = toml_lib.load(tmp_path / "communication.toml")
    assert data["slack"]["bot_token"] == "xoxb-123"


async def test_handle_communication_email_credentials(state, tmp_path, monkeypatch):
    monkeypatch.setattr("src.setup.handlers.CONFIG_DIR", tmp_path)
    config = {
        "channels": ["email"],
        "primary": "email",
        "email_smtp_host": "smtp.gmail.com",
        "email_username": "user@gmail.com",
        "email_password": "pass",
    }
    state, result = await handle_communication(state, config)
    import toml as toml_lib
    data = toml_lib.load(tmp_path / "communication.toml")
    assert data["email"]["smtp_host"] == "smtp.gmail.com"


async def test_handle_claude_connection(state, tmp_path, monkeypatch):
    # Create Claude Desktop config dir
    claude_dir = tmp_path / "Library" / "Application Support" / "Claude"
    claude_dir.mkdir(parents=True)
    (claude_dir / "claude_desktop_config.json").write_text("{}")
    monkeypatch.setattr("src.setup.handlers.Path.home", lambda: tmp_path)

    state, result = await handle_claude_connection(state, {})
    assert result["registered"] is True
    step = get_step(state, 4)
    assert step.completed is True

    import json
    data = json.loads((claude_dir / "claude_desktop_config.json").read_text())
    assert "jarvis" in data["mcpServers"]


async def test_handle_contacts(state, tmp_path, monkeypatch):
    monkeypatch.setattr("src.setup.handlers.CONFIG_DIR", tmp_path)
    config = {"nicknames": {"mom": "Jane Keller", "bro": "Mike Keller"}}
    state, result = await handle_contacts(state, config)
    assert result["nickname_count"] == 2
    step = get_step(state, 5)
    assert step.completed is True
    assert (tmp_path / "contacts_nicknames.toml").exists()


async def test_handle_services_multiple(state):
    config = {"services": ["apple", "google", "microsoft"]}
    state, result = await handle_services(state, config)
    assert result["count"] == 3
    assert "google" in result["services"]
    step = get_step(state, 6)
    assert step.completed is True


async def test_handle_services_default(state):
    state, result = await handle_services(state, {})
    assert result["services"] == ["apple"]


async def test_handle_scout_sources(state, tmp_path, monkeypatch):
    monkeypatch.setattr("src.setup.handlers.CONFIG_DIR", tmp_path)
    import toml

    example = tmp_path / "scout_sources.example.toml"
    example.write_text(toml.dumps({
        "sources": {
            "anthropic_changelog": {"enabled": False, "cadence": "hourly", "description": "t"},
            "mcp_registry": {"enabled": False, "cadence": "daily", "description": "t"},
        }
    }))
    config = {"sources": ["anthropic_changelog", "mcp_registry"]}
    state, result = await handle_scout_sources(state, config)
    assert result["count"] == 2
    step = get_step(state, 7)
    assert step.completed is True


async def test_handle_github_auth(state):
    state, result = await handle_github_auth(state, {})
    step = get_step(state, 8)
    assert step.completed is True


async def test_handle_obsidian_vault_valid(state, tmp_path, monkeypatch):
    monkeypatch.setattr("src.setup.handlers.CONFIG_DIR", tmp_path)
    vault = tmp_path / "my-vault"
    vault.mkdir()
    (vault / ".obsidian").mkdir()
    state, result = await handle_obsidian_vault(state, {"vault_path": str(vault)})
    assert result["valid"] is True
    step = get_step(state, 9)
    assert step.completed is True


async def test_handle_obsidian_vault_invalid(state, tmp_path, monkeypatch):
    monkeypatch.setattr("src.setup.handlers.CONFIG_DIR", tmp_path)
    state, result = await handle_obsidian_vault(state, {"vault_path": "/nonexistent"})
    assert result["valid"] is False


async def test_handle_obsidian_vault_empty(state, tmp_path, monkeypatch):
    monkeypatch.setattr("src.setup.handlers.CONFIG_DIR", tmp_path)
    state, result = await handle_obsidian_vault(state, {})
    assert result["valid"] is False
    assert "can add later" in result["message"]


async def test_handle_voice_setup_defaults(state, tmp_path, monkeypatch):
    monkeypatch.setattr("src.setup.handlers.CONFIG_DIR", tmp_path)
    state, result = await handle_voice_setup(state, {})
    assert result["tts_provider"] == "macos_say"
    assert result["stt_provider"] == "macos_dictation"
    step = get_step(state, 10)
    assert step.completed is True
    assert (tmp_path / "voice.toml").exists()


async def test_handle_voice_setup_custom(state, tmp_path, monkeypatch):
    monkeypatch.setattr("src.setup.handlers.CONFIG_DIR", tmp_path)
    config = {
        "tts_provider": "fish_audio",
        "tts_api_key": "key123",
        "stt_provider": "deepgram",
        "stt_api_key": "dgkey",
    }
    state, result = await handle_voice_setup(state, config)
    assert result["tts_provider"] == "fish_audio"
    assert result["stt_provider"] == "deepgram"
    import toml as toml_lib
    data = toml_lib.load(tmp_path / "voice.toml")
    assert data["tts"]["api_key"] == "key123"
    assert data["stt"]["api_key"] == "dgkey"


async def test_handle_first_scan(state):
    with patch("src.scout.engine.run_discovery", new_callable=AsyncMock) as mock_disc:
        mock_disc.return_value = []
        state, result = await handle_first_scan(state, {})
        assert result["scan_count"] == 0
        mock_disc.assert_awaited_once()
    step = get_step(state, 11)
    assert step.completed is True


async def test_handle_done_default_name(state):
    state, result = await handle_done(state, {})
    assert "Sir" in result["message"]
    assert "JARVIS" in result["message"]
    assert "more time for" in result["message"]
    assert "Avery Keller" in result["message"]
    assert result["sent_via"] == "macos_notifications"
    step = get_step(state, 12)
    assert step.completed is True


async def test_handle_done_personalised(state):
    complete_step(state, 2, {"user_name": "Avery", "assistant_name": "JARVIS"})
    complete_step(state, 3, {"primary": "telegram", "enabled": ["telegram"]})
    state, result = await handle_done(state, {})
    assert "Avery" in result["message"]
    assert result["user_name"] == "Avery"
    assert result["sent_via"] == "telegram"
    assert "driver's seat" in result["message"]


def test_step_handlers_dict_has_all_12():
    assert len(STEP_HANDLERS) == 12
    for i in range(1, 13):
        assert i in STEP_HANDLERS


# ── Engine ────────────────────────────────────────────────────────────


async def test_start_setup():
    state = await start_setup()
    assert len(state.steps) == 12
    assert state.current_step == 1
    assert state.started_at != ""


async def test_execute_step_runs_handler():
    state = await start_setup()
    state, result = await execute_step(state, 1, {})
    assert result["assistant_name"] == "JARVIS"
    assert state.current_step == 2


async def test_execute_step_invalid_number():
    state = await start_setup()
    with pytest.raises(ValueError, match="No handler"):
        await execute_step(state, 99, {})


async def test_skip_setup_step_optional():
    state = await start_setup()
    state, result = await skip_setup_step(state, 2)
    assert result["skipped"] is True
    step = get_step(state, 2)
    assert step.skipped is True


async def test_skip_setup_step_required_fails():
    state = await start_setup()
    with pytest.raises(ValueError, match="required"):
        await skip_setup_step(state, 1)


def test_is_setup_complete_false_initially():
    from src.setup.steps import create_setup_steps

    state = SetupState(steps=create_setup_steps(), started_at="t")
    assert is_setup_complete(state) is False


def test_is_setup_complete_true_when_last_step_done():
    from src.setup.steps import create_setup_steps

    state = SetupState(steps=create_setup_steps(), started_at="t")
    complete_step(state, 12, {"done": True})
    assert is_setup_complete(state) is True


def test_get_setup_progress_initial():
    from src.setup.steps import create_setup_steps

    state = SetupState(steps=create_setup_steps(), started_at="t")
    prog = get_setup_progress(state)
    assert prog["total"] == 12
    assert prog["completed"] == 0
    assert prog["skipped"] == 0
    assert prog["remaining"] == 12
    assert prog["percent"] == 0


def test_get_setup_progress_partial():
    from src.setup.steps import create_setup_steps

    state = SetupState(steps=create_setup_steps(), started_at="t")
    complete_step(state, 1)
    complete_step(state, 2)
    skip_step(state, 5)
    prog = get_setup_progress(state)
    assert prog["completed"] == 2
    assert prog["skipped"] == 1
    assert prog["remaining"] == 9
    assert prog["percent"] == 17  # round(2/12 * 100) = 17


# ── Server endpoints ─────────────────────────────────────────────────


async def test_setup_start_endpoint(client):
    resp = await client.post("/setup/start")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "started"
    assert data["total_steps"] == 12
    assert data["current_step"] == 1


async def test_setup_step_endpoint(client):
    await client.post("/setup/start")
    resp = await client.post("/setup/step/1", json={"config": {}})
    assert resp.status_code == 200
    data = resp.json()
    assert data["step"] == 1
    assert "result" in data
    assert data["current_step"] == 2


async def test_setup_step_without_start(client):
    import src.server.app as srv
    srv._setup_state = None

    resp = await client.post("/setup/step/1", json={"config": {}})
    assert resp.status_code == 200
    data = resp.json()
    assert "error" in data


async def test_setup_skip_endpoint(client):
    await client.post("/setup/start")
    resp = await client.post("/setup/skip/2")
    assert resp.status_code == 200
    data = resp.json()
    assert data["result"]["skipped"] is True


async def test_setup_skip_required_returns_error(client):
    await client.post("/setup/start")
    resp = await client.post("/setup/skip/1")
    assert resp.status_code == 200
    data = resp.json()
    assert "error" in data
    assert "required" in data["error"]


async def test_setup_progress_endpoint(client):
    await client.post("/setup/start")
    await client.post("/setup/step/1", json={"config": {}})
    resp = await client.get("/setup/progress")
    assert resp.status_code == 200
    data = resp.json()
    assert data["completed"] == 1
    assert data["total"] == 12


async def test_setup_progress_without_start(client):
    import src.server.app as srv
    srv._setup_state = None

    resp = await client.get("/setup/progress")
    assert resp.status_code == 200
    data = resp.json()
    assert "error" in data


async def test_status_includes_setup(client):
    resp = await client.get("/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["services"]["setup"] == "available"


# ── Full walkthrough ─────────────────────────────────────────────────


async def test_full_setup_walkthrough(client, tmp_path, monkeypatch):
    """Walk through all 12 steps end-to-end."""
    monkeypatch.setattr("src.setup.handlers.CONFIG_DIR", tmp_path)

    # Start
    resp = await client.post("/setup/start")
    assert resp.json()["status"] == "started"

    # Step 1 — welcome
    resp = await client.post("/setup/step/1", json={"config": {}})
    assert resp.json()["result"]["assistant_name"] == "JARVIS"

    # Step 2 — personalization
    resp = await client.post(
        "/setup/step/2",
        json={"config": {"user_name": "Avery", "assistant_name": "JARVIS"}},
    )
    assert resp.json()["result"]["user_name"] == "Avery"

    # Step 3 — communication
    resp = await client.post(
        "/setup/step/3",
        json={
            "config": {
                "channels": ["imessage", "telegram"],
                "primary": "telegram",
                "telegram_bot_token": "123:ABC",
                "telegram_chat_id": "999",
            }
        },
    )
    assert resp.json()["result"]["primary"] == "telegram"

    # Step 4 — claude desktop MCP registration
    claude_dir = tmp_path / "Library" / "Application Support" / "Claude"
    claude_dir.mkdir(parents=True)
    (claude_dir / "claude_desktop_config.json").write_text("{}")
    monkeypatch.setattr("src.setup.handlers.Path.home", lambda: tmp_path)
    resp = await client.post("/setup/step/4", json={"config": {}})
    assert resp.json()["result"]["registered"] is True

    # Step 5 — contacts
    resp = await client.post(
        "/setup/step/5",
        json={"config": {"nicknames": {"mom": "Jane"}}},
    )

    # Step 6 — services
    resp = await client.post(
        "/setup/step/6",
        json={"config": {"services": ["apple", "google"]}},
    )
    assert resp.json()["result"]["count"] == 2

    # Step 7 — scout sources (skip — no example file in tmp_path)
    resp = await client.post(
        "/setup/step/7",
        json={"config": {"sources": []}},
    )
    assert resp.json()["step"] == 7

    # Step 8 — github
    resp = await client.post("/setup/step/8", json={"config": {}})

    # Step 9 — obsidian vault
    vault = tmp_path / "my-vault"
    vault.mkdir()
    (vault / ".obsidian").mkdir()
    resp = await client.post(
        "/setup/step/9",
        json={"config": {"vault_path": str(vault)}},
    )
    assert resp.json()["result"]["valid"] is True

    # Step 10 — voice setup
    resp = await client.post(
        "/setup/step/10",
        json={"config": {"tts_provider": "macos_say", "stt_provider": "macos_dictation"}},
    )
    assert resp.json()["result"]["tts_provider"] == "macos_say"

    # Step 11 — first scan (mock discovery)
    with patch("src.scout.engine.run_discovery", new_callable=AsyncMock) as mock_d:
        mock_d.return_value = []
        resp = await client.post("/setup/step/11", json={"config": {}})
        assert resp.json()["result"]["scan_count"] == 0

    # Step 12 — done (first contact message)
    resp = await client.post("/setup/step/12", json={"config": {}})
    data = resp.json()
    assert "Avery" in data["result"]["message"]
    assert "more time for" in data["result"]["message"]
    assert data["result"]["sent_via"] == "telegram"
    assert data["complete"] is True

    # Verify progress
    resp = await client.get("/setup/progress")
    prog = resp.json()
    assert prog["completed"] == 12
    assert prog["percent"] == 100
