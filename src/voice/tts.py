"""Text-to-Speech engine — Fish Audio API with local phrase cache."""

from __future__ import annotations

import hashlib
import os
import time
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CACHE_DIR = "cache/tts"

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


@dataclass
class TTSResult:
    """Result from a text-to-speech synthesis."""

    audio_path: str
    text: str
    source: str  # "cache" | "api"
    duration_ms: int


def get_cache_path(text: str, cache_dir: str = DEFAULT_CACHE_DIR) -> str:
    """Return a deterministic cache file path for the given text."""
    digest = hashlib.md5(text.encode()).hexdigest()  # noqa: S324
    return str(Path(cache_dir) / f"{digest}.wav")


def is_cached(text: str, cache_dir: str = DEFAULT_CACHE_DIR) -> bool:
    """Check whether a cached audio file already exists for *text*."""
    return Path(get_cache_path(text, cache_dir)).exists()


async def synthesize(
    text: str,
    cache_dir: str = DEFAULT_CACHE_DIR,
    user_name: str = "Sir",
) -> TTSResult:
    """Synthesize speech for *text*, using the cache when possible.

    1. Expand template variables ({user_name}, etc.).
    2. Check cache — if hit, return immediately with source="cache".
    3. On miss — call Fish Audio API (mocked), write placeholder, cache result.
    """
    expanded = text.replace("{user_name}", user_name).replace("{time}", "7 AM")
    cache_path = get_cache_path(expanded, cache_dir)

    if Path(cache_path).exists():
        return TTSResult(
            audio_path=cache_path,
            text=expanded,
            source="cache",
            duration_ms=0,
        )

    # Cache miss → mock Fish Audio API call
    start = time.monotonic()
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    Path(cache_path).write_bytes(b"RIFF_MOCK_WAV_DATA")
    elapsed = int((time.monotonic() - start) * 1000)

    return TTSResult(
        audio_path=cache_path,
        text=expanded,
        source="api",
        duration_ms=max(elapsed, 1),
    )


async def generate_phrase_cache(
    user_name: str = "Sir",
    cache_dir: str = DEFAULT_CACHE_DIR,
) -> int:
    """Pre-generate cached audio for all COMMON_PHRASES.

    Returns the number of phrases generated (skips already-cached ones).
    """
    generated = 0
    for phrase in COMMON_PHRASES:
        expanded = phrase.replace("{user_name}", user_name).replace("{time}", "7 AM")
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
