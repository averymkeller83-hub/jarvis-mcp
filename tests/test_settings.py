"""Comprehensive tests for the Settings module."""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any

import httpx
import pytest
import toml
from httpx import ASGITransport

import src.settings.manager as manager
from src.server.app import app
from src.settings.dashboard import render_dashboard


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _use_tmp_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Redirect CONFIG_DIR to a temp directory for every test."""
    monkeypatch.setattr(manager, "CONFIG_DIR", tmp_path)


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:7900")


# ── Settings manager: load_all_settings ─────────────────────────────────


def test_load_all_settings_returns_all_sections():
    result = manager.load_all_settings()
    expected_keys = {
        "personality", "voice", "behavior", "scout_sources",
        "contacts", "control_tiers", "briefing", "notifications",
        "communication", "privacy",
    }
    assert expected_keys == set(result.keys())


def test_load_all_settings_returns_defaults_when_no_files():
    result = manager.load_all_settings()
    assert isinstance(result["notifications"], dict)
    assert "morning_briefing" in result["notifications"]
    assert isinstance(result["control_tiers"], dict)
    assert "low_stakes" in result["control_tiers"]


# ── save_setting / save_section ──────────────────────────────────────────


def test_save_setting_writes_to_correct_file():
    assert manager.save_setting("privacy", "telemetry_enabled", True)
    data = manager.load_privacy()
    assert data["telemetry_enabled"] is True


def test_save_setting_unknown_section_returns_false():
    assert manager.save_setting("nonexistent", "key", "val") is False


def test_save_section_writes_entire_section():
    section_data = {"time": "08:30", "timezone": "US/Pacific"}
    assert manager.save_section("briefing", section_data)
    loaded = manager.load_briefing()
    assert loaded["time"] == "08:30"
    assert loaded["timezone"] == "US/Pacific"


def test_save_section_unknown_section_returns_false():
    assert manager.save_section("nonexistent", {"a": 1}) is False


def test_save_section_voice_merges_into_personality():
    manager.save_personality(dict(manager.DEFAULT_PERSONALITY))
    assert manager.save_section("voice", {"profile": "warm", "hotkey": "ctrl+j"})
    p = manager.load_personality()
    assert p["voice"]["profile"] == "warm"
    assert p["voice"]["hotkey"] == "ctrl+j"


def test_save_section_behavior_merges_into_personality():
    manager.save_personality(dict(manager.DEFAULT_PERSONALITY))
    assert manager.save_section("behavior", {"do_not_disturb": True})
    p = manager.load_personality()
    assert p["behavior"]["do_not_disturb"] is True


# ── Personality ──────────────────────────────────────────────────────────


def test_load_personality_with_existing_file():
    data = {"identity": {"assistant_name": "Jarvis", "user_display_name": "Boss"}}
    manager.save_personality(data)
    loaded = manager.load_personality()
    assert loaded["identity"]["assistant_name"] == "Jarvis"


def test_load_personality_missing_file_returns_defaults():
    loaded = manager.load_personality()
    assert loaded["identity"]["assistant_name"] == "JARVIS"
    assert loaded["identity"]["user_display_name"] == "Sir"


def test_save_personality_creates_file():
    data = {"identity": {"assistant_name": "Friday"}}
    assert manager.save_personality(data)
    path = manager.CONFIG_DIR / "personality.toml"
    assert path.exists()
    on_disk = toml.load(path)
    assert on_disk["identity"]["assistant_name"] == "Friday"


# ── Scout sources ────────────────────────────────────────────────────────


def test_load_scout_sources_defaults():
    loaded = manager.load_scout_sources()
    assert "sources" in loaded


def test_save_and_load_scout_sources():
    data = {"sources": {"github_trending": {"enabled": True, "cadence": "daily"}}}
    assert manager.save_scout_sources(data)
    loaded = manager.load_scout_sources()
    assert loaded["sources"]["github_trending"]["enabled"] is True


# ── Contacts nicknames ───────────────────────────────────────────────────


def test_load_contacts_defaults():
    loaded = manager.load_contacts_nicknames()
    assert "nicknames" in loaded


def test_save_and_load_contacts():
    data = {"nicknames": {"bro": "James Keller"}}
    assert manager.save_contacts_nicknames(data)
    loaded = manager.load_contacts_nicknames()
    assert loaded["nicknames"]["bro"] == "James Keller"


# ── Control tiers ────────────────────────────────────────────────────────


def test_load_control_tiers_defaults():
    loaded = manager.load_control_tiers()
    assert "alarm" in loaded["low_stakes"]
    assert "message" in loaded["high_stakes"]


def test_save_and_load_control_tiers():
    data = {"low_stakes": ["play", "pause"], "high_stakes": ["call"]}
    assert manager.save_control_tiers(data)
    loaded = manager.load_control_tiers()
    assert loaded["low_stakes"] == ["play", "pause"]
    assert loaded["high_stakes"] == ["call"]


# ── Notifications ────────────────────────────────────────────────────────


def test_load_notifications_default_matrix():
    loaded = manager.load_notifications()
    assert "morning_briefing" in loaded
    assert loaded["morning_briefing"]["telegram"] is True
    assert loaded["control_confirm"]["macos"] is True
    assert loaded["scout_curated"]["silent"] is True


def test_save_and_load_notifications():
    custom = dict(manager.DEFAULT_NOTIFICATIONS)
    custom["morning_briefing"] = {"macos": True, "telegram": False, "voice": False, "silent": False}
    assert manager.save_notifications(custom)
    loaded = manager.load_notifications()
    assert loaded["morning_briefing"]["macos"] is True
    assert loaded["morning_briefing"]["telegram"] is False


# ── Export ───────────────────────────────────────────────────────────────


def test_export_all_data_creates_zip(tmp_path: Path):
    # Write a config file so the zip is not empty
    manager.save_personality({"identity": {"assistant_name": "Test"}})
    export_path = str(tmp_path / "export.zip")
    result = manager.export_all_data(export_path)
    assert result == export_path
    assert Path(result).exists()
    with zipfile.ZipFile(result) as zf:
        names = zf.namelist()
        assert any("personality.toml" in n for n in names)


# ── Dashboard rendering ─────────────────────────────────────────────────


def test_render_dashboard_returns_html():
    settings = manager.load_all_settings()
    html = render_dashboard(settings)
    assert "<!DOCTYPE html>" in html
    assert "</html>" in html


def test_dashboard_contains_all_section_headings():
    settings = manager.load_all_settings()
    html = render_dashboard(settings)
    for heading in [
        "Personality", "Voice", "Behavior", "Scout Sources",
        "Contact Nicknames", "CONTROL Tier Assignments",
        "Briefing Preferences", "Notification Matrix", "Privacy",
    ]:
        assert heading in html, f"Missing section heading: {heading}"


def test_dashboard_contains_save_buttons():
    settings = manager.load_all_settings()
    html = render_dashboard(settings)
    assert "Save Personality" in html
    assert "Export All Data" in html


# ── Server endpoints ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_settings_returns_all_sections(client: httpx.AsyncClient):
    resp = await client.get("/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert "personality" in data
    assert "voice" in data
    assert "behavior" in data
    assert "notifications" in data
    assert "control_tiers" in data


@pytest.mark.asyncio
async def test_get_settings_dashboard_returns_html(client: httpx.AsyncClient):
    resp = await client.get("/settings/dashboard")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "JARVIS Settings" in resp.text


@pytest.mark.asyncio
async def test_put_settings_section(client: httpx.AsyncClient):
    resp = await client.put(
        "/settings/privacy",
        json={"telemetry_enabled": True, "local_only": False},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["section"] == "privacy"


@pytest.mark.asyncio
async def test_put_settings_section_unknown(client: httpx.AsyncClient):
    resp = await client.put("/settings/does_not_exist", json={"a": 1})
    assert resp.status_code == 404
    data = resp.json()
    assert data["success"] is False


@pytest.mark.asyncio
async def test_put_settings_key(client: httpx.AsyncClient):
    resp = await client.put(
        "/settings/privacy/telemetry_enabled",
        json={"value": True},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["key"] == "telemetry_enabled"


@pytest.mark.asyncio
async def test_get_notifications(client: httpx.AsyncClient):
    resp = await client.get("/settings/notifications")
    assert resp.status_code == 200
    data = resp.json()
    assert "morning_briefing" in data


@pytest.mark.asyncio
async def test_put_notifications(client: httpx.AsyncClient):
    body = {"morning_briefing": {"macos": True, "telegram": False, "voice": False, "silent": False}}
    resp = await client.put("/settings/notifications", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True


@pytest.mark.asyncio
async def test_get_control_tiers(client: httpx.AsyncClient):
    resp = await client.get("/settings/control-tiers")
    assert resp.status_code == 200
    data = resp.json()
    assert "low_stakes" in data
    assert "high_stakes" in data


@pytest.mark.asyncio
async def test_put_control_tiers(client: httpx.AsyncClient):
    body = {"low_stakes": ["play"], "high_stakes": ["call"]}
    resp = await client.put("/settings/control-tiers", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True


@pytest.mark.asyncio
async def test_settings_export(client: httpx.AsyncClient):
    resp = await client.post("/settings/export")
    assert resp.status_code == 200
    data = resp.json()
    assert "path" in data
    assert data["path"].endswith(".zip")


@pytest.mark.asyncio
async def test_status_shows_settings_available(client: httpx.AsyncClient):
    resp = await client.get("/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["services"]["settings"] == "available"


# ── Round-trip tests ─────────────────────────────────────────────────────


def test_roundtrip_personality():
    original = {"identity": {"assistant_name": "FRIDAY", "user_display_name": "Boss"}}
    manager.save_personality(original)
    loaded = manager.load_personality()
    assert loaded["identity"]["assistant_name"] == "FRIDAY"
    assert loaded["identity"]["user_display_name"] == "Boss"


def test_roundtrip_notifications():
    custom = dict(manager.DEFAULT_NOTIFICATIONS)
    custom["ci_failure"] = {"macos": True, "telegram": True, "voice": True, "silent": True}
    manager.save_notifications(custom)
    loaded = manager.load_notifications()
    assert loaded["ci_failure"]["macos"] is True
    assert loaded["ci_failure"]["voice"] is True


def test_roundtrip_control_tiers():
    custom = {"low_stakes": ["alarm", "timer"], "high_stakes": ["message", "call", "facetime"]}
    manager.save_control_tiers(custom)
    loaded = manager.load_control_tiers()
    assert loaded == custom


@pytest.mark.asyncio
async def test_roundtrip_via_api(client: httpx.AsyncClient):
    """Save via PUT, then load via GET and verify the data matches."""
    put_resp = await client.put(
        "/settings/privacy",
        json={"telemetry_enabled": True, "local_only": False, "auto_delete_logs_days": 7},
    )
    assert put_resp.status_code == 200
    get_resp = await client.get("/settings")
    assert get_resp.status_code == 200
    privacy = get_resp.json()["privacy"]
    assert privacy["telemetry_enabled"] is True
    assert privacy["local_only"] is False
    assert privacy["auto_delete_logs_days"] == 7
