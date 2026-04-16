"""Voice activation — hotkey and optional wake word support."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ActivationConfig:
    """Configuration for voice activation triggers."""

    hotkey: str = "alt+space"
    wake_word_enabled: bool = False
    wake_word_phrase: str = "hey jarvis"
    listening: bool = False


class VoiceActivation:
    """Manages voice activation state (hotkey + wake word).

    In production this would register a global hotkey listener and
    optionally run Porcupine/OpenWakeWord for on-device detection.
    Currently mocked — tracks state only.
    """

    def __init__(self, config: ActivationConfig | None = None) -> None:
        self._config = config or ActivationConfig()

    # ── Listening lifecycle ──────────────────────────────────────────

    def start_listening(self) -> bool:
        """Begin listening for voice input. Returns True on success."""
        self._config.listening = True
        return True

    def stop_listening(self) -> bool:
        """Stop listening for voice input. Returns True on success."""
        self._config.listening = False
        return True

    def is_listening(self) -> bool:
        """Return whether the system is currently listening."""
        return self._config.listening

    # ── Configuration ────────────────────────────────────────────────

    def update_wake_word(self, new_phrase: str) -> None:
        """Update the wake word phrase (e.g. when the user renames the assistant)."""
        self._config.wake_word_phrase = new_phrase.lower().strip()

    def get_status(self) -> dict[str, object]:
        """Return current activation status as a plain dict."""
        return {
            "hotkey": self._config.hotkey,
            "wake_word_enabled": self._config.wake_word_enabled,
            "wake_word_phrase": self._config.wake_word_phrase,
            "listening": self._config.listening,
        }
