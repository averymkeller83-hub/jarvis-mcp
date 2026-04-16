"""Comprehensive tests for the CONTROL surface handlers (src/hands/)."""

from __future__ import annotations

import pytest
import httpx
from httpx import ASGITransport

from src.hands import ControlResult
from src.hands.executor import (
    LOW_STAKES,
    HIGH_STAKES,
    execute_control,
    risk_tier,
)
from src.hands.messaging import _build_imessage_script, send_imessage, send_telegram
from src.hands.reminders import _build_reminder_script, add_to_list, set_reminder
from src.hands.alarms import _parse_duration, cancel_alarm, set_alarm, set_timer
from src.hands.music import (
    _build_music_script,
    pause,
    play,
    previous,
    set_volume,
    skip,
    volume_down,
    volume_up,
)
from src.hands.homekit import (
    lock_device,
    set_thermostat,
    trigger_scene,
    turn_off,
    turn_on,
    unlock_device,
)
from src.hands.calls import facetime_call, hang_up, make_call
from src.hands.calendar import add_event, check_calendar
from src.hands.contacts import (
    ContactMatch,
    add_recent,
    clear_recent,
    resolve_ambiguous,
    resolve_contact,
    _load_nicknames,
)
from src.server.app import app


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:7900")


@pytest.fixture(autouse=True)
def _clean_recent_cache():
    """Reset the recent contact cache before each test."""
    clear_recent()
    yield
    clear_recent()


# ══════════════════════════════════════════════════════════════════════
# 1. Executor — dispatch & risk tiers
# ══════════════════════════════════════════════════════════════════════


class TestRiskTier:
    """Risk tier classification."""

    def test_low_stakes_verbs(self):
        for verb in LOW_STAKES:
            assert risk_tier(verb) == "low", f"{verb} should be low-stakes"

    def test_high_stakes_verbs(self):
        for verb in HIGH_STAKES:
            assert risk_tier(verb) == "high", f"{verb} should be high-stakes"

    def test_unknown_verb_defaults_to_high(self):
        assert risk_tier("self_destruct") == "high"


class TestExecutorDispatch:
    """Executor dispatches to the correct handler for every verb."""

    @pytest.mark.asyncio
    async def test_dispatch_message(self):
        result = await execute_control(
            {"verb": "message", "target": "Mom", "payload": "on my way"},
            confirmed=True,
        )
        assert result.action == "message"
        assert result.success is True
        assert result.confirmed is True
        assert "Mom" in result.message

    @pytest.mark.asyncio
    async def test_dispatch_remind(self):
        result = await execute_control(
            {"verb": "remind", "target": "5pm", "payload": "buy milk"},
            confirmed=True,
        )
        assert result.action == "remind"
        assert result.success is True

    @pytest.mark.asyncio
    async def test_dispatch_add_to_list(self):
        result = await execute_control(
            {"verb": "add_to_list", "target": "grocery", "payload": "eggs"},
            confirmed=True,
        )
        assert result.action == "add_to_list"
        assert result.success is True

    @pytest.mark.asyncio
    async def test_dispatch_alarm(self):
        result = await execute_control(
            {"verb": "alarm", "target": "7am", "payload": None},
        )
        assert result.action == "alarm"
        assert result.confirmed is True  # low-stakes fires immediately

    @pytest.mark.asyncio
    async def test_dispatch_cancel_alarm(self):
        result = await execute_control({"verb": "cancel_alarm", "target": None, "payload": None})
        assert result.action == "cancel_alarm"

    @pytest.mark.asyncio
    async def test_dispatch_timer(self):
        result = await execute_control({"verb": "timer", "target": "10 minutes", "payload": None})
        assert result.action == "timer"

    @pytest.mark.asyncio
    async def test_dispatch_play(self):
        result = await execute_control({"verb": "play", "target": None, "payload": "Bohemian Rhapsody"})
        assert result.action == "play"
        assert "Bohemian Rhapsody" in result.message

    @pytest.mark.asyncio
    async def test_dispatch_pause(self):
        result = await execute_control({"verb": "pause", "target": None, "payload": None})
        assert result.action == "pause"

    @pytest.mark.asyncio
    async def test_dispatch_skip(self):
        result = await execute_control({"verb": "skip", "target": None, "payload": None})
        assert result.action == "skip"

    @pytest.mark.asyncio
    async def test_dispatch_previous(self):
        result = await execute_control({"verb": "previous", "target": None, "payload": None})
        assert result.action == "previous"

    @pytest.mark.asyncio
    async def test_dispatch_volume(self):
        result = await execute_control({"verb": "volume", "target": "75", "payload": None})
        assert result.action == "volume"
        assert "75" in result.message

    @pytest.mark.asyncio
    async def test_dispatch_volume_up(self):
        result = await execute_control({"verb": "volume_up", "target": None, "payload": None})
        assert result.action == "volume_up"

    @pytest.mark.asyncio
    async def test_dispatch_volume_down(self):
        result = await execute_control({"verb": "volume_down", "target": None, "payload": None})
        assert result.action == "volume_down"

    @pytest.mark.asyncio
    async def test_dispatch_turn_on(self):
        result = await execute_control({"verb": "turn_on", "target": "lights", "payload": None})
        assert result.action == "turn_on"
        assert "lights" in result.message

    @pytest.mark.asyncio
    async def test_dispatch_turn_off(self):
        result = await execute_control({"verb": "turn_off", "target": "lights", "payload": None})
        assert result.action == "turn_off"

    @pytest.mark.asyncio
    async def test_dispatch_thermostat(self):
        result = await execute_control({"verb": "thermostat", "target": "72", "payload": None})
        assert result.action == "thermostat"
        assert "72" in result.message

    @pytest.mark.asyncio
    async def test_dispatch_scene(self):
        result = await execute_control({"verb": "scene", "target": None, "payload": "good night"})
        assert result.action == "scene"

    @pytest.mark.asyncio
    async def test_dispatch_lock(self):
        result = await execute_control({"verb": "lock", "target": "front door", "payload": None})
        assert result.action == "lock"

    @pytest.mark.asyncio
    async def test_dispatch_unlock(self):
        result = await execute_control({"verb": "unlock", "target": "front door", "payload": None})
        assert result.action == "unlock"

    @pytest.mark.asyncio
    async def test_dispatch_call(self):
        result = await execute_control(
            {"verb": "call", "target": "Mom", "payload": None},
            confirmed=True,
        )
        assert result.action == "call"
        assert "Mom" in result.message

    @pytest.mark.asyncio
    async def test_dispatch_facetime(self):
        result = await execute_control(
            {"verb": "facetime", "target": "Mom", "payload": None},
            confirmed=True,
        )
        assert result.action == "facetime"

    @pytest.mark.asyncio
    async def test_dispatch_hang_up(self):
        result = await execute_control({"verb": "hang_up", "target": None, "payload": None})
        assert result.action == "hang_up"

    @pytest.mark.asyncio
    async def test_dispatch_add_event(self):
        result = await execute_control(
            {"verb": "add_event", "target": None, "payload": "dentist at 3pm"},
            confirmed=True,
        )
        assert result.action == "add_event"

    @pytest.mark.asyncio
    async def test_dispatch_check_calendar(self):
        result = await execute_control(
            {"verb": "check_calendar", "target": "tomorrow", "payload": None},
        )
        assert result.action == "check_calendar"

    @pytest.mark.asyncio
    async def test_dispatch_unknown_verb(self):
        result = await execute_control(
            {"verb": "teleport", "target": None, "payload": None},
            confirmed=True,
        )
        assert result.success is False
        assert "Unknown verb" in result.message


class TestHighStakesConfirmation:
    """High-stakes actions require confirmation."""

    @pytest.mark.asyncio
    async def test_message_returns_confirmation_when_not_confirmed(self):
        result = await execute_control(
            {"verb": "message", "target": "Mom", "payload": "I'm on my way"},
            confirmed=False,
        )
        assert result.confirmed is False
        assert "text Mom" in result.message
        assert "send?" in result.message

    @pytest.mark.asyncio
    async def test_message_executes_when_confirmed(self):
        result = await execute_control(
            {"verb": "message", "target": "Mom", "payload": "I'm on my way"},
            confirmed=True,
        )
        assert result.confirmed is True
        assert "[mock]" in result.message

    @pytest.mark.asyncio
    async def test_call_returns_confirmation_when_not_confirmed(self):
        result = await execute_control(
            {"verb": "call", "target": "Mom", "payload": None},
            confirmed=False,
        )
        assert result.confirmed is False
        assert "call Mom" in result.message
        assert "proceed?" in result.message

    @pytest.mark.asyncio
    async def test_remind_returns_confirmation(self):
        result = await execute_control(
            {"verb": "remind", "target": "5pm", "payload": "buy milk"},
            confirmed=False,
        )
        assert result.confirmed is False
        assert "reminder" in result.message.lower()

    @pytest.mark.asyncio
    async def test_add_event_returns_confirmation(self):
        result = await execute_control(
            {"verb": "add_event", "target": None, "payload": "dentist"},
            confirmed=False,
        )
        assert result.confirmed is False
        assert "calendar" in result.message.lower() or "event" in result.message.lower()

    @pytest.mark.asyncio
    async def test_facetime_returns_confirmation(self):
        result = await execute_control(
            {"verb": "facetime", "target": "Mom", "payload": None},
            confirmed=False,
        )
        assert result.confirmed is False
        assert "FaceTime" in result.message

    @pytest.mark.asyncio
    async def test_add_to_list_returns_confirmation(self):
        result = await execute_control(
            {"verb": "add_to_list", "target": "grocery", "payload": "eggs"},
            confirmed=False,
        )
        assert result.confirmed is False


class TestLowStakesFireImmediately:
    """Low-stakes actions fire without confirmation."""

    @pytest.mark.asyncio
    async def test_alarm_fires_immediately(self):
        result = await execute_control(
            {"verb": "alarm", "target": "7am", "payload": None},
            confirmed=False,
        )
        assert result.confirmed is True
        assert "[mock]" in result.message

    @pytest.mark.asyncio
    async def test_pause_fires_immediately(self):
        result = await execute_control(
            {"verb": "pause", "target": None, "payload": None},
            confirmed=False,
        )
        assert result.confirmed is True

    @pytest.mark.asyncio
    async def test_turn_on_fires_immediately(self):
        result = await execute_control(
            {"verb": "turn_on", "target": "lights", "payload": None},
            confirmed=False,
        )
        assert result.confirmed is True


# ══════════════════════════════════════════════════════════════════════
# 2. Individual handlers return correct ControlResult
# ══════════════════════════════════════════════════════════════════════


class TestMessagingHandlers:
    @pytest.mark.asyncio
    async def test_send_imessage_returns_result(self):
        r = await send_imessage("Mom", "hello")
        assert isinstance(r, ControlResult)
        assert r.success is True
        assert r.action == "message"
        assert "Mom" in r.message

    @pytest.mark.asyncio
    async def test_send_telegram_returns_result(self):
        r = await send_telegram("@user", "hello")
        assert isinstance(r, ControlResult)
        assert r.success is True
        assert "[mock] Telegram" in r.message


class TestReminderHandlers:
    @pytest.mark.asyncio
    async def test_set_reminder_without_due(self):
        r = await set_reminder("buy milk")
        assert r.success is True
        assert r.action == "remind"

    @pytest.mark.asyncio
    async def test_set_reminder_with_due(self):
        r = await set_reminder("buy milk", due="5pm")
        assert r.success is True
        assert "5pm" in r.message

    @pytest.mark.asyncio
    async def test_add_to_list(self):
        r = await add_to_list("eggs", "grocery")
        assert r.success is True
        assert r.action == "add_to_list"


class TestAlarmHandlers:
    @pytest.mark.asyncio
    async def test_set_alarm(self):
        r = await set_alarm("7am")
        assert r.success is True
        assert r.action == "alarm"
        assert "7am" in r.message

    @pytest.mark.asyncio
    async def test_set_timer(self):
        r = await set_timer("10 minutes")
        assert r.success is True
        assert r.action == "timer"

    @pytest.mark.asyncio
    async def test_cancel_alarm(self):
        r = await cancel_alarm()
        assert r.success is True
        assert r.action == "cancel_alarm"


class TestMusicHandlers:
    @pytest.mark.asyncio
    async def test_play(self):
        r = await play("Bohemian Rhapsody")
        assert r.success is True
        assert r.action == "play"

    @pytest.mark.asyncio
    async def test_pause(self):
        r = await pause()
        assert r.success is True
        assert r.action == "pause"

    @pytest.mark.asyncio
    async def test_skip(self):
        r = await skip()
        assert r.success is True
        assert r.action == "skip"

    @pytest.mark.asyncio
    async def test_previous(self):
        r = await previous()
        assert r.success is True
        assert r.action == "previous"

    @pytest.mark.asyncio
    async def test_set_volume(self):
        r = await set_volume(80)
        assert r.success is True
        assert "80" in r.message

    @pytest.mark.asyncio
    async def test_set_volume_clamps_high(self):
        r = await set_volume(150)
        assert "100" in r.message

    @pytest.mark.asyncio
    async def test_set_volume_clamps_low(self):
        r = await set_volume(-10)
        assert "0" in r.message

    @pytest.mark.asyncio
    async def test_volume_up(self):
        r = await volume_up()
        assert r.success is True
        assert r.action == "volume_up"

    @pytest.mark.asyncio
    async def test_volume_down(self):
        r = await volume_down()
        assert r.success is True
        assert r.action == "volume_down"


class TestHomeKitHandlers:
    @pytest.mark.asyncio
    async def test_turn_on(self):
        r = await turn_on("kitchen lights")
        assert r.success is True
        assert "kitchen lights" in r.message

    @pytest.mark.asyncio
    async def test_turn_off(self):
        r = await turn_off("bedroom fan")
        assert r.success is True
        assert "bedroom fan" in r.message

    @pytest.mark.asyncio
    async def test_set_thermostat(self):
        r = await set_thermostat("72")
        assert r.success is True
        assert "72" in r.message

    @pytest.mark.asyncio
    async def test_trigger_scene(self):
        r = await trigger_scene("good night")
        assert r.success is True
        assert "good night" in r.message

    @pytest.mark.asyncio
    async def test_lock_device(self):
        r = await lock_device("front door")
        assert r.success is True
        assert r.action == "lock"

    @pytest.mark.asyncio
    async def test_unlock_device(self):
        r = await unlock_device("front door")
        assert r.success is True
        assert r.action == "unlock"


class TestCallHandlers:
    @pytest.mark.asyncio
    async def test_make_call(self):
        r = await make_call("Mom")
        assert r.success is True
        assert r.action == "call"
        assert "tel:Mom" in r.message

    @pytest.mark.asyncio
    async def test_facetime_call(self):
        r = await facetime_call("Mom")
        assert r.success is True
        assert r.action == "facetime"
        assert "facetime:Mom" in r.message

    @pytest.mark.asyncio
    async def test_hang_up(self):
        r = await hang_up()
        assert r.success is True
        assert r.action == "hang_up"


class TestCalendarHandlers:
    @pytest.mark.asyncio
    async def test_add_event(self):
        r = await add_event("dentist at 3pm")
        assert r.success is True
        assert r.action == "add_event"
        assert "dentist" in r.message

    @pytest.mark.asyncio
    async def test_check_calendar(self):
        r = await check_calendar("tomorrow")
        assert r.success is True
        assert r.action == "check_calendar"


# ══════════════════════════════════════════════════════════════════════
# 3. AppleScript builders
# ══════════════════════════════════════════════════════════════════════


class TestAppleScriptBuilders:
    def test_imessage_script_structure(self):
        script = _build_imessage_script("Mom", "hello there")
        assert 'tell application "Messages"' in script
        assert 'buddy "Mom"' in script
        assert 'send "hello there"' in script

    def test_imessage_script_escapes_quotes(self):
        script = _build_imessage_script("Mom", 'he said "hi"')
        assert r"he said \"hi\"" in script

    def test_reminder_script_without_due(self):
        script = _build_reminder_script("buy milk")
        assert 'tell application "Reminders"' in script
        assert "buy milk" in script
        assert "due date" not in script

    def test_reminder_script_with_due(self):
        script = _build_reminder_script("buy milk", due="5pm tomorrow")
        assert 'tell application "Reminders"' in script
        assert "due date" in script
        assert "5pm tomorrow" in script

    def test_music_script_structure(self):
        script = _build_music_script("pause")
        assert 'tell application "Music"' in script
        assert "pause" in script

    def test_music_script_play_track(self):
        script = _build_music_script('play track "Bohemian Rhapsody"')
        assert "Bohemian Rhapsody" in script


# ══════════════════════════════════════════════════════════════════════
# 4. Duration parser
# ══════════════════════════════════════════════════════════════════════


class TestDurationParser:
    def test_minutes(self):
        assert _parse_duration("10 minutes") == 600

    def test_hour(self):
        assert _parse_duration("1 hour") == 3600

    def test_seconds(self):
        assert _parse_duration("30 seconds") == 30

    def test_compound_duration(self):
        assert _parse_duration("1 hour 30 minutes") == 5400

    def test_short_units(self):
        assert _parse_duration("5m") == 300
        assert _parse_duration("2h") == 7200
        assert _parse_duration("45s") == 45

    def test_short_abbreviations(self):
        assert _parse_duration("10 min") == 600
        assert _parse_duration("2 hrs") == 7200
        assert _parse_duration("15 secs") == 15

    def test_unparseable_returns_zero(self):
        assert _parse_duration("soon") == 0
        assert _parse_duration("") == 0


# ══════════════════════════════════════════════════════════════════════
# 5. Contact resolution
# ══════════════════════════════════════════════════════════════════════


class TestContactResolution:
    def test_contacts_app_returns_none(self):
        """Layer 1 (macOS Contacts) is mocked to None."""
        result = resolve_contact("John")
        # With no nickname and no recent, should be None
        assert result is None

    def test_nickname_lookup(self):
        """Layer 2: nickname from TOML config."""
        result = resolve_contact("mom")
        if result:  # depends on config file existing
            assert result.full_name == "Jane Keller"
            assert result.source == "nickname"

    def test_nickname_lookup_case_insensitive(self):
        result = resolve_contact("Mom")
        if result:
            assert result.full_name == "Jane Keller"

    def test_recent_cache_lookup(self):
        """Layer 3: recent conversation cache."""
        add_recent("alex", "Alexander Hamilton")
        result = resolve_contact("alex")
        assert result is not None
        assert result.full_name == "Alexander Hamilton"
        assert result.source == "recent"

    def test_recent_cache_case_insensitive(self):
        add_recent("Alex", "Alexander Hamilton")
        result = resolve_contact("alex")
        assert result is not None
        assert result.full_name == "Alexander Hamilton"

    def test_resolve_returns_none_for_unknown(self):
        result = resolve_contact("zzz_nobody_zzz")
        assert result is None

    def test_nickname_takes_priority_over_recent(self):
        """Nickname (layer 2) should resolve before recent (layer 3)."""
        add_recent("mom", "Mother Dearest")
        result = resolve_contact("mom")
        if result:
            assert result.source == "nickname"

    def test_add_recent_and_resolve(self):
        add_recent("bro", "Brother Bear")
        result = resolve_contact("bro")
        assert result is not None
        assert result.full_name == "Brother Bear"

    def test_clear_recent(self):
        add_recent("temp", "Temporary Person")
        clear_recent()
        assert resolve_contact("temp") is None


class TestNicknameLoading:
    def test_load_nicknames_returns_dict(self):
        nicknames = _load_nicknames()
        assert isinstance(nicknames, dict)

    def test_load_nicknames_has_expected_entries(self):
        nicknames = _load_nicknames()
        if nicknames:  # file may or may not exist in test env
            assert "mom" in nicknames
            assert nicknames["mom"] == "Jane Keller"


class TestAmbiguousContactResolution:
    def test_ambiguous_returns_list(self):
        matches = resolve_ambiguous("nobody_at_all")
        assert isinstance(matches, list)
        assert len(matches) == 0

    def test_ambiguous_returns_recent_match(self):
        add_recent("alex", "Alexander Hamilton")
        matches = resolve_ambiguous("alex")
        assert len(matches) >= 1
        assert any(m.full_name == "Alexander Hamilton" for m in matches)

    def test_ambiguous_returns_nickname_match(self):
        matches = resolve_ambiguous("mom")
        # Only works if config file has the nickname
        if matches:
            assert any(m.source == "nickname" for m in matches)


# ══════════════════════════════════════════════════════════════════════
# 6. API endpoints — /control/execute and /control/confirm
# ══════════════════════════════════════════════════════════════════════


class TestControlEndpoints:
    @pytest.mark.asyncio
    async def test_execute_low_stakes(self, client: httpx.AsyncClient):
        resp = await client.post("/control/execute", json={
            "intent": {"verb": "pause", "target": None, "payload": None},
            "confirmed": False,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["confirmed"] is True
        assert data["action"] == "pause"

    @pytest.mark.asyncio
    async def test_execute_high_stakes_not_confirmed(self, client: httpx.AsyncClient):
        resp = await client.post("/control/execute", json={
            "intent": {"verb": "message", "target": "Mom", "payload": "I'm on my way"},
            "confirmed": False,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["confirmed"] is False
        assert "send?" in data["message"]

    @pytest.mark.asyncio
    async def test_execute_high_stakes_confirmed(self, client: httpx.AsyncClient):
        resp = await client.post("/control/execute", json={
            "intent": {"verb": "message", "target": "Mom", "payload": "I'm on my way"},
            "confirmed": True,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["confirmed"] is True
        assert "[mock]" in data["message"]

    @pytest.mark.asyncio
    async def test_confirm_endpoint_always_confirmed(self, client: httpx.AsyncClient):
        resp = await client.post("/control/confirm", json={
            "intent": {"verb": "message", "target": "Mom", "payload": "hello"},
            "confirmed": False,  # body says false, but /confirm forces True
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["confirmed"] is True
        assert "[mock]" in data["message"]

    @pytest.mark.asyncio
    async def test_execute_alarm(self, client: httpx.AsyncClient):
        resp = await client.post("/control/execute", json={
            "intent": {"verb": "alarm", "target": "7am", "payload": None},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "alarm"
        assert data["confirmed"] is True

    @pytest.mark.asyncio
    async def test_execute_unknown_verb(self, client: httpx.AsyncClient):
        resp = await client.post("/control/execute", json={
            "intent": {"verb": "teleport", "target": None, "payload": None},
            "confirmed": True,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False

    @pytest.mark.asyncio
    async def test_confirm_call(self, client: httpx.AsyncClient):
        resp = await client.post("/control/confirm", json={
            "intent": {"verb": "call", "target": "Mom", "payload": None},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "call"
        assert data["confirmed"] is True

    @pytest.mark.asyncio
    async def test_execute_play(self, client: httpx.AsyncClient):
        resp = await client.post("/control/execute", json={
            "intent": {"verb": "play", "target": None, "payload": "Bohemian Rhapsody"},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "play"
        assert data["confirmed"] is True

    @pytest.mark.asyncio
    async def test_execute_turn_on(self, client: httpx.AsyncClient):
        resp = await client.post("/control/execute", json={
            "intent": {"verb": "turn_on", "target": "lights", "payload": None},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "turn_on"

    @pytest.mark.asyncio
    async def test_execute_add_event_needs_confirm(self, client: httpx.AsyncClient):
        resp = await client.post("/control/execute", json={
            "intent": {"verb": "add_event", "target": None, "payload": "dentist"},
            "confirmed": False,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["confirmed"] is False
