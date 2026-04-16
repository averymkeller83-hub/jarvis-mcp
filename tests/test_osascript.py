"""Tests for the osascript execution layer and live-mode wiring in handlers.

Most tests mock ``asyncio.create_subprocess_exec`` so they run anywhere.
One test (``test_run_osascript_real_hello``) executes a harmless script for real.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.hands.osascript import (
    OSAResult,
    check_app_running,
    launch_app,
    open_url,
    run_osascript,
    run_shortcut,
)
from src.hands import ControlResult


# ══════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════

def _mock_process(stdout: bytes = b"", stderr: bytes = b"", returncode: int = 0):
    """Return a mock process whose communicate() resolves immediately."""
    proc = AsyncMock()
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    proc.returncode = returncode
    proc.kill = MagicMock()
    proc.wait = AsyncMock()
    return proc


# ══════════════════════════════════════════════════════════════════════
# 1. OSAResult dataclass
# ══════════════════════════════════════════════════════════════════════


class TestOSAResult:
    def test_fields_exist(self):
        r = OSAResult(success=True, stdout="ok", stderr="", return_code=0, script="return 1")
        assert r.success is True
        assert r.stdout == "ok"
        assert r.stderr == ""
        assert r.return_code == 0
        assert r.script == "return 1"

    def test_failure_result(self):
        r = OSAResult(success=False, stdout="", stderr="err", return_code=1, script="bad")
        assert r.success is False
        assert r.return_code == 1


# ══════════════════════════════════════════════════════════════════════
# 2. run_osascript
# ══════════════════════════════════════════════════════════════════════


class TestRunOsascript:
    @pytest.mark.asyncio
    async def test_run_osascript_real_hello(self):
        """Harmless real execution: ``return "hello"``."""
        result = await run_osascript('return "hello"')
        assert result.success is True
        assert result.stdout == "hello"
        assert result.return_code == 0

    @pytest.mark.asyncio
    async def test_run_osascript_success_mocked(self):
        proc = _mock_process(stdout=b"42\n", returncode=0)
        with patch("src.hands.osascript.asyncio.create_subprocess_exec", return_value=proc):
            r = await run_osascript("return 42")
        assert r.success is True
        assert r.stdout == "42"
        assert r.return_code == 0
        assert r.script == "return 42"

    @pytest.mark.asyncio
    async def test_run_osascript_captures_stderr(self):
        proc = _mock_process(stderr=b"execution error: blah\n", returncode=1)
        with patch("src.hands.osascript.asyncio.create_subprocess_exec", return_value=proc):
            r = await run_osascript("bad script")
        assert r.success is False
        assert "execution error" in r.stderr
        assert r.return_code == 1

    @pytest.mark.asyncio
    async def test_run_osascript_timeout(self):
        proc = AsyncMock()
        proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError)
        proc.kill = MagicMock()
        proc.wait = AsyncMock()
        with patch("src.hands.osascript.asyncio.create_subprocess_exec", return_value=proc):
            r = await run_osascript("delay 999", timeout=0.01)
        assert r.success is False
        assert "Timed out" in r.stderr
        assert r.return_code == -1

    @pytest.mark.asyncio
    async def test_run_osascript_exception(self):
        with patch(
            "src.hands.osascript.asyncio.create_subprocess_exec",
            side_effect=FileNotFoundError("not found"),
        ):
            r = await run_osascript("whatever")
        assert r.success is False
        assert "not found" in r.stderr


# ══════════════════════════════════════════════════════════════════════
# 3. run_shortcut
# ══════════════════════════════════════════════════════════════════════


class TestRunShortcut:
    @pytest.mark.asyncio
    async def test_run_shortcut_builds_command(self):
        proc = _mock_process(stdout=b"done\n", returncode=0)
        with patch("src.hands.osascript.asyncio.create_subprocess_exec", return_value=proc) as m:
            r = await run_shortcut("Set Alarm", input_text="7:00 AM")
        assert r.success is True
        # Verify the correct binary and arguments were passed
        call_args = m.call_args[0]
        assert call_args[0] == "/usr/bin/shortcuts"
        assert call_args[1] == "run"
        assert call_args[2] == "Set Alarm"
        assert "--input-text" in call_args
        assert "7:00 AM" in call_args

    @pytest.mark.asyncio
    async def test_run_shortcut_without_input(self):
        proc = _mock_process(returncode=0)
        with patch("src.hands.osascript.asyncio.create_subprocess_exec", return_value=proc) as m:
            r = await run_shortcut("Cancel Alarm")
        assert r.success is True
        call_args = m.call_args[0]
        assert "--input-text" not in call_args

    @pytest.mark.asyncio
    async def test_run_shortcut_failure(self):
        proc = _mock_process(stderr=b"shortcut not found\n", returncode=1)
        with patch("src.hands.osascript.asyncio.create_subprocess_exec", return_value=proc):
            r = await run_shortcut("Nonexistent")
        assert r.success is False
        assert "shortcut not found" in r.stderr


# ══════════════════════════════════════════════════════════════════════
# 4. open_url
# ══════════════════════════════════════════════════════════════════════


class TestOpenUrl:
    @pytest.mark.asyncio
    async def test_open_url_builds_command(self):
        proc = _mock_process(returncode=0)
        with patch("src.hands.osascript.asyncio.create_subprocess_exec", return_value=proc) as m:
            r = await open_url("tel:+15551234567")
        assert r.success is True
        call_args = m.call_args[0]
        assert call_args[0] == "/usr/bin/open"
        assert call_args[1] == "tel:+15551234567"

    @pytest.mark.asyncio
    async def test_open_url_facetime(self):
        proc = _mock_process(returncode=0)
        with patch("src.hands.osascript.asyncio.create_subprocess_exec", return_value=proc) as m:
            r = await open_url("facetime:mom@example.com")
        assert r.success is True
        assert m.call_args[0][1] == "facetime:mom@example.com"


# ══════════════════════════════════════════════════════════════════════
# 5. check_app_running
# ══════════════════════════════════════════════════════════════════════


class TestCheckAppRunning:
    @pytest.mark.asyncio
    async def test_app_is_running(self):
        proc = _mock_process(stdout=b"true\n", returncode=0)
        with patch("src.hands.osascript.asyncio.create_subprocess_exec", return_value=proc):
            assert await check_app_running("Music") is True

    @pytest.mark.asyncio
    async def test_app_not_running(self):
        proc = _mock_process(stdout=b"false\n", returncode=0)
        with patch("src.hands.osascript.asyncio.create_subprocess_exec", return_value=proc):
            assert await check_app_running("Music") is False

    @pytest.mark.asyncio
    async def test_app_check_error(self):
        proc = _mock_process(stderr=b"error\n", returncode=1)
        with patch("src.hands.osascript.asyncio.create_subprocess_exec", return_value=proc):
            assert await check_app_running("Music") is False


# ══════════════════════════════════════════════════════════════════════
# 6. launch_app
# ══════════════════════════════════════════════════════════════════════


class TestLaunchApp:
    @pytest.mark.asyncio
    async def test_launch_app_success(self):
        proc = _mock_process(returncode=0)
        with patch("src.hands.osascript.asyncio.create_subprocess_exec", return_value=proc):
            r = await launch_app("Music")
        assert r.success is True

    @pytest.mark.asyncio
    async def test_launch_app_failure(self):
        proc = _mock_process(stderr=b"failed\n", returncode=1)
        with patch("src.hands.osascript.asyncio.create_subprocess_exec", return_value=proc):
            r = await launch_app("FakeApp")
        assert r.success is False


# ══════════════════════════════════════════════════════════════════════
# 7. Handler mock-mode preservation (all _LIVE_MODE=False by default)
# ══════════════════════════════════════════════════════════════════════


class TestHandlersMockMode:
    """Ensure every handler returns [mock] results when _LIVE_MODE is False."""

    @pytest.mark.asyncio
    async def test_messaging_mock(self):
        from src.hands.messaging import send_imessage
        r = await send_imessage("Mom", "hello")
        assert r.success is True
        assert "[mock]" in r.message

    @pytest.mark.asyncio
    async def test_music_play_mock(self):
        from src.hands.music import play
        r = await play("Bohemian Rhapsody")
        assert r.success is True
        assert "[mock]" in r.message

    @pytest.mark.asyncio
    async def test_music_pause_mock(self):
        from src.hands.music import pause
        r = await pause()
        assert "[mock]" in r.message

    @pytest.mark.asyncio
    async def test_reminders_mock(self):
        from src.hands.reminders import set_reminder
        r = await set_reminder("buy milk", due="5pm")
        assert "[mock]" in r.message

    @pytest.mark.asyncio
    async def test_add_to_list_mock(self):
        from src.hands.reminders import add_to_list
        r = await add_to_list("eggs", "grocery")
        assert "[mock]" in r.message

    @pytest.mark.asyncio
    async def test_alarm_mock(self):
        from src.hands.alarms import set_alarm
        r = await set_alarm("7am")
        assert "[mock]" in r.message

    @pytest.mark.asyncio
    async def test_timer_mock(self):
        from src.hands.alarms import set_timer
        r = await set_timer("5 minutes")
        assert "[mock]" in r.message

    @pytest.mark.asyncio
    async def test_calls_mock(self):
        from src.hands.calls import make_call
        r = await make_call("Mom")
        assert "[mock]" in r.message

    @pytest.mark.asyncio
    async def test_facetime_mock(self):
        from src.hands.calls import facetime_call
        r = await facetime_call("Mom")
        assert "[mock]" in r.message

    @pytest.mark.asyncio
    async def test_hang_up_mock(self):
        from src.hands.calls import hang_up
        r = await hang_up()
        assert "[mock]" in r.message

    @pytest.mark.asyncio
    async def test_homekit_turn_on_mock(self):
        from src.hands.homekit import turn_on
        r = await turn_on("lights")
        assert "[mock]" in r.message

    @pytest.mark.asyncio
    async def test_homekit_scene_mock(self):
        from src.hands.homekit import trigger_scene
        r = await trigger_scene("good night")
        assert "[mock]" in r.message

    @pytest.mark.asyncio
    async def test_calendar_add_event_mock(self):
        from src.hands.calendar import add_event
        r = await add_event("dentist at 3pm")
        assert "[mock]" in r.message

    @pytest.mark.asyncio
    async def test_calendar_check_mock(self):
        from src.hands.calendar import check_calendar
        r = await check_calendar("tomorrow")
        assert "[mock]" in r.message


# ══════════════════════════════════════════════════════════════════════
# 8. Auto-fix pattern (diagnose → fix → retry)
# ══════════════════════════════════════════════════════════════════════


class TestAutoFixPattern:
    """Test the diagnostic recovery pattern in live mode."""

    @pytest.mark.asyncio
    async def test_messaging_auto_fix_launches_app(self):
        """If Messages.app isn't running, handler launches it and retries."""
        import src.hands.messaging as mod

        original = mod._LIVE_MODE
        mod._LIVE_MODE = True
        try:
            call_count = 0

            async def mock_check(app_name):
                nonlocal call_count
                call_count += 1
                # First call: not running; second call (after launch): running
                return call_count > 1

            async def mock_launch(app_name):
                return OSAResult(True, "", "", 0, "launch")

            async def mock_run(script, timeout=10.0):
                return OSAResult(True, "", "", 0, script)

            with (
                patch("src.hands.messaging.check_app_running", side_effect=mock_check),
                patch("src.hands.messaging.launch_app", side_effect=mock_launch),
                patch("src.hands.messaging.run_osascript", side_effect=mock_run),
                patch("asyncio.sleep", new_callable=AsyncMock),
            ):
                r = await mod.send_imessage("Mom", "hello")
            assert r.success is True
            assert "Mom" in r.message
        finally:
            mod._LIVE_MODE = original

    @pytest.mark.asyncio
    async def test_music_auto_fix_launches_app(self):
        """If Music.app isn't running, handler launches it and retries."""
        import src.hands.music as mod

        original = mod._LIVE_MODE
        mod._LIVE_MODE = True
        try:
            call_count = 0

            async def mock_check(app_name):
                nonlocal call_count
                call_count += 1
                return call_count > 1

            async def mock_launch(app_name):
                return OSAResult(True, "", "", 0, "launch")

            async def mock_run(script, timeout=10.0):
                return OSAResult(True, "", "", 0, script)

            with (
                patch("src.hands.music.check_app_running", side_effect=mock_check),
                patch("src.hands.music.launch_app", side_effect=mock_launch),
                patch("src.hands.music.run_osascript", side_effect=mock_run),
                patch("asyncio.sleep", new_callable=AsyncMock),
            ):
                r = await mod.pause()
            assert r.success is True
        finally:
            mod._LIVE_MODE = original

    @pytest.mark.asyncio
    async def test_messaging_retry_after_failure(self):
        """If first osascript call fails, handler relaunches and retries."""
        import src.hands.messaging as mod

        original = mod._LIVE_MODE
        mod._LIVE_MODE = True
        try:
            async def mock_check(app_name):
                return True

            call_count = 0

            async def mock_run(script, timeout=10.0):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return OSAResult(False, "", "error", 1, script)
                return OSAResult(True, "", "", 0, script)

            async def mock_launch(app_name):
                return OSAResult(True, "", "", 0, "launch")

            with (
                patch("src.hands.messaging.check_app_running", side_effect=mock_check),
                patch("src.hands.messaging.launch_app", side_effect=mock_launch),
                patch("src.hands.messaging.run_osascript", side_effect=mock_run),
                patch("asyncio.sleep", new_callable=AsyncMock),
            ):
                r = await mod.send_imessage("Mom", "hello")
            assert r.success is True
            assert "retry" in r.message
        finally:
            mod._LIVE_MODE = original

    @pytest.mark.asyncio
    async def test_reminders_auto_fix_kill_relaunch(self):
        """If Reminders.app fails, handler kills and relaunches."""
        import src.hands.reminders as mod

        original = mod._LIVE_MODE
        mod._LIVE_MODE = True
        try:
            check_count = 0

            async def mock_check(app_name):
                nonlocal check_count
                check_count += 1
                return True  # App appears running

            osa_count = 0

            async def mock_run(script, timeout=10.0):
                nonlocal osa_count
                osa_count += 1
                if osa_count == 1:
                    # First call (the actual reminder creation) fails
                    return OSAResult(False, "", "unresponsive", 1, script)
                # Kill+relaunch script and retry both succeed
                return OSAResult(True, "", "", 0, script)

            with (
                patch("src.hands.reminders.check_app_running", side_effect=mock_check),
                patch("src.hands.reminders.run_osascript", side_effect=mock_run),
                patch("asyncio.sleep", new_callable=AsyncMock),
            ):
                r = await mod.set_reminder("buy milk")
            assert r.success is True
            assert "recovery" in r.message
        finally:
            mod._LIVE_MODE = original

    @pytest.mark.asyncio
    async def test_calls_live_mode(self):
        """Calls handler uses open_url in live mode."""
        import src.hands.calls as mod

        original = mod._LIVE_MODE
        mod._LIVE_MODE = True
        try:
            async def mock_open(url):
                return OSAResult(True, "", "", 0, f"open {url}")

            with patch("src.hands.calls.open_url", side_effect=mock_open):
                r = await mod.make_call("Mom")
            assert r.success is True
            assert "Mom" in r.message
        finally:
            mod._LIVE_MODE = original

    @pytest.mark.asyncio
    async def test_homekit_live_mode(self):
        """HomeKit handler uses run_shortcut in live mode."""
        import src.hands.homekit as mod

        original = mod._LIVE_MODE
        mod._LIVE_MODE = True
        try:
            async def mock_shortcut(name, input_text=None):
                return OSAResult(True, "", "", 0, f"shortcuts run {name}")

            with patch("src.hands.homekit.run_shortcut", side_effect=mock_shortcut):
                r = await mod.trigger_scene("good night")
            assert r.success is True
            assert "good night" in r.message
        finally:
            mod._LIVE_MODE = original

    @pytest.mark.asyncio
    async def test_calendar_live_mode(self):
        """Calendar handler uses run_osascript in live mode."""
        import src.hands.calendar as mod

        original = mod._LIVE_MODE
        mod._LIVE_MODE = True
        try:
            async def mock_run(script, timeout=10.0):
                return OSAResult(True, "meeting, dentist", "", 0, script)

            with patch("src.hands.calendar.run_osascript", side_effect=mock_run):
                r = await mod.check_calendar("today")
            assert r.success is True
            assert "meeting" in r.message
        finally:
            mod._LIVE_MODE = original

    @pytest.mark.asyncio
    async def test_alarm_live_mode(self):
        """Alarm handler uses run_shortcut in live mode."""
        import src.hands.alarms as mod

        original = mod._LIVE_MODE
        mod._LIVE_MODE = True
        try:
            async def mock_shortcut(name, input_text=None):
                return OSAResult(True, "", "", 0, f"shortcuts run {name}")

            with patch("src.hands.alarms.run_shortcut", side_effect=mock_shortcut):
                r = await mod.set_alarm("7:00 AM")
            assert r.success is True
            assert "7:00 AM" in r.message
        finally:
            mod._LIVE_MODE = original

    @pytest.mark.asyncio
    async def test_messaging_total_failure(self):
        """If all retries fail, handler reports failure."""
        import src.hands.messaging as mod

        original = mod._LIVE_MODE
        mod._LIVE_MODE = True
        try:
            async def mock_check(app_name):
                return True

            async def mock_run(script, timeout=10.0):
                return OSAResult(False, "", "permanent error", 1, script)

            async def mock_launch(app_name):
                return OSAResult(True, "", "", 0, "launch")

            with (
                patch("src.hands.messaging.check_app_running", side_effect=mock_check),
                patch("src.hands.messaging.launch_app", side_effect=mock_launch),
                patch("src.hands.messaging.run_osascript", side_effect=mock_run),
                patch("asyncio.sleep", new_callable=AsyncMock),
            ):
                r = await mod.send_imessage("Mom", "hello")
            assert r.success is False
            assert "Failed" in r.message
        finally:
            mod._LIVE_MODE = original
