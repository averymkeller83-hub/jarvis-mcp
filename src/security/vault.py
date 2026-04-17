"""Credential vault — stores secrets in macOS Keychain, never in plaintext files.

Usage:
    from src.security.vault import vault
    vault.store("telegram", "bot_token", "abc123")
    token = vault.retrieve("telegram", "bot_token")
    vault.delete("telegram", "bot_token")
"""

from __future__ import annotations

import logging
import subprocess

logger = logging.getLogger(__name__)

_KEYCHAIN_ACCOUNT = "jarvis-mcp"


class Vault:
    """macOS Keychain-backed secret storage."""

    def store(self, service: str, key: str, value: str) -> bool:
        """Store a secret in the Keychain. Overwrites if it already exists."""
        label = self._label(service, key)
        try:
            subprocess.run(
                [
                    "security", "add-generic-password",
                    "-a", _KEYCHAIN_ACCOUNT,
                    "-s", label,
                    "-w", value,
                    "-U",  # update if exists
                ],
                capture_output=True, text=True, timeout=5,
                check=True,
            )
            return True
        except subprocess.CalledProcessError as exc:
            logger.warning("Vault store failed for %s: %s", label, exc.stderr.strip())
            return False

    def retrieve(self, service: str, key: str) -> str | None:
        """Retrieve a secret from the Keychain. Returns None if not found."""
        label = self._label(service, key)
        try:
            result = subprocess.run(
                [
                    "security", "find-generic-password",
                    "-a", _KEYCHAIN_ACCOUNT,
                    "-s", label,
                    "-w",
                ],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except Exception:
            return None

    def delete(self, service: str, key: str) -> bool:
        """Remove a secret from the Keychain."""
        label = self._label(service, key)
        try:
            subprocess.run(
                [
                    "security", "delete-generic-password",
                    "-a", _KEYCHAIN_ACCOUNT,
                    "-s", label,
                ],
                capture_output=True, text=True, timeout=5,
            )
            return True
        except Exception:
            return False

    def exists(self, service: str, key: str) -> bool:
        """Check if a secret exists without reading it."""
        return self.retrieve(service, key) is not None

    def store_channel_credentials(self, channel: str, creds: dict[str, str]) -> None:
        """Store all credentials for a channel."""
        for key, value in creds.items():
            if value:
                self.store(channel, key, value)

    def retrieve_channel_credentials(self, channel: str, keys: list[str]) -> dict[str, str]:
        """Retrieve all credentials for a channel."""
        result = {}
        for key in keys:
            val = self.retrieve(channel, key)
            if val is not None:
                result[key] = val
        return result

    def _label(self, service: str, key: str) -> str:
        return f"jarvis/{service}/{key}"


# Singleton
vault = Vault()

# ── Secret field definitions ────────────────────────────────────────

# Which keys per channel are secrets (Keychain) vs config (toml)
CHANNEL_SECRET_KEYS: dict[str, list[str]] = {
    "telegram": ["bot_token"],
    "discord": ["bot_token"],
    "slack": ["bot_token"],
    "email": ["password"],
}

VOICE_SECRET_KEYS: dict[str, list[str]] = {
    "tts": ["api_key"],
    "stt": ["api_key"],
}


def load_channel_config(channel: str) -> dict | None:
    """Load a channel's config by merging communication.toml with vault secrets.

    Non-secret fields come from toml; secret fields come from Keychain.
    Returns None if the channel has no config at all.
    """
    from pathlib import Path

    import toml as _toml

    config_dir = Path(__file__).resolve().parent.parent.parent / "config"
    comm_path = config_dir / "communication.toml"
    if not comm_path.exists():
        return None
    try:
        data = _toml.load(comm_path)
    except Exception:
        return None

    section = data.get(channel, {})

    # Legacy: iMessage target in channels
    if not section and channel == "imessage":
        target = data.get("channels", {}).get("imessage_target")
        if target:
            return {"target": target}
        return None

    if not section:
        return None

    # Merge secrets from vault
    secret_keys = CHANNEL_SECRET_KEYS.get(channel, [])
    for key in secret_keys:
        secret = vault.retrieve(channel, key)
        if secret:
            section[key] = secret

    return section


def load_voice_config() -> dict | None:
    """Load voice.toml and merge api_key secrets from vault."""
    from pathlib import Path

    import toml as _toml

    config_dir = Path(__file__).resolve().parent.parent.parent / "config"
    voice_path = config_dir / "voice.toml"
    if not voice_path.exists():
        return None
    try:
        data = _toml.load(voice_path)
    except Exception:
        return None

    for section_name, secret_keys in VOICE_SECRET_KEYS.items():
        section = data.get(section_name, {})
        for key in secret_keys:
            secret = vault.retrieve(f"voice_{section_name}", key)
            if secret:
                section[key] = secret
        if section:
            data[section_name] = section

    return data
