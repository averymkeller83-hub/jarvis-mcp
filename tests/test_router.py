"""Tests for the smart router — classification, intent extraction, and fallback."""

import pytest

from src.brain.router import Surface, classify, control_intent, local_intent


# ──────────────────────────────────────────────────────────────────────────────
# CONTROL classification — each action family
# ──────────────────────────────────────────────────────────────────────────────

class TestControlClassification:
    """CONTROL surface should catch Siri-style imperative commands."""

    @pytest.mark.parametrize("msg", [
        "text Mom I'll be late",
        "message John hey are you free",
        "send a text to Sarah saying happy birthday",
        "tell Dad that dinner is ready",
        "sms Alex pick up milk",
    ])
    def test_messaging(self, msg: str) -> None:
        assert classify(msg) == Surface.CONTROL

    @pytest.mark.parametrize("msg", [
        "remind me to call the dentist at 3pm",
        "remind me to take out the trash",
        "set a reminder to buy groceries",
        "add eggs to my shopping list",
        "add milk to grocery list",
    ])
    def test_reminders(self, msg: str) -> None:
        assert classify(msg) == Surface.CONTROL

    @pytest.mark.parametrize("msg", [
        "set alarm for 7am",
        "set an alarm for 6:30",
        "set a timer for 10 minutes",
        "wake me up at 5am",
        "snooze",
        "stop the alarm",
        "cancel the timer",
    ])
    def test_alarms_timers(self, msg: str) -> None:
        assert classify(msg) == Surface.CONTROL

    @pytest.mark.parametrize("msg", [
        "play Bohemian Rhapsody",
        "pause",
        "skip",
        "next track",
        "volume 50",
        "set volume to 80",
        "turn up the volume",
        "shuffle",
    ])
    def test_music(self, msg: str) -> None:
        assert classify(msg) == Surface.CONTROL

    @pytest.mark.parametrize("msg", [
        "turn on the living room lights",
        "turn off the fan",
        "set thermostat to 72",
        "good night",
        "good morning",
        "lock the front door",
        "unlock the garage",
        "dim the bedroom lights",
    ])
    def test_homekit(self, msg: str) -> None:
        assert classify(msg) == Surface.CONTROL

    @pytest.mark.parametrize("msg", [
        "call Mom",
        "facetime John",
        "dial 911",
        "hang up",
    ])
    def test_calls(self, msg: str) -> None:
        assert classify(msg) == Surface.CONTROL

    @pytest.mark.parametrize("msg", [
        "add event lunch with Sarah at noon",
        "schedule a meeting for tomorrow at 2",
        "what's on my calendar for today",
    ])
    def test_calendar(self, msg: str) -> None:
        assert classify(msg) == Surface.CONTROL


# ──────────────────────────────────────────────────────────────────────────────
# CONTROL intent extraction
# ──────────────────────────────────────────────────────────────────────────────

class TestControlIntent:
    """control_intent should parse structured verb/target/payload."""

    def test_text_message(self) -> None:
        result = control_intent("text Mom I'll be late")
        assert result is not None
        assert result["verb"] == "message"
        assert result["target"] == "Mom"
        assert result["payload"] is not None
        assert "late" in result["payload"]

    def test_send_message_to(self) -> None:
        result = control_intent("send a text to Sarah saying happy birthday")
        assert result is not None
        assert result["verb"] == "message"
        assert result["target"] == "Sarah"
        assert "happy birthday" in result["payload"]

    def test_tell_someone(self) -> None:
        result = control_intent("tell Dad that dinner is ready")
        assert result is not None
        assert result["verb"] == "message"
        assert result["target"] == "Dad"
        assert "dinner" in result["payload"]

    def test_remind_with_time(self) -> None:
        result = control_intent("remind me to call the dentist at 3pm")
        assert result is not None
        assert result["verb"] == "remind"
        assert result["payload"] is not None
        assert "dentist" in result["payload"]

    def test_set_alarm(self) -> None:
        result = control_intent("set alarm for 7am")
        assert result is not None
        assert result["verb"] == "alarm"
        assert result["target"] == "7am"

    def test_set_timer(self) -> None:
        result = control_intent("set a timer for 10 minutes")
        assert result is not None
        assert result["verb"] == "timer"
        assert result["target"] == "10 minutes"

    def test_play_music(self) -> None:
        result = control_intent("play Bohemian Rhapsody")
        assert result is not None
        assert result["verb"] == "play"
        assert result["payload"] == "Bohemian Rhapsody"

    def test_volume(self) -> None:
        result = control_intent("volume 50")
        assert result is not None
        assert result["verb"] == "volume"
        assert result["target"] == "50"

    def test_turn_on_device(self) -> None:
        result = control_intent("turn on the living room lights")
        assert result is not None
        assert result["verb"] == "turn_on"
        assert "living room" in result["target"]

    def test_turn_off_device(self) -> None:
        result = control_intent("turn off the fan")
        assert result is not None
        assert result["verb"] == "turn_off"
        assert result["target"] == "fan"

    def test_thermostat(self) -> None:
        result = control_intent("set thermostat to 72")
        assert result is not None
        assert result["verb"] == "thermostat"
        assert "72" in result["target"]

    def test_good_night_scene(self) -> None:
        result = control_intent("good night")
        assert result is not None
        assert result["verb"] == "scene"
        assert result["payload"] is not None
        assert "good night" in result["payload"].lower()

    def test_call(self) -> None:
        result = control_intent("call Mom")
        assert result is not None
        assert result["verb"] == "call"
        assert result["target"] == "Mom"

    def test_facetime(self) -> None:
        result = control_intent("facetime John")
        assert result is not None
        assert result["verb"] == "facetime"
        assert result["target"] == "John"

    def test_add_event(self) -> None:
        result = control_intent("add event lunch with Sarah at noon")
        assert result is not None
        assert result["verb"] == "add_event"
        assert "lunch" in result["payload"]

    def test_add_to_list(self) -> None:
        result = control_intent("add eggs to my shopping list")
        assert result is not None
        assert result["verb"] == "add_to_list"
        assert result["payload"] == "eggs"
        assert "shopping" in result["target"]

    def test_none_on_garbage(self) -> None:
        assert control_intent("asdfghjkl") is None

    def test_none_on_empty(self) -> None:
        assert control_intent("") is None
        assert control_intent("   ") is None


# ──────────────────────────────────────────────────────────────────────────────
# LOCAL classification + intent mapping
# ──────────────────────────────────────────────────────────────────────────────

class TestLocalClassification:

    @pytest.mark.parametrize("msg,expected_handler", [
        ("morning briefing", "briefing"),
        ("what's on my plate", "briefing"),
        ("my tasks", "tasks"),
        ("show my queue", "tasks"),
        ("my schedule", "schedule"),
        ("check my calendar", "schedule"),
        ("any unread messages", "unread"),
        ("what's the weather", "weather"),
        ("show me the headlines", "headlines"),
        ("system status", "status"),
        ("show patterns", "patterns"),
        ("recent lessons", "lessons"),
    ])
    def test_local_routes(self, msg: str, expected_handler: str) -> None:
        assert classify(msg) == Surface.LOCAL
        assert local_intent(msg) == expected_handler

    def test_good_morning_jarvis_local_intent(self) -> None:
        """'good morning Jarvis' routes to CONTROL (HomeKit scene) but
        local_intent still maps it to briefing for downstream use."""
        assert local_intent("good morning Jarvis") == "briefing"

    def test_local_intent_none_for_unrecognized(self) -> None:
        assert local_intent("something random") is None

    def test_local_intent_none_for_empty(self) -> None:
        assert local_intent("") is None


# ──────────────────────────────────────────────────────────────────────────────
# CODE classification
# ──────────────────────────────────────────────────────────────────────────────

class TestCodeClassification:

    @pytest.mark.parametrize("msg", [
        "write a function to parse CSV files",
        "fix the bug in the login handler",
        "debug this crash",
        "refactor the database module",
        "create a PR for the auth changes",
        "git rebase main",
        "run the tests",
        "npm install lodash",
        "pip install requests",
        "deploy the staging build",
        "lint the project",
    ])
    def test_code_messages(self, msg: str) -> None:
        assert classify(msg) == Surface.CODE


# ──────────────────────────────────────────────────────────────────────────────
# DESKTOP classification
# ──────────────────────────────────────────────────────────────────────────────

class TestDesktopClassification:

    @pytest.mark.parametrize("msg", [
        "click on the submit button",
        "take a screenshot",
        "open Safari",
        "close the terminal app",
        "navigate to settings",
        "automate the report export",
        "drag and drop the file",
        "scroll down",
        "move the cursor to the top",
    ])
    def test_desktop_messages(self, msg: str) -> None:
        assert classify(msg) == Surface.DESKTOP


# ──────────────────────────────────────────────────────────────────────────────
# REASON classification
# ──────────────────────────────────────────────────────────────────────────────

class TestReasonClassification:

    @pytest.mark.parametrize("msg", [
        "analyze the Q4 revenue data",
        "research the latest trends in AI",
        "explain in depth how TCP works",
        "write an essay about climate change",
        "compare React and Vue",
        "pros and cons of microservices",
        "deep dive into Kubernetes networking",
        "evaluate these two options",
        "break down the architecture",
        "step by step how does OAuth work",
    ])
    def test_reason_messages(self, msg: str) -> None:
        assert classify(msg) == Surface.REASON


# ──────────────────────────────────────────────────────────────────────────────
# CHAT fallback
# ──────────────────────────────────────────────────────────────────────────────

class TestChatFallback:

    @pytest.mark.parametrize("msg", [
        "hello",
        "how are you doing today",
        "what do you think about that",
        "thanks!",
        "tell me a joke",
        "who are you",
        "interesting",
    ])
    def test_casual_messages_fall_to_chat(self, msg: str) -> None:
        assert classify(msg) == Surface.CHAT


# ──────────────────────────────────────────────────────────────────────────────
# Edge cases
# ──────────────────────────────────────────────────────────────────────────────

class TestEdgeCases:

    def test_empty_string(self) -> None:
        assert classify("") == Surface.CHAT

    def test_whitespace_only(self) -> None:
        assert classify("   ") == Surface.CHAT
        assert classify("\n\t") == Surface.CHAT

    def test_control_priority_over_chat(self) -> None:
        """'text Mom' must route to CONTROL, not CHAT."""
        assert classify("text Mom") == Surface.CONTROL

    def test_control_priority_over_code(self) -> None:
        """'play something' must not route to CODE even though 'play' is a word."""
        assert classify("play my playlist") == Surface.CONTROL

    def test_good_morning_is_control_not_local(self) -> None:
        """'good morning' is a HomeKit scene trigger (CONTROL) before LOCAL."""
        assert classify("good morning") == Surface.CONTROL

    def test_good_morning_jarvis_is_local(self) -> None:
        """'good morning Jarvis' is a briefing trigger (LOCAL) — but CONTROL
        matches first because 'good morning' hits HomeKit. This is by design;
        the CONTROL handler can choose to also trigger the briefing."""
        # CONTROL matches first due to priority order — this is correct behavior
        assert classify("good morning Jarvis") == Surface.CONTROL

    def test_case_insensitive(self) -> None:
        assert classify("TEXT MOM") == Surface.CONTROL
        assert classify("Play Bohemian Rhapsody") == Surface.CONTROL
        assert classify("My Tasks") == Surface.LOCAL

    def test_surface_enum_values(self) -> None:
        assert Surface.CHAT.value == "chat"
        assert Surface.CONTROL.value == "control"
        assert Surface.LOCAL.value == "local"
        assert Surface.CODE.value == "code"
        assert Surface.DESKTOP.value == "desktop"
        assert Surface.REASON.value == "reason"

    def test_surface_is_str_enum(self) -> None:
        assert isinstance(Surface.CHAT, str)
        assert Surface.CHAT == "chat"
