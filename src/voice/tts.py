"""Text-to-Speech engine — multi-provider with phrase cache."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path

import toml

logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"
DEFAULT_CACHE_DIR = "cache/tts"

TTS_PROVIDERS = ["fish_audio", "claude_tts", "elevenlabs", "openai_tts", "macos_say"]

COMMON_PHRASES: list[str] = [
    "Good morning, {user_name}.",
    "Good afternoon, {user_name}.",
    "Good evening, {user_name}.",
    "Done.",
    "Sent.",
    "Cancelled.",
    "Alarm set for {time}.",
    "Reminder set.",
    "Here's what I found.",
    "Nothing to report, {user_name}.",
    "Right away, {user_name}.",
    "On it.",
    "Understood.",
    "One moment, please.",
    "Working on it now.",
    "All clear, {user_name}.",
    "Task complete.",
    "Message sent.",
    "File saved.",
    "Connection established.",
    "Updated successfully.",
    "I'll handle that.",
    "As you wish, {user_name}.",
    "Ready when you are.",
    "Standing by.",
    "Briefing ready, {user_name}.",
    "No new notifications.",
    "You have new messages.",
    "Search complete.",
    "System nominal.",
]


def _load_tts_config() -> dict:
    """Load TTS config from voice.toml."""
    voice_path = CONFIG_DIR / "voice.toml"
    if not voice_path.exists():
        return {"provider": "macos_say"}
    try:
        data = toml.load(voice_path)
        return data.get("tts", {"provider": "macos_say"})
    except Exception:
        return {"provider": "macos_say"}


@dataclass
class TTSResult:
    """Result from a text-to-speech synthesis."""

    audio_path: str
    text: str
    source: str  # "cache" | provider name
    duration_ms: int


def get_cache_path(text: str, cache_dir: str = DEFAULT_CACHE_DIR) -> str:
    """Return a deterministic cache file path for the given text."""
    digest = hashlib.md5(text.encode()).hexdigest()  # noqa: S324
    return str(Path(cache_dir) / f"{digest}.wav")


def is_cached(text: str, cache_dir: str = DEFAULT_CACHE_DIR) -> bool:
    """Check whether a cached audio file already exists for *text*."""
    return Path(get_cache_path(text, cache_dir)).exists()


async def _synth_macos_say(text: str, cache_path: str) -> None:
    """Synthesize via macOS `say` command."""
    proc = await asyncio.create_subprocess_exec(
        "say", "-o", cache_path, "--data-format=LEI16@22050", text,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()


async def _synth_fish_audio(text: str, cache_path: str, config: dict) -> None:
    """Synthesize via Fish Audio API."""
    import httpx

    api_key = config.get("api_key", "")
    voice_id = config.get("voice_id", "")
    if not api_key:
        logger.warning("Fish Audio API key not set, falling back to macOS say")
        await _synth_macos_say(text, cache_path)
        return

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.fish.audio/v1/tts",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"text": text, "voice_id": voice_id},
            timeout=30,
        )
        resp.raise_for_status()
        Path(cache_path).write_bytes(resp.content)


async def _synth_elevenlabs(text: str, cache_path: str, config: dict) -> None:
    """Synthesize via ElevenLabs API."""
    import httpx

    api_key = config.get("api_key", "")
    voice_id = config.get("voice_id", "21m00Tcm4TlvDq8ikWAM")  # default: Rachel
    if not api_key:
        logger.warning("ElevenLabs API key not set, falling back to macOS say")
        await _synth_macos_say(text, cache_path)
        return

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            headers={"xi-api-key": api_key},
            json={"text": text, "model_id": "eleven_monolingual_v1"},
            timeout=30,
        )
        resp.raise_for_status()
        Path(cache_path).write_bytes(resp.content)


async def _synth_openai_tts(text: str, cache_path: str, config: dict) -> None:
    """Synthesize via OpenAI TTS API."""
    import httpx

    api_key = config.get("api_key", "")
    voice = config.get("voice_id", "onyx")
    if not api_key:
        logger.warning("OpenAI TTS API key not set, falling back to macOS say")
        await _synth_macos_say(text, cache_path)
        return

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.openai.com/v1/audio/speech",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": "tts-1", "input": text, "voice": voice},
            timeout=30,
        )
        resp.raise_for_status()
        Path(cache_path).write_bytes(resp.content)


async def _synth_claude_tts(text: str, cache_path: str, config: dict) -> None:
    """Synthesize via Anthropic TTS — not yet available, falls back to macOS say."""
    logger.info("Claude TTS not yet available, falling back to macOS say")
    await _synth_macos_say(text, cache_path)


async def synthesize(
    text: str,
    cache_dir: str = DEFAULT_CACHE_DIR,
    user_name: str = "Sir",
    config: dict | None = None,
) -> TTSResult:
    """Synthesize speech for *text*, using the cache when possible.

    Reads provider from voice.toml unless config is passed explicitly.
    """
    cfg = config or _load_tts_config()
    provider = cfg.get("provider", "macos_say")

    from datetime import datetime
    current_time = datetime.now().strftime("%-I:%M %p")
    expanded = text.replace("{user_name}", user_name).replace("{time}", current_time)
    cache_path = get_cache_path(expanded, cache_dir)

    if Path(cache_path).exists():
        return TTSResult(
            audio_path=cache_path,
            text=expanded,
            source="cache",
            duration_ms=0,
        )

    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    start = time.monotonic()

    if provider == "macos_say":
        await _synth_macos_say(expanded, cache_path)
    elif provider == "fish_audio":
        await _synth_fish_audio(expanded, cache_path, cfg)
    elif provider == "elevenlabs":
        await _synth_elevenlabs(expanded, cache_path, cfg)
    elif provider == "openai_tts":
        await _synth_openai_tts(expanded, cache_path, cfg)
    elif provider == "claude_tts":
        await _synth_claude_tts(expanded, cache_path, cfg)
    else:
        logger.warning("Unknown TTS provider: %s, falling back to macOS say", provider)
        await _synth_macos_say(expanded, cache_path)

    elapsed = int((time.monotonic() - start) * 1000)
    return TTSResult(
        audio_path=cache_path,
        text=expanded,
        source=provider,
        duration_ms=max(elapsed, 1),
    )


async def generate_phrase_cache(
    user_name: str = "Sir",
    cache_dir: str = DEFAULT_CACHE_DIR,
) -> int:
    """Pre-generate cached audio for all COMMON_PHRASES."""
    generated = 0
    for phrase in COMMON_PHRASES:
        from datetime import datetime as _dt
        expanded = phrase.replace("{user_name}", user_name).replace("{time}", _dt.now().strftime("%-I:%M %p"))
        if not is_cached(expanded, cache_dir):
            await synthesize(phrase, cache_dir=cache_dir, user_name=user_name)
            generated += 1
    return generated


def invalidate_cache(cache_dir: str = DEFAULT_CACHE_DIR) -> int:
    """Remove all cached TTS files. Returns the number of files removed."""
    cache = Path(cache_dir)
    if not cache.exists():
        return 0
    removed = 0
    for f in cache.iterdir():
        if f.is_file():
            f.unlink()
            removed += 1
    return removed
